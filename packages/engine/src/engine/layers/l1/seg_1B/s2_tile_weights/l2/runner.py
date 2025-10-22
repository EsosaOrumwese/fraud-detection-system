"""L2 orchestration scaffolding for Segment 1B S2 (Tile Weights)."""

from __future__ import annotations
import time
import json
import shutil
import uuid

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, MutableMapping

import polars as pl

from engine.layers.l1.seg_1B.s1_tile_index.l0.loaders import IsoCountryTable, load_iso_countries
from engine.layers.l1.seg_1B.s1_tile_index.l2.runner import compute_partition_digest

from ...shared.dictionary import get_dataset_entry, load_dictionary, resolve_dataset_path
from ..exceptions import S2Error, err
from ..l0.tile_index import TileIndexPartition, load_tile_index_partition
from ..l1 import QuantisationResult, compute_tile_masses, quantise_tile_weights
from ..l3 import build_run_report
from ..l1.guards import validate_tile_index


ALLOWED_BASES = frozenset({"uniform", "area_m2", "population"})


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
    """Mass table derived from governed basis."""

    frame: pl.DataFrame



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
        try:
            iso_table = load_iso_countries(iso_path)
        except Exception as exc:  # noqa: BLE001 - surface as canonical failure
            raise err(
                "E101_TILE_INDEX_MISSING",
                f"failed to load ISO canonical table from '{iso_path}': {exc}",
            ) from exc
        pat = PatCounters()
        iso_size = iso_path.stat().st_size if iso_path.exists() else 0
        pat.bytes_read_vectors_total += int(iso_size)
        pat.vector_bytes_reference = int(iso_size)

        tile_index = load_tile_index_partition(
            base_path=config.data_root,
            parameter_hash=config.parameter_hash,
            dictionary=dictionary,
        )
        validate_tile_index(partition=tile_index, iso_table=iso_table)
        pat.bytes_read_tile_index_total += tile_index.byte_size
        pat.tile_index_bytes_reference = tile_index.byte_size

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
        frame = compute_tile_masses(
            tile_index=prepared.tile_index,
            basis=prepared.governed.basis,
            data_root=prepared.data_root,
            dictionary=prepared.dictionary,
            pat=prepared.pat,
        )
        return MassComputation(frame=frame)

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
        result = quantise_tile_weights(mass_frame=masses.frame, dp=prepared.governed.dp)
        prepared.pat.countries_processed = len(result.summaries)
        prepared.pat.rows_emitted = result.frame.height
        return result

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

        temp_dir = partition_path.parent / f".tmp.{uuid.uuid4().hex}"
        temp_dir.mkdir(parents=True, exist_ok=False)
        try:
            dataset_frame = quantised.frame.select(
                ["country_iso", "tile_id", "weight_fp", "dp", "zero_mass_fallback"]
            ).sort(["country_iso", "tile_id"])
            dataset_frame.write_parquet(temp_dir / "part-00000.parquet", compression="zstd")
            temp_dir.replace(partition_path)
        except Exception as exc:  # noqa: BLE001 - enforce atomic publish discipline
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
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