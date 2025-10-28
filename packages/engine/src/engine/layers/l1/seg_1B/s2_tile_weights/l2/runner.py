"""L2 orchestration scaffolding for Segment 1B S2 (Tile Weights)."""

from __future__ import annotations
import json
import logging
import shutil
import time
import uuid

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, MutableMapping, Sequence, TYPE_CHECKING

import numpy as np
import polars as pl
import rasterio
from rasterio.windows import Window

from engine.layers.l1.seg_1B.s1_tile_index.l0.loaders import (
    IsoCountryTable,
    load_iso_countries,
    load_population_raster,
)
from engine.layers.l1.seg_1B.s1_tile_index.l2.runner import compute_partition_digest

from ...shared.dictionary import get_dataset_entry, load_dictionary, resolve_dataset_path
from ..exceptions import S2Error, err
from ..l0.tile_index import (
    CountryTileBatch,
    TileIndexPartition,
    iter_tile_index_countries,
    load_tile_index_partition,
)
from ..l3 import build_run_report

if TYPE_CHECKING:
    from rasterio.io import DatasetReader


ALLOWED_BASES = frozenset({"uniform", "area_m2", "population"})
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunnerConfig:
    """Configuration inputs required to orchestrate S2."""

    data_root: Path
    parameter_hash: str
    basis: str = "uniform"
    dp: int = 4
    dictionary: Mapping[str, object] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "data_root", self.data_root.expanduser().resolve())
        object.__setattr__(self, "parameter_hash", str(self.parameter_hash))


@dataclass(frozen=True)
class GovernedParameters:
    """Governed knobs recorded in the S2 run report and evidence bundle."""

    basis: str
    dp: int

    @staticmethod
    def from_config(config: RunnerConfig) -> GovernedParameters:
        basis_normalised = config.basis.lower().strip()
        if basis_normalised not in ALLOWED_BASES:
            raise ValueError(
                f"basis '{config.basis}' not in allowed set {sorted(ALLOWED_BASES)}"
            )
        if config.dp < 0:
            raise ValueError("dp must be a non-negative integer")
        return GovernedParameters(basis=basis_normalised, dp=int(config.dp))


@dataclass
class PatCounters:
    """Container for §11 PAT metrics (initialised for future accumulation)."""

    countries_processed: int = 0
    rows_emitted: int = 0
    bytes_read_tile_index_total: int = 0
    bytes_read_raster_total: int = 0
    bytes_read_vectors_total: int = 0
    wall_clock_seconds_total: float = 0.0
    cpu_seconds_total: float = 0.0
    max_worker_rss_bytes: int = 0
    open_files_peak: int = 0
    workers_used: int | None = None
    chunk_size: int | None = None
    io_baseline_ti_bps: float | None = None
    io_baseline_raster_bps: float | None = None
    io_baseline_vectors_bps: float | None = None
    tile_index_bytes_reference: int = 0
    raster_bytes_reference: int = 0
    vector_bytes_reference: int = 0

    def to_dict(self) -> MutableMapping[str, int | float | None]:
        return {
            "countries_processed": self.countries_processed,
            "rows_emitted": self.rows_emitted,
            "bytes_read_tile_index_total": self.bytes_read_tile_index_total,
            "bytes_read_raster_total": self.bytes_read_raster_total,
            "bytes_read_vectors_total": self.bytes_read_vectors_total,
            "wall_clock_seconds_total": self.wall_clock_seconds_total,
            "cpu_seconds_total": self.cpu_seconds_total,
            "max_worker_rss_bytes": self.max_worker_rss_bytes,
            "open_files_peak": self.open_files_peak,
            "workers_used": self.workers_used,
            "chunk_size": self.chunk_size,
            "io_baseline_ti_bps": self.io_baseline_ti_bps,
            "io_baseline_raster_bps": self.io_baseline_raster_bps,
            "io_baseline_vectors_bps": self.io_baseline_vectors_bps,
            "tile_index_bytes_reference": self.tile_index_bytes_reference,
            "raster_bytes_reference": self.raster_bytes_reference,
            "vector_bytes_reference": self.vector_bytes_reference,
        }

    def validate_envelope(self) -> None:
        """Validate counters against §11 performance envelopes."""

        def _require(condition: bool, message: str) -> None:
            if not condition:
                raise err("E109_PERF_BUDGET", message)

        if self.bytes_read_tile_index_total > 0:
            _require(
                self.tile_index_bytes_reference > 0,
                "tile_index reference size missing for PAT evaluation",
            )
            ratio = self.bytes_read_tile_index_total / self.tile_index_bytes_reference
            _require(ratio <= 1.25, f"tile_index I/O amplification {ratio:.2f} exceeds 1.25")
            _require(
                self.io_baseline_ti_bps and self.io_baseline_ti_bps > 0,
                "io_baseline_ti_bps must be recorded when tile_index bytes are read",
            )
        if self.bytes_read_raster_total > 0:
            _require(
                self.raster_bytes_reference > 0,
                "population raster reference size missing for PAT evaluation",
            )
            ratio = self.bytes_read_raster_total / self.raster_bytes_reference
            _require(ratio <= 1.25, f"raster I/O amplification {ratio:.2f} exceeds 1.25")
            _require(
                self.io_baseline_raster_bps and self.io_baseline_raster_bps > 0,
                "io_baseline_raster_bps must be recorded when raster bytes are read",
            )
        if self.bytes_read_vectors_total > 0:
            _require(
                self.vector_bytes_reference > 0,
                "vector reference size missing for PAT evaluation",
            )
            ratio = self.bytes_read_vectors_total / self.vector_bytes_reference
            _require(ratio <= 1.25, f"vector I/O amplification {ratio:.2f} exceeds 1.25")
            _require(
                self.io_baseline_vectors_bps and self.io_baseline_vectors_bps > 0,
                "io_baseline_vectors_bps must be recorded when vector bytes are read",
            )

        expected_wall_clock = 0.0
        if self.bytes_read_tile_index_total > 0 and self.io_baseline_ti_bps:
            expected_wall_clock += self.bytes_read_tile_index_total / self.io_baseline_ti_bps
        if self.bytes_read_raster_total > 0 and self.io_baseline_raster_bps:
            expected_wall_clock += self.bytes_read_raster_total / self.io_baseline_raster_bps
        if self.bytes_read_vectors_total > 0 and self.io_baseline_vectors_bps:
            expected_wall_clock += self.bytes_read_vectors_total / self.io_baseline_vectors_bps

        if expected_wall_clock > 0:
            max_allowed = 1.75 * expected_wall_clock + 300
            _require(
                self.wall_clock_seconds_total <= max_allowed,
                "wall clock time exceeds PAT bound",
            )

        _require(
            self.max_worker_rss_bytes <= 1_073_741_824,
            "max worker RSS exceeds 1.0 GiB",
        )
        _require(
            self.open_files_peak <= 256,
            "open files peak exceeds 256",
        )


@dataclass(frozen=True)
class PreparedInputs:
    """Result of phases 0–2: validated ingress and governed parameters."""

    data_root: Path
    governed: GovernedParameters
    dictionary: Mapping[str, object]
    tile_index: TileIndexPartition
    iso_table: IsoCountryTable
    iso_size_bytes: int
    pat: PatCounters = field(default_factory=PatCounters)


@dataclass(frozen=True)
class MassComputation:
    """Streaming context for governed mass computation."""

    columns: tuple[str, ...]
    partition: TileIndexPartition
    raster_reader: "DatasetReader | None"
    raster_dtype: np.dtype | None
    raster_nodata: float | int | None
    rows: int

    def close(self) -> None:
        """Release any transient resources held by the mass computation context."""

        reader = getattr(self, "raster_reader", None)
        if reader is not None and not reader.closed:
            reader.close()


@dataclass(frozen=True)
class QuantisationResult:
    """Streaming quantisation result."""

    temp_dir: Path
    rows_emitted: int
    summaries: list[dict[str, object]]
    dp: int


@dataclass(frozen=True)
class S2RunResult:
    """Materialisation artefacts emitted by S2."""

    tile_weights_path: Path
    report_path: Path
    country_summary_path: Path
    determinism_receipt: Mapping[str, str]


class S2TileWeightsRunner:
    """High-level helper that prepares deterministic inputs for S2."""

    def prepare(self, config: RunnerConfig) -> PreparedInputs:
        dictionary = config.dictionary or load_dictionary()
        governed = GovernedParameters.from_config(config)

        # Ensure writer dictionary entry exists before proceeding.
        get_dataset_entry("tile_weights", dictionary=dictionary)

        iso_path = resolve_dataset_path(
            "iso3166_canonical_2024",
            base_path=config.data_root,
            template_args={},
            dictionary=dictionary,
        )
        logger.info("S2: loading ISO canonical table from %s", iso_path)
        try:
            iso_table = load_iso_countries(iso_path)
        except Exception as exc:  # noqa: BLE001 - surface as canonical failure
            raise err(
                "E101_TILE_INDEX_MISSING",
                f"failed to load ISO canonical table from '{iso_path}': {exc}",
            ) from exc
        logger.info("S2: ISO canonical table loaded (rows=%d)", iso_table.table.height)
        pat = PatCounters()
        iso_size = iso_path.stat().st_size if iso_path.exists() else 0
        pat.bytes_read_vectors_total += int(iso_size)
        pat.vector_bytes_reference = int(iso_size)

        logger.info(
            "S2: loading tile_index partition for parameter_hash=%s", config.parameter_hash
        )
        tile_index = load_tile_index_partition(
            base_path=config.data_root,
            parameter_hash=config.parameter_hash,
            dictionary=dictionary,
            eager=False,
        )
        pat.bytes_read_tile_index_total += tile_index.byte_size
        pat.tile_index_bytes_reference = tile_index.byte_size
        logger.info(
            "S2: tile_index loaded (tiles=%d, bytes=%d)",
            tile_index.rows,
            tile_index.byte_size,
        )

        return PreparedInputs(
            data_root=config.data_root,
            governed=governed,
            dictionary=dictionary,
            tile_index=tile_index,
            iso_table=iso_table,
            iso_size_bytes=int(iso_size),
            pat=pat,
        )

    def compute_masses(self, prepared: PreparedInputs) -> MassComputation:
        logger.info(
            "S2: computing tile masses (basis=%s, rows=%d)",
            prepared.governed.basis,
            prepared.tile_index.rows,
        )
        columns: list[str] = ["country_iso", "tile_id"]
        basis = prepared.governed.basis
        if basis in {"area_m2", "population"}:
            columns.append("pixel_area_m2")
        if basis == "population":
            columns.extend(["raster_row", "raster_col"])

        raster_reader: DatasetReader | None = None
        raster_dtype: np.dtype | None = None
        raster_nodata: float | int | None = None
        if basis == "population":
            raster_path = resolve_dataset_path(
                "population_raster_2025",
                base_path=prepared.data_root,
                template_args={},
                dictionary=prepared.dictionary,
            )
            raster_info = load_population_raster(raster_path)
            raster_reader = rasterio.open(raster_info.path)
            raster_nodata = raster_reader.nodata
            raster_dtype = np.dtype(raster_reader.dtypes[0])
            raster_size_bytes = int(raster_reader.width) * int(raster_reader.height) * int(raster_dtype.itemsize)
            prepared.pat.raster_bytes_reference = max(
                prepared.pat.raster_bytes_reference,
                raster_size_bytes,
                int(raster_path.stat().st_size) if raster_path.exists() else 0,
            )

        mass_context = MassComputation(
            columns=tuple(dict.fromkeys(columns)),
            partition=prepared.tile_index,
            raster_reader=raster_reader,
            raster_dtype=raster_dtype,
            raster_nodata=raster_nodata,
            rows=prepared.tile_index.rows,
        )
        logger.info("S2: mass computation context ready (rows=%d)", mass_context.rows)
        return mass_context

    def measure_baselines(self, prepared: PreparedInputs, *, measure_raster: bool = False) -> None:
        """Measure sustained read throughput for PAT baselines."""

        def _stream_read(path: Path) -> tuple[int, float]:
            chunk_size = 4 * 1024 * 1024
            total = 0
            start = time.perf_counter()
            with path.open("rb") as handle:
                while True:
                    data = handle.read(chunk_size)
                    if not data:
                        break
                    total += len(data)
            elapsed = time.perf_counter() - start
            if elapsed <= 0.0:
                elapsed = 1e-6
            return total, elapsed

        files = sorted(prepared.tile_index.path.glob("*.parquet"))
        if files:
            total = 0
            elapsed = 0.0
            for file_path in files:
                size, duration = _stream_read(file_path)
                total += size
                elapsed += duration
            if elapsed > 0.0:
                prepared.pat.io_baseline_ti_bps = total / elapsed

        iso_path = resolve_dataset_path(
            "iso3166_canonical_2024",
            base_path=prepared.data_root,
            template_args={},
            dictionary=prepared.dictionary,
        )
        if iso_path.exists():
            size, duration = _stream_read(iso_path)
            prepared.pat.vector_bytes_reference = max(prepared.pat.vector_bytes_reference, size)
            if duration > 0.0:
                prepared.pat.io_baseline_vectors_bps = size / duration

        if measure_raster:
            raster_path = resolve_dataset_path(
                "population_raster_2025",
                base_path=prepared.data_root,
                template_args={},
                dictionary=prepared.dictionary,
            )
            if raster_path.exists():
                size, duration = _stream_read(raster_path)
                prepared.pat.raster_bytes_reference = max(prepared.pat.raster_bytes_reference, size)
                if duration > 0.0:
                    prepared.pat.io_baseline_raster_bps = size / duration

        prepared.pat.cpu_seconds_total = max(prepared.pat.cpu_seconds_total, 0.0)
        prepared.pat.wall_clock_seconds_total = max(prepared.pat.wall_clock_seconds_total, 0.0)


    def quantise(self, prepared: PreparedInputs, masses: MassComputation) -> QuantisationResult:
        dp = prepared.governed.dp
        logger.info("S2: quantising tile weights (dp=%d)", dp)

        temp_dir = prepared.data_root / "data" / "layer1" / "1B" / "tile_weights" / f".tmp.s2_quantise.{uuid.uuid4().hex}"
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
        writer = _TileWeightsBatchWriter(temp_dir=temp_dir)

        summaries: list[dict[str, object]] = []
        rows_emitted = 0
        iso_seen: set[str] = set()

        try:
            for batch in iter_tile_index_countries(
                masses.partition,
                columns=masses.columns,
            ):
                iso = batch.iso
                iso_seen.add(iso)
                tile_ids = batch.tile_id.astype(np.uint64, copy=False)
                if tile_ids.size == 0:
                    continue

                if tile_ids.size > 1 and np.any(np.diff(tile_ids) <= 0):
                    raise err(
                        "E101_TILE_INDEX_MISSING",
                        f"tile_index for country {iso} is not strictly increasing by tile_id",
                    )

                masses_array = self._compute_country_masses(batch, prepared, masses)
                weights_fp, residue_allocations, fallback, mass_sum, weight_sum = self._quantise_country(
                    iso=iso,
                    tile_ids=tile_ids,
                    masses=masses_array,
                    dp=dp,
                )

                country_column = np.full(tile_ids.size, iso, dtype="U4")
                dp_column = np.full(tile_ids.size, dp, dtype=np.uint32)
                fallback_column = np.full(tile_ids.size, fallback, dtype=bool)

                writer.append_batch(
                    country_iso=country_column,
                    tile_id=tile_ids,
                    weight_fp=weights_fp,
                    dp=dp_column,
                    zero_mass_fallback=fallback_column,
                )

                rows_emitted += tile_ids.size
                summaries.append(
                    {
                        "country_iso": iso,
                        "tiles": int(tile_ids.size),
                        "mass_sum": float(mass_sum),
                        "prequant_sum_real": float(weight_sum),
                        "K": int(10**dp),
                        "postquant_sum_fp": int(weights_fp.sum()),
                        "residue_allocations": int(residue_allocations),
                        "zero_mass_fallback": bool(fallback),
                    }
                )
        except Exception:
            writer.abort()
            raise
        else:
            writer.close()
        finally:
            masses.close()

        prepared.pat.countries_processed = len(summaries)
        prepared.pat.rows_emitted = rows_emitted

        iso_codes = frozenset(prepared.iso_table.codes)
        if not iso_seen.issubset(iso_codes):
            unknown = sorted(iso_seen.difference(iso_codes))
            raise err(
                "E102_FK_MISMATCH",
                f"tile_index contains country_iso values not present in ISO surface: {unknown}",
            )

        logger.info(
            "S2: quantisation complete (rows=%d, countries=%d)",
            rows_emitted,
            len(summaries),
        )
        return QuantisationResult(
            temp_dir=temp_dir,
            rows_emitted=rows_emitted,
            summaries=summaries,
            dp=dp,
        )

    def materialise(self, prepared: PreparedInputs, quantised: QuantisationResult) -> S2RunResult:
        dictionary = prepared.dictionary
        partition_path = resolve_dataset_path(
            "tile_weights",
            base_path=prepared.data_root,
            template_args={"parameter_hash": prepared.tile_index.parameter_hash},
            dictionary=dictionary,
        )
        if partition_path.exists():
            raise err(
                "E108_WRITER_HYGIENE",
                f"tile_weights partition '{partition_path}' already exists",
            )

        try:
            quantised.temp_dir.replace(partition_path)
        except Exception as exc:  # noqa: BLE001 - enforce atomic publish discipline
            if quantised.temp_dir.exists():
                shutil.rmtree(quantised.temp_dir, ignore_errors=True)
            raise err(
                "E108_WRITER_HYGIENE",
                f"failed to publish tile_weights partition: {exc}",
            ) from exc

        determinism_receipt = {
            "partition_path": str(partition_path),
            "sha256_hex": compute_partition_digest(partition_path),
        }

        prepared.pat.validate_envelope()

        control_dir = (
            prepared.data_root
            / "control"
            / "s2_tile_weights"
            / f"parameter_hash={prepared.tile_index.parameter_hash}"
        )
        control_dir.mkdir(parents=True, exist_ok=True)

        summaries_path = control_dir / "normalisation_summaries.jsonl"
        with summaries_path.open("w", encoding="utf-8") as handle:
            for entry in quantised.summaries:
                handle.write(json.dumps(entry) + "\n")

        report_payload = build_run_report(
            prepared=prepared,
            quantised=quantised,
            determinism_receipt=determinism_receipt,
        )
        report_path = control_dir / "s2_run_report.json"
        report_path.write_text(json.dumps(report_payload, indent=2, sort_keys=True), encoding="utf-8")

        return S2RunResult(
            tile_weights_path=partition_path,
            report_path=report_path,
            country_summary_path=summaries_path,
            determinism_receipt=determinism_receipt,
        )

    def _compute_country_masses(
        self,
        batch: CountryTileBatch,
        prepared: PreparedInputs,
        masses: MassComputation,
    ) -> np.ndarray:
        basis = prepared.governed.basis
        rows = batch.rows
        if basis == "uniform":
            return np.ones(rows, dtype=np.float64)
        if basis == "area_m2":
            if batch.pixel_area_m2 is None:
                raise err("E105_NORMALIZATION", f"pixel_area_m2 missing for country {batch.iso}")
            return batch.pixel_area_m2.astype(np.float64, copy=False)
        if basis == "population":
            if (
                masses.raster_reader is None
                or batch.raster_row is None
                or batch.raster_col is None
                or masses.raster_dtype is None
            ):
                raise err("E105_NORMALIZATION", "population basis requires raster metadata")
            rows_idx = batch.raster_row.astype(np.int64, copy=False)
            cols_idx = batch.raster_col.astype(np.int64, copy=False)
            intensities = np.empty(rows_idx.size, dtype=np.float64)
            bytes_read = 0
            dtype_itemsize = int(masses.raster_dtype.itemsize)
            row_order = np.argsort(rows_idx, kind="mergesort")
            sorted_rows = rows_idx[row_order]
            sorted_cols = cols_idx[row_order]
            row_boundaries = np.flatnonzero(sorted_rows[1:] != sorted_rows[:-1]) + 1
            row_segments = np.concatenate(([0], row_boundaries, [sorted_rows.size]))
            for row_start, row_end in zip(row_segments[:-1], row_segments[1:]):
                row_value = int(sorted_rows[row_start])
                row_positions = row_order[row_start:row_end]
                row_cols_subset = sorted_cols[row_start:row_end]
                col_order = np.argsort(row_cols_subset, kind="mergesort")
                sorted_positions = row_positions[col_order]
                sorted_cols_for_row = row_cols_subset[col_order]
                col_boundaries = np.flatnonzero(np.diff(sorted_cols_for_row) != 1) + 1
                col_segments = np.concatenate(([0], col_boundaries, [sorted_cols_for_row.size]))
                for seg_start, seg_end in zip(col_segments[:-1], col_segments[1:]):
                    seg_positions = sorted_positions[seg_start:seg_end]
                    seg_cols = sorted_cols_for_row[seg_start:seg_end]
                    if seg_cols.size == 0:
                        continue
                    col_min = int(seg_cols[0])
                    col_max = int(seg_cols[-1])
                    width = int(col_max - col_min + 1)
                    window = Window(
                        row_off=row_value,
                        col_off=col_min,
                        height=1,
                        width=width,
                    )
                    raster_slice = masses.raster_reader.read(1, window=window, masked=False)
                    if raster_slice.ndim != 2:
                        raise err(
                            "E105_NORMALIZATION",
                            f"population raster returned unexpected shape for country {batch.iso}",
                        )
                    row_values = raster_slice[0].astype(np.float64, copy=False)
                    offsets = seg_cols - col_min
                    intensities[seg_positions] = row_values[offsets]
                    bytes_read += width * dtype_itemsize
            prepared.pat.bytes_read_raster_total += bytes_read
            nodata = masses.raster_nodata
            if nodata is not None:
                mask = np.isclose(intensities, nodata, equal_nan=True)
                if mask.any():
                    intensities = intensities.copy()
                    intensities[mask] = 0.0
            if not np.isfinite(intensities).all():
                raise err(
                    "E105_NORMALIZATION",
                    f"population raster produced non-finite intensities for country {batch.iso}",
                )
            return intensities
        raise ValueError(f"unsupported basis '{basis}'")

    def _quantise_country(
        self,
        *,
        iso: str,
        tile_ids: np.ndarray,
        masses: np.ndarray,
        dp: int,
    ) -> tuple[np.ndarray, int, bool, float, float]:
        K = 10**dp
        masses = masses.astype(np.float64, copy=False)
        mass_sum = float(np.sum(masses, dtype=np.float64))
        fallback = False
        if mass_sum <= 0.0 or not np.isfinite(mass_sum):
            fallback = True
            masses = np.ones_like(masses, dtype=np.float64)
            mass_sum = float(np.sum(masses, dtype=np.float64))
        weights = masses / mass_sum
        quotas = weights * K
        base = np.floor(quotas).astype(np.int64)
        residues = quotas - base
        base_sum = int(base.sum())
        shortfall = int(round(K - base_sum))
        if shortfall > 0:
            order = np.lexsort((tile_ids, -residues))
            base[order[:shortfall]] += 1
        elif shortfall < 0:
            order = np.lexsort((tile_ids, residues))
            base[order[: -shortfall]] -= 1
        if int(base.sum()) != K:
            raise err(
                "E105_NORMALIZATION",
                f"quantisation sum mismatch for country {iso}",
            )
        weights_fp = base.astype(np.uint64, copy=False)
        residue_allocations = max(shortfall, 0)
        return weights_fp, residue_allocations, fallback, mass_sum, float(weights.sum())


__all__ = [
    "PatCounters",
    "PreparedInputs",
    "MassComputation",
    "S2RunResult",
    "QuantisationResult",
    "RunnerConfig",
    "GovernedParameters",
    "S2TileWeightsRunner",
    "S2Error",
]


class _TileWeightsBatchWriter:
    """Buffer rows and emit Parquet shards for tile_weights."""

    _columns: tuple[str, ...] = (
        "country_iso",
        "tile_id",
        "weight_fp",
        "dp",
        "zero_mass_fallback",
    )
    _schema: Mapping[str, pl.DataType] = {
        "country_iso": pl.Utf8,
        "tile_id": pl.UInt64,
        "weight_fp": pl.UInt64,
        "dp": pl.UInt32,
        "zero_mass_fallback": pl.Boolean,
    }

    def __init__(self, *, temp_dir: Path, batch_size: int = 1_000_000) -> None:
        self.temp_dir = temp_dir
        self.batch_size = batch_size
        self.temp_dir.mkdir(parents=True, exist_ok=False)
        self._buffers: dict[str, list[np.ndarray]] = {column: [] for column in self._columns}
        self._rows_buffered = 0
        self._rows_written = 0
        self._shard_index = 0
        self._closed = False

    def append_batch(
        self,
        *,
        country_iso: np.ndarray,
        tile_id: np.ndarray,
        weight_fp: np.ndarray,
        dp: np.ndarray,
        zero_mass_fallback: np.ndarray,
    ) -> None:
        if self._closed:
            raise RuntimeError("Cannot append to a closed writer")
        arrays = {
            "country_iso": country_iso,
            "tile_id": tile_id,
            "weight_fp": weight_fp,
            "dp": dp,
            "zero_mass_fallback": zero_mass_fallback,
        }
        length = len(tile_id)
        for column, values in arrays.items():
            if len(values) != length:
                raise ValueError(f"Column '{column}' length mismatch in append_batch")
            self._buffers[column].append(values)
        self._rows_buffered += length
        if self._rows_buffered >= self.batch_size:
            self._flush()

    def close(self) -> None:
        if self._closed:
            return
        self._flush()
        if not any(self.temp_dir.glob("*.parquet")):
            frame = pl.DataFrame(
                {column: pl.Series(column, [], dtype=self._schema[column]) for column in self._columns}
            )
            frame.write_parquet(self.temp_dir / "part-00000.parquet", compression="zstd")
        self._closed = True

    def abort(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        self._closed = True

    def _flush(self) -> None:
        if self._rows_buffered == 0:
            return
        data: dict[str, np.ndarray] = {}
        for column in self._columns:
            parts = self._buffers[column]
            if not parts:
                raise RuntimeError(f"No buffered data present for column '{column}' during flush")
            data[column] = np.concatenate(parts)
            self._buffers[column] = []
        frame = pl.DataFrame(
            {
                column: pl.Series(
                    name=column,
                    values=data[column],
                    dtype=self._schema[column],
                )
                for column in self._columns
            }
        )
        shard_name = f"part-{self._shard_index:05d}.parquet"
        frame.write_parquet(self.temp_dir / shard_name, compression="zstd")
        self._rows_written += frame.height
        self._shard_index += 1
        self._rows_buffered = 0
