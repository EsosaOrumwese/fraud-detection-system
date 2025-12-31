"""Derive 3B virtual_settlement_coords from pelias_cached.sqlite."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import polars as pl


ROOT = Path(__file__).resolve().parents[1]
MERCHANT_PATH = (
    "reference/layer1/transaction_schema_merchant_ids/2025-12-31/"
    "transaction_schema_merchant_ids.parquet"
)
PELIA_PATH = "artefacts/geocode/pelias_cached.sqlite"
ISO_PATH = "reference/iso/iso3166_canonical/2024-12-31/iso3166.parquet"
OUT_PATH = "artefacts/virtual/virtual_settlement_coords.csv"
PROV_PATH = "artefacts/virtual/virtual_settlement_coords.provenance.json"

N_MAX = 500
BUCKET_RANGES = [(0, 0), (1, 4), (5, 19), (20, 99), (100, N_MAX - 1)]
BUCKET_PROBS = [0.15, 0.25, 0.30, 0.20, 0.10]
TZ_RE = re.compile(r"^[A-Za-z]+(?:[A-Za-z0-9_+.-]*)?(?:/[A-Za-z0-9_+.-]+)+$")


def round_half_away(value: float, ndigits: int) -> float:
    factor = 10**ndigits
    return math.copysign(math.floor(abs(value) * factor + 0.5) / factor, value)


def u_det(stage: str, merchant_id: int, country_iso: str, batch: str) -> float:
    msg = f"3B.settlement|{stage}|{merchant_id}|{country_iso}|{batch}"
    h = hashlib.sha256(msg.encode("utf-8")).digest()
    x = int.from_bytes(h[:8], "big")
    return (x + 0.5) / 2**64


def build_buckets(n: int) -> List[Tuple[int, List[int], float]]:
    buckets = []
    for idx, (start, end) in enumerate(BUCKET_RANGES, start=1):
        if start > n - 1:
            continue
        end = min(end, n - 1)
        indices = list(range(start, end + 1))
        buckets.append((idx, indices, BUCKET_PROBS[idx - 1]))
    total_prob = sum(bucket[2] for bucket in buckets)
    buckets = [(bid, indices, prob / total_prob) for bid, indices, prob in buckets]
    return buckets


def choose_bucket(u: float, buckets: List[Tuple[int, List[int], float]]):
    cumulative = 0.0
    for bucket_id, indices, prob in buckets:
        cumulative += prob
        if u <= cumulative:
            return bucket_id, indices
    return buckets[-1][0], buckets[-1][1]


def choose_candidate(
    u: float, indices: List[int], candidates: List[Tuple]
) -> Tuple[int, Tuple]:
    weights = []
    for idx in indices:
        population = candidates[idx][3]
        weights.append((population + 1000) ** 0.85)
    total = sum(weights)
    target = u * total
    cumulative = 0.0
    for idx, weight in zip(indices, weights):
        cumulative += weight
        if target <= cumulative:
            return idx, candidates[idx]
    return indices[-1], candidates[indices[-1]]


def load_iso_set(path: Path) -> set[str]:
    frame = pl.read_parquet(path)
    cols = {c.lower(): c for c in frame.columns}
    if "country_iso" in cols:
        iso_col = cols["country_iso"]
    elif "alpha2" in cols:
        iso_col = cols["alpha2"]
    else:
        raise RuntimeError("ISO file missing country_iso or alpha2 column")
    return {
        str(code).strip().upper()
        for code in frame[iso_col].to_list()
        if str(code).strip()
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--merchant-path", default=MERCHANT_PATH)
    parser.add_argument("--pelias-path", default=PELIA_PATH)
    parser.add_argument("--iso-path", default=ISO_PATH)
    parser.add_argument("--out-path", default=OUT_PATH)
    parser.add_argument("--prov-path", default=PROV_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    merchant_path = ROOT / args.merchant_path
    pelias_path = ROOT / args.pelias_path
    iso_path = ROOT / args.iso_path
    out_path = ROOT / args.out_path
    prov_path = ROOT / args.prov_path

    coordinate_batch = merchant_path.parent.name

    iso_set = load_iso_set(iso_path)
    merchants = pl.read_parquet(merchant_path).select(
        "merchant_id", "home_country_iso"
    )
    merchants = merchants.with_columns(
        pl.col("home_country_iso").cast(pl.Utf8).str.to_uppercase()
    )
    merchants = merchants.sort("merchant_id")

    unknown_iso = (
        merchants.filter(~pl.col("home_country_iso").is_in(sorted(iso_set)))
        .get_column("home_country_iso")
        .unique()
        .to_list()
    )
    if unknown_iso:
        raise RuntimeError(f"Unknown ISO2 in merchant_ids: {unknown_iso[:10]}")

    conn = sqlite3.connect(pelias_path)
    cur = conn.cursor()

    countries = merchants.get_column("home_country_iso").unique().to_list()
    candidate_map: Dict[str, List[Tuple]] = {}
    bucket_map: Dict[str, List[Tuple[int, List[int], float]]] = {}
    candidate_counts: Dict[str, int] = {}

    for iso in sorted(countries):
        rows = cur.execute(
            """
            SELECT geonameid, latitude, longitude, population, timezone
            FROM geoname
            WHERE country_code = ? AND feature_class = 'P' AND population >= 0
            ORDER BY population DESC, geonameid ASC
            LIMIT ?
            """,
            (iso, N_MAX),
        ).fetchall()
        if not rows:
            raise RuntimeError(f"No pelias candidates for country {iso}")
        candidates = [
            (
                int(row[0]),
                float(row[1]),
                float(row[2]),
                int(row[3]) if row[3] is not None else 0,
                row[4] if row[4] is not None else "",
            )
            for row in rows
        ]
        candidate_map[iso] = candidates
        bucket_map[iso] = build_buckets(len(candidates))
        candidate_counts[iso] = len(candidates)

    conn.close()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    prov_path.parent.mkdir(parents=True, exist_ok=True)

    distinct_geoname = set()
    country_counts = defaultdict(int)
    country_geoname_counts: Dict[str, Dict[int, int]] = defaultdict(
        lambda: defaultdict(int)
    )
    country_bucket_counts: Dict[str, Dict[int, int]] = defaultdict(
        lambda: defaultdict(int)
    )

    with out_path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(
            "merchant_id,lat_deg,lon_deg,evidence_url,coord_source,"
            "tzid_settlement,notes\n"
        )
        for merchant_id, home_iso in merchants.iter_rows():
            candidates = candidate_map[home_iso]
            buckets = bucket_map[home_iso]

            u1 = u_det("bucket", int(merchant_id), home_iso, coordinate_batch)
            bucket_id, indices = choose_bucket(u1, buckets)
            u2 = u_det("within", int(merchant_id), home_iso, coordinate_batch)
            _, chosen = choose_candidate(u2, indices, candidates)

            geonameid, lat, lon, population, timezone = chosen
            lat = round_half_away(lat, 6)
            lon = round_half_away(lon, 6)
            if lon == -180.0:
                lon = 180.0
            if not (-90.0 <= lat <= 90.0):
                raise RuntimeError("Latitude out of bounds")
            if not (-180.0 < lon <= 180.0):
                raise RuntimeError("Longitude out of bounds")

            tzid = timezone if timezone and TZ_RE.match(timezone) else ""
            evidence_url = f"https://sws.geonames.org/{geonameid}/"
            notes = f"geonameid={geonameid};bucket=B{bucket_id}"

            handle.write(
                f"{merchant_id},{lat:.6f},{lon:.6f},{evidence_url},"
                "geonames:cities500_via_pelias_cached,"
                f"{tzid},{notes}\n"
            )

            distinct_geoname.add(geonameid)
            country_counts[home_iso] += 1
            country_geoname_counts[home_iso][geonameid] += 1
            country_bucket_counts[home_iso][bucket_id] += 1

    merchant_total = merchants.height
    min_distinct = max(500, int(math.floor(0.05 * merchant_total)))
    if len(distinct_geoname) < min_distinct:
        raise RuntimeError("Distinct settlement diversity floor failed")

    max_share_by_country = {}
    for iso, count in country_counts.items():
        distinct_count = len(country_geoname_counts[iso])
        if count >= 200:
            required = min(10, candidate_counts.get(iso, 0))
            if distinct_count < required:
                raise RuntimeError(f"Country spread floor failed for {iso}")
        if count >= 1000:
            max_share = max(country_geoname_counts[iso].values()) / count
            if max_share > 0.40:
                raise RuntimeError(f"Anti-collapse floor failed for {iso}")
            max_share_by_country[iso] = max_share

    provenance = {
        "dataset_id": "virtual_settlement_coords",
        "coordinate_batch": coordinate_batch,
        "inputs": {
            "merchant_snapshot": str(merchant_path.relative_to(ROOT)),
            "pelias_cached_sqlite": str(pelias_path.relative_to(ROOT)),
        },
        "algorithm": {
            "bucket_ranges": BUCKET_RANGES,
            "bucket_probs": BUCKET_PROBS,
            "population_exponent": 0.85,
            "population_smoothing": 1000,
            "rounding_dp": 6,
            "max_candidates": N_MAX,
        },
        "summary": {
            "row_count": merchant_total,
            "distinct_settlements": len(distinct_geoname),
            "max_share_top_settlement_by_country": max_share_by_country,
            "candidate_counts": candidate_counts,
        },
    }
    prov_path.write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
