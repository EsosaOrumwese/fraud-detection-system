"""Read-only validation harness for S0 outputs (L3)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable

import polars as pl

from ..exceptions import err
from ..l2.output import S0Outputs
from ..l2.runner import SealedFoundations


def _load_parquet(path: Path) -> pl.DataFrame:
    if not path.exists():
        raise err("E_VALIDATION_MISMATCH", f"missing parquet dataset '{path.name}'")
    return pl.read_parquet(path)


def _sort_frame(frame: pl.DataFrame, keys: Iterable[str]) -> pl.DataFrame:
    return frame.sort(keys).select(frame.columns)


def _assert_frame_equal(
    expected: pl.DataFrame, observed: pl.DataFrame, *, dataset: str
) -> None:
    if expected.shape != observed.shape:
        raise err(
            "E_VALIDATION_MISMATCH",
            f"{dataset} shape mismatch expected {expected.shape} got {observed.shape}",
        )
    if expected.columns != observed.columns:
        raise err(
            "E_VALIDATION_MISMATCH",
            f"{dataset} column mismatch expected {expected.columns} got {observed.columns}",
        )
    lhs = expected.to_pandas(use_pyarrow_extension_array=True)
    rhs = observed.to_pandas(use_pyarrow_extension_array=True)
    if not lhs.equals(rhs):
        raise err("E_VALIDATION_MISMATCH", f"{dataset} content mismatch")


def _verify_pass_flag(bundle_dir: Path) -> None:
    files = sorted(p for p in bundle_dir.iterdir() if p.name != "_passed.flag")
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.read_bytes())
    flag_path = bundle_dir / "_passed.flag"
    if not flag_path.exists():
        raise err("E_VALIDATION_DIGEST", "missing _passed.flag")
    expected = f"sha256_hex = {digest.hexdigest()}"
    if flag_path.read_text(encoding="utf-8").strip() != expected:
        raise err("E_VALIDATION_DIGEST", "validation bundle digest mismatch")


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise err("E_VALIDATION_MISMATCH", f"missing JSON artefact '{path.name}'")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_outputs(
    *,
    base_path: Path,
    sealed: SealedFoundations,
    outputs: S0Outputs,
    seed: int,
    run_id: str,
) -> None:
    """Re-open persisted artefacts and ensure they match deterministic expectations."""

    parameter_hash = sealed.parameter_hash.parameter_hash
    manifest_fingerprint = sealed.manifest_fingerprint.manifest_fingerprint

    parameter_dir = base_path / "parameter_scoped" / f"parameter_hash={parameter_hash}"
    if not parameter_dir.exists():
        raise err("E_VALIDATION_MISMATCH", "parameter-scoped directory missing")

    observed_flags = _load_parquet(
        parameter_dir / "crossborder_eligibility_flags.parquet"
    )
    observed_design = _load_parquet(parameter_dir / "hurdle_design_matrix.parquet")

    expected_flags = _sort_frame(outputs.crossborder_flags, ["merchant_id"])
    expected_design = _sort_frame(outputs.design_matrix, ["merchant_id"])
    _assert_frame_equal(
        expected_flags,
        _sort_frame(observed_flags, ["merchant_id"]),
        dataset="crossborder_eligibility_flags",
    )
    _assert_frame_equal(
        expected_design,
        _sort_frame(observed_design, ["merchant_id"]),
        dataset="hurdle_design_matrix",
    )

    diag_path = parameter_dir / "hurdle_pi_probs.parquet"
    if outputs.diagnostics is not None:
        observed_diag = _load_parquet(diag_path)
        expected_diag = _sort_frame(outputs.diagnostics, ["merchant_id"])
        _assert_frame_equal(
            expected_diag,
            _sort_frame(observed_diag, ["merchant_id"]),
            dataset="hurdle_pi_probs",
        )
    elif diag_path.exists():
        raise err("E_VALIDATION_MISMATCH", "unexpected diagnostics parquet present")

    bundle_dir = (
        base_path / "validation_bundle" / f"manifest_fingerprint={manifest_fingerprint}"
    )
    if not bundle_dir.exists():
        raise err("E_VALIDATION_MISMATCH", "validation bundle missing")
    summary = _load_json(bundle_dir / "validation_summary.json")
    if summary.get("run_id") != run_id:
        raise err("E_VALIDATION_MISMATCH", "validation summary run_id mismatch")
    if summary.get("parameter_hash") != parameter_hash:
        raise err("E_VALIDATION_MISMATCH", "validation summary parameter_hash mismatch")
    if summary.get("manifest_fingerprint") != manifest_fingerprint:
        raise err("E_VALIDATION_MISMATCH", "validation summary manifest mismatch")
    _verify_pass_flag(bundle_dir)

    rng_dir = (
        base_path
        / "rng_logs"
        / f"seed={seed}"
        / f"parameter_hash={parameter_hash}"
        / f"run_id={run_id}"
    )
    audit_path = rng_dir / "rng_audit_log.json"
    if not audit_path.exists():
        raise err("E_VALIDATION_MISMATCH", "rng_audit_log.json missing")
    audit = _load_json(audit_path)
    if (
        audit.get("parameter_hash") != parameter_hash
        or audit.get("manifest_fingerprint") != manifest_fingerprint
    ):
        raise err("E_VALIDATION_MISMATCH", "rng audit lineage mismatch")

    events_root = base_path / "rng_logs" / "events"
    event_exists = any(events_root.rglob("part-00000.jsonl"))
    if not event_exists:
        raise err("E_VALIDATION_MISMATCH", "rng event logs missing")


__all__ = ["validate_outputs"]
