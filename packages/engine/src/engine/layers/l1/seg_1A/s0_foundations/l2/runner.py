"""L2 orchestration helpers for S0 foundations.

``S0FoundationsRunner`` stitches together the L0/L1 helpers so that callers can
drive state-0 from a handful of file paths.  The module also provides the
``S0RunResult`` dataclass, making it easy to persist or forward lineage info.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence
import time

import polars as pl

from ..exceptions import S0Error, err
from ..l0.artifacts import ArtifactDigest, hash_artifacts
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
from ..l1.numeric import (
    build_numeric_policy_attestation,
    load_math_profile_manifest,
    load_numeric_policy,
)
from ..l1.rng import PhiloxEngine, comp_u64
from ..l2.failure import emit_failure_record
from ..l2.output import S0Outputs, write_outputs
from ..l2.rng_logging import RNGLogWriter, rng_event

_REQUIRED_PARAMETER_FILES = (
    "hurdle_coefficients.yaml",
    "nb_dispersion_coefficients.yaml",
    "crossborder_hyperparams.yaml",
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SealedFoundations:
    """Bundle of the run context plus the computed lineage digests."""

    context: RunContext
    parameter_hash: ParameterHashResult
    manifest_fingerprint: ManifestFingerprintResult
    numeric_policy_digest: Optional[ArtifactDigest] = None
    math_profile_digest: Optional[ArtifactDigest] = None


@dataclass(frozen=True)
class S0RunResult:
    """Return value for ``run_from_paths`` with the essentials for bookkeeping."""

    sealed: SealedFoundations
    outputs: S0Outputs
    run_id: str
    base_path: Path


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

    @staticmethod
    def _collect_manifest_artifacts(paths: Iterable[Path]) -> list[Path]:
        """Expand directory inputs so the manifest can hash every file explicitly."""
        artifacts: list[Path] = []
        for raw in paths:
            path = Path(raw)
            if not path.exists():
                continue
            if path.is_file():
                artifacts.append(path)
            else:
                for file_path in sorted(p for p in path.rglob("*") if p.is_file()):
                    artifacts.append(file_path)
        return artifacts

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
        numeric_policy_path: Optional[Path] = None,
        math_profile_manifest_path: Optional[Path] = None,
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

        manifest_paths = list(manifest_artifacts)
        policy_obj = None
        policy_digest = None
        profile_obj = None
        profile_digest = None
        attestation = None

        if numeric_policy_path is not None:
            policy_obj, policy_digest = load_numeric_policy(numeric_policy_path)
            manifest_paths.append(numeric_policy_path)
        if math_profile_manifest_path is not None:
            profile_obj, profile_digest = load_math_profile_manifest(
                math_profile_manifest_path
            )
            manifest_paths.append(math_profile_manifest_path)
        if policy_obj and profile_obj and policy_digest and profile_digest:
            attestation = build_numeric_policy_attestation(
                policy=policy_obj,
                policy_digest=policy_digest,
                math_profile=profile_obj,
                math_digest=profile_digest,
            )

        manifest_digests = hash_artifacts(manifest_paths, error_prefix="E_ARTIFACT")
        manifest_fingerprint = compute_manifest_fingerprint(
            manifest_digests,
            git_commit_raw=git_commit_raw,
            parameter_hash_bytes=parameter_hash.parameter_hash_bytes,
        )

        context = context.with_lineage(
            parameter_hash=parameter_hash.parameter_hash,
            manifest_fingerprint=manifest_fingerprint.manifest_fingerprint,
            numeric_policy=policy_obj,
            math_profile=profile_obj,
            numeric_attestation=attestation,
        )

        return SealedFoundations(
            context=context,
            parameter_hash=parameter_hash,
            manifest_fingerprint=manifest_fingerprint,
            numeric_policy_digest=policy_digest,
            math_profile_digest=profile_digest,
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

    def build_outputs_bundle(
        self,
        *,
        sealed: SealedFoundations,
        parameter_files: Mapping[str, Path],
        include_diagnostics: bool = True,
    ) -> S0Outputs:
        parameter_hash = sealed.parameter_hash.parameter_hash
        manifest_fingerprint = sealed.manifest_fingerprint.manifest_fingerprint

        hurdle_cfg = self.load_yaml_mapping(parameter_files["hurdle_coefficients.yaml"])
        dispersion_cfg = self.load_yaml_mapping(
            parameter_files["nb_dispersion_coefficients.yaml"]
        )
        crossborder_cfg = self.load_yaml_mapping(
            parameter_files["crossborder_hyperparams.yaml"]
        )

        hurdle, dispersion, vectors = self.build_design_vectors(
            sealed.context,
            hurdle_config=hurdle_cfg,
            dispersion_config=dispersion_cfg,
        )
        design_df = self.design_dataframe(vectors).with_columns(
            [
                pl.lit(parameter_hash).alias("parameter_hash"),
                pl.lit(manifest_fingerprint).alias("produced_by_fingerprint"),
            ]
        )
        flags_df = self.build_eligibility_flags(
            sealed.context,
            crossborder_config=crossborder_cfg,
            parameter_hash=parameter_hash,
            produced_by_fingerprint=manifest_fingerprint,
        )

        diagnostics_df: Optional[pl.DataFrame] = None
        if include_diagnostics:
            diagnostics_df = self.logistic_diagnostics(
                vectors,
                beta=hurdle.beta,
                parameter_hash=parameter_hash,
                produced_by_fingerprint=manifest_fingerprint,
            )

        return S0Outputs(
            crossborder_flags=flags_df,
            design_matrix=design_df,
            hurdle_coefficients=hurdle,
            dispersion_coefficients=dispersion,
            diagnostics=diagnostics_df,
            numeric_attestation=sealed.context.numeric_attestation,
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

    @staticmethod
    def _log_progress(message: str, start_time: float, last_checkpoint: float) -> float:
        """Emit a deterministic progress log with cumulative and step timing."""

        now = time.perf_counter()
        total = now - start_time
        delta = now - last_checkpoint
        logger.info("%s (elapsed=%.2fs, delta=%.2fs)", message, total, delta)
        return now

    def run_from_paths(
        self,
        *,
        base_path: Path,
        merchant_table_path: Path,
        iso_table_path: Path,
        gdp_table_path: Path,
        bucket_table_path: Path,
        parameter_files: Mapping[str, Path],
        git_commit_hex: str,
        seed: int,
        numeric_policy_path: Optional[Path] = None,
        math_profile_manifest_path: Optional[Path] = None,
        include_diagnostics: bool = True,
        start_time_ns: Optional[int] = None,
        validate: bool = True,
        extra_manifest_artifacts: Sequence[Path] | None = None,
    ) -> S0RunResult:
        """Execute the full S0 flow given concrete artefact paths on disk."""
        start_perf = time.perf_counter()
        last_checkpoint = start_perf
        last_checkpoint = self._log_progress(
            "S0: run initialised",
            start_perf,
            last_checkpoint,
        )

        merchant_table = self.load_table(merchant_table_path)
        iso_table = self.load_table(iso_table_path)
        gdp_table = self.load_table(gdp_table_path)
        bucket_table = self.load_table(bucket_table_path)
        last_checkpoint = self._log_progress(
            "S0: loaded ingress tables",
            start_perf,
            last_checkpoint,
        )

        parameter_paths = {name: Path(path) for name, path in parameter_files.items()}

        manifest_sources: list[Path] = list(parameter_paths.values()) + [
            Path(merchant_table_path),
            Path(iso_table_path),
            Path(gdp_table_path),
            Path(bucket_table_path),
        ]
        if extra_manifest_artifacts is not None:
            manifest_sources.extend(Path(p) for p in extra_manifest_artifacts)
        manifest_artifacts = self._collect_manifest_artifacts(manifest_sources)

        try:
            git_commit_raw = bytes.fromhex(git_commit_hex)
        except ValueError as exc:  # pragma: no cover - invalid configuration
            raise err(
                "E_GIT_BYTES", f"invalid git commit hex '{git_commit_hex}'"
            ) from exc

        sealed = self.seal(
            merchant_table=merchant_table,
            iso_table=iso_table,
            gdp_table=gdp_table,
            bucket_table=bucket_table,
            parameter_files=parameter_paths,
            manifest_artifacts=manifest_artifacts,
            git_commit_raw=git_commit_raw,
            numeric_policy_path=numeric_policy_path,
            math_profile_manifest_path=math_profile_manifest_path,
        )
        last_checkpoint = self._log_progress(
            "S0: sealed run context and computed lineage digests",
            start_perf,
            last_checkpoint,
        )

        start_ns = start_time_ns or time.time_ns()
        run_id = self.issue_run_id(
            manifest_fingerprint_bytes=sealed.manifest_fingerprint.manifest_fingerprint_bytes,
            seed=seed,
            start_time_ns=start_ns,
        )
        engine = self.philox_engine(
            seed=seed, manifest_fingerprint=sealed.manifest_fingerprint
        )
        rng_logger = RNGLogWriter(
            base_path=base_path / "rng_logs",
            seed=seed,
            parameter_hash=sealed.parameter_hash.parameter_hash,
            manifest_fingerprint=sealed.manifest_fingerprint.manifest_fingerprint,
            run_id=run_id,
        )
        anchor_stream = engine.derive_substream("s0.anchor", (comp_u64(0),))
        with rng_event(
            logger=rng_logger,
            substream=anchor_stream,
            module="1A.s0",
            family="core",
            event="anchor",
            substream_label="s0.anchor",
            expected_blocks=0,
            expected_draws=0,
        ):
            pass

        outputs = self.build_outputs_bundle(
            sealed=sealed,
            parameter_files=parameter_paths,
            include_diagnostics=include_diagnostics,
        )
        last_checkpoint = self._log_progress(
            "S0: built outputs bundle "
            f"(run_id={run_id}, parameter_hash={sealed.parameter_hash.parameter_hash})",
            start_perf,
            last_checkpoint,
        )

        try:
            write_outputs(
                base_path=base_path,
                sealed=sealed,
                outputs=outputs,
                run_id=run_id,
                seed=seed,
                philox_engine=engine,
            )
            last_checkpoint = self._log_progress(
                f"S0: wrote outputs to {base_path}",
                start_perf,
                last_checkpoint,
            )
            if validate:
                from ..l3.validator import (
                    validate_outputs,
                )  # local import to avoid cycle

                validate_outputs(
                    base_path=base_path,
                    sealed=sealed,
                    outputs=outputs,
                    seed=seed,
                    run_id=run_id,
                )
                last_checkpoint = self._log_progress(
                    "S0: validated persisted artefacts",
                    start_perf,
                    last_checkpoint,
                )
        except S0Error as failure:
            emit_failure_record(
                base_path=base_path,
                fingerprint=sealed.manifest_fingerprint.manifest_fingerprint,
                seed=seed,
                run_id=run_id,
                failure=failure,
                state="S0",
                module="1A.s0.orchestrator",
                parameter_hash=sealed.parameter_hash.parameter_hash,
            )
            raise

        self._log_progress(
            "S0: completed run "
            f"(run_id={run_id}, manifest_fingerprint={sealed.manifest_fingerprint.manifest_fingerprint})",
            start_perf,
            last_checkpoint,
        )
        return S0RunResult(
            sealed=sealed,
            outputs=outputs,
            run_id=run_id,
            base_path=base_path,
        )


__all__ = [
    "S0FoundationsRunner",
    "SealedFoundations",
    "S0RunResult",
]
