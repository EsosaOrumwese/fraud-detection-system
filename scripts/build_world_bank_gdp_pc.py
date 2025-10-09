"""Download and materialise World Bank GDP per capita (constant 2015 USD).

This script fetches country metadata and GDP per capita observations for the
target year, filters to sovereign ISO-2 codes (skipping aggregates), and
produces CSV/Parquet outputs together with a manifest capturing digests of
inputs and outputs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

import polars as pl
import requests


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_BASE = ROOT / "reference" / "economic" / "world_bank_gdp_per_capita"
ARTEFACT_BASE = ROOT / "artefacts" / "economic" / "world_bank_gdp_per_capita"
for directory in (REFERENCE_BASE, ARTEFACT_BASE):
    directory.mkdir(parents=True, exist_ok=True)


def fetch_all_pages(url: str, *, params: Dict[str, str] | None = None) -> Tuple[List[dict], List[dict]]:
    """Fetch paginated World Bank API data, returning records and raw payloads."""

    base_params = {"per_page": "1000", "format": "json"}
    if params:
        base_params.update(params)

    page = 1
    data: List[dict] = []
    raw_payloads: List[dict] = []
    while True:
        base_params["page"] = str(page)
        resp = requests.get(url, params=base_params, timeout=120, headers={"User-Agent": "fraud-engine/0"})
        resp.raise_for_status()
        payload = resp.json()
        raw_payloads.append(payload)
        if not isinstance(payload, list) or len(payload) != 2:
            raise RuntimeError(f"Unexpected response structure for {url}: {payload[:1]}")
        meta, items = payload
        data.extend(items)
        if page >= int(meta.get("pages", 0)):
            break
        page += 1
    return data, raw_payloads


def build_iso_mapping(raw_dir: Path) -> Dict[str, str]:
    countries, raw = fetch_all_pages("https://api.worldbank.org/v2/country")
    (raw_dir / "countries.json").write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")

    mapping: Dict[str, str] = {}
    excluded: List[str] = []
    for item in countries:
        iso2 = (item.get("iso2Code") or "").upper()
        iso3 = (item.get("id") or "").upper()
        region_id = (item.get("region") or {}).get("id") or ""
        income_level = (item.get("incomeLevel") or {}).get("id") or ""
        if len(iso2) != 2 or not iso3:
            excluded.append(iso3 or iso2)
            continue
        if not iso2.isalpha():
            excluded.append(iso3)
            continue
        if region_id == "Aggregates" or income_level in {"HIC", "LIC", "MIC", "NOC"} and iso2 in {"1A", "1W"}:
            excluded.append(iso3)
            continue
        if iso3 in mapping:
            continue
        mapping[iso3] = iso2
    if not mapping:
        raise RuntimeError("ISO mapping came back empty")
    (raw_dir / "countries-excluded.json").write_text(json.dumps(sorted(excluded), indent=2) + "\n", encoding="utf-8")
    return mapping


def fetch_gdp_series(year: int, raw_dir: Path) -> pl.DataFrame:
    observations, raw = fetch_all_pages(
        "https://api.worldbank.org/v2/country/all/indicator/NY.GDP.PCAP.KD",
        params={"date": str(year)},
    )
    (raw_dir / f"gdp_{year}.json").write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")

    iso_map = build_iso_mapping(raw_dir)
    rows = []
    missing_iso3: Dict[str, float] = {}
    for obs in observations:
        iso3 = (obs.get("countryiso3code") or "").upper()
        if iso3 not in iso_map:
            value = obs.get("value")
            if value not in (None, ""):
                missing_iso3[iso3] = value
            continue
        value = obs.get("value")
        if value is None:
            continue
        rows.append(
            {
                "country_iso": iso_map[iso3],
                "gdp_pc_usd_2015": float(value),
                "observation_year": year,
                "source_series": "NY.GDP.PCAP.KD",
            }
        )

    if not rows:
        raise RuntimeError("No GDP observations collected for the specified year")

    df = (
        pl.DataFrame(rows)
        .group_by("country_iso")
        .agg(
            pl.col("gdp_pc_usd_2015").mean().alias("gdp_pc_usd_2015"),
            pl.col("observation_year").max().alias("observation_year"),
            pl.col("source_series").first().alias("source_series"),
        )
        .sort("country_iso")
    )

    # Log ISO3 codes that were dropped (aggregates/missing mapping) for audit.
    (raw_dir / f"gdp_{year}_missing_iso3.json").write_text(json.dumps(missing_iso3, indent=2) + "\n", encoding="utf-8")
    return df


def sha256sum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_outputs(df: pl.DataFrame, version: str, raw_dir: Path) -> None:
    out_dir = REFERENCE_BASE / version
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "world_bank_gdp_pc_2024.csv"
    parquet_path = out_dir / "gdp.parquet"
    df.write_csv(csv_path)
    df.write_parquet(parquet_path, compression="zstd", statistics=True)

    raw_digests = {}
    for raw_file in raw_dir.glob("*.json"):
        raw_digests[str(raw_file.relative_to(ROOT))] = sha256sum(raw_file)

    manifest = {
        "dataset_id": "world_bank_gdp_per_capita_2024",
        "version": version,
        "observation_year": int(df["observation_year"][0]),
        "source_series": "NY.GDP.PCAP.KD",
        "source_url": "https://api.worldbank.org/v2/",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "row_count": df.height,
        "output_csv": str(csv_path.relative_to(ROOT)),
        "output_csv_sha256": sha256sum(csv_path),
        "output_parquet": str(parquet_path.relative_to(ROOT)),
        "output_parquet_sha256": sha256sum(parquet_path),
        "raw_artifacts": raw_digests,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument("--version", type=str, default="2025-10-07")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    raw_dir = (ARTEFACT_BASE / args.version)
    raw_dir.mkdir(parents=True, exist_ok=True)
    df = fetch_gdp_series(year=args.year, raw_dir=raw_dir)
    write_outputs(df, version=args.version, raw_dir=raw_dir)


if __name__ == "__main__":
    main()
