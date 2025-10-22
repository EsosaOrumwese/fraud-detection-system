"""L2 orchestration scaffolding for Segment 1B S2 (Tile Weights)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, MutableMapping

from engine.layers.l1.seg_1B.s1_tile_index.l0.loaders import (
    IsoCountryTable,
    load_iso_countries,
)

from ...shared.dictionary import (
    get_dataset_entry,
    load_dictionary,
    resolve_dataset_path,
)
from ..exceptions import S2Error, err
from ..l0.tile_index import TileIndexPartition, load_tile_index_partition
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
        }


@dataclass(frozen=True)
class PreparedInputs:
    """Result of phases 0–2: validated ingress and governed parameters."""

    governed: GovernedParameters
    dictionary: Mapping[str, object]
    tile_index: TileIndexPartition
    iso_table: IsoCountryTable
    pat: PatCounters = field(default_factory=PatCounters)


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

        tile_index = load_tile_index_partition(
            base_path=config.data_root,
            parameter_hash=config.parameter_hash,
            dictionary=dictionary,
        )
        validate_tile_index(partition=tile_index, iso_table=iso_table)

        return PreparedInputs(
            governed=governed,
            dictionary=dictionary,
            tile_index=tile_index,
            iso_table=iso_table,
        )


__all__ = [
    "PatCounters",
    "PreparedInputs",
    "RunnerConfig",
    "GovernedParameters",
    "S2TileWeightsRunner",
    "S2Error",
]

