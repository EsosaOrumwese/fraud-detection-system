"""Materialisation helpers for S0 outputs (S0.10)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional, TYPE_CHECKING

import polars as pl

from ..l1.context import RunContext
from ..l1.design import DispersionCoefficients, HurdleCoefficients
from ..l1.numeric import NumericPolicyAttestation
from ..l1.rng import PhiloxEngine, PhiloxState

if TYPE_CHECKING:
    from ..l2.runner import SealedFoundations


@dataclass(frozen=True)
class S0Outputs:
    crossborder_flags: pl.DataFrame
    design_matrix: pl.DataFrame
    hurdle_coefficients: HurdleCoefficients
    dispersion_coefficients: DispersionCoefficients
    diagnostics: Optional[pl.DataFrame] = None
    numeric_attestation: Optional[NumericPolicyAttestation] = None


def _ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _write_parquet(frame: pl.DataFrame, path: Path) -> None:
    frame.write_parquet(path, compression="zstd")


def _write_json(payload: Mapping[str, object], path: Path) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)


def _audit_payload(
    engine: PhiloxEngine,
    state: PhiloxState,
    sealed: "SealedFoundations",
    *,
    seed: int,
    run_id: str,
) -> Mapping[str, object]:
    return {
        "seed": seed,
        "run_id": run_id,
        "algorithm": "philox2x64-10",
        "parameter_hash": sealed.parameter_hash.parameter_hash,
        "manifest_fingerprint": sealed.manifest_fingerprint.manifest_fingerprint,
        "rng_key": state.key,
        "rng_counter_hi": state.counter_hi,
        "rng_counter_lo": state.counter_lo,
    }


def write_outputs(
    *,
    base_path: Path,
    sealed: "SealedFoundations",
    outputs: S0Outputs,
    run_id: str,
    seed: int,
    philox_engine: PhiloxEngine,
    context: Optional[RunContext] = None,
) -> None:
    if context is None:
        context = sealed.context
    parameter_hash = sealed.parameter_hash.parameter_hash
    manifest_fingerprint = sealed.manifest_fingerprint.manifest_fingerprint

    parameter_dir = base_path / "parameter_scoped" / f"parameter_hash={parameter_hash}"
    _ensure_directory(parameter_dir)
    _write_parquet(
        outputs.crossborder_flags,
        parameter_dir / "crossborder_eligibility_flags.parquet",
    )
    _write_parquet(
        outputs.design_matrix, parameter_dir / "hurdle_design_matrix.parquet"
    )
    if outputs.diagnostics is not None:
        _write_parquet(outputs.diagnostics, parameter_dir / "hurdle_pi_probs.parquet")

    validation_dir = (
        base_path / "validation_bundle" / f"manifest_fingerprint={manifest_fingerprint}"
    )
    _ensure_directory(validation_dir)
    validation_summary = {
        "parameter_hash": parameter_hash,
        "manifest_fingerprint": manifest_fingerprint,
        "datasets": {
            "crossborder_eligibility_flags": int(outputs.crossborder_flags.height),
            "hurdle_design_matrix": int(outputs.design_matrix.height),
            "hurdle_pi_probs": int(
                outputs.diagnostics.height if outputs.diagnostics is not None else 0
            ),
        },
        "run_id": run_id,
    }
    if outputs.numeric_attestation is not None:
        attestation_path = validation_dir / "numeric_policy_attest.json"
        attestation_path.write_text(
            outputs.numeric_attestation.to_json(), encoding="utf-8"
        )
        validation_summary["numeric_attestation"] = outputs.numeric_attestation.content

    _write_json(validation_summary, validation_dir / "validation_summary.json")

    rng_dir = (
        base_path
        / "rng_logs"
        / f"seed={seed}"
        / f"parameter_hash={parameter_hash}"
        / f"run_id={run_id}"
    )
    _ensure_directory(rng_dir)
    root_state = philox_engine.root_state
    _write_json(
        _audit_payload(philox_engine, root_state, sealed, seed=seed, run_id=run_id),
        rng_dir / "rng_audit_log.json",
    )


__all__ = ["S0Outputs", "write_outputs"]
