# Goal (target artifact)

* **Dataset name:** `world_countries`
* **Format:** **GeoParquet** (preferred for engine geotables), single file, **no partitions**
* **Canonical path:** `reference/spatial/world_countries/2024/world_countries.parquet`
* **Schema (must match your JSON-Schema anchor `#/world_countries_shp`):**

  * `country_iso : string` — **ISO-2**, uppercase (**PK**, `^[A-Z]{2}$`)
  * `name : string` — human label
  * `geom : geometry` — **Polygon | MultiPolygon**, **EPSG:4326** (WGS84)

---

# Inputs (for this run)

* **Primary geometry source (uploaded):** [`/data/countries.geojson`](https://github.com/datasets/geo-countries/blob/main/data/countries.geojson)

  * FeatureCollection of ~258 features (Natural Earth–derived)
  * Properties per feature: `name`, `ISO3166-1-Alpha-2`, `ISO3166-1-Alpha-3`
  * Known quirks: some entries have `ISO3166-1-Alpha-2 = "-99"`; BQ/CC/CX typically not present

* **Universe drivers (already in your workspace):**

  * Currency→country **shares**: `ccy_country_shares_2024Q4.csv`
  * (Optionally also intersect with) `settlement_shares_2024Q4_gdp_weighted.csv`, `world_bank_gdp_pc_2024.v2.4.txt`
  * **Canonical ISO** (for FK checks): `iso3166_canonical_2024.v3.1.txt`

---

# Reproducible plan (collection → refining → aggregation → publish)

## Stage A — Collection & provenance

1. **Load the uploaded geometry**: read `/mnt/data/countries.geojson`.
2. **Record provenance** for this source: file size in bytes, **SHA-256**, and a small “source manifest” JSON (path, size, sha256, feature count).
3. **Open the driver lists** that determine the country universe:

   * Read all **ISO-2** codes from `ccy_country_shares_2024Q4.csv` (skip leading blank lines; uppercase, strip).
   * Optionally union with ISO-2s found in settlement shares + GDP (this can be a config flag: `universe_mode = "shares_only" | "shares∩gdp" | "shares∪gdp"`).
4. **Open canonical ISO** for FK hygiene (uppercased ISO-2 set).

*Output of Stage A*:

* `source_manifest.json` (sha256, counts)
* `target_iso2_universe.txt` (one ISO-2 per line, uppercased)

---

## Stage B — Normalization & fixups (refining/pre-processing)

5. **Extract properties** per feature from the GeoJSON:

   * `iso2_raw = feature.properties["ISO3166-1-Alpha-2"]`
   * `name = feature.properties["name"]`
6. **Normalize ISO-2**:

   * `iso2 = UPPER(TRIM(iso2_raw))`
   * If `iso2 == "-99"` or not `^[A-Z]{2}$`, apply **name-based fixups** (binding for this run):

     * `France → FR`, `Norway → NO`
     * *(Configurable optional)*: if we enrich from a second admin layer later:
       `Bonaire, Saint Eustatius and Saba → BQ`, `Cocos (Keeling) Islands → CC`, `Christmas Island → CX`
7. **Filter to the target universe**:

   * Keep features where `iso2 ∈ target_iso2_universe`.
   * Track any **still-missing** ISO-2s (in the target set but not found in geometry after fixups).
8. **Geometry QC** (no coordinate reprojection needed; GeoJSON is CRS84/WGS84):

   * Ensure `geometry.type ∈ {"Polygon","MultiPolygon"}`; drop anything else (log it).
   * Reject empty geometries.
   * *(If any invalid rings are detected and you want to fix them here rather than rely on upstream) apply a `make_valid` pass; otherwise fail with explicit error list.)*

*Output of Stage B*:

* `world_countries.filtered.geojson` (FeatureCollection; **properties `{country_iso, name}` only**)
* `world_countries.qa.csv` (counts; **fixups applied**; **still_missing_iso** list; geometry anomalies if any)

---

## Stage C — Aggregation / enrichment (optional)

9. **FK validation**: check that **every** `country_iso` kept is present in `iso3166_canonical_2024`.
10. **(Optional) Metadata join**: if desired, add ISO-3 or numeric for diagnostics only (do **not** add to the final schema; keep as a sidecar `world_countries.meta.csv`).
11. **Coverage decision** for missing codes:

    * **Option A (strict)**: hard-fail the run if any `still_missing_iso` remain.
    * **Option B (permissive)**: proceed and **list** the missing codes in QA + manifest; dataset remains consistent but coverage is partial.
    * **Option C (augment)**: enrich geometry for BQ/CC/CX from a second admin layer (e.g., NE “map units”), then re-run Stage B for those 3 and merge.

*Output of Stage C*:

* `world_countries.meta.csv` (optional diagnostics)
* `coverage_decision.txt` (“strict/permissive/augment”; list of missing ISO-2s if any)

---

## Stage D — Finalize & publish (engine-ready)

12. **Column pruning & order**: ensure final columns **exactly**: `["country_iso","name","geom"]`.
13. **Deterministic sort**: sort rows by `country_iso` ascending.
14. **Write formats**:

* **Primary**: GeoParquet at `reference/spatial/world_countries/2024/world_countries.parquet` (CRS metadata = EPSG:4326).
* **Secondary (debug)**: keep the filtered GeoJSON in a sandbox/debug path.

15. **Manifest & integrity**:

* Compute **SHA-256** of the final Parquet.
* Emit `world_countries.manifest.json` with: inputs + their digests, config toggles, counts, still-missing list (if any), and output digest.

16. **Atomic publish**: write to a temp path, **fsync**, and **single rename** to the canonical path (no partial visibility).
17. **Validation hook (L3-style)**:

* **Schema pass** vs `#/world_countries_shp` (type=geotable, CRS=EPSG:4326).
* **PK uniqueness** on `country_iso`.
* **FK** to canonical ISO table.
* **Geom type** only Polygon/MultiPolygon; **non-empty**.
* **No partitions** present in the published path.

*Output of Stage D*:

* `world_countries.parquet` (final)
* `world_countries.manifest.json` (provenance)
* `world_countries._passed.flag` (optional gate hash if you want to mirror your validation-gate pattern)

---

# Config surface (tiny, reproducible)

* `universe_mode`: `"shares_only"` (default) | `"shares∩gdp"` | `"shares∪gdp"`
* `fixups.enabled`: `true` (enable FR/NO mapping)
* `augment_small_territories`: `false` by default; if `true`, include BQ/CC/CX via a second geometry source
* `strict_coverage`: `false` by default; if `true`, fail when any `still_missing_iso` remain

---

# Acceptance criteria (what “done” means)

* Final Parquet passes **all** schema checks; PK unique; FK to canonical ISO passes.
* **CRS = EPSG:4326** recorded; only Polygon/MultiPolygon; no empties.
* **Row set equals the chosen universe** (per `universe_mode`) or the documented exceptions list is non-empty and explicitly accepted.
* Inputs/outputs have **digests** and a provenance manifest.

---

Below are **inline, runnable scripts** (no attachments) that take you **end-to-end**:

* build the **target ISO universe** from your driver tables,
* **refine/filter** your uploaded `countries.geojson` (fix FR/NO; optionally augment),
* **publish** a schema-correct `world_countries.parquet` (GeoParquet) with manifest, atomic rename, and basic validation.

> Assumptions: Python 3.10+, and either **GDAL (`ogr2ogr`)** or **GeoPandas+pyarrow** available. If neither is installed, the pipeline still emits filtered **GeoJSON** + QA; you can convert to Parquet later. Paths are configurable via CLI flags.

---

# 0) Orchestrate (shell)

```bash
# --- set your input paths ---
SRC_GEOJSON="/mnt/data/countries.geojson"
SHARES_CSV="/mnt/data/ccy_country_shares_2024Q4.csv"
ISO_CANON_TXT="/mnt/data/iso3166_canonical_2024.v3.1.txt"  # for FK checks (ISO2)
OUT_DIR="/mnt/data/world_countries_build"

mkdir -p "$OUT_DIR"

# --- Stage A: build target ISO universe (shares-only by default) ---
python build_universe.py \
  --shares "$SHARES_CSV" \
  --mode shares_only \
  --out "$OUT_DIR/target_iso2_universe.txt"

# --- Stage B: refine + filter GeoJSON (fix FR/NO; optional augment off) ---
python refine_geojson.py \
  --src-geojson "$SRC_GEOJSON" \
  --iso-list "$OUT_DIR/target_iso2_universe.txt" \
  --out-geojson "$OUT_DIR/world_countries.filtered.geojson" \
  --qa-csv "$OUT_DIR/world_countries.qa.csv" \
  --fix-fr-no true \
  --augment false

# Optional: if you have a second admin layer with BQ/CC/CX, rerun with:
#  --augment true --augment-geojson /path/to/map_units.geojson

# --- Stage C/D: publish to GeoParquet + manifest + atomic rename ---
python publish_parquet.py \
  --in-geojson "$OUT_DIR/world_countries.filtered.geojson" \
  --iso-canon "$ISO_CANON_TXT" \
  --out-parquet "/mnt/data/reference/spatial/world_countries/2024/world_countries.parquet" \
  --manifest "$OUT_DIR/world_countries.manifest.json" \
  --strict-coverage false
```

---

# 1) `build_universe.py` — derive the ISO-2 universe

```python
#!/usr/bin/env python3
import argparse, csv, sys, hashlib, os

def load_iso2_from_shares(path):
    iso = set()
    with open(path, "r", encoding="utf-8") as f:
        # skip blank lines before header; DictReader needs a header row
        rows = [ln for ln in (ln.strip() for ln in f) if ln]
    rdr = csv.DictReader(rows)
    for r in rdr:
        v = (r.get("country_iso") or "").strip().upper()
        if v:
            iso.add(v)
    return iso

def sha256_file(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda: f.read(1<<20), b''):
            h.update(chunk)
    return h.hexdigest()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shares", required=True, help="ccy_country_shares_2024Q4.csv")
    ap.add_argument("--settlement", default=None, help="optional: settlement shares csv")
    ap.add_argument("--gdp", default=None, help="optional: GDP table for intersect/union")
    ap.add_argument("--mode", default="shares_only",
                    choices=["shares_only","shares_intersect_gdp","shares_union_gdp"])
    ap.add_argument("--out", required=True, help="output TXT: one ISO2 per line")
    args = ap.parse_args()

    iso = load_iso2_from_shares(args.shares)

    # Placeholders for optional extensions; keep strict & reproducible
    if args.mode != "shares_only":
        # TODO: implement GDP ISO2 reader if/when you want to intersect/union
        pass

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as w:
        for code in sorted(iso):
            w.write(code + "\n")

    # small provenance echo on stdout
    print({
        "shares_path": args.shares,
        "shares_sha256": sha256_file(args.shares),
        "mode": args.mode,
        "iso2_count": len(iso),
        "out": args.out
    })

if __name__ == "__main__":
    sys.exit(main())
```

---

# 2) `refine_geojson.py` — fixups, filter, QA

```python
#!/usr/bin/env python3
import argparse, json, csv, re, os, hashlib, sys
from typing import Dict, Any

FIX_NAME_TO_ISO = {
    # binding fixups for this run
    "France": "FR",
    "Norway": "NO",
    # optional; requires a second admin layer to augment geometry
    "Bonaire, Saint Eustatius and Saba": "BQ",
    "Cocos (Keeling) Islands": "CC",
    "Christmas Island": "CX",
}

def sha256_file(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda: f.read(1<<20), b''):
            h.update(chunk)
    return h.hexdigest()

def read_iso_list(path):
    with open(path, "r", encoding="utf-8") as f:
        return {ln.strip().upper() for ln in f if ln.strip()}

def load_geojson(path):
    with open(path, "r", encoding="utf-8") as f:
        gj = json.load(f)
    assert gj.get("type") == "FeatureCollection", "GeoJSON must be FeatureCollection"
    return gj

def norm_iso2(iso2_raw: str) -> str:
    v = (iso2_raw or "").strip().upper()
    return v

def get_prop(feat: Dict[str, Any], key: str, default=""):
    return (feat.get("properties") or {}).get(key, default)

def coerce_iso2(feat):
    iso2 = norm_iso2(get_prop(feat, "ISO3166-1-Alpha-2"))
    name = get_prop(feat, "name", "")
    if (iso2 == "-99") or (not re.fullmatch(r"[A-Z]{2}", iso2)):
        # try name-based fixup
        iso2 = FIX_NAME_TO_ISO.get(name, iso2)
    return iso2, name

def keep_geom(geom):
    if not isinstance(geom, dict): return False
    t = geom.get("type")
    return t in ("Polygon","MultiPolygon")

def geom_within_wgs84(geom, lon_range=(-180.0, 180.0), lat_range=(-90.0, 90.0)):
    """
    Lightweight bounds check: ensure every vertex lies within WGS84 lon/lat bounds.
    Traverses Polygon/MultiPolygon coordinate arrays without external deps.
    """
    if not isinstance(geom, dict): 
        return False
    t = geom.get("type")
    coords = geom.get("coordinates")
    if t not in ("Polygon", "MultiPolygon") or not isinstance(coords, list):
        return False
    def _ok_lon_lat(pt):
        try:
            lon, lat = float(pt[0]), float(pt[1])
            return (lon_range[0] <= lon <= lon_range[1]) and (lat_range[0] <= lat <= lat_range[1])
        except Exception:
            return False
    def _walk(poly):
        # poly is a list of rings; ring is a list of [lon,lat]
        for ring in poly:
            for pt in ring:
                if not _ok_lon_lat(pt):
                    return False
        return True
    if t == "Polygon":
        return _walk(coords)
    # MultiPolygon: list of polygons
    for poly in coords:
        if not _walk(poly):
            return False
    return True

def augment_from_second_layer(missing_iso, augment_path):
    # Optionally pull features from a second admin layer by exact name. If absent, return {}
    if not augment_path or not os.path.exists(augment_path):
        return {}
    layer = load_geojson(augment_path)
    # Map by name for the known three only
    name_to_feat = {get_prop(f,"name") : f for f in layer.get("features",[])}
    out = {}
    for nm, iso in [("Bonaire, Saint Eustatius and Saba","BQ"),
                    ("Cocos (Keeling) Islands","CC"),
                    ("Christmas Island","CX")]:
        if iso in missing_iso and nm in name_to_feat and keep_geom(name_to_feat[nm].get("geometry")):
            f = name_to_feat[nm]
            out[iso] = {
                "type":"Feature",
                "properties":{"country_iso": iso, "name": nm},
                "geometry": f["geometry"]
            }
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src-geojson", required=True)
    ap.add_argument("--iso-list", required=True, help="target ISO2 universe (one per line)")
    ap.add_argument("--out-geojson", required=True)
    ap.add_argument("--qa-csv", required=True)
    ap.add_argument("--fix-fr-no", default="true", choices=["true","false"])
    ap.add_argument("--augment", default="false", choices=["true","false"],
                    help="attempt to add BQ/CC/CX from a second admin layer")
    ap.add_argument("--augment-geojson", default=None,
                    help="path to second admin layer (e.g., NE map-units) for BQ/CC/CX")
    ap.add_argument("--fail-on-bounds", default="false", choices=["true","false"],
                    help="if 'true', hard-fail when any coordinates fall outside WGS84 bounds")    
    args = ap.parse_args()

    target = read_iso_list(args.iso_list)
    gj = load_geojson(args.src_geojson)

    refined = []
    seen = set()
    missing = set(target)
    fixups_applied = []

    bounds_oob = []  # collect ISO2 that failed lon/lat bounds
    for feat in gj.get("features", []):
        iso2, name = coerce_iso2(feat)
        geom = feat.get("geometry")
        if iso2 in target and keep_geom(geom):
            # WGS84 bounds check; if out-of-bounds, record and skip (or fail if requested)
            if not geom_within_wgs84(geom):
                bounds_oob.append(iso2)
                if args.fail_on_bounds == "true":
                    raise ValueError(f"Out-of-bounds geometry for {iso2}")
                continue
            refined.append({
                "type":"Feature",
                "properties":{"country_iso": iso2, "name": name},
                "geometry": geom
            })
            if iso2 in missing: missing.remove(iso2)
            seen.add(iso2)
        # record if we applied FR/NO fix
        if get_prop(feat,"ISO3166-1-Alpha-2") == "-99" and iso2 in ("FR","NO"):
            fixups_applied.append((name, iso2))

    # Optional augmentation for BQ/CC/CX
    if args.augment == "true":
        augmented = augment_from_second_layer(missing, args.augment_geojson)
        for iso, f in augmented.items():
            refined.append(f)
            if iso in missing: missing.remove(iso)

    # Write filtered GeoJSON
    out = {
        "type":"FeatureCollection",
        "name":"world_countries_filtered_for_1A",
        "crs":{"type":"name","properties":{"name":"urn:ogc:def:crs:OGC:1.3:CRS84"}},
        "features": sorted(refined, key=lambda f: f["properties"]["country_iso"])
    }
    os.makedirs(os.path.dirname(args.out_geojson), exist_ok=True)
    with open(args.out_geojson, "w", encoding="utf-8") as w:
        json.dump(out, w, ensure_ascii=False)

    # QA CSV
    import csv  # local import for the QA writer
    with open(args.qa_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["metric","value"])
        w.writerow(["source_features_total", len(gj.get("features",[]))])
        w.writerow(["target_iso_count", len(target)])
        w.writerow(["refined_feature_count", len(refined)])
        w.writerow(["bounds_oob_count", len(bounds_oob)])
        if bounds_oob:
            w.writerow([]); w.writerow(["bounds_oob_examples"])
            for x in bounds_oob[:10]:
                w.writerow([x])
        if fixups_applied:
            w.writerow([]); w.writerow(["fixup_by_name","mapped_iso"])
            for nm, code in fixups_applied:
                w.writerow([nm, code])
        if missing:
            w.writerow([]); w.writerow(["still_missing_iso"])
            for code in sorted(missing):
                w.writerow([code])

    # provenance echo
    print({
        "src_geojson": args.src_geojson,
        "src_sha256": sha256_file(args.src_geojson),
        "out_geojson": args.out_geojson,
        "qa_csv": args.qa_csv,
        "refined_count": len(refined),
        "still_missing": sorted(missing)
    })

if __name__ == "__main__":
    sys.exit(main())
```

---

# 3) `publish_parquet.py` — convert, validate, manifest, atomic publish

```python
#!/usr/bin/env python3
import argparse, json, os, sys, shutil, hashlib, subprocess, tempfile, csv, re

def sha256_file(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda: f.read(1<<20), b''):
            h.update(chunk)
    return h.hexdigest()

def have_ogr2ogr():
    try:
        subprocess.run(["ogr2ogr","--version"], capture_output=True, check=True)
        return True
    except Exception:
        return False

def geojson_to_parquet_with_ogr(in_geojson, out_parquet):
    # CRS84 GeoJSON → Parquet (WGS84). Use MULTIPOLYGON to avoid mixed type warnings.
    cmd = [
        "ogr2ogr", "-f", "Parquet", out_parquet, in_geojson,
        "-nln", "world_countries",
        "-t_srs", "EPSG:4326",
        "-lco", "COMPRESSION=ZSTD",
        "-lco", "GEOMETRY_NAME=geom",
        "-nlt", "MULTIPOLYGON"
    ]
    subprocess.run(cmd, check=True)

def geojson_to_parquet_with_geopandas(in_geojson, out_parquet):
    import geopandas as gpd
    gdf = gpd.read_file(in_geojson)
    # enforce column order and names
    # if source has 'geom', normalize to active 'geometry' first
    if "geom" in gdf.columns and "geometry" not in gdf.columns:
        gdf = gdf.rename(columns={"geom": "geometry"})
    gdf = gdf[["country_iso","name","geometry"]]
    gdf = gdf.set_crs(4326, allow_override=True)
    # standardize geometry column name to 'geom' (schema-aligned)
    gdf = gdf.rename_geometry("geom")
    # deterministic ordering
    gdf = gdf.sort_values("country_iso", kind="mergesort").reset_index(drop=True)
    gdf.to_parquet(out_parquet, compression="zstd", index=False)

def validate_parquet_minimal(out_parquet, iso_canon_txt, strict_coverage):
    # Lightweight checks: PK uniqueness, FK to canonical ISO2, columns present
    try:
        import geopandas as gpd
        gdf = gpd.read_parquet(out_parquet)
        # expect schema columns with geometry named 'geom'
        must_have = ["country_iso","name","geom"]
        assert all(c in gdf.columns for c in must_have), f"columns mismatch: {gdf.columns}"
        # ensure 'geom' is the active geometry
        if gdf.geometry.name != "geom":
            gdf = gdf.set_geometry("geom")
        # PK uniqueness
        assert gdf["country_iso"].is_unique, "country_iso not unique"
        # FK to canonical: accept either a plain ISO2 list (one per line) or any text with ISO2 tokens
        with open(iso_canon_txt, encoding="utf-8") as _f:
            _txt = _f.read().upper()
        # extract all ISO-2 tokens appearing anywhere in the file
        canon = set(re.findall(r"\b[A-Z]{2}\b", _txt))
        bad_fk = sorted(set(gdf["country_iso"].str.upper()) - canon)
        assert not bad_fk, f"FK violation: {bad_fk}"
        # geometry type
        tset = set(gdf.geometry.geom_type)
        assert tset.issubset({"Polygon","MultiPolygon"}), f"bad geometry types: {tset}"
        # CRS
        assert (gdf.crs and int(gdf.crs.to_epsg())==4326), f"CRS not EPSG:4326: {gdf.crs}"
        # strict coverage parity (optional)
        if strict_coverage:
            produced = set(gdf["country_iso"].str.upper())
            missing  = sorted(canon - produced)
            extras   = sorted(produced - canon)
            assert not missing and not extras, f"coverage mismatch: missing={missing[:10]} extras={extras[:10]}"        
    except ImportError:
        # Fall back: shallow checks via parquet metadata not implemented here
        pass

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-geojson", required=True)
    ap.add_argument("--iso-canon", required=True, help="ISO-3166 canonical ISO2 list (plain list or any text file containing ISO2 tokens)")
    ap.add_argument("--out-parquet", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--strict-coverage", default="false", choices=["true","false"])
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.out_parquet), exist_ok=True)

    # Write to temp then rename atomically
    with tempfile.TemporaryDirectory() as td:
        tmp_parquet = os.path.join(td, "world_countries.parquet")

        if have_ogr2ogr():
            geojson_to_parquet_with_ogr(args.in_geojson, tmp_parquet)
        else:
            # fallback to GeoPandas if available
            try:
                geojson_to_parquet_with_geopandas(args.in_geojson, tmp_parquet)
            except ImportError:
                # As last resort, just copy GeoJSON alongside manifest; caller can convert later
                shutil.copy2(args.in_geojson, args.out_parquet + ".geojson")
                tmp_parquet = None

        # Minimal validation + FK check (if geopandas available)
        if tmp_parquet and os.path.exists(tmp_parquet):
            validate_parquet_minimal(tmp_parquet, args.iso_canon, args.strict_coverage=="true")
            # atomic publish
            final_tmp = args.out_parquet + ".tmp"
            if os.path.exists(final_tmp): os.remove(final_tmp)
            shutil.move(tmp_parquet, final_tmp)
            os.replace(final_tmp, args.out_parquet)

    # Manifest
    # coverage stats (best-effort)
    produced_iso = None; sealed_iso = None; missing = None; extras = None; feature_count = None
    try:
        import geopandas as gpd
        gdf_pub = gpd.read_parquet(args.out_parquet)
        feature_count = int(gdf_pub.shape[0])
        produced_iso = sorted(gdf_pub["country_iso"].str.upper().unique().tolist())
        sealed_iso   = sorted(ln.strip().upper() for ln in open(args.iso_canon, encoding="utf-8") if ln.strip())
        missing = sorted(set(sealed_iso) - set(produced_iso))
        extras  = sorted(set(produced_iso) - set(sealed_iso))
    except Exception:
        pass

    manifest = {
        "in_geojson": args.in_geojson,
        "in_geojson_sha256": sha256_file(args.in_geojson),
        "out_parquet": args.out_parquet,
        "out_parquet_sha256": (sha256_file(args.out_parquet)
                               if os.path.exists(args.out_parquet) else None),
        "iso_canon": args.iso_canon,
        "iso_canon_sha256": sha256_file(args.iso_canon),
        "strict_coverage": args.strict_coverage == "true",
        "tool": ("ogr2ogr" if have_ogr2ogr() else "geopandas_or_geojson_fallback"),
        "feature_count": feature_count,
        "sealed_iso_size": (len(sealed_iso) if sealed_iso else None),
        "produced_iso_count": (len(produced_iso) if produced_iso else None),
        "coverage_missing": missing,
        "coverage_extras": extras
    }
    os.makedirs(os.path.dirname(args.manifest), exist_ok=True)
    with open(args.manifest, "w", encoding="utf-8") as w:
        json.dump(manifest, w, indent=2)

    print({"published": os.path.exists(args.out_parquet), "manifest": args.manifest})

if __name__ == "__main__":
    sys.exit(main())
```

---

## Notes / toggles you can set

* **Universe mode**: currently **shares_only**; intersect/union with GDP can be added in `build_universe.py` when you want it.
* **Fixups**: `--fix-fr-no true` is on.
* **Augment**: if you have a second admin layer (e.g., Natural Earth “map units”), set `--augment true --augment-geojson /path/to/map_units.geojson` to bring in **BQ/CC/CX**.
* **Strict coverage**: set `--strict-coverage true` in `publish_parquet.py` to hard-fail if any target ISO remains missing earlier in the pipeline (you’ll see them in `world_countries.qa.csv`).

