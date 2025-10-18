"""Context dataclasses and builders for the Segment 1A scenario runner."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Mapping, Optional, Tuple

from engine.layers.l1.seg_1A.s0_foundations.l2.runner import S0RunResult
from engine.layers.l1.seg_1A.s1_hurdle.l2.runner import HurdleDecision, S1RunResult
from engine.layers.l1.seg_1A.s1_hurdle.l3.catalogue import GatedStream
from engine.layers.l1.seg_1A.s2_nb_outlets.l2.deterministic import S2DeterministicContext
from engine.layers.l1.seg_1A.s2_nb_outlets.l2.runner import NBFinalRecord, S2RunResult
from engine.layers.l1.seg_1A.s3_crossborder_universe import (
    S3DeterministicContext,
    S3RunResult,
)
from engine.layers.l1.seg_1A.s4_ztp_target.contexts import S4DeterministicContext
from engine.layers.l1.seg_1A.s4_ztp_target.l2 import S4RunResult, ZTPFinalRecord
from engine.layers.l1.seg_1A.s5_currency_weights import (
    S5DeterministicContext,
    S5RunOutputs,
)
from engine.layers.l1.seg_1A.s6_foreign_selection.contexts import S6DeterministicContext
from engine.layers.l1.seg_1A.s6_foreign_selection.runner import S6RunOutputs
from engine.layers.l1.seg_1A.s7_integer_allocation.contexts import S7DeterministicContext
from engine.layers.l1.seg_1A.s7_integer_allocation.runner import S7RunOutputs
from engine.layers.l1.seg_1A.s7_integer_allocation.types import MerchantAllocationResult
from engine.layers.l1.seg_1A.s8_outlet_catalogue.contexts import S8DeterministicContext
from engine.layers.l1.seg_1A.s8_outlet_catalogue.runner import S8RunOutputs
from engine.layers.l1.seg_1A.s9_validation.contexts import S9DeterministicContext
from engine.layers.l1.seg_1A.s9_validation.runner import S9RunOutputs

__all__ = [
    "HurdleStateContext",
    "S2StateContext",
    "S3StateContext",
    "S4StateContext",
    "S5StateContext",
    "S6StateContext",
    "S7StateContext",
    "S8StateContext",
    "S9StateContext",
    "Segment1ARunResult",
    "build_hurdle_context",
    "build_s2_context",
    "build_s3_context",
    "build_s4_context",
    "build_s5_context",
    "build_s6_context",
    "build_s7_context",
    "build_s8_context",
    "build_s9_context",
]


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
    stage_log_path: Path | None
    metrics: Mapping[str, object]
    per_currency_metrics: Tuple[Mapping[str, object], ...]


def build_s5_context(outputs: S5RunOutputs) -> S5StateContext:
    """Construct the downstream context bundle for S5 outputs."""

    metadata = outputs.policy
    return S5StateContext(
        deterministic=outputs.deterministic,
        weights_path=outputs.weights_path,
        sparse_flag_path=outputs.sparse_flag_path,
        receipt_path=outputs.receipt_path
        or outputs.weights_path.parent / "S5_VALIDATION.json",
        policy_digest=metadata.digest_hex,
        policy_path=metadata.path,
        policy_semver=metadata.semver,
        policy_version=metadata.version,
        merchant_currency_path=outputs.merchant_currency_path,
        stage_log_path=outputs.stage_log_path,
        metrics=dict(outputs.metrics),
        per_currency_metrics=tuple(outputs.per_currency_metrics),
    )


@dataclass(frozen=True)
class S6StateContext:
    """Context bundle produced after S6 foreign-set selection."""

    deterministic: S6DeterministicContext
    events_path: Path | None
    trace_path: Path | None
    membership_path: Path | None
    policy_digest: str
    policy_path: Path
    policy_semver: str
    policy_version: str
    events_expected: int
    events_written: int
    shortfall_count: int
    reason_code_counts: Mapping[str, int]
    membership_rows: int
    trace_events: int
    trace_reconciled: bool
    log_all_candidates: bool
    rng_isolation_ok: bool
    validation_payload: Mapping[str, object] | None
    validation_passed: bool | None
    metrics: Mapping[str, object]
    metrics_log_path: Path | None


def build_s6_context(
    outputs: S6RunOutputs,
    *,
    validation_payload: Mapping[str, object] | None,
    validation_passed: bool | None,
) -> S6StateContext:
    """Construct the downstream context bundle for S6 outputs."""

    return S6StateContext(
        deterministic=outputs.deterministic,
        events_path=outputs.events_path,
        trace_path=outputs.trace_path,
        membership_path=outputs.membership_path,
        policy_digest=outputs.policy_digest,
        policy_path=outputs.deterministic.policy_path,
        policy_semver=outputs.policy.policy_semver,
        policy_version=outputs.policy.policy_version,
        events_expected=outputs.events_expected,
        events_written=outputs.events_written,
        shortfall_count=outputs.shortfall_count,
        reason_code_counts=dict(outputs.reason_code_counts),
        membership_rows=outputs.membership_rows,
        trace_events=outputs.trace_events,
        trace_reconciled=outputs.trace_reconciled,
        log_all_candidates=outputs.log_all_candidates,
        rng_isolation_ok=outputs.rng_isolation_ok,
        validation_payload=validation_payload,
        validation_passed=validation_passed,
        metrics=dict(outputs.metrics),
        metrics_log_path=outputs.metrics_log_path,
    )


@dataclass(frozen=True)
class S7StateContext:
    """Context bundle produced after S7 integer allocation."""

    deterministic: S7DeterministicContext
    results: Tuple[MerchantAllocationResult, ...]
    policy_digest: str
    artefact_digests: Mapping[str, str]
    residual_events_path: Path
    dirichlet_events_path: Path | None
    trace_path: Path
    residual_events: int
    dirichlet_events: int
    trace_events: int
    metrics: Mapping[str, object]

    @property
    def parameter_hash(self) -> str:
        return self.deterministic.parameter_hash

    @property
    def manifest_fingerprint(self) -> str:
        return self.deterministic.manifest_fingerprint

    @property
    def run_id(self) -> str:
        return self.deterministic.run_id


def build_s7_context(outputs: S7RunOutputs) -> S7StateContext:
    """Construct the downstream context bundle for S7 outputs."""

    return S7StateContext(
        deterministic=outputs.deterministic,
        results=tuple(outputs.results),
        policy_digest=outputs.policy_digest,
        artefact_digests=dict(outputs.artefact_digests),
        residual_events_path=outputs.residual_events_path,
        dirichlet_events_path=outputs.dirichlet_events_path,
        trace_path=outputs.trace_path,
        residual_events=outputs.residual_events,
        dirichlet_events=outputs.dirichlet_events,
        trace_events=outputs.trace_events,
        metrics=dict(outputs.metrics),
    )


@dataclass(frozen=True)
class S8StateContext:
    """Context bundle produced after S8 outlet catalogue materialisation."""

    deterministic: S8DeterministicContext
    catalogue_path: Path
    sequence_finalize_path: Path | None
    sequence_overflow_path: Path | None
    validation_bundle_path: Path | None
    stage_log_path: Path | None
    metrics: Mapping[str, object]
    auxiliary_paths: Mapping[str, Path] | None


def build_s8_context(outputs: S8RunOutputs) -> S8StateContext:
    """Construct the downstream context bundle for S8 outputs."""

    return S8StateContext(
        deterministic=outputs.deterministic,
        catalogue_path=outputs.catalogue_path,
        sequence_finalize_path=outputs.sequence_finalize_path,
        sequence_overflow_path=outputs.sequence_overflow_path,
        validation_bundle_path=outputs.validation_bundle_path,
        stage_log_path=outputs.stage_log_path,
        metrics=dict(outputs.metrics.__dict__),
        auxiliary_paths=dict(outputs.auxiliary_paths or {}),
    )


@dataclass(frozen=True)
class S9StateContext:
    """Context bundle produced after S9 validation."""

    deterministic: S9DeterministicContext
    result: Mapping[str, object]
    failures: Tuple[Mapping[str, object], ...]
    bundle_path: Path
    passed_flag_path: Path | None
    stage_log_path: Path


def build_s9_context(outputs: S9RunOutputs) -> S9StateContext:
    """Construct the downstream context bundle for S9 outputs."""

    return S9StateContext(
        deterministic=outputs.deterministic,
        result=dict(outputs.result.summary),
        failures=tuple(outputs.result.failures),
        bundle_path=outputs.bundle_path,
        passed_flag_path=outputs.passed_flag_path,
        stage_log_path=outputs.stage_log_path,
    )


@dataclass(frozen=True)
class Segment1ARunResult:
    """Combined result for running Segment 1A states S0 through S9."""

    s0_result: S0RunResult
    s1_result: S1RunResult
    s2_result: S2RunResult
    s3_result: S3RunResult
    s4_result: S4RunResult
    s5_result: S5RunOutputs
    s6_result: S6RunOutputs
    s7_result: S7RunOutputs
    s8_result: S8RunOutputs
    s9_result: S9RunOutputs
    hurdle_context: HurdleStateContext
    nb_context: S2StateContext
    s3_context: S3StateContext
    s4_context: S4StateContext
    s5_context: S5StateContext
    s6_context: S6StateContext
    s7_context: S7StateContext
    s8_context: S8StateContext
    s9_context: S9StateContext
