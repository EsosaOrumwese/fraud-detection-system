"""L2 orchestration helpers for S3 requirements."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Mapping

from ..l0 import (
    GateReceipt,
    IsoCountryTable,
    OutletCataloguePartition,
    TileWeightsPartition,
    load_gate_receipt,
    load_iso_countries,
    load_outlet_catalogue_partition,
    load_tile_weights_partition,
)
from ..l1.validators import validate_path_embeddings
from .aggregate import AggregationResult, compute_requirements
from .config import RunnerConfig
from .materialise import S3RunResult, materialise_requirements


@dataclass(frozen=True)
class PreparedInputs:
    """Resolved inputs and references required for aggregation."""

    config: RunnerConfig
    dictionary: Mapping[str, object]
    receipt: GateReceipt
    outlet_catalogue: OutletCataloguePartition
    tile_weights: TileWeightsPartition
    iso_table: IsoCountryTable


def prepare_inputs(config: RunnerConfig) -> PreparedInputs:
    """Resolve and validate all deterministic inputs for S3."""

    dictionary = config.dictionary or _load_dictionary()

    receipt = load_gate_receipt(
        base_path=config.data_root,
        manifest_fingerprint=config.manifest_fingerprint,
        dictionary=dictionary,
    )

    outlet_catalogue = load_outlet_catalogue_partition(
        base_path=config.data_root,
        seed=config.seed,
        manifest_fingerprint=config.manifest_fingerprint,
        dictionary=dictionary,
    )
    validate_path_embeddings(
        outlet_catalogue.frame,
        manifest_fingerprint=config.manifest_fingerprint,
        seed=config.seed,
    )

    tile_weights = load_tile_weights_partition(
        base_path=config.data_root,
        parameter_hash=config.parameter_hash,
        dictionary=dictionary,
    )

    iso_table = load_iso_countries(base_path=config.data_root, dictionary=dictionary)

    return PreparedInputs(
        config=config,
        dictionary=dictionary,
        receipt=receipt,
        outlet_catalogue=outlet_catalogue,
        tile_weights=tile_weights,
        iso_table=iso_table,
    )


class S3RequirementsRunner:
    """High-level orchestrator that prepares inputs and computes requirements."""

    def prepare(self, config: RunnerConfig) -> PreparedInputs:
        return prepare_inputs(config)

    def aggregate(self, prepared: PreparedInputs) -> AggregationResult:
        return compute_requirements(
            outlet_frame=prepared.outlet_catalogue.frame,
            iso_table=prepared.iso_table,
            tile_weights=prepared.tile_weights,
        )

    def materialise(self, prepared: PreparedInputs, aggregation: AggregationResult) -> S3RunResult:
        return materialise_requirements(prepared=prepared, aggregation=aggregation)

    def run(self, config: RunnerConfig) -> S3RunResult:
        logger = logging.getLogger(__name__)
        prepared = self.prepare(config)
        outlet_rows = int(prepared.outlet_catalogue.frame.height)
        tile_weight_rows = int(prepared.tile_weights.frame.height)
        logger.info(
            "S3: prepared inputs (outlet_rows=%d, tile_weight_rows=%d, iso_rows=%d)",
            outlet_rows,
            tile_weight_rows,
            int(prepared.iso_table.table.height),
        )
        aggregation = self.aggregate(prepared)
        logger.info(
            "S3: aggregation summary (rows=%d, merchants=%d, countries=%d, source_rows=%d)",
            aggregation.rows_emitted,
            aggregation.merchants_total,
            aggregation.countries_total,
            aggregation.source_rows_total,
        )
        return self.materialise(prepared, aggregation)


def _load_dictionary() -> Mapping[str, object]:
    from ..shared.dictionary import load_dictionary as _shared_load_dictionary

    return _shared_load_dictionary()


__all__ = ["PreparedInputs", "S3RequirementsRunner", "prepare_inputs"]
