"""Scenario-runner helpers for Layer-1 Segment 1A states."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Mapping, Optional, Sequence, Tuple

import yaml

from engine.layers.l1.seg_1A.s0_foundations import S0FoundationsRunner, SchemaAuthority
from engine.layers.l1.seg_1A.s0_foundations.exceptions import S0Error, err
from engine.layers.l1.seg_1A.s0_foundations.l1.design import iter_design_vectors
from engine.layers.l1.seg_1A.s0_foundations.l2.runner import S0RunResult
from engine.layers.l1.seg_1A.s1_hurdle import HurdleDesignRow, S1HurdleRunner
from engine.layers.l1.seg_1A.s1_hurdle.l2.runner import S1RunResult
from engine.layers.l1.seg_1A.s1_hurdle.l3.catalogue import GatedStream
from engine.layers.l1.seg_1A.s1_hurdle.l3.validator import validate_hurdle_run
from engine.layers.l1.seg_1A.s2_nb_outlets import (
    NBFinalRecord,
    S2DeterministicContext,
    S2NegativeBinomialRunner,
    S2RunResult,
    build_deterministic_context as build_s2_deterministic_context,
    validate_nb_run,
)
from engine.layers.l1.seg_1A.s2_nb_outlets.l3.bundle import publish_s2_validation_artifacts
from engine.layers.l1.seg_1A.s2_nb_outlets.l3.catalogue import write_nb_catalogue
from engine.layers.l1.seg_1A.s3_crossborder_universe import (
    ArtefactSpec as S3ArtefactSpec,
    MerchantProfile,
    S3CrossBorderRunner,
    S3DeterministicContext,
    S3FeatureToggles,
    S3RunResult,
    build_deterministic_context as build_s3_deterministic_context,
)
from engine.layers.l1.seg_1A.s3_crossborder_universe.l0.policy import (
    load_base_weight_policy,
    load_thresholds_policy,
)
from engine.layers.l1.seg_1A.s3_crossborder_universe.l3.bundle import (
    publish_s3_validation_artifacts,
)
from engine.layers.l1.seg_1A.s3_crossborder_universe.l3.validator import (
    validate_s3_outputs,
)
from engine.layers.l1.seg_1A.s4_ztp_target import (
    S4ZTPTargetRunner,
    build_deterministic_context as build_s4_deterministic_context,
)
from engine.layers.l1.seg_1A.s4_ztp_target.contexts import S4DeterministicContext
from engine.layers.l1.seg_1A.s4_ztp_target.l2 import (
    S4RunResult,
    ZTPFinalRecord,
)
from engine.layers.l1.seg_1A.s4_ztp_target.l3.bundle import (
    publish_s4_validation_artifacts,
)
from engine.layers.l1.seg_1A.s4_ztp_target.l3.validator import validate_s4_run
from engine.layers.l1.seg_1A.s5_currency_weights import (
    DEFAULT_PATHS as S5_DEFAULT_PATHS,
    MerchantCurrencyInput,
    S5CurrencyWeightsRunner,
    S5DeterministicContext,
    S5RunOutputs,
)
from engine.layers.l1.seg_1A.shared.dictionary import get_repo_root

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HurdleStateContext:
    """Context bundle handed to downstream states after S1 completes."""

    parameter_hash: str
    manifest_fingerprint: str
    run_id: str
    seed: int
    multi_merchant_ids: Tuple[int, ...]
    gated_streams: Tuple[GatedStream, ...]
    catalogue_path: Path

    @property
    def gated_dataset_ids(self) -> Tuple[str, ...]:
        """Return the dataset identifiers gated by the hurdle stream."""

        return tuple(stream.dataset_id for stream in self.gated_streams)

    def stream_by_dataset(self) -> Dict[str, GatedStream]:
        """Return a dictionary keyed by dataset identifier."""

        return {stream.dataset_id: stream for stream in self.gated_streams}


def build_hurdle_context(result: S1RunResult) -> HurdleStateContext:
    """Construct the downstream-facing context from an ``S1RunResult``."""

    return HurdleStateContext(
        parameter_hash=result.parameter_hash,
        manifest_fingerprint=result.manifest_fingerprint,
        run_id=result.run_id,
        seed=result.seed,
        multi_merchant_ids=result.multi_merchant_ids,
        gated_streams=result.gated_streams,
        catalogue_path=result.catalogue_path,
    )


@dataclass(frozen=True)
class S2StateContext:
    """Downstream context bundle produced after S2 NB sampling completes."""

    deterministic: S2DeterministicContext
    finals: Tuple[NBFinalRecord, ...]
    gamma_events_path: Path
    poisson_events_path: Path
    final_events_path: Path
    trace_path: Path
    metrics: Dict[str, float] | None
    catalogue_path: Path | None
    validation_artifacts_path: Path | None

    @property
    def parameter_hash(self) -> str:
        """Parameter hash carried across the S2 deterministic context."""

        return self.deterministic.parameter_hash

    @property
    def manifest_fingerprint(self) -> str:
        """Manifest fingerprint for the run."""

        return self.deterministic.manifest_fingerprint

    @property
    def run_id(self) -> str:
        """Run identifier used by the RNG envelopes."""

        return self.deterministic.run_id

    @property
    def seed(self) -> int:
        """Philox seed associated with the run."""

        return self.deterministic.seed

    def final_by_merchant(self) -> Dict[int, NBFinalRecord]:
        """Return the accepted NB outcome per merchant."""

        return {record.merchant_id: record for record in self.finals}

    def counts_by_merchant(self) -> Dict[int, Tuple[int, int]]:
        """Return ``(n_outlets, nb_rejections)`` for quick downstream use."""

        return {
            record.merchant_id: (record.n_outlets, record.nb_rejections)
            for record in self.finals
        }


def build_s2_context(
    result: S2RunResult,
    *,
    metrics: Dict[str, float] | None,
    catalogue_path: Path | None,
    validation_artifacts_path: Path | None,
) -> S2StateContext:
    """Construct the downstream-facing context from an ``S2RunResult``."""

    return S2StateContext(
        deterministic=result.deterministic,
        finals=result.finals,
        gamma_events_path=result.gamma_events_path,
        poisson_events_path=result.poisson_events_path,
        final_events_path=result.final_events_path,
        trace_path=result.trace_path,
        metrics=metrics,
        catalogue_path=catalogue_path,
    validation_artifacts_path=validation_artifacts_path,
)


@dataclass(frozen=True)
class S3StateContext:
    """Downstream context bundle after S3 cross-border universe completes."""

    deterministic: S3DeterministicContext
    candidate_set_path: Path
    base_weight_priors_path: Path | None
    integerised_counts_path: Path | None
    site_sequence_path: Path | None
    metrics: Dict[str, float] | None = None
    validation_passed: bool | None = None
    validation_failed_merchants: Dict[int, str] | None = None
    validation_artifacts_path: Path | None = None
    validation_diagnostics: Tuple[Mapping[str, object], ...] | None = None

    @property
    def parameter_hash(self) -> str:
        return self.deterministic.parameter_hash

    @property
    def manifest_fingerprint(self) -> str:
        return self.deterministic.manifest_fingerprint

    @property
    def run_id(self) -> str:
        return self.deterministic.run_id

    @property
    def seed(self) -> int:
        return self.deterministic.seed


@dataclass(frozen=True)
class S4StateContext:
    """Downstream context bundle after S4 target sampling completes."""

    deterministic: S4DeterministicContext
    finals: Tuple[ZTPFinalRecord, ...]
    poisson_events_path: Path
    rejection_events_path: Path
    retry_exhausted_events_path: Path
    final_events_path: Path
    trace_path: Path
    metrics: Dict[str, float] | None = None
    validation_passed: bool | None = None
    validation_artifacts_path: Path | None = None

    @property
    def run_id(self) -> str:
        return self.deterministic.run_id

    @property
    def seed(self) -> int:
        return self.deterministic.seed


@dataclass(frozen=True)
class S5StateContext:
    """Context bundle produced after S5 currency-weight expansion."""

    deterministic: S5DeterministicContext
    weights_path: Path
    sparse_flag_path: Path | None
    receipt_path: Path
    policy_digest: str
    policy_path: Path
    policy_semver: str
    policy_version: str
    merchant_currency_path: Path | None


def build_s3_context(
    result: S3RunResult,
    *,
    metrics: Dict[str, float] | None = None,
    validation_passed: bool | None = None,
    validation_failed_merchants: Dict[int, str] | None = None,
    validation_artifacts_path: Path | None = None,
    validation_diagnostics: Tuple[Mapping[str, object], ...] | None = None,
) -> S3StateContext:
    """Construct the downstream-facing context bundle from the S3 run."""

    return S3StateContext(
        deterministic=result.deterministic,
        candidate_set_path=result.candidate_set_path,
        base_weight_priors_path=result.base_weight_priors_path,
        integerised_counts_path=result.integerised_counts_path,
        site_sequence_path=result.site_sequence_path,
        metrics=metrics,
        validation_passed=validation_passed,
        validation_failed_merchants=validation_failed_merchants,
        validation_artifacts_path=validation_artifacts_path,
        validation_diagnostics=validation_diagnostics,
    )


def build_s4_context(
    result: S4RunResult,
    *,
    metrics: Dict[str, float] | None = None,
    validation_passed: bool | None = None,
    validation_artifacts_path: Path | None = None,
) -> S4StateContext:
    """Construct the downstream-facing context from an ``S4RunResult``."""

    return S4StateContext(
        deterministic=result.deterministic,
        finals=result.finals,
        poisson_events_path=result.poisson_events_path,
        rejection_events_path=result.rejection_events_path,
        retry_exhausted_events_path=result.retry_exhausted_events_path,
        final_events_path=result.final_events_path,
        trace_path=result.trace_path,
        metrics=metrics,
        validation_passed=validation_passed,
        validation_artifacts_path=validation_artifacts_path,
    )


def build_s5_context(outputs: S5RunOutputs) -> S5StateContext:
    """Construct the downstream context bundle for S5 outputs."""

    metadata = outputs.policy
    return S5StateContext(
        deterministic=outputs.deterministic,
        weights_path=outputs.weights_path,
        sparse_flag_path=outputs.sparse_flag_path,
        receipt_path=outputs.receipt_path or outputs.weights_path.parent / "S5_VALIDATION.json",
        policy_digest=metadata.digest_hex,
        policy_path=metadata.path,
        policy_semver=metadata.semver,
        policy_version=metadata.version,
        merchant_currency_path=outputs.merchant_currency_path,
    )


@dataclass(frozen=True)
class Segment1ARunResult:
    """Combined result for running S0 foundations through S4 target sampling."""

    s0_result: S0RunResult
    s1_result: S1RunResult
    s2_result: S2RunResult
    hurdle_context: HurdleStateContext
    nb_context: S2StateContext
    s3_result: S3RunResult
    s3_context: S3StateContext
    s4_result: S4RunResult
    s4_context: S4StateContext
    s5_result: S5RunOutputs
    s5_context: S5StateContext


class Segment1AOrchestrator:
    """Convenience wrapper that executes S0 foundations followed by S1 hurdle."""

    def __init__(self, *, schema_authority: SchemaAuthority | None = None) -> None:
        authority = schema_authority or SchemaAuthority(
            ingress_ref="l1/seg_1A/merchant_ids.schema.json",
            segment_ref="l1/seg_1A/s0_outputs.schema.json",
            rng_ref="layer1/schemas.layer1.yaml",
        )
        self._authority = authority
        self._s0_runner = S0FoundationsRunner(schema_authority=authority)
        self._s1_runner = S1HurdleRunner()
        self._s2_runner = S2NegativeBinomialRunner()
        self._s3_runner = S3CrossBorderRunner()
        self._s4_runner = S4ZTPTargetRunner()
        self._s5_runner = S5CurrencyWeightsRunner()


    def _resolve_s5_policy_path(self, param_mapping: Mapping[str, Path]) -> Path:
        """Resolve the governed S5 smoothing policy path."""

        candidate_keys = (
            "ccy_smoothing_params.yaml",
            "config.allocation.ccy_smoothing_params.yaml",
            "config/allocation/ccy_smoothing_params.yaml",
        )
        for key in candidate_keys:
            policy_path = param_mapping.get(key)
            if policy_path is not None:
                return policy_path.expanduser().resolve()

        default_path = (
            get_repo_root()
            / "config"
            / "allocation"
            / "ccy_smoothing_params.yaml"
        )
        if not default_path.exists():
            raise err(
                "E_GOVERNANCE_MISSING",
                f"default S5 policy not found at '{default_path}'",
            )
        return default_path.resolve()


    def run(
        self,
        *,
        base_path: Path,
        merchant_table: Path,
        iso_table: Path,
        gdp_table: Path,
        bucket_table: Path,
        parameter_files: Mapping[str, Path],
        git_commit_hex: str,
        seed: int,
        numeric_policy_path: Path | None = None,
        math_profile_manifest_path: Path | None = None,
        include_diagnostics: bool = True,
        validate_s0: bool = True,
        validate_s1: bool = True,
        validate_s2: bool = True,
        extra_manifest_artifacts: Sequence[Path] | None = None,
        validation_policy_path: Path | None = None,
        validate_s3: bool = True,
        s3_priors: bool = False,
        s3_integerisation: bool = False,
        s3_sequencing: bool = False,
        s4_features: Path | None = None,
        validate_s4: bool = True,
        s4_validation_output: Path | None = None,
    ) -> Segment1ARunResult:
        base_path = base_path.expanduser().resolve()
        param_mapping = {
            name: Path(path).expanduser().resolve() for name, path in parameter_files.items()
        }
        extras = (
            [Path(item).expanduser().resolve() for item in extra_manifest_artifacts]
            if extra_manifest_artifacts
            else []
        )
        s5_policy_path = self._resolve_s5_policy_path(param_mapping)
        if s5_policy_path not in extras:
            extras.append(s5_policy_path)
        feature_path_input = s4_features.expanduser().resolve() if s4_features else None
        if feature_path_input is not None:
            extras.append(feature_path_input)
        validation_policy: Mapping[str, object] | None = None
        if validation_policy_path is not None:
            policy_path = validation_policy_path.expanduser().resolve()
            data = yaml.safe_load(policy_path.read_text(encoding="utf-8")) or {}
            if not isinstance(data, Mapping):
                raise err(
                    "ERR_S2_CORRIDOR_POLICY_MISSING",
                    f"validation policy at {policy_path} must decode to a mapping",
                )
            validation_policy = data

        logger.info(
            "Segment1A orchestrator starting (seed=%d, git_commit=%s, base_path=%s)",
            seed,
            git_commit_hex,
            base_path,
        )

        s0_result = self._s0_runner.run_from_paths(
            base_path=base_path,
            merchant_table_path=merchant_table.expanduser().resolve(),
            iso_table_path=iso_table.expanduser().resolve(),
            gdp_table_path=gdp_table.expanduser().resolve(),
            bucket_table_path=bucket_table.expanduser().resolve(),
            parameter_files=param_mapping,
            git_commit_hex=git_commit_hex,
            seed=seed,
            numeric_policy_path=(
                numeric_policy_path.expanduser().resolve()
                if numeric_policy_path is not None
                else None
            ),
            math_profile_manifest_path=(
                math_profile_manifest_path.expanduser().resolve()
                if math_profile_manifest_path is not None
                else None
            ),
            include_diagnostics=include_diagnostics,
            validate=validate_s0,
            extra_manifest_artifacts=extras,
        )

        logger.info(
            "Segment1A S0 completed (run_id=%s, parameter_hash=%s)",
            s0_result.run_id,
            s0_result.sealed.parameter_hash.parameter_hash,
        )

        design_vectors = tuple(
            iter_design_vectors(
                s0_result.sealed.context,
                hurdle=s0_result.outputs.hurdle_coefficients,
                dispersion=s0_result.outputs.dispersion_coefficients,
            )
        )
        design_rows: Tuple[HurdleDesignRow, ...] = tuple(
            HurdleDesignRow(
                merchant_id=vector.merchant_id,
                bucket_id=vector.bucket,
                design_vector=vector.x_hurdle,
            )
            for vector in design_vectors
        )

        s1_result = self._s1_runner.run(
            base_path=base_path,
            manifest_fingerprint=s0_result.sealed.manifest_fingerprint.manifest_fingerprint,
            parameter_hash=s0_result.sealed.parameter_hash.parameter_hash,
            beta=s0_result.outputs.hurdle_coefficients.beta,
            design_rows=design_rows,
            seed=seed,
            run_id=s0_result.run_id,
        )

        logger.info(
            "Segment1A S1 completed (multi_merchants=%d)",
            len(s1_result.multi_merchant_ids),
        )

        if validate_s1:
            validate_hurdle_run(
                base_path=base_path,
                manifest_fingerprint=s1_result.manifest_fingerprint,
                parameter_hash=s1_result.parameter_hash,
                seed=s1_result.seed,
                run_id=s1_result.run_id,
                beta=s0_result.outputs.hurdle_coefficients.beta,
                design_rows=design_rows,
            )
            logger.info("Segment1A S1 validation passed")

        hurdle_context = build_hurdle_context(s1_result)

        deterministic_context = build_s2_deterministic_context(
            parameter_hash=s1_result.parameter_hash,
            manifest_fingerprint=s1_result.manifest_fingerprint,
            run_id=s1_result.run_id,
            seed=s1_result.seed,
            multi_merchant_ids=s1_result.multi_merchant_ids,
            decisions=s1_result.decisions,
            design_vectors=design_vectors,
            hurdle=s0_result.outputs.hurdle_coefficients,
            dispersion=s0_result.outputs.dispersion_coefficients,
        )

        logger.info(
            "Segment1A S2 deterministic context built (merchants=%d)",
            len(deterministic_context.rows),
        )

        s2_result = self._s2_runner.run(
            base_path=base_path,
            deterministic=deterministic_context,
        )

        logger.info(
            "Segment1A S2 completed (accepted_merchants=%d)",
            len(s2_result.finals),
        )

        metrics: Dict[str, float] | None = None
        validation_output_dir: Path | None = None
        validation_artifacts_path: Path | None = None
        if validate_s2:
            if validation_policy is None:
                raise err(
                    "ERR_S2_CORRIDOR_POLICY_MISSING",
                    "validation policy path must be supplied when validate_s2=True",
                )
            validation_output_dir = (
                base_path
                / "validation"
                / f"parameter_hash={deterministic_context.parameter_hash}"
                / f"run_id={deterministic_context.run_id}"
                / "s2"
            )
            metrics = validate_nb_run(
                base_path=base_path,
                deterministic=deterministic_context,
                expected_finals=s2_result.finals,
                policy=validation_policy,
                output_dir=validation_output_dir,
            )
            logger.info("Segment1A S2 validation passed")

        catalogue_path = write_nb_catalogue(
            base_path=base_path,
            parameter_hash=s2_result.deterministic.parameter_hash,
            multi_merchant_ids=hurdle_context.multi_merchant_ids,
            metrics=metrics,
        )
        if metrics is not None:
            validation_artifacts_path = publish_s2_validation_artifacts(
                base_path=base_path,
                manifest_fingerprint=s2_result.deterministic.manifest_fingerprint,
                metrics=metrics,
                validation_output_dir=validation_output_dir,
            )
        nb_context = build_s2_context(
            s2_result,
            metrics=metrics,
            catalogue_path=catalogue_path,
            validation_artifacts_path=validation_artifacts_path,
        )

        rule_ladder_path = param_mapping.get("policy.s3.rule_ladder.yaml")
        if rule_ladder_path is None:
            raise err(
                "ERR_S3_AUTHORITY_MISSING",
                "parameter 'policy.s3.rule_ladder.yaml' is required for S3",
            )
        multi_ids = set(s1_result.multi_merchant_ids)
        merchant_rows = (
            s0_result.sealed.context.merchants.merchants.sort("merchant_id").to_dicts()
        )
        merchant_profiles: list[MerchantProfile] = []
        for row in merchant_rows:
            merchant_id = int(row["merchant_id"])
            if merchant_id not in multi_ids:
                continue
            merchant_profiles.append(
                MerchantProfile(
                    merchant_id=merchant_id,
                    home_country_iso=str(row["home_country_iso"]),
                    mcc=str(row["mcc"]),
                    channel=str(row["channel_sym"]),
                )
            )
        merchant_currency_inputs = tuple(
            MerchantCurrencyInput(
                merchant_id=int(row["merchant_id"]),
                home_country_iso=str(row["home_country_iso"]),
                share_vector=None,
            )
            for row in merchant_rows
        )

        if not merchant_profiles:
            raise err(
                "ERR_S3_PRECONDITION",
                "no multi-site merchants available for S3",
            )

        base_weight_path = param_mapping.get("policy.s3.base_weight.yaml")
        thresholds_path = param_mapping.get("policy.s3.thresholds.yaml")

        s3_toggles = S3FeatureToggles(
            priors_enabled=s3_priors,
            integerisation_enabled=s3_integerisation,
            sequencing_enabled=s3_sequencing,
        )
        s3_toggles.validate()

        if s3_toggles.priors_enabled and base_weight_path is None:
            raise err(
                "ERR_S3_AUTHORITY_MISSING",
                "policy.s3.base_weight.yaml required when priors are enabled",
            )

        s3_deterministic = build_s3_deterministic_context(
            parameter_hash=s2_result.deterministic.parameter_hash,
            manifest_fingerprint=s2_result.deterministic.manifest_fingerprint,
            run_id=s2_result.deterministic.run_id,
            seed=s2_result.deterministic.seed,
            merchant_profiles=merchant_profiles,
            decisions=s1_result.decisions,
            nb_finals=s2_result.finals,
            iso_countries=s0_result.sealed.context.iso_countries,
            rule_ladder_spec=S3ArtefactSpec(
                artefact_id="policy.s3.rule_ladder.yaml",
                path=rule_ladder_path,
            ),
            iso_countries_spec=S3ArtefactSpec(
                artefact_id="iso3166_canonical_2024",
                path=iso_table.expanduser().resolve(),
            ),
            base_weight_spec=(
                S3ArtefactSpec(
                    artefact_id="policy.s3.base_weight.yaml",
                    path=base_weight_path,
                )
                if base_weight_path is not None
                else None
            ),
            thresholds_spec=(
                S3ArtefactSpec(
                    artefact_id="policy.s3.thresholds.yaml",
                    path=thresholds_path,
                )
                if thresholds_path is not None
                else None
            ),
        )

        logger.info(
            "Segment1A S3 deterministic context built (merchants=%d)",
            len(s3_deterministic.merchants),
        )

        base_weight_policy = None
        if s3_toggles.priors_enabled:
            base_weight_policy = load_base_weight_policy(
                base_weight_path,
                iso_countries=s3_deterministic.iso_countries,
            )

        thresholds_policy = None
        if thresholds_path is not None:
            thresholds_policy = load_thresholds_policy(
                thresholds_path,
                iso_countries=s3_deterministic.iso_countries,
            )

        s3_result = self._s3_runner.run(
            base_path=base_path,
            deterministic=s3_deterministic,
            rule_ladder_path=rule_ladder_path,
            toggles=s3_toggles,
            base_weight_policy=base_weight_policy,
            thresholds_policy=thresholds_policy,
        )

        logger.info(
            "Segment1A S3 completed (merchants=%d)",
            len(s3_deterministic.merchants),
        )

        s3_metrics: Dict[str, float] | None = None
        s3_validation_artifacts_path: Path | None = None
        s3_validation_passed: bool | None = None
        s3_failed_merchants: Dict[int, str] | None = None
        s3_diagnostics: Tuple[Mapping[str, object], ...] | None = None
        if validate_s3:
            try:
                validation = validate_s3_outputs(
                    deterministic=s3_deterministic,
                    candidate_set_path=s3_result.candidate_set_path,
                    rule_ladder_path=rule_ladder_path,
                    toggles=s3_toggles,
                    base_weight_policy=base_weight_policy,
                    thresholds_policy=thresholds_policy,
                    base_weight_priors_path=s3_result.base_weight_priors_path,
                    integerised_counts_path=s3_result.integerised_counts_path,
                    site_sequence_path=s3_result.site_sequence_path,
                )
            except S0Error as exc:
                s3_validation_passed = False
                logger.exception("Segment1A S3 validation failed")
                s3_validation_artifacts_path = publish_s3_validation_artifacts(
                    base_path=base_path,
                    manifest_fingerprint=s3_result.deterministic.manifest_fingerprint,
                    metrics=None,
                    passed=False,
                    failed_merchants={},
                    error_message=str(exc),
                    diagnostics=None,
                )
                raise
            else:
                s3_metrics = dict(validation.metrics)
                s3_validation_passed = validation.passed
                s3_failed_merchants = dict(validation.failed_merchants)
                s3_diagnostics = tuple(validation.diagnostics)
                logger.info(
                    "Segment1A S3 validation %s",
                    "passed" if s3_validation_passed else "completed with issues",
                )
                s3_validation_artifacts_path = publish_s3_validation_artifacts(
                    base_path=base_path,
                    manifest_fingerprint=s3_result.deterministic.manifest_fingerprint,
                    metrics=s3_metrics,
                    passed=s3_validation_passed,
                    failed_merchants=s3_failed_merchants,
                    diagnostics=validation.diagnostics,
                )
                if s3_validation_artifacts_path is not None:
                    logger.info(
                        "Segment1A S3 validation artefacts %s",
                        s3_validation_artifacts_path,
                    )
        else:
            logger.info("Segment1A S3 validation skipped (validate_s3=False)")

        hyperparams_path = param_mapping.get('crossborder_hyperparams.yaml')
        if hyperparams_path is None:
            raise err(
                "ERR_S4_POLICY_INVALID",
                "parameter 'crossborder_hyperparams.yaml' required for S4",
            )

        feature_path = feature_path_input
        s4_deterministic, _ = build_s4_deterministic_context(
            parameter_hash=s2_result.deterministic.parameter_hash,
            manifest_fingerprint=s2_result.deterministic.manifest_fingerprint,
            run_id=s2_result.deterministic.run_id,
            seed=s2_result.deterministic.seed,
            hyperparams_path=hyperparams_path,
            nb_finals=s2_result.finals,
            hurdle_decisions=s1_result.decisions,
            crossborder_flags=s0_result.outputs.crossborder_flags,
            candidate_set_path=s3_result.candidate_set_path,
            feature_view_path=feature_path,
        )

        s4_result = self._s4_runner.run(
            base_path=base_path,
            deterministic=s4_deterministic,
        )

        s4_metrics: Dict[str, float] | None = None
        s4_validation_passed: bool | None = None
        s4_validation_artifacts_path: Path | None = None
        validation_output_dir = (
            s4_validation_output.expanduser().resolve() if s4_validation_output else None
        )
        if validate_s4:
            try:
                s4_metrics = validate_s4_run(
                    base_path=base_path,
                    deterministic=s4_result.deterministic,
                    expected_outcomes=s4_result.finals,
                    output_dir=validation_output_dir,
                )
                s4_validation_passed = True
            except S0Error as exc:
                s4_validation_passed = False
                logger.exception("Segment1A S4 validation failed")
                raise
            else:
                s4_validation_artifacts_path = publish_s4_validation_artifacts(
                    base_path=base_path,
                    manifest_fingerprint=s4_result.deterministic.manifest_fingerprint,
                    metrics=s4_metrics,
                    validation_output_dir=validation_output_dir,
                )
        else:
            logger.info("Segment1A S4 validation skipped (validate_s4=False)")

        s4_context = build_s4_context(
            s4_result,
            metrics=s4_metrics,
            validation_passed=s4_validation_passed,
            validation_artifacts_path=s4_validation_artifacts_path,
        )

        repo_root = get_repo_root()

        def _resolve_reference_path(path: Path | None) -> Path | None:
            if path is None:
                return None
            return (path if path.is_absolute() else (repo_root / path)).resolve()

        s5_deterministic = S5DeterministicContext(
            parameter_hash=s2_result.deterministic.parameter_hash,
            manifest_fingerprint=s2_result.deterministic.manifest_fingerprint,
            run_id=s2_result.deterministic.run_id,
            seed=s2_result.deterministic.seed,
            policy_path=s5_policy_path,
            merchants=merchant_currency_inputs,
            settlement_shares_path=_resolve_reference_path(
                S5_DEFAULT_PATHS.settlement_shares
            ),
            ccy_country_shares_path=_resolve_reference_path(
                S5_DEFAULT_PATHS.ccy_country_shares
            ),
            iso_legal_tender_path=_resolve_reference_path(
                S5_DEFAULT_PATHS.iso_legal_tender
            ),
        )

        s5_result = self._s5_runner.run(
            base_path=base_path,
            deterministic=s5_deterministic,
            emit_sparse_flag=True,
        )
        s5_context = build_s5_context(s5_result)

        logger.info(
            "Segment1A S5 completed (weights=%s, policy_digest=%s)",
            s5_result.weights_path,
            s5_context.policy_digest,
        )

        s3_context = build_s3_context(
            s3_result,
            metrics=s3_metrics,
            validation_passed=s3_validation_passed,
            validation_failed_merchants=s3_failed_merchants,
            validation_artifacts_path=s3_validation_artifacts_path,
            validation_diagnostics=s3_diagnostics,
        )

        logger.info(
            "Segment1A orchestrator finished (run_id=%s)",
            s2_result.deterministic.run_id,
        )
        return Segment1ARunResult(
            s0_result=s0_result,
            s1_result=s1_result,
            s2_result=s2_result,
            hurdle_context=hurdle_context,
            nb_context=nb_context,
            s3_result=s3_result,
            s3_context=s3_context,
            s4_result=s4_result,
            s4_context=s4_context,
            s5_result=s5_result,
            s5_context=s5_context,
        )


__all__ = [
    "HurdleStateContext",
    "S2StateContext",
    "S3StateContext",
    "S4StateContext",
    "S5StateContext",
    "Segment1ARunResult",
    "Segment1AOrchestrator",
    "build_hurdle_context",
    "build_s2_context",
    "build_s3_context",
    "build_s4_context",
    "build_s5_context",
]
