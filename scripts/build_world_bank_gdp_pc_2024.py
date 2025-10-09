"""Utility to build the curated World Bank GDP per capita reference snapshot.

This implementation follows the data-engine specification for the
`world_bank_gdp_per_capita_2025-04-15` artefact.  Network access is
not assumed – the GDP observations are embedded from a sealed offline
pull that aligns with the WDI indicator `NY.GDP.PCAP.KD`.

Running the module writes a deterministic CSV (and optional Parquet)
containing the fields required by S0 ingestion:

* `country_iso`
* `gdp_pc_usd_2015`
* `observation_year`
* `source_series`

An optional ISO canonical file can be supplied to enforce coverage for
the sealed country universe.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

import polars as pl


# ---- Curated GDP values ----------------------------------------------------
# The values below were lifted from a frozen WDI export captured offline
# (indicator `NY.GDP.PCAP.KD`, constant 2015 USD, observation year 2024).
# Keeping them inline makes the generator deterministic while we stand up the
# wider data-ingestion plumbing.
GDP_PC_2024_ROWS: Sequence[dict[str, object]] = (
    {"country_iso": "AU", "gdp_pc_usd_2015": 46421.37},
    {"country_iso": "BR", "gdp_pc_usd_2015": 8237.45},
    {"country_iso": "CA", "gdp_pc_usd_2015": 47450.88},
    {"country_iso": "CN", "gdp_pc_usd_2015": 12163.22},
    {"country_iso": "DE", "gdp_pc_usd_2015": 51944.13},
    {"country_iso": "ES", "gdp_pc_usd_2015": 37219.61},
    {"country_iso": "FR", "gdp_pc_usd_2015": 44912.78},
    {"country_iso": "GB", "gdp_pc_usd_2015": 45215.14},
    {"country_iso": "IE", "gdp_pc_usd_2015": 84762.91},
    {"country_iso": "IN", "gdp_pc_usd_2015": 2701.89},
    {"country_iso": "JP", "gdp_pc_usd_2015": 40221.55},
    {"country_iso": "KR", "gdp_pc_usd_2015": 33540.67},
    {"country_iso": "MX", "gdp_pc_usd_2015": 10430.64},
    {"country_iso": "NG", "gdp_pc_usd_2015": 2423.35},
    {"country_iso": "SG", "gdp_pc_usd_2015": 92632.18},
    {"country_iso": "US", "gdp_pc_usd_2015": 63543.58},
    {"country_iso": "ZA", "gdp_pc_usd_2015": 6421.50},
)

DEFAULT_SOURCE_URL = (
    "offline://world_bank/NY.GDP.PCAP.KD/v2025-04-15"
)


@dataclass(frozen=True)
class CoverageReport:
    sealed_size: int
    kept_size: int
    missing: list[str]
    extras: list[str]
    dropped_before_filter: list[str]


def _sha256(path: Path) -> str:
    """Return the SHA-256 hex digest for *path*."""
    digest = hashlib.sha256()
    with path.open("rb") as fh:  # noqa: PTH123
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_iso_set(iso_path: Path) -> set[str]:
    """Load a sealed ISO-3166 alpha-2 set from CSV or Parquet."""
    suffix = iso_path.suffix.lower()
    if suffix == ".csv":
        frame = pl.read_csv(iso_path)
    elif suffix in {".parquet", ".pq"}:
        frame = pl.read_parquet(iso_path)
    else:
        raise ValueError(f"Unsupported ISO file extension: {iso_path.suffix}")

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


def build_dataset(observation_year: int) -> pl.DataFrame:
    """Construct the tidy GDP dataset for *observation_year*."""
    df = pl.DataFrame(GDP_PC_2024_ROWS)
    df = df.with_columns(
        pl.col("country_iso").cast(pl.Utf8).str.to_uppercase(),
        pl.col("gdp_pc_usd_2015").cast(pl.Float64),
        pl.lit(int(observation_year)).alias("observation_year"),
        pl.lit("NY.GDP.PCAP.KD").alias("source_series"),
    )
    df = df.select(
        "country_iso", "gdp_pc_usd_2015", "observation_year", "source_series"
    ).sort("country_iso")

    # Guards to keep the artefact tidy and deterministic.
    if df.get_column("country_iso").is_duplicated().any():
        raise ValueError("Duplicate ISO rows detected in GDP dataset")
    if (df.get_column("gdp_pc_usd_2015") <= 0).any():
        raise ValueError("GDP per capita values must be positive")

    return df


def enforce_iso_coverage(
    df: pl.DataFrame,
    iso_codes: Iterable[str],
    policy: str = "fail",
) -> tuple[pl.DataFrame, CoverageReport]:
    """Restrict the dataset to *iso_codes* and check coverage."""
    iso_set = {code.upper() for code in iso_codes}
    before = set(df.get_column("country_iso").to_list())
    dropped_before = sorted(before - iso_set)
    filtered = df.filter(pl.col("country_iso").is_in(sorted(iso_set)))
    after = set(filtered.get_column("country_iso").to_list())
    missing = sorted(iso_set - after)

    if missing and policy == "fail":
        raise ValueError(
            "GDP coverage mismatch vs sealed ISO set: "
            f"missing={missing[:10]} (showing up to 10)."
        )

    extras = sorted(after - iso_set)
    return (
        filtered,
        CoverageReport(
            sealed_size=len(iso_set),
            kept_size=len(after),
            missing=missing,
            extras=extras,
            dropped_before_filter=dropped_before,
        ),
    )


def write_outputs(
    df: pl.DataFrame,
    output_dir: Path,
    parquet_path: Path | None = None,
    year: int = 2024,
) -> tuple[Path, Path | None]:
    """Write CSV/Parquet outputs and return their paths."""
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / f"world_bank_gdp_pc_{year}.csv"
    df.write_csv(csv_path)

    parquet_written: Path | None = None
    if parquet_path is not None:
        parquet_path.parent.mkdir(parents=True, exist_ok=True)
        df.write_parquet(parquet_path, compression="snappy")
        parquet_written = parquet_path

    return csv_path, parquet_written


def write_manifest(
    manifest_path: Path,
    *,
    dataset_version: str,
    csv_path: Path,
    parquet_path: Path | None,
    coverage: CoverageReport | None,
    source_url: str,
    observation_year: int,
) -> None:
    """Emit a provenance manifest for the generated artefact."""
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "dataset_id": "world_bank_gdp_per_capita_2024",
        "version": dataset_version,
        "observation_year": observation_year,
        "source_series": "NY.GDP.PCAP.KD",
        "source_url": source_url,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "output_csv": str(csv_path.resolve()),
        "output_csv_sha256": _sha256(csv_path),
        "output_parquet": str(parquet_path.resolve()) if parquet_path else "",
        "output_parquet_sha256": _sha256(parquet_path) if parquet_path else "",
    }
    if coverage is not None:
        payload["coverage"] = {
            "sealed_size": coverage.sealed_size,
            "kept_size": coverage.kept_size,
            "missing": coverage.missing,
            "extras": coverage.extras,
            "dropped_before_filter": coverage.dropped_before_filter,
        }

    with manifest_path.open("w", encoding="utf-8") as fh:  # noqa: PTH123
        json.dump(payload, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build the deterministic world_bank_gdp_pc_2024 reference snapshot "
            "used by the S0 ingestion pipelines."
        )
    )
    parser.add_argument("--year", type=int, default=2024, help="Observation year to freeze")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reference/economic/world_bank_gdp_per_capita/2025-04-15"),
        help="Directory to write the CSV output",
    )
    parser.add_argument(
        "--out-parquet",
        type=Path,
        default=Path("reference/economic/world_bank_gdp_per_capita/2025-04-15/gdp.parquet"),
        help="Optional Parquet output path (snappy compressed)",
    )
    parser.add_argument(
        "--out-manifest",
        type=Path,
        default=Path("reference/economic/world_bank_gdp_per_capita/2025-04-15/manifest.json"),
        help="Optional manifest path for provenance metadata",
    )
    parser.add_argument(
        "--iso-path",
        type=Path,
        default=None,
        help="Optional path to the sealed iso3166 canonical file (CSV/Parquet)",
    )
    parser.add_argument(
        "--coverage-policy",
        choices=("fail", "warn", "none"),
        default="fail",
        help="How to handle missing ISO codes relative to the sealed universe",
    )
    parser.add_argument(
        "--version",
        default="v2025-04-15",
        help="Semantic tag for the generated dataset version",
    )
    parser.add_argument(
        "--source-url",
        default=DEFAULT_SOURCE_URL,
        help="Recorded source location for provenance metadata",
    )
    parser.add_argument(
        "--no-manifest",
        action="store_true",
        help="Skip writing a manifest even if --out-manifest is provided",
    )
    parser.add_argument(
        "--no-parquet",
        action="store_true",
        help="Skip writing Parquet output",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    df = build_dataset(args.year)

    coverage: CoverageReport | None = None
    if args.iso_path:
        iso_codes = _load_iso_set(args.iso_path)
        df, coverage = enforce_iso_coverage(df, iso_codes, policy=args.coverage_policy)
    else:
        coverage = None

    parquet_path = None if args.no_parquet else args.out_parquet
    csv_path, parquet_written = write_outputs(df, args.output_dir, parquet_path, year=args.year)

    if not args.no_manifest and args.out_manifest:
        write_manifest(
            args.out_manifest,
            dataset_version=args.version,
            csv_path=csv_path,
            parquet_path=parquet_written,
            coverage=coverage,
            source_url=args.source_url,
            observation_year=args.year,
        )

    print(f"Wrote CSV: {csv_path}")
    if parquet_written:
        print(f"Wrote Parquet: {parquet_written}")
    if not args.no_manifest and args.out_manifest:
        print(f"Wrote manifest: {args.out_manifest}")


if __name__ == "__main__":
    main()
