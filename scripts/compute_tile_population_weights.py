"""Compute per-tile population weights from the lightweight global population raster.

Usage:
    python scripts/compute_tile_population_weights.py \
        --data-root . \
        --parameter-hash <hash from 1B tile_index> \
        --source-vintage 2025

This reads:
  - the 1B tile_index partition (resolved via the 1B dataset dictionary)
  - the global population raster registered as `global_population_raster` in the 3B dictionary

And writes:
  reference/spatial/tile_weights/from_hrsl/{source_vintage}/tile_population_weights.csv

Notes:
  - This is a build-time helper; it streams tiles country-by-country to avoid loading the full raster.
  - NODATA values in the raster are treated as zero population.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import polars as pl
import rasterio
from rasterio.windows import Window

from engine.layers.l1.seg_3B.shared.dictionary import load_dictionary as load_dict_3b, render_dataset_path
from engine.layers.l1.seg_1B.s2_tile_weights.l0 import iter_tile_index_countries, load_tile_index_partition
from engine.layers.l1.seg_1B.shared.dictionary import load_dictionary as load_dict_1b


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute per-tile population weights from global raster")
    parser.add_argument("--data-root", type=Path, default=Path("."), help="Repository root (default: cwd)")
    parser.add_argument(
        "--parameter-hash",
        required=True,
        help="parameter_hash for the 1B tile_index partition to use",
    )
    parser.add_argument(
        "--source-vintage",
        default="2025",
        help="Source vintage tag for output path (matches dictionary placeholder)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional override for output CSV; defaults to dictionary-rendered path",
    )
    parser.add_argument(
        "--dictionary-3b",
        type=Path,
        default=None,
        help="Optional path to 3B dataset dictionary (layer1.3B.yaml)",
    )
    parser.add_argument(
        "--dictionary-1b",
        type=Path,
        default=None,
        help="Optional path to 1B dataset dictionary (layer1.1B.yaml)",
    )
    return parser.parse_args()


def _resolve_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    data_root = args.data_root.resolve()
    dict3b = load_dict_3b(args.dictionary_3b)
    raster_rel = render_dataset_path(
        dataset_id="global_population_raster",
        template_args={},
        dictionary=dict3b,
    )
    raster_path = data_root / Path(raster_rel)
    if not raster_path.exists():
        raise FileNotFoundError(f"Global population raster not found at {raster_path}")

    if args.output is not None:
        out_path = args.output.resolve()
    else:
        out_rel = render_dataset_path(
            dataset_id="tile_population_weights",
            template_args={"source_vintage": args.source_vintage},
            dictionary=dict3b,
        )
        out_path = data_root / Path(out_rel)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    return raster_path, out_path


def _load_tile_index(data_root: Path, parameter_hash: str, dict1b_path: Path | None):
    dict1b = load_dict_1b(dict1b_path)
    partition = load_tile_index_partition(
        base_path=data_root,
        parameter_hash=parameter_hash,
        dictionary=dict1b,
        eager=False,
    )
    return partition


def _compute_weights(partition, raster_path: Path) -> pl.DataFrame:
    with rasterio.open(raster_path) as dataset:
        nodata = dataset.nodata
        results: list[pl.DataFrame] = []
        for batch in iter_tile_index_countries(
            partition, columns=("country_iso", "tile_id", "raster_row", "raster_col")
        ):
            if batch.raster_row is None or batch.raster_col is None:
                raise RuntimeError("tile_index batch missing raster indices")
            rows = batch.raster_row
            cols = batch.raster_col
            min_row = int(rows.min())
            max_row = int(rows.max())
            min_col = int(cols.min())
            max_col = int(cols.max())
            window = Window(
                col_off=min_col,
                row_off=min_row,
                width=max_col - min_col + 1,
                height=max_row - min_row + 1,
            )
            arr = dataset.read(1, window=window, boundless=False)
            rel_rows = rows - min_row
            rel_cols = cols - min_col
            values = arr[rel_rows, rel_cols]
            if nodata is not None:
                values = np.where(values == nodata, 0.0, values)
            df = pl.DataFrame(
                {
                    "country_iso3": pl.repeat(batch.iso, len(batch.tile_id)),
                    "tile_id": batch.tile_id.astype(np.uint64, copy=False),
                    "population": values.astype(np.float64, copy=False),
                }
            )
            results.append(df)
        if not results:
            return pl.DataFrame(schema={"country_iso3": pl.Utf8, "tile_id": pl.UInt64, "population": pl.Float64})
        full = pl.concat(results, how="vertical")
        return full.sort(["country_iso3", "tile_id"])


def main() -> int:
    args = _parse_args()
    raster_path, out_path = _resolve_paths(args)
    partition = _load_tile_index(args.data_root, args.parameter_hash, args.dictionary_1b)
    weights = _compute_weights(partition, raster_path)
    weights.write_csv(out_path)
    print(f"Wrote tile population weights -> {out_path} (rows={weights.height})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
