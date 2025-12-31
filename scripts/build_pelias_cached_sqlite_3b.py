"""Build the 3B pelias_cached.sqlite bundle from GeoNames dumps."""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

import requests


ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = ROOT / "artefacts/geocode/pelias_cached.sqlite"
META_PATH = ROOT / "artefacts/geocode/pelias_cached_bundle.json"
PROV_PATH = ROOT / "artefacts/geocode/pelias_cached_bundle.provenance.json"
RAW_DIR = ROOT / "artefacts/geocode/source/pelias_cached"

BASE_URL = "https://download.geonames.org/export/dump/"
FILES = {
    "cities500.zip": 1_000_000,
    "countryInfo.txt": 1_000,
    "admin1CodesASCII.txt": 1_000,
    "timeZones.txt": 1_000,
}


@dataclass(frozen=True)
class RawFile:
    name: str
    path: Path
    sha256: str
    bytes: int


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:  # noqa: PTH123
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_file(name: str, min_bytes: int, out_dir: Path) -> RawFile:
    url = f"{BASE_URL}{name}"
    response = requests.get(url, timeout=120)
    if response.status_code != 200:
        raise RuntimeError(f"HTTP {response.status_code} for {url}")
    if response.text.lstrip().startswith("<!DOCTYPE html"):
        raise RuntimeError(f"GeoNames returned HTML for {name}")
    path = out_dir / name
    path.write_bytes(response.content)
    size = path.stat().st_size
    if size < min_bytes:
        raise RuntimeError(f"{name} too small ({size} bytes)")
    return RawFile(name=name, path=path, sha256=sha256_path(path), bytes=size)


def parse_cities500(path: Path) -> list[tuple]:
    with zipfile.ZipFile(path, "r") as zf:
        with zf.open("cities500.txt") as handle:
            lines = handle.read().decode("utf-8").splitlines()

    rows = []
    for line in lines:
        parts = line.split("\t")
        if len(parts) != 19:
            raise RuntimeError("Invalid cities500 row")
        (
            geonameid,
            name,
            asciiname,
            alternatenames,
            latitude,
            longitude,
            feature_class,
            feature_code,
            country_code,
            cc2,
            admin1_code,
            admin2_code,
            admin3_code,
            admin4_code,
            population,
            elevation,
            dem,
            timezone,
            modification_date,
        ) = parts
        rows.append(
            (
                int(geonameid),
                name,
                asciiname,
                alternatenames,
                float(latitude),
            float(longitude),
            feature_class,
            feature_code,
            country_code,
            admin1_code,
                admin2_code,
                admin3_code,
                admin4_code,
                int(population) if population else 0,
                int(elevation) if elevation else None,
                int(dem) if dem else None,
                timezone,
                modification_date,
            )
        )
    rows.sort(key=lambda row: row[0])
    return rows


def parse_country_info(path: Path) -> list[tuple]:
    lines = path.read_text(encoding="utf-8").splitlines()
    rows = []
    for line in lines:
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 19:
            raise RuntimeError("Invalid countryInfo row")
        rows.append(tuple(parts[:19]))
    rows.sort(key=lambda row: row[0])
    return rows


def parse_admin1(path: Path) -> list[tuple]:
    lines = path.read_text(encoding="utf-8").splitlines()
    rows = []
    for line in lines:
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 4:
            raise RuntimeError("Invalid admin1 row")
        rows.append(tuple(parts[:4]))
    rows.sort(key=lambda row: row[0])
    return rows


def parse_timezones(path: Path) -> list[tuple]:
    lines = path.read_text(encoding="utf-8").splitlines()
    rows = []
    for line in lines:
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 5:
            raise RuntimeError("Invalid timeZones row")
        rows.append(tuple(parts[:5]))
    rows.sort(key=lambda row: (row[0], row[1]))
    return rows


def chunked(rows: Sequence[tuple], size: int = 10_000) -> Iterable[Sequence[tuple]]:
    for idx in range(0, len(rows), size):
        yield rows[idx : idx + size]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pelias-version", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    raw_files = []
    for name, min_bytes in FILES.items():
        raw_files.append(download_file(name, min_bytes, RAW_DIR))

    cities_rows = parse_cities500(RAW_DIR / "cities500.zip")
    country_rows = parse_country_info(RAW_DIR / "countryInfo.txt")
    admin_rows = parse_admin1(RAW_DIR / "admin1CodesASCII.txt")
    tz_rows = parse_timezones(RAW_DIR / "timeZones.txt")

    if OUT_PATH.exists():
        OUT_PATH.unlink()

    conn = sqlite3.connect(OUT_PATH)
    cur = conn.cursor()
    cur.execute("PRAGMA page_size=4096")
    cur.execute("PRAGMA journal_mode=OFF")
    cur.execute("PRAGMA synchronous=OFF")
    cur.execute("PRAGMA temp_store=MEMORY")

    cur.execute(
        """
        CREATE TABLE geoname (
            geonameid INTEGER PRIMARY KEY,
            name TEXT,
            asciiname TEXT,
            alternatenames TEXT,
            latitude REAL,
            longitude REAL,
            feature_class TEXT,
            feature_code TEXT,
            country_code TEXT,
            admin1_code TEXT,
            admin2_code TEXT,
            admin3_code TEXT,
            admin4_code TEXT,
            population INTEGER,
            elevation INTEGER,
            dem INTEGER,
            timezone TEXT,
            modification_date TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE country_info (
            iso2 TEXT,
            iso3 TEXT,
            iso_numeric TEXT,
            fips TEXT,
            country TEXT,
            capital TEXT,
            area REAL,
            population INTEGER,
            continent TEXT,
            tld TEXT,
            currency_code TEXT,
            currency_name TEXT,
            phone TEXT,
            postal_code_format TEXT,
            postal_code_regex TEXT,
            languages TEXT,
            geonameid INTEGER,
            neighbours TEXT,
            equivalent_fips_code TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE admin1_codes (
            code TEXT,
            name TEXT,
            asciiname TEXT,
            geonameid INTEGER
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE timezones (
            country_code TEXT,
            timezone_id TEXT,
            gmt_offset TEXT,
            dst_offset TEXT,
            raw_offset TEXT
        )
        """
    )

    for batch in chunked(cities_rows):
        cur.executemany(
            """
            INSERT INTO geoname VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            batch,
        )

    for batch in chunked(country_rows):
        cur.executemany(
            """
            INSERT INTO country_info VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            batch,
        )

    for batch in chunked(admin_rows):
        cur.executemany("INSERT INTO admin1_codes VALUES (?,?,?,?)", batch)

    for batch in chunked(tz_rows):
        cur.executemany("INSERT INTO timezones VALUES (?,?,?,?,?)", batch)

    cur.execute("CREATE INDEX geoname_country_code_idx ON geoname(country_code)")
    cur.execute(
        "CREATE INDEX geoname_feature_idx ON geoname(feature_class, feature_code)"
    )
    cur.execute("CREATE INDEX geoname_population_idx ON geoname(population DESC)")
    cur.execute("CREATE INDEX geoname_name_idx ON geoname(name)")
    cur.execute("CREATE INDEX geoname_asciiname_idx ON geoname(asciiname)")

    conn.commit()
    cur.execute("VACUUM")
    conn.commit()

    integrity = cur.execute("PRAGMA integrity_check").fetchone()
    if integrity is None or integrity[0] != "ok":
        raise RuntimeError("SQLite integrity check failed")

    geoname_count = cur.execute("SELECT COUNT(*) FROM geoname").fetchone()[0]
    country_count = cur.execute(
        "SELECT COUNT(DISTINCT country_code) FROM geoname"
    ).fetchone()[0]
    country_info_count = cur.execute("SELECT COUNT(*) FROM country_info").fetchone()[0]

    if geoname_count < 150000:
        raise RuntimeError("geoname table below realism floor")
    if country_count < 200:
        raise RuntimeError("geoname country coverage below realism floor")
    if country_info_count < 200:
        raise RuntimeError("country_info table below realism floor")

    sqlite_version = cur.execute("select sqlite_version()").fetchone()[0]
    indexes = [
        row[1]
        for row in cur.execute(
            "SELECT type, name FROM sqlite_master WHERE type='index'"
        ).fetchall()
    ]
    conn.close()

    sqlite_sha256 = sha256_path(OUT_PATH)
    sqlite_bytes = OUT_PATH.stat().st_size

    META_PATH.write_text(
        json.dumps(
            {
                "version": args.pelias_version,
                "sha256_hex": sqlite_sha256,
                "tile_span": "global",
                "licence": "CC-BY-4.0 (GeoNames Gazetteer extract)",
                "notes": (
                    "Built deterministically from GeoNames dump files: "
                    "cities500.zip, countryInfo.txt, admin1CodesASCII.txt, timeZones.txt."
                ),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    provenance = {
        "dataset_id": "pelias_cached_bundle",
        "pelias_version": args.pelias_version,
        "upstream_sources": {
            "base_url": BASE_URL,
            "files": [
                {"name": rf.name, "sha256": rf.sha256, "bytes": rf.bytes}
                for rf in raw_files
            ],
        },
        "build": {
            "sqlite_version": sqlite_version,
            "row_counts": {
                "geoname": geoname_count,
                "country_info": country_info_count,
                "admin1_codes": len(admin_rows),
                "timezones": len(tz_rows),
            },
            "indexes": indexes,
        },
        "output": {"sha256": sqlite_sha256, "bytes": sqlite_bytes},
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    PROV_PATH.write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
