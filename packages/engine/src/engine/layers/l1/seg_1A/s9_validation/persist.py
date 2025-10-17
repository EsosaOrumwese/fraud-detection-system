"""Persistence helpers for S9 validation outputs."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence
import time

import polars as pl

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
            {
                "parameter_hash": context.parameter_hash,
                "files": _sorted_lineage_filenames(context.lineage_paths.get("param_digest_log.jsonl")),
            },
        )
        _write_json(
            staging_dir / "manifest_fingerprint_resolved.json",
            {
                "manifest_fingerprint": context.manifest_fingerprint,
                "files": _sorted_lineage_filenames(context.lineage_paths.get("fingerprint_artifacts.jsonl")),
            },
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
                seed=context.seed,
                manifest_fingerprint=context.manifest_fingerprint,
            ),
        )
        index_entries = _build_index_entries(staging_dir)
        _assert_required_bundle_entries(index_entries)
        _write_json(
            manifest_path,
            _build_manifest_payload(
                context=context,
                created_utc_ns=created_utc_ns,
                artifact_count=len(index_entries),
            ),
        )
        index_path = staging_dir / "index.json"
        _write_json(index_path, index_entries)
        if not index_path.exists():
            raise err("E_BUNDLE_FILE_MISSING", "index.json missing in validation bundle")

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


def _build_egress_checksums(
    files: Sequence[Path],
    *,
    base_path: Path,
    seed: int,
    manifest_fingerprint: str,
) -> Mapping[str, object]:
    if not files:
        raise err("E_BUNDLE_FILE_MISSING", "outlet_catalogue shards missing for checksum generation")

    base_path = base_path.resolve()
    writer_sort_columns = ("merchant_id", "legal_country_iso", "site_order")
    composite = hashlib.sha256()
    entries: list[Mapping[str, object]] = []
    previous_key: tuple[int, str, int] | None = None

    sorted_files = sorted(files, key=lambda path: _relative_path_as_posix(path.resolve(), base_path))
    for file_path in sorted_files:
        resolved = file_path.resolve()
        if not resolved.exists():
            raise err("E_BUNDLE_FILE_MISSING", f"expected outlet shard missing: {file_path}")

        relative_path = _relative_path_as_posix(resolved, base_path)
        try:
            shard = pl.read_parquet(resolved, columns=list(writer_sort_columns))
        except Exception as exc:  # pragma: no cover - indicates environment/parquet corruption
            raise err(
                "E_EGRESS_CHECKSUM_READ_FAILED",
                f"failed to read outlet shard '{relative_path}' during checksum validation",
            ) from exc

        missing_columns = [column for column in writer_sort_columns if column not in shard.columns]
        if missing_columns:
            raise err(
                "E_SCHEMA_INVALID",
                f"outlet shard '{relative_path}' missing columns required for writer sort validation: {missing_columns}",
            )

        if shard.height > 0:
            key_frame = shard.select(writer_sort_columns)
            rows = key_frame.rows()
            if rows != key_frame.sort(writer_sort_columns).rows():
                raise err(
                    "E_EGRESS_WRITER_SORT",
                    f"outlet shard '{relative_path}' violates writer sort {writer_sort_columns}",
                )

            first_key = _normalised_sort_key(rows[0])
            last_key = _normalised_sort_key(rows[-1])
            if previous_key is not None and first_key < previous_key:
                raise err(
                    "E_EGRESS_WRITER_SORT",
                    f"outlet shard '{relative_path}' is out of order relative to preceding shards",
                )
            previous_key = last_key

        digest_hex, size_bytes = _hash_file_for_checksums(resolved, composite)
        entries.append(
            {
                "path": relative_path,
                "sha256_hex": digest_hex,
                "size_bytes": size_bytes,
            }
        )

    if not entries:
        raise err("E_BUNDLE_FILE_MISSING", "outlet_catalogue shards missing for checksum generation")

    return {
        "dataset_id": c.DATASET_OUTLET_CATALOGUE,
        "seed": seed,
        "manifest_fingerprint": manifest_fingerprint,
        "files": entries,
        "composite_sha256_hex": composite.hexdigest(),
    }


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
                    "mime": _infer_artifact_mime(path),
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


def _relative_path_as_posix(path: Path, base_path: Path) -> str:
    try:
        relative = path.relative_to(base_path)
        return relative.as_posix()
    except ValueError:
        return path.name


def _normalised_sort_key(values: Sequence[object]) -> tuple[int, str, int]:
    merchant_id, country_iso, site_order = values
    return int(merchant_id), str(country_iso), int(site_order)


def _hash_file_for_checksums(path: Path, composite: hashlib._Hash) -> tuple[str, int]:
    digest = hashlib.sha256()
    bytes_read = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
            composite.update(chunk)
            bytes_read += len(chunk)
    size_bytes = path.stat().st_size
    if bytes_read != size_bytes:
        raise err(
            "E_EGRESS_SIZE_MISMATCH",
            f"size mismatch detected while hashing '{path}': read {bytes_read} bytes, stat reports {size_bytes}",
        )
    return digest.hexdigest(), size_bytes


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


def _sorted_lineage_filenames(path: Path | None) -> Sequence[str]:
    if path is None or not path.exists():
        return []
    records = _read_jsonl_records(path)
    filenames = [record.get("filename") for record in records if record.get("filename")]
    return sorted(filenames)


def _read_jsonl_records(path: Path) -> Sequence[Mapping[str, object]]:
    records: list[Mapping[str, object]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                records.append(json.loads(line))
    except FileNotFoundError:
        return []
    return records


def _assert_required_bundle_entries(index_entries: Sequence[Mapping[str, object]]) -> None:
    present = {entry["path"] for entry in index_entries}
    required = c.BUNDLE_FILES - {"index.json"}
    missing = required - present
    if missing:
        raise err(
            "E_BUNDLE_FILE_MISSING",
            f"validation bundle missing required artifacts: {sorted(missing)}",
        )


def _infer_artifact_mime(path: Path) -> str:
    if path.suffix == ".json":
        return "application/json"
    if path.suffix == ".jsonl":
        return "application/jsonl"
    return "text/plain"


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
    if path.name in c.BUNDLE_INDEX_SUMMARY_FILES or path.name.endswith("_summary.json"):
        return c.BUNDLE_INDEX_KIND_SUMMARY
    if path.suffix == ".json":
        return c.BUNDLE_INDEX_KIND_TABLE
    return c.BUNDLE_INDEX_KIND_TEXT
