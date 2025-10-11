"""Materialisation helpers for S0 outputs (S0.10).

The orchestration layer collects the in-memory outputs (eligibility flags,
design matrices, diagnostics) and delegates the boring-but-essential work of
partition checks, parquet writes, validation bundle construction and RNG audit
logging to this module.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional, TYPE_CHECKING

import polars as pl

from ..exceptions import err
from ..l1.context import RunContext
from ..l1.design import DispersionCoefficients, HurdleCoefficients
from ..l1.numeric import NumericPolicyAttestation
from ..l1.rng import PhiloxEngine, PhiloxState

if TYPE_CHECKING:
    from ..l2.runner import SealedFoundations


@dataclass(frozen=True)
class S0Outputs:
    """Container that groups all in-memory artefacts produced by S0."""

    crossborder_flags: pl.DataFrame
    design_matrix: pl.DataFrame
    hurdle_coefficients: HurdleCoefficients
    dispersion_coefficients: DispersionCoefficients
    diagnostics: Optional[pl.DataFrame] = None
    numeric_attestation: Optional[NumericPolicyAttestation] = None


def _ensure_directory(path: Path) -> None:
    """Create ``path`` (and parents) if it does not already exist."""
    path.mkdir(parents=True, exist_ok=True)


def _write_parquet(frame: pl.DataFrame, path: Path) -> None:
    """Write ``frame`` to ``path`` using zstd compression."""
    frame.write_parquet(path, compression="zstd")


def _write_json(payload: Mapping[str, object], path: Path) -> None:
    """Serialise ``payload`` as JSON with stable ordering."""
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)


def _write_jsonl(path: Path, rows: list[Mapping[str, object]]) -> None:
    """Write a JSON Lines file from an iterable of mapping rows."""
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True))
            handle.write("\n")


def refresh_validation_bundle_flag(bundle_dir: Path) -> None:
    """Recompute the validation bundle digest and overwrite ``_passed.flag``."""

    files_for_hash = sorted(
        (
            path
            for path in bundle_dir.rglob("*")
            if path.is_file() and path.name != "_passed.flag"
        ),
        key=lambda path: path.relative_to(bundle_dir).as_posix(),
    )
    digest = hashlib.sha256()
    for file_path in files_for_hash:
        digest.update(file_path.read_bytes())
    (bundle_dir / "_passed.flag").write_text(
        f"sha256_hex = {digest.hexdigest()}\n",
        encoding="utf-8",
    )


def _assert_partition_value(
    frame: pl.DataFrame,
    *,
    column: str,
    expected: str,
    dataset: str,
) -> None:
    """Ensure ``frame[column]`` contains only ``expected`` (if non-empty)."""
    if column not in frame.columns:
        raise err("E_PARTITION_COLUMN_MISSING", f"{dataset} missing column '{column}'")
    if frame.height == 0:
        return
    if not bool((frame.get_column(column) == expected).all()):
        raise err(
            "E_PARTITION_MISMATCH",
            f"{dataset} embeds {column} '{expected}' mismatch",
        )


def _audit_payload(
    engine: PhiloxEngine,
    state: PhiloxState,
    sealed: "SealedFoundations",
    *,
    seed: int,
    run_id: str,
) -> Mapping[str, object]:
    """Build the payload recorded in ``rng_audit_log.json``."""
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


def _materialise_validation_bundle(
    *,
    base_path: Path,
    sealed: "SealedFoundations",
    validation_summary: Mapping[str, object],
    outputs: S0Outputs,
) -> None:
    """Create the validation bundle, gate it with `_passed.flag`, and publish."""
    parameter_hash = sealed.parameter_hash.parameter_hash
    manifest_fingerprint = sealed.manifest_fingerprint.manifest_fingerprint
    bundle_root = base_path / "validation_bundle"
    bundle_root.mkdir(parents=True, exist_ok=True)

    temp_dir = bundle_root / f"_tmp.{uuid.uuid4().hex}"
    temp_dir.mkdir(parents=False, exist_ok=False)

    try:
        manifest_artefacts = sorted(
            sealed.manifest_fingerprint.artefacts, key=lambda d: d.basename
        )
        parameter_artefacts = sorted(
            sealed.parameter_hash.artefacts, key=lambda d: d.basename
        )

        manifest_payload: dict[str, object] = {
            "version": "1A.validation.v1",
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": parameter_hash,
            "git_commit_hex": sealed.manifest_fingerprint.git_commit_hex,
            "artifact_count": len(manifest_artefacts),
            "created_utc_ns": time.time_ns(),
            "compiler_flags": {
                "fma": False,
                "ftz": False,
                "rounding": "RNE",
                "fast_math": False,
                "blas": "none",
            },
        }
        if sealed.context.numeric_policy is not None:
            manifest_payload["numeric_policy_version"] = (
                sealed.context.numeric_policy.version
            )
        if sealed.context.math_profile is not None:
            manifest_payload["math_profile_id"] = sealed.context.math_profile.profile_id
        _write_json(manifest_payload, temp_dir / "MANIFEST.json")

        _write_json(
            {
                "parameter_hash": parameter_hash,
                "filenames_sorted": [d.basename for d in parameter_artefacts],
                "artifact_count": len(parameter_artefacts),
            },
            temp_dir / "parameter_hash_resolved.json",
        )

        _write_json(
            {
                "manifest_fingerprint": manifest_fingerprint,
                "git_commit_hex": sealed.manifest_fingerprint.git_commit_hex,
                "parameter_hash": parameter_hash,
                "artifact_count": len(manifest_artefacts),
            },
            temp_dir / "manifest_fingerprint_resolved.json",
        )

        _write_jsonl(
            temp_dir / "param_digest_log.jsonl",
            [
                {
                    "filename": digest.basename,
                    "path": str(digest.path),
                    "size_bytes": digest.size_bytes,
                    "sha256_hex": digest.sha256_hex,
                    "mtime_ns": digest.mtime_ns,
                }
                for digest in parameter_artefacts
            ],
        )

        _write_jsonl(
            temp_dir / "fingerprint_artifacts.jsonl",
            [
                {
                    "filename": digest.basename,
                    "path": str(digest.path),
                    "size_bytes": digest.size_bytes,
                    "sha256_hex": digest.sha256_hex,
                    "mtime_ns": digest.mtime_ns,
                }
                for digest in manifest_artefacts
            ],
        )

        _write_json(validation_summary, temp_dir / "validation_summary.json")

        if outputs.numeric_attestation is not None:
            (temp_dir / "numeric_policy_attest.json").write_text(
                outputs.numeric_attestation.to_json(),
                encoding="utf-8",
            )

        refresh_validation_bundle_flag(temp_dir)

        final_dir = bundle_root / f"manifest_fingerprint={manifest_fingerprint}"
        if final_dir.exists():
            shutil.rmtree(final_dir)
        temp_dir.rename(final_dir)
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


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
    """Persist parameter-scoped datasets, RNG audit logs, and the bundle."""
    if context is None:
        context = sealed.context
    parameter_hash = sealed.parameter_hash.parameter_hash
    manifest_fingerprint = sealed.manifest_fingerprint.manifest_fingerprint

    parameter_dir = base_path / "parameter_scoped" / f"parameter_hash={parameter_hash}"
    _ensure_directory(parameter_dir)
    _assert_partition_value(
        outputs.crossborder_flags,
        column="parameter_hash",
        expected=parameter_hash,
        dataset="crossborder_eligibility_flags",
    )
    if "produced_by_fingerprint" in outputs.crossborder_flags.columns:
        _assert_partition_value(
            outputs.crossborder_flags,
            column="produced_by_fingerprint",
            expected=manifest_fingerprint,
            dataset="crossborder_eligibility_flags",
        )
    _write_parquet(
        outputs.crossborder_flags,
        parameter_dir / "crossborder_eligibility_flags.parquet",
    )
    _assert_partition_value(
        outputs.design_matrix,
        column="parameter_hash",
        expected=parameter_hash,
        dataset="hurdle_design_matrix",
    )
    if "produced_by_fingerprint" in outputs.design_matrix.columns:
        _assert_partition_value(
            outputs.design_matrix,
            column="produced_by_fingerprint",
            expected=manifest_fingerprint,
            dataset="hurdle_design_matrix",
        )
    _write_parquet(
        outputs.design_matrix, parameter_dir / "hurdle_design_matrix.parquet"
    )
    if outputs.diagnostics is not None:
        _assert_partition_value(
            outputs.diagnostics,
            column="parameter_hash",
            expected=parameter_hash,
            dataset="hurdle_pi_probs",
        )
        if "produced_by_fingerprint" in outputs.diagnostics.columns:
            _assert_partition_value(
                outputs.diagnostics,
                column="produced_by_fingerprint",
                expected=manifest_fingerprint,
                dataset="hurdle_pi_probs",
            )
        _write_parquet(outputs.diagnostics, parameter_dir / "hurdle_pi_probs.parquet")

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

    _materialise_validation_bundle(
        base_path=base_path,
        sealed=sealed,
        validation_summary=validation_summary,
        outputs=outputs,
    )

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


__all__ = ["S0Outputs", "refresh_validation_bundle_flag", "write_outputs"]
