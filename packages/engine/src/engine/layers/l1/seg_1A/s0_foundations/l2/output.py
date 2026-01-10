"""Materialisation helpers for S0 outputs (S0.10).

The orchestration layer collects the in-memory outputs (eligibility flags,
design matrices, diagnostics) and delegates the boring-but-essential work of
partition checks, parquet writes, validation bundle construction and RNG audit
logging to this module.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import re
import shutil
import time
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence, TYPE_CHECKING

import polars as pl
import yaml

from ..exceptions import err
from ..l1.context import RunContext
from ..l1.design import DispersionCoefficients, HurdleCoefficients
from ..l1.numeric import NumericPolicyAttestation
from ..l1.rng import PhiloxEngine, PhiloxState
from ...shared.dictionary import get_repo_root, load_dictionary, resolve_dataset_path
from ...shared.passed_flag import format_passed_flag

if TYPE_CHECKING:
    from ..l2.runner import SealedFoundations

_UNKNOWN_SCHEMA_REF = "unknown"


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


def _relative_or_absolute_path(path: Path) -> str:
    """Return a repo-root relative path when possible, else an absolute path."""
    resolved = path.resolve()
    repo_root = get_repo_root()
    try:
        return resolved.relative_to(repo_root).as_posix()
    except ValueError:
        return str(resolved)


def _load_registry_index() -> dict[str, Mapping[str, object]]:
    repo_root = get_repo_root()
    registry_path = (
        repo_root
        / "docs"
        / "model_spec"
        / "data-engine"
        / "layer-1"
        / "specs"
        / "contracts"
        / "1A"
        / "artefact_registry_1A.yaml"
    )
    if not registry_path.exists():
        return {}
    payload = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    index: dict[str, Mapping[str, object]] = {}
    for block in payload.get("subsegments", []):
        if not isinstance(block, Mapping):
            continue
        artifacts = block.get("artifacts") or []
        if not isinstance(artifacts, Iterable):
            continue
        for artifact in artifacts:
            if not isinstance(artifact, Mapping):
                continue
            name = artifact.get("name")
            if isinstance(name, str) and name not in index:
                index[name] = artifact
    return index


def _template_to_glob(template: str) -> str:
    normalized = template.replace("\\", "/").strip()
    normalized = re.sub(r"\{[^}]+\}", "*", normalized)
    if normalized.endswith("/"):
        normalized = normalized.rstrip("/") + "/**"
    return normalized


def _template_to_regex(template: str) -> re.Pattern[str]:
    normalized = template.replace("\\", "/").strip()
    trailing = normalized.endswith("/")
    normalized = normalized.rstrip("/")
    escaped = re.escape(normalized)
    pattern = re.sub(r"\\{([^}]+)\\}", r"(?P<\1>[^/]+)", escaped)
    if trailing:
        pattern = f"{pattern}(?:/.*)?"
    return re.compile(f"^{pattern}$")


def _match_registry_entry(
    rel_path: str, registry_index: Mapping[str, Mapping[str, object]]
) -> tuple[str | None, Mapping[str, object] | None, Mapping[str, str]]:
    for name in sorted(registry_index):
        artifact = registry_index[name]
        template = artifact.get("path")
        if not isinstance(template, str) or not template.strip():
            continue
        glob_pattern = _template_to_glob(template)
        if not fnmatch.fnmatch(rel_path, glob_pattern):
            continue
        match = _template_to_regex(template).match(rel_path)
        token_map = match.groupdict() if match else {}
        return name, artifact, token_map
    return None, None, {}


def _resolve_version_tag(
    *,
    token_map: Mapping[str, str],
    artifact: Mapping[str, object] | None,
    fallback: str,
) -> str:
    for key in ("version", "config_version", "policy_version"):
        if key in token_map:
            return str(token_map[key])
    if artifact is not None:
        for key in ("version", "semver"):
            value = artifact.get(key)
            if isinstance(value, str) and value.strip() and "{" not in value:
                return value.strip()
    return fallback


def _resolve_schema_ref(artifact: Mapping[str, object] | None) -> str | None:
    if artifact is None:
        return None
    for key in ("schema_ref", "schema"):
        value = artifact.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _build_sealed_inputs(sealed: "SealedFoundations") -> list[Mapping[str, object]]:
    repo_root = get_repo_root()
    registry_index = _load_registry_index()
    rows: list[Mapping[str, object]] = []
    for digest in sealed.manifest_fingerprint.artefacts:
        resolved = digest.path.resolve()
        try:
            rel_path = resolved.relative_to(repo_root).as_posix()
        except ValueError:
            rel_path = resolved.as_posix()
        name, artifact, token_map = _match_registry_entry(rel_path, registry_index)
        asset_id = name or digest.basename
        version_tag = _resolve_version_tag(
            token_map=token_map, artifact=artifact, fallback=digest.basename
        )
        schema_ref = _resolve_schema_ref(artifact)
        entry: dict[str, object] = {
            "asset_id": asset_id,
            "version_tag": version_tag,
            "sha256_hex": digest.sha256_hex,
            "path": _relative_or_absolute_path(resolved),
            "partition": {key: str(value) for key, value in token_map.items()},
        }
        if schema_ref:
            entry["schema_ref"] = schema_ref
        rows.append(entry)
    rows.sort(key=lambda row: (row.get("asset_id", ""), row.get("path", "")))
    return rows


def _build_sealed_inputs_receipt(
    sealed_inputs: Sequence[Mapping[str, object]],
) -> list[Mapping[str, object]]:
    receipt: list[Mapping[str, object]] = []
    for entry in sealed_inputs:
        partition = entry.get("partition")
        partition_keys: list[str] = []
        if isinstance(partition, Mapping):
            partition_keys = sorted(str(key) for key in partition.keys())
        schema_ref = entry.get("schema_ref") or _UNKNOWN_SCHEMA_REF
        receipt.append(
            {
                "id": entry.get("asset_id", ""),
                "partition": partition_keys,
                "schema_ref": schema_ref,
            }
        )
    return receipt


def _utc_timestamp() -> str:
    """Return an RFC-3339 timestamp with microsecond precision."""
    return (
        datetime.now(timezone.utc)
        .replace(tzinfo=timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    )


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
        format_passed_flag(digest.hexdigest()),
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
        "ts_utc": _utc_timestamp(),
        "seed": seed,
        "run_id": run_id,
        "algorithm": "philox2x64-10",
        "parameter_hash": sealed.parameter_hash.parameter_hash,
        "manifest_fingerprint": sealed.manifest_fingerprint.manifest_fingerprint,
        "build_commit": sealed.manifest_fingerprint.git_commit_hex,
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
    dictionary = load_dictionary()
    final_dir = resolve_dataset_path(
        "validation_bundle_1A",
        base_path=base_path,
        template_args={"manifest_fingerprint": manifest_fingerprint},
        dictionary=dictionary,
    )
    bundle_root = final_dir.parent
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
                    "path": _relative_or_absolute_path(digest.path),
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
                    "path": _relative_or_absolute_path(digest.path),
                    "size_bytes": digest.size_bytes,
                    "sha256": digest.sha256_hex,
                }
                for digest in manifest_artefacts
            ],
        )

        _write_json(validation_summary, temp_dir / "validation_summary.json")

        if outputs.numeric_attestation is None:
            raise err("E_NUMERIC_POLICY_MISSING", "numeric_policy_attest required")
        (temp_dir / "numeric_policy_attest.json").write_text(
            outputs.numeric_attestation.to_json(),
            encoding="utf-8",
        )

        refresh_validation_bundle_flag(temp_dir)

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
    dictionary = load_dictionary()

    crossborder_path = resolve_dataset_path(
        "crossborder_eligibility_flags",
        base_path=base_path,
        template_args={"parameter_hash": parameter_hash},
        dictionary=dictionary,
    )
    crossborder_path.parent.mkdir(parents=True, exist_ok=True)
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
        crossborder_path,
    )
    design_path = resolve_dataset_path(
        "hurdle_design_matrix",
        base_path=base_path,
        template_args={"parameter_hash": parameter_hash},
        dictionary=dictionary,
    )
    design_path.parent.mkdir(parents=True, exist_ok=True)
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
        outputs.design_matrix,
        design_path,
    )
    if outputs.diagnostics is not None:
        diag_path = resolve_dataset_path(
            "hurdle_pi_probs",
            base_path=base_path,
            template_args={"parameter_hash": parameter_hash},
            dictionary=dictionary,
        )
        diag_path.parent.mkdir(parents=True, exist_ok=True)
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
        _write_parquet(outputs.diagnostics, diag_path)

    abort_log_path = resolve_dataset_path(
        "merchant_abort_log",
        base_path=base_path,
        template_args={"parameter_hash": parameter_hash},
        dictionary=dictionary,
    )
    abort_log_path.parent.mkdir(parents=True, exist_ok=True)
    abort_log_schema = {
        "merchant_id": pl.Int64,
        "state": pl.String,
        "module": pl.String,
        "reason": pl.String,
        "ts_utc": pl.String,
    }
    _write_parquet(pl.DataFrame(schema=abort_log_schema), abort_log_path)

    sealed_inputs = _build_sealed_inputs(sealed)
    sealed_inputs_path = resolve_dataset_path(
        "sealed_inputs_1A",
        base_path=base_path,
        template_args={"manifest_fingerprint": manifest_fingerprint},
        dictionary=dictionary,
    )
    sealed_inputs_path.parent.mkdir(parents=True, exist_ok=True)
    sealed_inputs_path.write_text(
        json.dumps(sealed_inputs, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    gate_receipt_path = resolve_dataset_path(
        "s0_gate_receipt_1A",
        base_path=base_path,
        template_args={"manifest_fingerprint": manifest_fingerprint},
        dictionary=dictionary,
    )
    gate_receipt_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(
        {
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": parameter_hash,
            "run_id": run_id,
            "sealed_inputs": _build_sealed_inputs_receipt(sealed_inputs),
        },
        gate_receipt_path,
    )

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

    audit_jsonl_path = resolve_dataset_path(
        "rng_audit_log",
        base_path=base_path,
        template_args={
            "seed": seed,
            "parameter_hash": parameter_hash,
            "run_id": run_id,
        },
        dictionary=dictionary,
    )
    audit_jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    root_state = philox_engine.root_state
    audit_payload = _audit_payload(
        philox_engine, root_state, sealed, seed=seed, run_id=run_id
    )
    _write_jsonl(audit_jsonl_path, [audit_payload])


__all__ = ["S0Outputs", "refresh_validation_bundle_flag", "write_outputs"]
