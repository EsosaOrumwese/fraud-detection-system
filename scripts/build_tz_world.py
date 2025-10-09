"""Build the tz_world_2025a reference dataset."""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

import geopandas as gpd
import shapely


ROOT = Path(__file__).resolve().parents[1]
RAW_BASE = ROOT / "artefacts" / "spatial" / "tz_world"
REFERENCE_BASE = ROOT / "reference" / "spatial" / "tz_world"


def sha256sum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def unzip_geojson(zip_path: Path, target_dir: Path) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = [name for name in zf.namelist() if name.lower().endswith((".geojson", ".json"))]
        if not names:
            raise ValueError("ZIP archive does not contain a GeoJSON file")
        geojson_name = names[0]
        geojson_path = target_dir / Path(geojson_name).name
        with zf.open(geojson_name) as source, geojson_path.open("wb") as out:
            out.write(source.read())
    return geojson_path


def normalise_tz_world(
    geojson_path: Path,
    version: str,
    world_countries_path: Path,
) -> None:
    gdf = gpd.read_file(geojson_path)
    gdf = gdf.to_crs("EPSG:4326")

    columns = [col.lower() for col in gdf.columns]
    if "tzid" in gdf.columns:
        tz_col = "tzid"
    elif "tzid" in columns:
        tz_col = columns[columns.index("tzid")]
    else:
        tz_col = "tzid"
    gdf.rename(columns={tz_col: "tzid"}, inplace=True)
    gdf = gdf[["tzid", "geometry"]]
    gdf["tzid"] = gdf["tzid"].astype(str)

    gdf = gdf[gdf["geometry"].notnull()]
    gdf["geometry"] = gdf["geometry"].apply(lambda geom: shapely.make_valid(geom))
    gdf = gdf[gdf["geometry"].geom_type.isin(["Polygon", "MultiPolygon"])]

    countries = gpd.read_parquet(world_countries_path)
    countries = countries[["country_iso", "geometry"]].to_crs("EPSG:4326")

    joined = gpd.overlay(gdf, countries, how="intersection")
    joined = joined[["tzid", "country_iso", "geometry"]]
    joined = joined.dissolve(by=["tzid", "country_iso"], as_index=False)
    joined.sort_values(["tzid", "country_iso"], inplace=True)

    output_dir = REFERENCE_BASE / version
    output_dir.mkdir(parents=True, exist_ok=True)

    parquet_path = output_dir / "tz_world_2025a.parquet"
    joined.to_parquet(parquet_path, index=False)

    qa_payload: Dict[str, object] = {
        "row_count": int(len(joined)),
        "tz_count": int(joined["tzid"].nunique()),
    }
    qa_path = output_dir / "tz_world_2025a.qa.json"
    qa_path.write_text(json.dumps(qa_payload, indent=2) + "\n", encoding="utf-8")

    manifest = {
        "dataset_id": "tz_world_2025a",
        "version": version,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "generator_script": "scripts/build_tz_world.py",
        "source_geojson": str(geojson_path.relative_to(ROOT)),
        "source_geojson_sha256": sha256sum(geojson_path),
        "world_countries": str(world_countries_path.relative_to(ROOT)),
        "world_countries_sha256": sha256sum(world_countries_path),
        "output_parquet": str(parquet_path.relative_to(ROOT)),
        "output_parquet_sha256": sha256sum(parquet_path),
        "qa_path": str(qa_path.relative_to(ROOT)),
        "qa_sha256": sha256sum(qa_path),
        "tz_count": qa_payload["tz_count"],
    }
    (output_dir / "tz_world_2025a.manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    sha_lines = [
        f"{manifest['source_geojson_sha256']}  {manifest['source_geojson']}",
        f"{manifest['world_countries_sha256']}  {manifest['world_countries']}",
        f"{manifest['output_parquet_sha256']}  {manifest['output_parquet']}",
        f"{manifest['qa_sha256']}  {manifest['qa_path']}",
    ]
    (output_dir / "SHA256SUMS").write_text("\n".join(sha_lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default="2025a")
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--world-countries", required=True, type=Path)
    args = parser.parse_args()

    zip_path = args.zip.resolve()
    world_countries = args.world_countries.resolve()
    temp_dir = RAW_BASE / args.version / "tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    geojson_path = unzip_geojson(zip_path, temp_dir)

    normalise_tz_world(geojson_path, args.version, world_countries)


if __name__ == "__main__":
    main()
