"""Create GDP bucket map (Jenks K=5) from the GDP per capita reference table."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import polars as pl


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_GDP = ROOT / "reference" / "economic" / "world_bank_gdp_per_capita"
REFERENCE_BUCKETS = ROOT / "reference" / "economic" / "gdp_bucket_map"
REFERENCE_BUCKETS.mkdir(parents=True, exist_ok=True)


def jenks_breaks(values: List[float], num_classes: int) -> List[float]:
    """Compute Jenks natural breaks using dynamic programming."""

    if num_classes <= 1:
        raise ValueError("num_classes must be >= 2")
    if len(values) < num_classes:
        raise ValueError("Not enough observations for requested classes")

    data = sorted(values)
    n = len(data)

    lower_class_limits = [[0] * (num_classes + 1) for _ in range(n + 1)]
    variance_combinations = [[0.0] * (num_classes + 1) for _ in range(n + 1)]

    for i in range(1, num_classes + 1):
        lower_class_limits[0][i] = 1
        variance_combinations[0][i] = 0.0
        for j in range(1, n + 1):
            variance_combinations[j][i] = float("inf")

    for l in range(1, n + 1):
        sum_val = 0.0
        sum_sq = 0.0
        w = 0.0
        for m in range(1, l + 1):
            val = data[l - m]
            sum_val += val
            sum_sq += val * val
            w += 1
            variance = sum_sq - (sum_val * sum_val) / w
            idx = l - m
            if idx != 0:
                for j in range(2, num_classes + 1):
                    if variance_combinations[l][j] >= (variance + variance_combinations[idx][j - 1]):
                        lower_class_limits[l][j] = idx + 1
                        variance_combinations[l][j] = variance + variance_combinations[idx][j - 1]
        lower_class_limits[l][1] = 1
        variance_combinations[l][1] = variance

    k = n
    breaks = [0.0] * (num_classes + 1)
    breaks[num_classes] = data[-1]
    breaks[0] = data[0]

    for j in range(num_classes, 1, -1):
        idx = int(lower_class_limits[k][j] - 2)
        if idx < 0:
            idx = 0
        breaks[j - 1] = data[idx]
        k = int(lower_class_limits[k][j] - 1)

    # Ensure breaks are strictly non-decreasing.
    for i in range(1, len(breaks)):
        if breaks[i] < breaks[i - 1]:
            breaks[i] = breaks[i - 1]

    return breaks


def sha256sum(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_bucket_map(version: str, source_version: str, num_classes: int) -> None:
    source_dir = REFERENCE_GDP / source_version
    if not source_dir.exists():
        raise FileNotFoundError(f"GDP source directory not found: {source_dir}")
    parquet_path = source_dir / "gdp.parquet"
    if not parquet_path.exists():
        raise FileNotFoundError(f"GDP parquet missing: {parquet_path}")

    df = pl.read_parquet(parquet_path)
    values = df["gdp_pc_usd_2015"].to_list()
    breaks = jenks_breaks(values, num_classes)

    # Assign each country to a bucket (1..num_classes).
    def assign_bucket(val: float) -> int:
        for idx in range(1, num_classes + 1):
            lower = breaks[idx - 1]
            upper = breaks[idx]
            if idx == num_classes:
                if val >= lower:
                    return idx
            if lower <= val < upper:
                return idx
        return num_classes

    bucket_df = df.with_columns(
        pl.col("gdp_pc_usd_2015").map_elements(assign_bucket, return_dtype=pl.Int32).alias("bucket_id")
    )

    out_dir = REFERENCE_BUCKETS / version
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = out_dir / "gdp_bucket_map_2024.csv"
    parquet_out = out_dir / "gdp_bucket_map.parquet"
    bucket_df.select("country_iso", "bucket_id", "gdp_pc_usd_2015").write_csv(csv_path)
    bucket_df.select("country_iso", "bucket_id", "gdp_pc_usd_2015").write_parquet(parquet_out, compression="zstd", statistics=True)

    manifest = {
        "dataset_id": "gdp_bucket_map_2024",
        "version": version,
        "source_version": source_version,
        "classification": "jenks",
        "num_classes": num_classes,
        "breaks": breaks,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_parquet": str(parquet_path.relative_to(ROOT)),
        "input_parquet_sha256": sha256sum(parquet_path),
        "output_csv": str(csv_path.relative_to(ROOT)),
        "output_csv_sha256": sha256sum(csv_path),
        "output_parquet": str(parquet_out.relative_to(ROOT)),
        "output_parquet_sha256": sha256sum(parquet_out),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-version", default="2025-10-07")
    parser.add_argument("--version", default="2025-10-07")
    parser.add_argument("--classes", type=int, default=5)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_bucket_map(version=args.version, source_version=args.source_version, num_classes=args.classes)


if __name__ == "__main__":
    main()
