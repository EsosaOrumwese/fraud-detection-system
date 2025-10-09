"""Build the canonical ISO-3166 reference dataset for S0.

The script downloads the DataHub country-codes CSV, curates the required
columns, enforces schema guardrails, and materialises CSV + Parquet outputs
alongside a manifest and QA summary.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import polars as pl
import requests


ROOT = Path(__file__).resolve().parents[1]
ARTEFACT_DIR = ROOT / "artefacts" / "data-intake" / "1A" / "iso_canonical"
REFERENCE_DIR = ROOT / "reference" / "layer1" / "iso_canonical"

DATAHUB_URL = "https://raw.githubusercontent.com/datasets/country-codes/master/data/country-codes.csv"

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

ALLOWED_REGIONS = {"Africa", "Americas", "Asia", "Europe", "Oceania"}


def sha256sum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_source(dest: Path) -> str:
    dest.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(DATAHUB_URL, timeout=120)
    response.raise_for_status()
    dest.write_bytes(response.content)
    return sha256sum(dest)


def load_source(path: Path) -> pl.DataFrame:
    return pl.read_csv(path, infer_schema_length=0)


def build_dataset(df: pl.DataFrame) -> pl.DataFrame:
    required = {
        "ISO3166-1-Alpha-2",
        "ISO3166-1-Alpha-3",
        "ISO3166-1-numeric",
        "official_name_en",
        "UNTERM English Short",
        "CLDR display name",
        "Region Name",
        "Sub-region Name",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Source CSV missing columns: {sorted(missing)}")

    # Compose the name column with fallbacks
    name = (
        pl.coalesce(
            [
                pl.col("official_name_en"),
                pl.col("UNTERM English Short"),
                pl.col("CLDR display name"),
            ]
        )
        .str.strip_chars()
        .alias("name")
    )

    result = df.select(
        pl.col("ISO3166-1-Alpha-2").str.strip_chars().str.to_uppercase().alias("country_iso"),
        pl.col("ISO3166-1-Alpha-3").str.strip_chars().str.to_uppercase().alias("alpha3"),
        pl.col("ISO3166-1-numeric").str.strip_chars().alias("numeric_code"),
        name,
        pl.col("Region Name").str.strip_chars().alias("region"),
        pl.col("Sub-region Name").str.strip_chars().alias("subregion"),
    )

    # Basic cleaning
    result = result.with_columns(
        pl.when(pl.col("subregion") == "").then(None).otherwise(pl.col("subregion")).alias("subregion"),
        pl.lit(None, dtype=pl.Null).alias("start_date"),
        pl.lit(None, dtype=pl.Null).alias("end_date"),
    )

    # Validations
    if result.select(pl.col("country_iso").n_unique()).item() != result.height:
        raise ValueError("Duplicate country_iso detected")
    if result.filter(~pl.col("country_iso").str.contains(r"^[A-Z]{2}$")).height > 0:
        raise ValueError("country_iso contains invalid values")
    if result.filter(~pl.col("alpha3").str.contains(r"^[A-Z]{3}$")).height > 0:
        raise ValueError("alpha3 contains invalid values")

    result = result.with_columns(pl.col("numeric_code").cast(pl.Int16))
    if result.filter(pl.col("numeric_code").is_null()).height > 0:
        raise ValueError("numeric_code contains nulls after cast")

    bad_regions = result.filter(~pl.col("region").is_in(list(ALLOWED_REGIONS)))
    if bad_regions.height > 0:
        raise ValueError(f"Unexpected regions: {bad_regions['region'].unique().to_list()}")

    return result.select(OUTPUT_COLUMNS)


def build_manifest(
    *,
    version: str,
    source_sha: str,
    csv_path: Path,
    parquet_path: Path,
    qa_path: Path,
    row_count: int,
) -> dict:
    return {
        "dataset_id": "iso3166_canonical_2024",
        "version": version,
        "source_url": DATAHUB_URL,
        "source_sha256": source_sha,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "generator_script": "scripts/build_iso_canonical.py",
        "generator_git_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT)
        .decode("utf-8")
        .strip(),
        "output_csv": str(csv_path.relative_to(ROOT)),
        "output_csv_sha256": sha256sum(csv_path),
        "output_parquet": str(parquet_path.relative_to(ROOT)),
        "output_parquet_sha256": sha256sum(parquet_path),
        "qa_path": str(qa_path.relative_to(ROOT)),
        "qa_sha256": sha256sum(qa_path),
        "row_count": row_count,
        "column_order": OUTPUT_COLUMNS,
        "allowed_regions": sorted(ALLOWED_REGIONS),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default="2025-10-08", help="Dataset version tag")
    args = parser.parse_args()

    raw_dir = ARTEFACT_DIR / args.version / "raw"
    output_dir = REFERENCE_DIR / f"v{args.version}"
    raw_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_csv = raw_dir / "country-codes.csv"
    source_sha = download_source(raw_csv)
    df = load_source(raw_csv)
    curated = build_dataset(df)

    csv_path = output_dir / "iso_canonical.csv"
    parquet_path = output_dir / "iso_canonical.parquet"
    qa_path = output_dir / "iso_canonical.qa.json"
    curated.write_csv(csv_path)
    curated.write_parquet(parquet_path, compression="zstd", statistics=True)

    regions = curated.select(pl.col("region")).unique().sort("region")["region"].to_list()
    qa = {
        "rows": curated.height,
        "regions": regions,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    qa_path.write_text(json.dumps(qa, indent=2), encoding="utf-8")

    manifest = build_manifest(
        version=args.version,
        source_sha=source_sha,
        csv_path=csv_path,
        parquet_path=parquet_path,
        qa_path=qa_path,
        row_count=curated.height,
    )
    (output_dir / "iso_canonical.manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    sha_lines = [
        f"{source_sha}  {raw_csv.relative_to(ROOT)}",
        f"{manifest['output_csv_sha256']}  {csv_path.relative_to(ROOT)}",
        f"{manifest['output_parquet_sha256']}  {parquet_path.relative_to(ROOT)}",
        f"{manifest['qa_sha256']}  {qa_path.relative_to(ROOT)}",
    ]
    (output_dir / "SHA256SUMS").write_text("\n".join(sha_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
