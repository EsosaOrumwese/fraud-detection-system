"""Mass calculators for S2 tile weights."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Mapping, TYPE_CHECKING

import numpy as np
import polars as pl
import rasterio

from engine.layers.l1.seg_1B.s1_tile_index.l0.loaders import load_population_raster

from ...shared.dictionary import resolve_dataset_path
from ..exceptions import err
from ..l0.tile_index import TileIndexPartition

if TYPE_CHECKING:
    from ..l2.runner import PatCounters


def compute_tile_masses(
    *,
    tile_index: TileIndexPartition,
    basis: str,
    data_root: Path,
    dictionary: Mapping[str, object],
    pat: "PatCounters",
) -> pl.DataFrame:
    """Return a copy of ``tile_index`` with the governed ``mass`` column."""

    frame = tile_index.frame.clone()
    if frame.height == 0:
        return frame.with_columns(pl.lit(0.0).cast(pl.Float64).alias("mass"))

    if basis == "uniform":
        mass_frame = frame.with_columns(pl.lit(1.0).cast(pl.Float64).alias("mass"))
    elif basis == "area_m2":
        mass_frame = frame.with_columns(pl.col("pixel_area_m2").cast(pl.Float64).alias("mass"))
    elif basis == "population":
        population_values = _population_intensity(frame, data_root=data_root, dictionary=dictionary, pat=pat)
        mass_frame = frame.with_columns(pl.Series("mass", population_values, dtype=pl.Float64))
    else:
        raise ValueError(f"unsupported basis '{basis}'")

    _ensure_mass_domain(mass_frame.get_column("mass"))
    return mass_frame


def _population_intensity(
    frame: pl.DataFrame,
    *,
    data_root: Path,
    dictionary: Mapping[str, object],
    pat: "PatCounters",
) -> np.ndarray:
    """Lookup population intensity per tile via ``population_raster_2025``."""

    raster_path = resolve_dataset_path(
        "population_raster_2025",
        base_path=data_root,
        template_args={},
        dictionary=dictionary,
    )
    if raster_path.exists():
        pat.raster_bytes_reference = max(
            pat.raster_bytes_reference, int(raster_path.stat().st_size)
        )
    raster_info = load_population_raster(raster_path)

    with rasterio.open(raster_info.path) as dataset:
        band = dataset.read(1, out_dtype="float64")
        pat.bytes_read_raster_total += int(band.nbytes)
        nodata = dataset.nodata

    rows = frame.get_column("raster_row").to_numpy()
    cols = frame.get_column("raster_col").to_numpy()
    intensities = band[rows, cols]

    if nodata is not None:
        mask = np.isclose(intensities, nodata, equal_nan=True)
        intensities[mask] = 0.0

    intensities = np.nan_to_num(intensities, nan=0.0, posinf=np.inf, neginf=np.inf)
    if np.isinf(intensities).any():
        raise err("E105_NORMALIZATION", "population raster produced infinite intensities")

    if (intensities < 0).any():
        raise err("E105_NORMALIZATION", "population raster produced negative intensities")

    return intensities.astype("float64")


def _ensure_mass_domain(series: pl.Series) -> None:
    """Ensure masses are finite and non-negative."""

    if series.is_null().any():
        raise err("E105_NORMALIZATION", "mass column contains null values")

    values = series.to_numpy()
    if not np.isfinite(values).all():
        raise err("E105_NORMALIZATION", "mass column contains non-finite values")
    if (values < 0).any():
        raise err("E105_NORMALIZATION", "mass column contains negative values")


__all__ = ["compute_tile_masses"]
