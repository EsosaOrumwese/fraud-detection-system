"""L2 orchestrator for S0 foundations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence

import polars as pl

from ..exceptions import err
from ..l0.artifacts import hash_artifacts
from ..l0.datasets import load_parquet_table, load_yaml
from ..l1.context import RunContext, SchemaAuthority
from ..l1.design import (
    DispersionCoefficients,
    DesignVectors,
    HurdleCoefficients,
    design_dataframe,
    iter_design_vectors,
    load_dispersion_coefficients,
    load_hurdle_coefficients,
)
from ..l1.diagnostics import build_hurdle_diagnostics
from ..l1.eligibility import (
    evaluate_eligibility,
    load_crossborder_eligibility,
)
from ..l1.hashing import (
    ManifestFingerprintResult,
    ParameterHashResult,
    compute_manifest_fingerprint,
    compute_parameter_hash,
    compute_run_id,
)
from ..l1.merchants import build_run_context
from ..l1.rng import PhiloxEngine

_REQUIRED_PARAMETER_FILES = (
    "hurdle_coefficients.yaml",
    "nb_dispersion_coefficients.yaml",
    "crossborder_hyperparams.yaml",
)


@dataclass(frozen=True)
class SealedFoundations:
    context: RunContext
    parameter_hash: ParameterHashResult
    manifest_fingerprint: ManifestFingerprintResult


class S0FoundationsRunner:
    """High-level helper that wires L0/L1 components together."""

    def __init__(self, schema_authority: SchemaAuthority) -> None:
        self.schema_authority = schema_authority

    @staticmethod
    def load_table(path: Path) -> pl.DataFrame:
        return load_parquet_table(path)

    @staticmethod
    def load_yaml_mapping(path: Path) -> Mapping[str, object]:
        return load_yaml(path)

    def seal(
        self,
        *,
        merchant_table: pl.DataFrame,
        iso_table: pl.DataFrame,
        gdp_table: pl.DataFrame,
        bucket_table: pl.DataFrame,
        parameter_files: Mapping[str, Path],
        manifest_artifacts: Sequence[Path],
        git_commit_raw: bytes,
    ) -> SealedFoundations:
        missing = [
            name for name in _REQUIRED_PARAMETER_FILES if name not in parameter_files
        ]
        if missing:
            raise err("E_PARAM_MISSING", f"missing parameter files {missing}")

        context = build_run_context(
            merchant_table=merchant_table,
            iso_table=iso_table,
            gdp_table=gdp_table,
            bucket_table=bucket_table,
            schema_authority=self.schema_authority,
        )

        param_paths = [parameter_files[name] for name in _REQUIRED_PARAMETER_FILES]
        parameter_digests = hash_artifacts(param_paths, error_prefix="E_PARAM")
        parameter_hash = compute_parameter_hash(parameter_digests)

        manifest_digests = hash_artifacts(manifest_artifacts, error_prefix="E_ARTIFACT")
        manifest_fingerprint = compute_manifest_fingerprint(
            manifest_digests,
            git_commit_raw=git_commit_raw,
            parameter_hash_bytes=parameter_hash.parameter_hash_bytes,
        )

        return SealedFoundations(
            context=context,
            parameter_hash=parameter_hash,
            manifest_fingerprint=manifest_fingerprint,
        )

    @staticmethod
    def build_design_vectors(
        context: RunContext,
        *,
        hurdle_config: Mapping[str, object],
        dispersion_config: Mapping[str, object],
    ) -> tuple[HurdleCoefficients, DispersionCoefficients, Sequence[DesignVectors]]:
        hurdle = load_hurdle_coefficients(hurdle_config)
        dispersion = load_dispersion_coefficients(
            dispersion_config, reference=hurdle.dictionaries
        )
        vectors = tuple(
            iter_design_vectors(context, hurdle=hurdle, dispersion=dispersion)
        )
        return hurdle, dispersion, vectors

    @staticmethod
    def design_dataframe(vectors: Iterable[DesignVectors]) -> pl.DataFrame:
        return design_dataframe(vectors)

    @staticmethod
    def logistic_diagnostics(
        vectors: Iterable[DesignVectors],
        *,
        beta: Sequence[float],
        parameter_hash: str,
        produced_by_fingerprint: Optional[str] = None,
    ) -> pl.DataFrame:
        return build_hurdle_diagnostics(
            vectors,
            beta=beta,
            parameter_hash=parameter_hash,
            produced_by_fingerprint=produced_by_fingerprint,
        )

    @staticmethod
    def build_eligibility_flags(
        context: RunContext,
        *,
        crossborder_config: Mapping[str, object],
        parameter_hash: str,
        produced_by_fingerprint: Optional[str] = None,
    ) -> pl.DataFrame:
        bundle = load_crossborder_eligibility(
            crossborder_config, iso_set=set(context.iso_countries)
        )
        return evaluate_eligibility(
            context,
            bundle=bundle,
            parameter_hash=parameter_hash,
            produced_by_fingerprint=produced_by_fingerprint,
        )

    @staticmethod
    def issue_run_id(
        *,
        manifest_fingerprint_bytes: bytes,
        seed: int,
        start_time_ns: int,
        existing_ids: Iterable[str] = (),
    ) -> str:
        return compute_run_id(
            manifest_fingerprint_bytes=manifest_fingerprint_bytes,
            seed=seed,
            start_time_ns=start_time_ns,
            existing_ids=existing_ids,
        )

    @staticmethod
    def philox_engine(
        *, seed: int, manifest_fingerprint: ManifestFingerprintResult
    ) -> PhiloxEngine:
        return PhiloxEngine(
            seed=seed,
            manifest_fingerprint=manifest_fingerprint.manifest_fingerprint_bytes,
        )


__all__ = [
    "S0FoundationsRunner",
    "SealedFoundations",
]
