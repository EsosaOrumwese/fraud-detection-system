"""Acquire external CDN weights proxy from World Bank indicators (CC-BY-4.0)."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, Tuple

import polars as pl
import requests


ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = ROOT / "artefacts/external/cdn_weights_ext.yaml"
PROV_PATH = ROOT / "artefacts/external/cdn_weights_ext.provenance.json"
RAW_DIR = ROOT / "artefacts/external/source/cdn_weights_ext"

INDICATOR_INTERNET = "IT.NET.USER.ZS"
INDICATOR_POP = "SP.POP.TOTL"
MAX_LAG_YEARS = 5
ISO_DEFAULT_PATH = "reference/iso/iso3166_canonical/2024-12-31/iso3166.parquet"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch_indicator(indicator: str, start_year: int, end_year: int) -> Tuple[bytes, list[dict]]:
    url = (
        "https://api.worldbank.org/v2/country/all/indicator/"
        f"{indicator}?date={start_year}:{end_year}&format=json&per_page=20000"
    )
    resp = requests.get(url, timeout=60, headers={"User-Agent": "fraud-detection-system/1.0"})
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code} for {indicator}")
    raw = resp.content
    payload = json.loads(raw)
    if isinstance(payload, dict) and payload.get("message"):
        raise RuntimeError(f"Error payload returned for {indicator}")
    if not isinstance(payload, list) or len(payload) < 2:
        raise RuntimeError(f"Unexpected payload shape for {indicator}")
    data = payload[1]
    if not isinstance(data, list):
        raise RuntimeError(f"Unexpected data list for {indicator}")
    return raw, data


def load_iso_set(path: Path) -> set[str]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        frame = pl.read_csv(path)
    elif suffix in {".parquet", ".pq"}:
        frame = pl.read_parquet(path)
    else:
        raise ValueError(f"Unsupported ISO file extension: {path.suffix}")

    cols = {c.lower(): c for c in frame.columns}
    if "country_iso" in cols:
        iso_col = cols["country_iso"]
    elif "alpha2" in cols:
        iso_col = cols["alpha2"]
    else:
        raise ValueError("ISO file must expose a 'country_iso' or 'alpha2' column")

    return {
        str(code).strip().upper()
        for code in frame[iso_col].to_list()
        if str(code).strip()
    }


def latest_by_country(
    rows: list[dict],
    iso_set: Iterable[str] | None,
) -> Tuple[Dict[str, Tuple[int, float]], set[str]]:
    latest: Dict[str, Tuple[int, float]] = {}
    seen: set[str] = set()
    iso_allow = {code.upper() for code in iso_set} if iso_set is not None else None
    for row in rows:
        country = row.get("country") or {}
        iso2 = country.get("id") or country.get("iso2Code")
        if not isinstance(iso2, str):
            continue
        iso2 = iso2.strip().upper()
        if not re.fullmatch(r"[A-Z]{2}", iso2):
            continue
        if iso_allow is not None and iso2 not in iso_allow:
            continue
        seen.add(iso2)
        year = row.get("date")
        value = row.get("value")
        if value is None:
            continue
        try:
            year_int = int(year)
            value_f = float(value)
        except (TypeError, ValueError):
            continue
        if not (value_f > 0.0):
            continue
        existing = latest.get(iso2)
        if existing is None or year_int > existing[0]:
            latest[iso2] = (year_int, value_f)
    return latest, seen


def collect_users(
    users_latest: Dict[str, Tuple[int, float]],
    pop_latest: Dict[str, Tuple[int, float]],
) -> Tuple[list[Tuple[str, float]], list[str]]:
    countries: list[Tuple[str, float]] = []
    missing: list[str] = []
    for iso2 in sorted(set(users_latest.keys()) | set(pop_latest.keys())):
        users = users_latest.get(iso2)
        pop = pop_latest.get(iso2)
        if users is None or pop is None:
            missing.append(iso2)
            continue
        users_count = pop[1] * (users[1] / 100.0)
        if not users_count > 0:
            missing.append(iso2)
            continue
        countries.append((iso2, users_count))
    return countries, missing


def impute_missing_users(
    users_latest: Dict[str, Tuple[int, float]],
    pop_latest: Dict[str, Tuple[int, float]],
) -> tuple[Dict[str, Tuple[int, float]], list[str], float]:
    values = [value for _, value in users_latest.values() if value > 0.0]
    if not values:
        raise RuntimeError("No valid internet user percentages to impute from")
    values.sort()
    mid = len(values) // 2
    if len(values) % 2 == 0:
        median_pct = (values[mid - 1] + values[mid]) / 2.0
    else:
        median_pct = values[mid]

    imputed: list[str] = []
    for iso2 in sorted(pop_latest.keys()):
        if iso2 in users_latest:
            continue
        users_latest[iso2] = (pop_latest[iso2][0], median_pct)
        imputed.append(iso2)

    return users_latest, imputed, median_pct


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vintage", required=True)
    parser.add_argument("--vintage-year", type=int, required=True)
    parser.add_argument("--iso-path", default=ISO_DEFAULT_PATH)
    args = parser.parse_args()

    vintage = args.vintage
    vintage_year = args.vintage_year
    start_year = vintage_year - MAX_LAG_YEARS

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    iso_set = load_iso_set(ROOT / args.iso_path)
    raw_users, rows_users = fetch_indicator(INDICATOR_INTERNET, start_year, vintage_year)
    raw_pop, rows_pop = fetch_indicator(INDICATOR_POP, start_year, vintage_year)

    users_path = RAW_DIR / f"{INDICATOR_INTERNET}_{start_year}_{vintage_year}.json"
    pop_path = RAW_DIR / f"{INDICATOR_POP}_{start_year}_{vintage_year}.json"
    users_path.write_bytes(raw_users)
    pop_path.write_bytes(raw_pop)

    users_latest, users_seen = latest_by_country(rows_users, iso_set)
    pop_latest, pop_seen = latest_by_country(rows_pop, iso_set)
    countries_seen = sorted(users_seen | pop_seen)
    countries, missing = collect_users(users_latest, pop_latest)

    filter_mode = "iso3166"
    imputed_countries: list[str] = []
    imputed_pct = None
    if len(countries) < 200:
        users_latest, imputed_countries, imputed_pct = impute_missing_users(
            dict(users_latest), pop_latest
        )
        countries, missing = collect_users(users_latest, pop_latest)
        filter_mode = "iso3166_impute_users_pct"

    if len(countries) < 200:
        users_latest, users_seen = latest_by_country(rows_users, None)
        pop_latest, pop_seen = latest_by_country(rows_pop, None)
        countries_seen = sorted(users_seen | pop_seen)
        countries, missing = collect_users(users_latest, pop_latest)
        filter_mode = "regex_only"

    if len(countries) < 200:
        raise RuntimeError("Coverage below 200 countries")

    total_users = sum(value for _, value in countries)
    if not total_users > 0:
        raise RuntimeError("Total users <= 0")

    weights = []
    for iso2, users_count in countries:
        weights.append((iso2, users_count / total_users))
    weights.sort(key=lambda item: item[0])

    top5 = sum(w for _, w in sorted(weights, key=lambda item: item[1], reverse=True)[:5])
    top10 = sum(w for _, w in sorted(weights, key=lambda item: item[1], reverse=True)[:10])
    if not (top5 >= 0.25 or top10 >= 0.40):
        raise RuntimeError("Heavy-tail check failed for external CDN weights")

    weight_sum = sum(w for _, w in weights)
    if abs(weight_sum - 1.0) > 1e-12:
        raise RuntimeError("Weights do not sum to 1.0")

    lines = [f'version: "{vintage}"', "countries:"]
    for iso2, weight in weights:
        lines.append(f"  - country_iso: \"{iso2}\"")
        lines.append(f"    weight: {weight:.12f}")
    OUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    top10_weight = sum(
        w for _, w in sorted(weights, key=lambda item: item[1], reverse=True)[:10]
    )
    top10_list = [
        {"country_iso": iso2, "weight": weight}
        for iso2, weight in sorted(weights, key=lambda item: item[1], reverse=True)[:10]
    ]
    provenance = {
        "dataset_id": "cdn_weights_ext_yaml",
        "vintage": vintage,
        "vintage_year": vintage_year,
        "MAX_LAG_YEARS": MAX_LAG_YEARS,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "urls": {
            "internet_users": f"https://api.worldbank.org/v2/country/all/indicator/{INDICATOR_INTERNET}?date={start_year}:{vintage_year}&format=json&per_page=20000",
            "population": f"https://api.worldbank.org/v2/country/all/indicator/{INDICATOR_POP}?date={start_year}:{vintage_year}&format=json&per_page=20000",
        },
        "raw": {
            "internet_users": {
                "path": str(users_path.relative_to(ROOT)),
                "sha256": sha256_bytes(raw_users),
                "bytes": len(raw_users),
            },
            "population": {
                "path": str(pop_path.relative_to(ROOT)),
                "sha256": sha256_bytes(raw_pop),
                "bytes": len(raw_pop),
            },
        },
        "counts": {
            "countries_total_seen": len(countries_seen),
            "countries_valid": len(weights),
            "countries_missing": len(missing),
            "countries_imputed": len(imputed_countries),
        },
        "summary": {
            "top5_weight": top5,
            "top10_weight": top10_weight,
            "top10": top10_list,
        },
        "filter_mode": filter_mode,
        "imputed_internet_pct": imputed_pct,
        "imputed_countries": imputed_countries,
        "license": "CC-BY-4.0 (World Bank Open Data)",
    }
    PROV_PATH.write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
