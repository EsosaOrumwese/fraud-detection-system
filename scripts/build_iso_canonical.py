"""Build the canonical ISO-3166 reference dataset for S0.

This follows the iso3166_canonical_2024 acquisition guide and prefers the
GeoNames countryInfo.txt snapshot, emitting the contracted parquet +
provenance sidecar under reference/iso/iso3166_canonical/<version>/.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import polars as pl
import requests


ROOT = Path(__file__).resolve().parents[1]
ISO_ROOT = ROOT / "reference" / "iso" / "iso3166_canonical"

GEONAMES_URL = "https://download.geonames.org/export/dump/countryInfo.txt"

OUTPUT_COLUMNS = [
    "country_iso",
    "alpha3",
    "numeric_code",
    "name",
    "region",
    "subregion",
    "start_date",
    "end_date",
]

COUNTRYINFO_COLUMNS = [
    "country_iso",
    "alpha3",
    "numeric_code",
    "fips",
    "name",
    "capital",
    "area_sq_km",
    "population",
    "continent",
    "tld",
    "currency_code",
    "currency_name",
    "phone",
    "postal_code_format",
    "postal_code_regex",
    "languages",
    "geonameid",
    "neighbours",
    "equivalent_fips_code",
]

EXCLUDED_ISO2 = {"UK", "XK"}


def sha256sum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_source(dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(GEONAMES_URL, timeout=120)
    response.raise_for_status()
    dest.write_bytes(response.content)


def load_source(path: Path) -> pl.DataFrame:
    lines = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip() or line.startswith("#"):
                continue
            lines.append(line)
    return pl.read_csv(
        io.StringIO("".join(lines)),
        separator="\t",
        has_header=False,
        infer_schema_length=0,
        new_columns=COUNTRYINFO_COLUMNS,
    )


def _isoformat_z(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def build_dataset(df: pl.DataFrame) -> pl.DataFrame:
    result = df.select(
        pl.col("country_iso").str.strip_chars().str.to_uppercase().alias("country_iso"),
        pl.col("alpha3").str.strip_chars().str.to_uppercase().alias("alpha3"),
        pl.col("numeric_code").str.strip_chars().alias("numeric_code"),
        pl.col("name").str.strip_chars().alias("name"),
    )

    result = result.filter(pl.col("country_iso").str.contains(r"^[A-Z]{2}$"))
    if EXCLUDED_ISO2:
        result = result.filter(~pl.col("country_iso").is_in(list(EXCLUDED_ISO2)))

    result = result.with_columns(
        pl.col("numeric_code").cast(pl.Int16, strict=True),
        pl.lit(None, dtype=pl.Utf8).alias("region"),
        pl.lit(None, dtype=pl.Utf8).alias("subregion"),
        pl.lit(None, dtype=pl.Date).alias("start_date"),
        pl.lit(None, dtype=pl.Date).alias("end_date"),
    )

    if result.select(pl.col("country_iso").n_unique()).item() != result.height:
        raise ValueError("Duplicate country_iso detected")
    if result.select(pl.struct(["alpha3", "numeric_code"]).n_unique()).item() != result.height:
        raise ValueError("Duplicate (alpha3, numeric_code) detected")
    if result.filter(pl.col("country_iso").is_null()).height > 0:
        raise ValueError("country_iso contains nulls")
    if result.filter(pl.col("alpha3").is_null()).height > 0:
        raise ValueError("alpha3 contains nulls")
    if result.filter(pl.col("numeric_code").is_null()).height > 0:
        raise ValueError("numeric_code contains nulls")
    if result.filter(pl.col("name").is_null()).height > 0:
        raise ValueError("name contains nulls")
    if result.filter(~pl.col("alpha3").str.contains(r"^[A-Z]{3}$")).height > 0:
        raise ValueError("alpha3 contains invalid values")

    return result.select(OUTPUT_COLUMNS).sort("country_iso")


def build_manifest(
    *,
    version: str,
    source_sha: str,
    parquet_path: Path,
    provenance_path: Path,
    row_count: int,
    upstream_retrieved_utc: str,
    is_exact_vintage: bool,
) -> dict:
    return {
        "dataset_id": "iso3166_canonical_2024",
        "version": version,
        "source_url": GEONAMES_URL,
        "source_sha256": source_sha,
        "upstream_retrieved_utc": upstream_retrieved_utc,
        "generated_at_utc": _isoformat_z(datetime.now(timezone.utc)),
        "generator_script": "scripts/build_iso_canonical.py",
        "output_parquet": str(parquet_path.relative_to(ROOT)),
        "output_parquet_sha256": sha256sum(parquet_path),
        "provenance_path": str(provenance_path.relative_to(ROOT)),
        "provenance_sha256": sha256sum(provenance_path),
        "row_count": row_count,
        "column_order": OUTPUT_COLUMNS,
        "excluded_iso2": sorted(EXCLUDED_ISO2),
        "is_exact_vintage": is_exact_vintage,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default="2024-12-31", help="Dataset version tag")
    parser.add_argument("--source-path", default=None, help="Optional path to GeoNames countryInfo.txt")
    parser.add_argument("--download", action="store_true", help="Force download of the GeoNames source.")
    parser.add_argument(
        "--is-exact-vintage",
        action="store_true",
        help="Flag that the source snapshot matches the version.",
    )
    args = parser.parse_args()

    output_dir = ISO_ROOT / args.version
    raw_dir = output_dir / "source"
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    raw_path = raw_dir / "countryInfo.txt"
    source_path = Path(args.source_path).resolve() if args.source_path else raw_path
    if args.download or not source_path.exists():
        download_source(raw_path)
        source_path = raw_path
        upstream_retrieved = datetime.now(timezone.utc)
    else:
        upstream_retrieved = datetime.fromtimestamp(source_path.stat().st_mtime, timezone.utc)
        if source_path != raw_path:
            shutil.copy2(source_path, raw_path)
            source_path = raw_path

    source_sha = sha256sum(source_path)
    curated = build_dataset(load_source(source_path))

    parquet_path = output_dir / "iso3166.parquet"
    curated.write_parquet(parquet_path, compression="zstd", statistics=True)

    provenance_path = output_dir / "iso3166.provenance.json"
    provenance = {
        "dataset_id": "iso3166_canonical_2024",
        "version": args.version,
        "upstream_url": GEONAMES_URL,
        "upstream_retrieved_utc": _isoformat_z(upstream_retrieved),
        "upstream_version_label": None,
        "raw_bytes_sha256": source_sha,
        "output_sha256": sha256sum(parquet_path),
        "row_count": curated.height,
        "is_exact_vintage": bool(args.is_exact_vintage),
        "exclusions": {
            "country_iso": sorted(EXCLUDED_ISO2),
            "excluded_count": len(EXCLUDED_ISO2),
        },
        "notes": (
            "GeoNames countryInfo.txt snapshot; excluded XK and UK per guide. "
            "Optional region/subregion/start_date/end_date left null."
        ),
    }
    provenance_path.write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")

    manifest = build_manifest(
        version=args.version,
        source_sha=source_sha,
        parquet_path=parquet_path,
        provenance_path=provenance_path,
        row_count=curated.height,
        upstream_retrieved_utc=_isoformat_z(upstream_retrieved),
        is_exact_vintage=bool(args.is_exact_vintage),
    )
    (output_dir / "iso3166.manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
