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
    "AN": (12.200, -69.000),
    "CS": (44.000, 20.500),
}


def sha256sum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_iso_index(path: Path) -> tuple[set[str], dict[str, str]]:
    df = pd.read_parquet(path)
    iso2 = df["country_iso"].astype(str).str.upper()
    alpha3 = df["alpha3"].astype(str).str.upper()
    alpha3_map = {
        a3: a2
        for a2, a3 in zip(iso2.tolist(), alpha3.tolist())
        if a3 and a3 != "NAN"
    }
    return set(iso2.tolist()), alpha3_map


def normalise_iso(
    feature_name: str,
    iso2_value: str,
    iso3_value: str,
    adm0_a3_value: str,
    alpha3_map: dict[str, str],
) -> str:
    iso = (iso2_value or "").strip().upper()
    if len(iso) != 2 or iso == "-99":
        iso = ""
    if not iso:
        iso3 = (iso3_value or "").strip().upper()
        if iso3 and iso3 != "-99":
            iso = alpha3_map.get(iso3, "")
    if not iso:
        adm0 = (adm0_a3_value or "").strip().upper()
        if adm0 and adm0 != "-99":
            iso = alpha3_map.get(adm0, "")
    if not iso:
        iso = FIXUP_MAP.get((feature_name or "").strip().upper(), "")
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

    iso_target, alpha3_map = load_iso_index(iso_canonical_path)

    if src_geojson.suffix.lower() == ".zip":
        gdf = gpd.read_file(f"zip://{src_geojson}")
    else:
        gdf = gpd.read_file(src_geojson)

    name_col = "NAME" if "NAME" in gdf.columns else "name"
    iso2_col = "ISO_A2" if "ISO_A2" in gdf.columns else "ISO3166-1-Alpha-2"
    iso3_col = (
        "ISO_A3" if "ISO_A3" in gdf.columns else ("ISO3166-1-Alpha-3" if "ISO3166-1-Alpha-3" in gdf.columns else None)
    )
    adm0_col = "ADM0_A3" if "ADM0_A3" in gdf.columns else None

    iso2_vals = gdf[iso2_col] if iso2_col in gdf.columns else [""] * len(gdf)
    iso3_vals = gdf[iso3_col] if iso3_col and iso3_col in gdf.columns else [""] * len(gdf)
    adm0_vals = gdf[adm0_col] if adm0_col and adm0_col in gdf.columns else [""] * len(gdf)

    gdf["country_iso"] = [
        normalise_iso(name, iso2, iso3, adm0, alpha3_map)
        for name, iso2, iso3, adm0 in zip(gdf[name_col], iso2_vals, iso3_vals, adm0_vals)
    ]
    gdf["name"] = gdf[name_col].astype(str)
    gdf = gdf[["country_iso", "name", "geometry"]]
    gdf = gdf[gdf["country_iso"].str.match(r"^[A-Z]{2}$")]
    gdf = gdf[gdf["country_iso"].isin(iso_target)]
    gdf = gdf.to_crs("EPSG:4326")
    gdf = gdf.rename_geometry("geom")

    produced_iso = set(gdf["country_iso"].to_list())
    missing_before = sorted(iso_target - produced_iso)

    synthetic_rows: List[Dict[str, object]] = []
    for iso in missing_before:
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
        synth_gdf = synth_gdf.rename_geometry("geom")
        gdf = gpd.GeoDataFrame(
            pd.concat([gdf, synth_gdf], ignore_index=True),
            geometry="geom",
            crs="EPSG:4326",
        )

    produced_iso = set(gdf["country_iso"].to_list())
    missing_after = sorted(iso_target - produced_iso)
    if missing_after:
        raise RuntimeError(f"Missing ISO2 coverage after synthetic fill: {missing_after}")

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
        "iso3166_canonical": str(iso_canonical_path.relative_to(ROOT)),
        "iso3166_canonical_sha256": sha256sum(iso_canonical_path),
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
        "missing_iso_before_aug": missing_before,
        "missing_iso_after_aug": missing_after,
        "produced_iso": sorted(gdf["country_iso"].unique().tolist()),
    }
    qa_path.write_text(json.dumps(qa_payload, indent=2) + "\n", encoding="utf-8")

    sha_path = output_dir / "SHA256SUMS"
    lines = [
        f"{manifest['source_geojson_sha256']}  {manifest['source_geojson']}",
        f"{manifest['iso3166_canonical_sha256']}  {manifest['iso3166_canonical']}",
        f"{manifest['output_parquet_sha256']}  {manifest['output_parquet']}",
        f"{sha256sum(qa_path)}  reference/spatial/world_countries/{version}/world_countries.qa.json",
    ]
    sha_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default="2025-10-08")
    parser.add_argument("--source", default=str(RAW_DIR / "countries.geojson"))
    parser.add_argument(
        "--iso-table",
        default=str(
            ROOT / "reference/iso/iso3166_canonical/2024-12-31/iso3166.parquet"
        ),
    )
    args = parser.parse_args()

    build_world_countries(Path(args.source), Path(args.iso_table), args.version)


if __name__ == "__main__":
    main()
