"""Build the world_countries reference dataset."""
from __future__ import annotations

import argparse
import hashlib
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Dict, List

import geopandas as gpd
import pandas as pd
import shapely.geometry as geom


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "artefacts" / "spatial" / "world_countries" / "raw"
REFERENCE_DIR = ROOT / "reference" / "spatial" / "world_countries"

FIXUP_MAP = {
    "FRANCE": "FR",
    "NORWAY": "NO",
}

SYNTHETIC_GEOM = {
    "BQ": (12.200, -68.260),
    "CC": (-12.160, 96.870),
    "CX": (-10.500, 105.670),
    "GF": (3.933, -53.125),
    "GP": (16.250, -61.580),
    "MQ": (14.641, -61.024),
    "RE": (-21.115, 55.538),
    "YT": (-12.827, 45.166),
    "SJ": (78.600, 16.300),
    "BV": (-54.420, 3.360),
    "TK": (-9.380, -171.200),
    "TW": (23.700, 120.960),
}


def sha256sum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_iso_set(path: Path) -> set[str]:
    df = pd.read_parquet(path)
    return set(df["country_iso"].astype(str).str.upper())


def normalise_iso(feature_name: str, iso_value: str) -> str:
    iso = (iso_value or "").strip().upper()
    if iso == "-99":
        iso = FIXUP_MAP.get(feature_name.strip().upper(), "")
    return iso


def geometry_from_point(lat: float, lon: float, size_deg: float = 0.5) -> geom.Polygon:
    half = size_deg / 2.0
    return geom.box(lon - half, lat - half, lon + half, lat + half)


def build_world_countries(
    src_geojson: Path,
    iso_canonical_path: Path,
    version: str,
) -> None:
    src_geojson = src_geojson.resolve()
    iso_canonical_path = iso_canonical_path.resolve()

    iso_target = load_iso_set(iso_canonical_path)

    gdf = gpd.read_file(src_geojson)
    gdf["country_iso"] = [
        normalise_iso(name, iso)
        for name, iso in zip(gdf["name"], gdf["ISO3166-1-Alpha-2"])
    ]
    gdf = gdf[["country_iso", "name", "geometry"]]
    gdf = gdf[gdf["country_iso"].str.match(r"^[A-Z]{2}$")]
    gdf = gdf[gdf["country_iso"].isin(iso_target)]
    gdf = gdf.to_crs("EPSG:4326")

    produced_iso = set(gdf["country_iso"].to_list())
    missing_iso = sorted(iso_target - produced_iso)

    synthetic_rows: List[Dict[str, object]] = []
    for iso in missing_iso:
        if iso in SYNTHETIC_GEOM:
            lat, lon = SYNTHETIC_GEOM[iso]
            synthetic_rows.append(
                {
                    "country_iso": iso,
                    "name": iso,
                    "geometry": geometry_from_point(lat, lon, size_deg=0.5),
                }
            )

    if synthetic_rows:
        synth_gdf = gpd.GeoDataFrame(synthetic_rows, crs="EPSG:4326")
        gdf = gpd.GeoDataFrame(pd.concat([gdf, synth_gdf], ignore_index=True), crs="EPSG:4326")

    gdf.sort_values("country_iso", inplace=True)
    gdf.reset_index(drop=True, inplace=True)

    output_dir = REFERENCE_DIR / version
    output_dir.mkdir(parents=True, exist_ok=True)

    parquet_path = output_dir / "world_countries.parquet"
    gdf.to_parquet(parquet_path, index=False)

    manifest = {
        "dataset_id": "world_countries",
        "version": version,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "generator_script": "scripts/build_world_countries.py",
        "source_geojson": str(src_geojson.relative_to(ROOT)),
        "source_geojson_sha256": sha256sum(src_geojson),
        "iso_canonical": str(iso_canonical_path.relative_to(ROOT)),
        "iso_canonical_sha256": sha256sum(iso_canonical_path),
        "output_parquet": str(parquet_path.relative_to(ROOT)),
        "output_parquet_sha256": sha256sum(parquet_path),
        "row_count": int(len(gdf)),
        "columns": ["country_iso", "name", "geometry"],
    }
    (output_dir / "world_countries.manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    qa_path = output_dir / "world_countries.qa.json"
    qa_payload = {
        "missing_iso_before_aug": missing_iso,
        "produced_iso": sorted(gdf["country_iso"].unique().tolist()),
    }
    qa_path.write_text(json.dumps(qa_payload, indent=2) + "\n", encoding="utf-8")

    sha_path = output_dir / "SHA256SUMS"
    lines = [
        f"{manifest['source_geojson_sha256']}  {manifest['source_geojson']}",
        f"{manifest['iso_canonical_sha256']}  {manifest['iso_canonical']}",
        f"{manifest['output_parquet_sha256']}  {manifest['output_parquet']}",
        f"{sha256sum(qa_path)}  reference/spatial/world_countries/{version}/world_countries.qa.json",
    ]
    sha_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default="2025-10-08")
    parser.add_argument("--source", default=str(RAW_DIR / "countries.geojson"))
    parser.add_argument("--iso-table", default=str(ROOT / "reference/layer1/iso_canonical/v2025-10-08/iso_canonical.parquet"))
    args = parser.parse_args()

    build_world_countries(Path(args.source), Path(args.iso_table), args.version)


if __name__ == "__main__":
    main()
