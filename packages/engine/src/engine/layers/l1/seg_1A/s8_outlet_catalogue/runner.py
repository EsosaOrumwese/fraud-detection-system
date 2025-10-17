"""Orchestrator for the S8 outlet catalogue pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from ..s0_foundations.l1.context import MerchantUniverse
from ..shared.dictionary import load_dictionary, resolve_dataset_path
from ..s1_hurdle.l2.runner import HurdleDecision
from ..s2_nb_outlets.l2.runner import NBFinalRecord
from ..s7_integer_allocation.types import MerchantAllocationResult
from .constants import (
    EVENT_FAMILY_SEQUENCE_FINALIZE,
    EVENT_FAMILY_SITE_SEQUENCE_OVERFLOW,
)
from .contexts import S8DeterministicContext, S8Metrics
from .kernel import build_outlet_catalogue
from .loader import load_deterministic_context
from .persist import (
    PersistConfig,
    write_outlet_catalogue,
    write_sequence_events,
    write_validation_bundle,
)
from .validate import validate_outputs


@dataclass(frozen=True)
class S8RunOutputs:
    """Materialised artefacts emitted by the S8 runner."""

    deterministic: S8DeterministicContext
    catalogue_path: Path
    sequence_finalize_path: Path | None
    sequence_overflow_path: Path | None
    validation_bundle_path: Path | None
    metrics: S8Metrics
    stage_log_path: Path | None = None
    auxiliary_paths: Mapping[str, Path] | None = None


class S8Runner:
    """Execute the S8 pipeline end-to-end."""

    def run(
        self,
        *,
        base_path: Path,
        parameter_hash: str,
        manifest_fingerprint: str,
        seed: int,
        run_id: str,
        merchant_universe: MerchantUniverse,
        hurdle_decisions: Sequence[HurdleDecision],
        nb_finals: Sequence[NBFinalRecord],
        s7_results: Sequence[MerchantAllocationResult],
        dictionary: Mapping[str, object] | None = None,
    ) -> S8RunOutputs:
        """Run the S8 pipeline using governed artefacts resolved from `base_path`."""
        base_path = Path(base_path).expanduser().resolve()
        dictionary = dictionary or load_dictionary()

        deterministic = load_deterministic_context(
            base_path=base_path,
            parameter_hash=parameter_hash,
            manifest_fingerprint=manifest_fingerprint,
            seed=seed,
            run_id=run_id,
            merchant_universe=merchant_universe,
            hurdle_decisions=hurdle_decisions,
            nb_finals=nb_finals,
            s7_results=s7_results,
            dictionary=dictionary,
        )

        rows, sequence_events, overflow_events, metrics = build_outlet_catalogue(deterministic)

        persist_config = PersistConfig(
            seed=seed,
            manifest_fingerprint=manifest_fingerprint,
            output_dir=base_path,
            parameter_hash=parameter_hash,
            run_id=run_id,
        )
        catalogue_path = write_outlet_catalogue(
            rows,
            config=persist_config,
            dictionary=dictionary,
        )
        event_paths = write_sequence_events(
            sequence_finalize=sequence_events,
            overflow_events=overflow_events,
            config=persist_config,
            dictionary=dictionary,
        )
        event_paths_for_validation = dict(event_paths)
        event_paths_for_validation["seed"] = seed

        metrics_payload, rng_accounting_payload = validate_outputs(
            base_path=base_path,
            parameter_hash=parameter_hash,
            manifest_fingerprint=manifest_fingerprint,
            seed=seed,
            run_id=run_id,
            catalogue_path=catalogue_path,
            event_paths=event_paths_for_validation,
            dictionary=dictionary,
        )
        rng_accounting_payload["pk_hash_hex"] = metrics_payload.get("pk_hash_hex", "")

        validation_dir = resolve_dataset_path(
            "validation_bundle",
            base_path=base_path,
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        validation_dir.mkdir(parents=True, exist_ok=True)
        validation_bundle_path = write_validation_bundle(
            bundle_dir=validation_dir,
            metrics_payload=metrics_payload,
            rng_accounting_payload=rng_accounting_payload,
            catalogue_path=catalogue_path,
        )

        auxiliary_paths: dict[str, Path] = {}
        for key, path in event_paths.items():
            if path is not None:
                auxiliary_paths[key] = path
        if validation_bundle_path is not None:
            auxiliary_paths["validation_bundle"] = validation_dir

        return S8RunOutputs(
            deterministic=deterministic,
            catalogue_path=catalogue_path,
            sequence_finalize_path=event_paths.get(EVENT_FAMILY_SEQUENCE_FINALIZE),
            sequence_overflow_path=event_paths.get(EVENT_FAMILY_SITE_SEQUENCE_OVERFLOW),
            validation_bundle_path=validation_bundle_path,
            metrics=metrics,
            stage_log_path=None,
            auxiliary_paths=auxiliary_paths or None,
        )


__all__ = [
    "S8RunOutputs",
    "S8Runner",
]
