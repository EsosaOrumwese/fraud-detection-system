"""Persistence helpers for S9 validation outputs."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence
import time

from ..s0_foundations.exceptions import err
from . import constants as c
from .contexts import S9DeterministicContext, S9ValidationResult

__all__ = ["PersistConfig", "write_validation_bundle", "write_stage_log"]


@dataclass(frozen=True)
class PersistConfig:
    """Configuration for persisting S9 outputs."""

    base_path: Path
    manifest_fingerprint: str


def write_validation_bundle(
    *,
    context: S9DeterministicContext,
    result: S9ValidationResult,
    config: PersistConfig,
) -> tuple[Path, Path | None]:
    """Materialise the validation bundle and optional `_passed.flag`."""

    bundle_root = (
        config.base_path
        / "data"
        / "layer1"
        / "1A"
        / "validation"
        / f"fingerprint={config.manifest_fingerprint}"
    ).resolve()
    bundle_root.parent.mkdir(parents=True, exist_ok=True)

    staging_dir = bundle_root.parent / f"_tmp.{uuid.uuid4().hex}"
    staging_dir.mkdir(parents=True, exist_ok=False)

    try:
        created_utc_ns = time.time_ns()
        manifest_path = staging_dir / "MANIFEST.json"
        _write_json(
            manifest_path,
            _build_manifest_payload(
                context=context,
                created_utc_ns=created_utc_ns,
                artifact_count=0,  # placeholder, overwritten post index build
            ),
        )
        _write_json(
            staging_dir / "parameter_hash_resolved.json",
            {"parameter_hash": context.parameter_hash},
        )
        _write_json(
            staging_dir / "manifest_fingerprint_resolved.json",
            {"manifest_fingerprint": context.manifest_fingerprint},
        )
        _write_json(
            staging_dir / "rng_accounting.json",
            result.rng_accounting,
        )
        _write_json(
            staging_dir / "s9_summary.json",
            {
                **result.summary,
                "metrics": asdict(result.metrics),
            },
        )
        _write_json(
            staging_dir / "egress_checksums.json",
            _build_egress_checksums(
                context.source_paths.get(c.DATASET_OUTLET_CATALOGUE, ()),
                base_path=context.base_path,
            ),
        )
        index_entries = _build_index_entries(staging_dir)
        _write_json(
            manifest_path,
            _build_manifest_payload(
                context=context,
                created_utc_ns=created_utc_ns,
                artifact_count=len(index_entries),
            ),
        )
        _write_json(staging_dir / "index.json", index_entries)

        passed_flag_path: Path | None = None
        if result.passed and not result.failures:
            digest = _compute_bundle_digest(staging_dir, index_entries)
            passed_flag_path = staging_dir / "_passed.flag"
            passed_flag_path.write_text(f"sha256_hex = {digest}\n", encoding="ascii")

        _atomic_replace(staging_dir, bundle_root)
        final_flag_path = bundle_root / passed_flag_path.name if passed_flag_path is not None else None
        return bundle_root, final_flag_path
    except Exception:
        if staging_dir.exists():
            _rmtree(staging_dir)
        raise


def write_stage_log(
    *,
    path: Path,
    records: Iterable[Mapping[str, object]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True))
            handle.write("\n")


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _build_egress_checksums(files: Sequence[Path], *, base_path: Path) -> Mapping[str, object]:
    entries = []
    for file_path in files:
        if not file_path.exists():
            continue
        try:
            relative_path = file_path.resolve().relative_to(base_path.resolve())
            path_str = relative_path.as_posix()
        except ValueError:
            path_str = file_path.name
        entries.append(
            {
                "path": path_str,
                "sha256": _sha256_file(file_path),
                "size_bytes": file_path.stat().st_size,
            }
        )
    composite = hashlib.sha256()
    for entry in sorted(entries, key=lambda item: item["path"]):
        composite.update(entry["sha256"].encode("ascii"))
    return {"files": entries, "composite_sha256": composite.hexdigest()}


def _build_index_entries(bundle_dir: Path) -> Sequence[Mapping[str, object]]:
    entries = []
    for path in sorted(bundle_dir.iterdir()):
        if path.name == "_passed.flag":
            continue
        if path.is_file():
            entries.append(
                {
                    "artifact_id": path.stem,
                    "kind": _infer_artifact_kind(path),
                    "path": path.name,
                }
            )
    return entries


def _compute_bundle_digest(bundle_dir: Path, index_entries: Sequence[Mapping[str, object]]) -> str:
    hasher = hashlib.sha256()
    for entry in sorted(index_entries, key=lambda item: item["path"]):
        file_path = bundle_dir / entry["path"]
        if not file_path.exists():
            raise err("E_BUNDLE_FILE_MISSING", f"expected bundle file missing: {entry['path']}")
        with file_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                hasher.update(chunk)
    return hasher.hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_replace(staging_dir: Path, target_dir: Path) -> None:
    if target_dir.exists():
        _rmtree(target_dir)
    staging_dir.rename(target_dir)


def _rmtree(path: Path) -> None:
    if not path.exists():
        return
    for child in path.iterdir():
        if child.is_dir():
            _rmtree(child)
        else:
            child.unlink()
    path.rmdir()


def _build_manifest_payload(
    *,
    context: S9DeterministicContext,
    created_utc_ns: int,
    artifact_count: int,
) -> Mapping[str, object]:
    payload: dict[str, object] = {
        "version": "1A.validation.v1",
        "manifest_fingerprint": context.manifest_fingerprint,
        "parameter_hash": context.parameter_hash,
        "seed": context.seed,
        "run_id": context.run_id,
        "created_utc_ns": created_utc_ns,
        "artifact_count": artifact_count,
    }
    upstream = context.upstream_manifest or {}
    for key in ("git_commit_hex", "compiler_flags", "math_profile_id", "numeric_policy_version"):
        if key in upstream:
            payload[key] = upstream[key]
    payload.setdefault(
        "compiler_flags",
        {
            "rounding": "RNE",
            "fma": False,
            "ftz": False,
            "fast_math": False,
            "blas": "unknown",
        },
    )
    return payload


def _infer_artifact_kind(path: Path) -> str:
    if path.name == "MANIFEST.json" or path.name.endswith("_summary.json"):
        return "summary"
    if path.suffix == ".json":
        return "table"
    return "text"
