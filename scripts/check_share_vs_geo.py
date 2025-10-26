#!/usr/bin/env python
"""Verify that governed share surfaces only reference ISO codes present in the geo boundary file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, Set

import polars as pl


DEFAULT_COUNTRIES = (
    Path("artefacts")
    / "spatial"
    / "world_countries"
    / "raw"
    / "countries.geojson"
)
DEFAULT_SHARES = (
    Path("reference")
    / "network"
    / "settlement_shares"
    / "2025-10-26"
    / "settlement_shares.parquet"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compares ISO country codes in settlement share surfaces against the geojson "
            "authority file and reports any missing coverage."
        )
    )
    parser.add_argument(
        "--countries",
        type=Path,
        default=DEFAULT_COUNTRIES,
        help="Path to the authoritative countries.geojson file.",
    )
    parser.add_argument(
        "--shares",
        type=Path,
        default=DEFAULT_SHARES,
        help="Path to the settlement_shares parquet file to validate.",
    )
    parser.add_argument(
        "--list-missing",
        action="store_true",
        help="Print the full list of missing ISO codes instead of just the count.",
    )
    return parser.parse_args()


def _load_geo_iso(path: Path) -> Set[str]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    features: Iterable[dict] = payload.get("features", [])
    codes = {
        str(feature.get("properties", {}).get("ISO3166-1-Alpha-2", ""))
        .strip()
        .upper()
        for feature in features
    }
    return {code for code in codes if code}


def _load_share_iso(path: Path) -> Set[str]:
    frame = pl.read_parquet(path, columns=["country_iso"])
    return {str(code).strip().upper() for code in frame["country_iso"].to_list() if code}


def main() -> int:
    args = parse_args()
    countries_path = args.countries.expanduser().resolve()
    shares_path = args.shares.expanduser().resolve()

    if not countries_path.exists():
        raise FileNotFoundError(f"countries geojson not found: {countries_path}")
    if not shares_path.exists():
        raise FileNotFoundError(f"settlement shares parquet not found: {shares_path}")

    geo_iso = _load_geo_iso(countries_path)
    share_iso = _load_share_iso(shares_path)

    missing = sorted(share_iso - geo_iso)
    extra = sorted(geo_iso - share_iso)

    print(f"[check-share-vs-geo] countries file: {countries_path}")
    print(f"[check-share-vs-geo] shares file:    {shares_path}")
    print(f"[check-share-vs-geo] total geo ISO codes:   {len(geo_iso)}")
    print(f"[check-share-vs-geo] total share ISO codes: {len(share_iso)}")

    if missing:
        print(f"[check-share-vs-geo] missing ISO codes in geojson: {len(missing)}")
        if args.list_missing:
            print(", ".join(missing))
    else:
        print("[check-share-vs-geo] ✓ no missing ISO codes.")

    if extra:
        print(f"[check-share-vs-geo] warning: {len(extra)} geo-only ISO codes (unused in shares).")
        if args.list_missing:
            print(", ".join(extra))

    return 1 if missing else 0


if __name__ == "__main__":  # pragma: no cover - convenience script
    raise SystemExit(main())
