"""S3 timetable cache runner for Segment 2A."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import struct
import subprocess
import tarfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import polars as pl

try:
    import pyarrow.parquet as pq

    _HAVE_PYARROW = True
except Exception:  # pragma: no cover - optional dependency.
    pq = None
    _HAVE_PYARROW = False

import zoneinfo._common as tz_common

from engine.contracts.loader import (
    find_artifact_entry,
    find_dataset_entry,
    load_artefact_registry,
    load_dataset_dictionary,
    load_schema_pack,
)
from engine.contracts.source import ContractSource
from engine.core.config import EngineConfig
from engine.core.errors import ContractError, EngineFailure, InputResolutionError, SchemaValidationError
from engine.core.hashing import sha256_file
from engine.core.logging import add_file_handler, get_logger
from engine.core.paths import RunPaths
from engine.core.time import utc_now_rfc3339_micro
from engine.layers.l1.seg_2A.s0_gate.runner import (
    _hash_partition,
    _load_json,
    _load_yaml,
    _render_catalog_path,
    _resolve_dataset_path,
    _resolve_release_dir,
    _resolve_run_receipt,
    _validate_payload,
)


MODULE_NAME = "2A.S3.timetable"
SEGMENT = "2A"
STATE = "S3"
MIN_INSTANT = -(2**63)
_HEX64 = "0123456789abcdef"
_TZ_SOURCE_ALLOWLIST = {
    "africa",
    "antarctica",
    "asia",
    "australasia",
    "backward",
    "backzone",
    "etcetera",
    "europe",
    "factory",
    "northamerica",
    "southamerica",
    "pacificnew",
    "systemv",
    "solar87",
    "solar88",
    "solar89",
}
_S3_INDEX_CACHE_SCHEMA = "s3_tz_index_v1"
_PROGRESS_LOG_INTERVAL_SECONDS = 1.0


@dataclass(frozen=True)
class S3Result:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    output_root: Path
    run_report_path: Path


class _StepTimer:
    def __init__(self, logger) -> None:
        self._logger = logger
        self._start = time.monotonic()
        self._last = self._start

    def info(self, message: str) -> None:
        now = time.monotonic()
        elapsed = now - self._start
        delta = now - self._last
        self._last = now
        self._logger.info("%s (elapsed=%.2fs, delta=%.2fs)", message, elapsed, delta)


class _ProgressTracker:
    def __init__(self, total: Optional[int], logger, label: str) -> None:
        self._total = int(total) if total is not None else None
        self._logger = logger
        self._label = label
        self._start = time.monotonic()
        self._last_log = self._start
        self._processed = 0

    def update(self, count: int) -> None:
        self._processed += int(count)
        now = time.monotonic()
        if now - self._last_log < _PROGRESS_LOG_INTERVAL_SECONDS and not (
            self._total is not None and self._processed >= self._total
        ):
            return
        self._last_log = now
        elapsed = now - self._start
        rate = self._processed / elapsed if elapsed > 0 else 0.0
        if self._total and self._total > 0:
            remaining = max(self._total - self._processed, 0)
            eta = remaining / rate if rate > 0 else 0.0
            self._logger.info(
                "%s %s/%s (elapsed=%.2fs, rate=%.2f/s, eta=%.2fs)",
                self._label,
                self._processed,
                self._total,
                elapsed,
                rate,
                eta,
            )
        else:
            self._logger.info(
                "%s processed=%s (elapsed=%.2fs, rate=%.2f/s)",
                self._label,
                self._processed,
                elapsed,
                rate,
            )


def _emit_event(
    logger,
    event: str,
    manifest_fingerprint: str,
    severity: str,
    **fields: object,
) -> None:
    payload = {
        "event": event,
        "segment": SEGMENT,
        "state": STATE,
        "manifest_fingerprint": manifest_fingerprint,
        "severity": severity,
        "timestamp_utc": utc_now_rfc3339_micro(),
    }
    payload.update(fields)
    message = json.dumps(payload, ensure_ascii=True, sort_keys=True)
    if severity == "ERROR":
        logger.error("%s %s", event, message)
    elif severity == "WARN":
        logger.warning("%s %s", event, message)
    elif severity == "DEBUG":
        logger.debug("%s %s", event, message)
    else:
        logger.info("%s %s", event, message)


def _emit_validation(
    logger,
    manifest_fingerprint: str,
    validator_id: str,
    result: str,
    error_code: Optional[str] = None,
    detail: Optional[object] = None,
) -> None:
    if result == "fail":
        severity = "ERROR"
    elif result == "warn":
        severity = "WARN"
    else:
        severity = "DEBUG"
    payload = {"validator_id": validator_id, "result": result}
    if error_code:
        payload["error_code"] = error_code
    if detail is not None:
        payload["detail"] = detail
    _emit_event(logger, "VALIDATION", manifest_fingerprint, severity, **payload)


def _emit_failure_event(
    logger,
    code: str,
    manifest_fingerprint: str,
    parameter_hash: str,
    run_id: str,
    detail: dict,
) -> None:
    payload = {
        "event": "S3_ERROR",
        "code": code,
        "at": utc_now_rfc3339_micro(),
        "manifest_fingerprint": manifest_fingerprint,
        "parameter_hash": parameter_hash,
        "run_id": run_id,
    }
    payload.update(detail)
    logger.error("S3_ERROR %s", json.dumps(payload, ensure_ascii=True, sort_keys=True))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True), encoding="utf-8")


def _s3_index_cache_root(runs_root: Path) -> Path:
    return runs_root / "_shared_cache" / "segment_2A" / "s3_timetable"


def _s3_index_cache_dir(runs_root: Path, archive_sha256: str) -> Path:
    return _s3_index_cache_root(runs_root) / _S3_INDEX_CACHE_SCHEMA / archive_sha256.lower()


def _try_load_s3_index_cache(
    runs_root: Path,
    archive_sha256: str,
    logger,
    manifest_fingerprint: str,
) -> Optional[dict]:
    cache_dir = _s3_index_cache_dir(runs_root, archive_sha256)
    meta_path = cache_dir / "index_meta.json"
    bytes_path = cache_dir / "index_bytes.bin"
    if not meta_path.exists() or not bytes_path.exists():
        return None
    try:
        meta = _load_json(meta_path)
        if not isinstance(meta, dict):
            raise ValueError("index_meta.json payload must be an object")
        if meta.get("schema") != _S3_INDEX_CACHE_SCHEMA:
            raise ValueError("schema mismatch")
        if str(meta.get("tzdb_archive_sha256", "")).lower() != archive_sha256.lower():
            raise ValueError("archive digest mismatch")
        compiled_tzids = meta.get("compiled_tzids")
        if not isinstance(compiled_tzids, list) or not compiled_tzids:
            raise ValueError("compiled_tzids missing/empty")
        cache_bytes = bytes_path.read_bytes()
        if len(cache_bytes) != int(meta.get("rle_cache_bytes", -1)):
            raise ValueError("cache bytes length mismatch")
        digest = hashlib.sha256(cache_bytes).hexdigest()
        if digest != str(meta.get("tz_index_digest", "")):
            raise ValueError("cache digest mismatch")
        return {
            "tz_index_digest": digest,
            "cache_bytes": cache_bytes,
            "compiled_tzids": {str(tzid) for tzid in compiled_tzids},
            "tzid_count": int(meta.get("tzid_count", 0)),
            "transitions_total": int(meta.get("transitions_total", 0)),
            "offset_minutes_min": int(meta.get("offset_minutes_min", 0)),
            "offset_minutes_max": int(meta.get("offset_minutes_max", 0)),
            "rle_cache_bytes": int(meta.get("rle_cache_bytes", 0)),
            "adjustments_sample": meta.get("adjustments_sample", []),
            "adjustments_count": int(meta.get("adjustments_count", 0)),
        }
    except Exception as exc:
        _emit_event(
            logger,
            "CACHE_LOAD_WARN",
            manifest_fingerprint,
            "WARN",
            cache_dir=str(cache_dir),
            detail=str(exc),
        )
        return None


def _write_s3_index_cache(
    runs_root: Path,
    archive_sha256: str,
    cache_bytes: bytes,
    *,
    tz_index_digest: str,
    compiled_tzids: set[str],
    tzid_count: int,
    transitions_total: int,
    offset_minutes_min: int,
    offset_minutes_max: int,
    rle_cache_bytes: int,
    adjustments: list[dict],
) -> None:
    cache_dir = _s3_index_cache_dir(runs_root, archive_sha256)
    if cache_dir.exists():
        return
    cache_dir.parent.mkdir(parents=True, exist_ok=True)
    tmp_root = cache_dir.parent / f".tmp_{cache_dir.name}_{uuid.uuid4().hex}"
    tmp_root.mkdir(parents=True, exist_ok=True)
    try:
        (tmp_root / "index_bytes.bin").write_bytes(cache_bytes)
        meta = {
            "schema": _S3_INDEX_CACHE_SCHEMA,
            "tzdb_archive_sha256": archive_sha256.lower(),
            "tz_index_digest": tz_index_digest,
            "tzid_count": int(tzid_count),
            "transitions_total": int(transitions_total),
            "offset_minutes_min": int(offset_minutes_min),
            "offset_minutes_max": int(offset_minutes_max),
            "rle_cache_bytes": int(rle_cache_bytes),
            "compiled_tzids": sorted(str(tzid) for tzid in compiled_tzids),
            "adjustments_count": len(adjustments),
            "adjustments_sample": adjustments[:10],
        }
        _write_json(tmp_root / "index_meta.json", meta)
        try:
            tmp_root.replace(cache_dir)
        except FileExistsError:
            # Concurrent or prior writer won the cache key race; keep existing.
            pass
    finally:
        if tmp_root.exists():
            shutil.rmtree(tmp_root, ignore_errors=True)


def _resolve_schema_ref(entry: dict, registry_entry: Optional[dict], dataset_id: str) -> str:
    dict_ref = entry.get("schema_ref")
    registry_ref = None
    if registry_entry:
        registry_ref = registry_entry.get("schema")
        if isinstance(registry_ref, dict):
            registry_ref = registry_ref.get("index_schema_ref") or registry_ref.get("schema_ref")
    if dict_ref and registry_ref and dict_ref != registry_ref:
        raise EngineFailure(
            "F4",
            "2A-S3-080",
            STATE,
            MODULE_NAME,
            {
                "detail": "schema_ref_mismatch",
                "dataset_id": dataset_id,
                "dictionary": dict_ref,
                "registry": registry_ref,
            },
        )
    return dict_ref or registry_ref or ""


def _schema_from_pack(schema_pack: dict, path: str) -> dict:
    node: dict = schema_pack
    for part in path.strip("#/").split("/"):
        node = node[part]
    schema: dict = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": schema_pack.get("$id", ""),
        "$defs": schema_pack.get("$defs", {}),
    }
    schema.update(node)
    return schema


def _assert_schema_ref(
    schema_ref: str,
    schema_packs: dict[str, dict],
    dataset_id: str,
    logger,
    manifest_fingerprint: str,
    parameter_hash: str,
    run_id: str,
) -> None:
    if not schema_ref:
        _emit_failure_event(
            logger,
            "2A-S3-080",
            manifest_fingerprint,
            parameter_hash,
            run_id,
            {"detail": "missing_schema_ref", "dataset_id": dataset_id},
        )
        raise EngineFailure(
            "F4",
            "2A-S3-080",
            STATE,
            MODULE_NAME,
            {"detail": "missing_schema_ref", "dataset_id": dataset_id},
        )
    for prefix, pack in schema_packs.items():
        if schema_ref.startswith(prefix + "#"):
            try:
                _schema_from_pack(pack, schema_ref.split("#", 1)[1])
            except Exception as exc:
                _emit_failure_event(
                    logger,
                    "2A-S3-080",
                    manifest_fingerprint,
                    parameter_hash,
                    run_id,
                    {
                        "detail": "schema_ref_invalid",
                        "dataset_id": dataset_id,
                        "schema_ref": schema_ref,
                        "error": str(exc),
                    },
                )
                raise EngineFailure(
                    "F4",
                    "2A-S3-080",
                    STATE,
                    MODULE_NAME,
                    {"detail": "schema_ref_invalid", "dataset_id": dataset_id, "schema_ref": schema_ref},
                ) from exc
            return
    _emit_failure_event(
        logger,
        "2A-S3-080",
        manifest_fingerprint,
        parameter_hash,
        run_id,
        {"detail": "schema_ref_unknown_prefix", "dataset_id": dataset_id, "schema_ref": schema_ref},
    )
    raise EngineFailure(
        "F4",
        "2A-S3-080",
        STATE,
        MODULE_NAME,
        {"detail": "schema_ref_unknown_prefix", "dataset_id": dataset_id, "schema_ref": schema_ref},
    )


def _hex64(value: str) -> bool:
    if not value or len(value) != 64:
        return False
    return all(ch in _HEX64 for ch in value)


def _atomic_publish_dir(tmp_root: Path, final_root: Path, logger, label: str) -> None:
    if final_root.exists():
        tmp_hash, _ = _hash_partition(tmp_root)
        final_hash, _ = _hash_partition(final_root)
        if tmp_hash != final_hash:
            raise EngineFailure(
                "F4",
                "2A-S3-041",
                STATE,
                MODULE_NAME,
                {"detail": "non-identical output exists", "partition": str(final_root), "label": label},
            )
        shutil.rmtree(tmp_root)
        logger.info("S3: %s partition already exists and is identical; skipping publish.", label)
        return
    final_root.parent.mkdir(parents=True, exist_ok=True)
    tmp_root.replace(final_root)


def _load_tzid_set(path: Path) -> set[str]:
    if not path.exists():
        raise InputResolutionError(f"tz_world not found: {path}")
    if _HAVE_PYARROW:
        table = pq.read_table(path, columns=["tzid"])
        tzids = table.column("tzid").to_pylist()
        return {str(tzid) for tzid in tzids if tzid is not None}
    tzids = pl.read_parquet(path, columns=["tzid"]).get_column("tzid").to_list()
    return {str(tzid) for tzid in tzids if tzid is not None}


def _detect_zic() -> tuple[list[str], bool] | tuple[None, None]:
    if shutil.which("zic"):
        return ["zic"], False
    if os.name == "nt" and shutil.which("wsl"):
        probe = subprocess.run(["wsl", "zic", "-v"], capture_output=True, text=True)
        if probe.returncode == 0:
            return ["wsl", "zic"], True
    return None, None


def _to_wsl_path(path: Path) -> str:
    resolved = path.resolve()
    drive = resolved.drive.rstrip(":").lower()
    rest = resolved.as_posix().split(":", 1)[-1]
    return f"/mnt/{drive}{rest}"


def _safe_extract_tar(archive_path: Path, target_dir: Path) -> None:
    with tarfile.open(archive_path, "r:gz") as tar:
        for member in tar.getmembers():
            member_path = target_dir / member.name
            if not str(member_path.resolve()).startswith(str(target_dir.resolve())):
                raise EngineFailure(
                    "F4",
                    "2A-S3-020",
                    STATE,
                    MODULE_NAME,
                    {"detail": f"unsafe tar member: {member.name}"},
                )
        tar.extractall(target_dir)


def _list_tzdb_sources(root: Path) -> tuple[list[Path], Optional[Path]]:
    sources: list[Path] = []
    leaps: Optional[Path] = None
    for path in sorted(root.iterdir(), key=lambda item: item.name):
        if not path.is_file():
            continue
        if path.name.startswith("tzdb_release"):
            continue
        if path.name in {"zoneinfo_version", "zoneinfo_version.yml"}:
            continue
        if path.suffix:
            continue
        if path.name == "leapseconds":
            leaps = path
            continue
        if path.name in _TZ_SOURCE_ALLOWLIST:
            sources.append(path)
            continue
        if _looks_like_tz_source(path):
            sources.append(path)
    return sources, leaps


def _looks_like_tz_source(path: Path) -> bool:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            for _ in range(200):
                line = handle.readline()
                if not line:
                    break
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                token = stripped.split(maxsplit=1)[0]
                return token in {"Zone", "Rule", "Link"}
    except Exception:
        return False
    return False


def _compile_tzdb(
    archive_path: Path,
    tmp_base: Path,
    logger,
    manifest_fingerprint: str,
    parameter_hash: str,
    run_id: str,
) -> tuple[Path, Path]:
    zic_cmd, use_wsl = _detect_zic()
    if not zic_cmd:
        _emit_failure_event(
            logger,
            "2A-S3-020",
            manifest_fingerprint,
            parameter_hash,
            run_id,
            {"detail": "zic_unavailable"},
        )
        raise EngineFailure(
            "F4",
            "2A-S3-020",
            STATE,
            MODULE_NAME,
            {"detail": "zic_unavailable"},
        )
    tmp_base.mkdir(parents=True, exist_ok=True)
    tmp_root = tmp_base / f"s3_tzdb_{uuid.uuid4().hex}"
    tmp_root.mkdir(parents=True, exist_ok=True)
    source_dir = tmp_root / "src"
    output_dir = tmp_root / "zoneinfo"
    source_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    _safe_extract_tar(archive_path, source_dir)
    sources, leaps = _list_tzdb_sources(source_dir)
    if not sources:
        _emit_failure_event(
            logger,
            "2A-S3-020",
            manifest_fingerprint,
            parameter_hash,
            run_id,
            {"detail": "tzdb_sources_missing"},
        )
        raise EngineFailure(
            "F4",
            "2A-S3-020",
            STATE,
            MODULE_NAME,
            {"detail": "tzdb_sources_missing"},
        )
    cmd = list(zic_cmd)
    cmd.extend(["-b", "fat", "-d"])
    if use_wsl:
        cmd.append(_to_wsl_path(output_dir))
    else:
        cmd.append(str(output_dir))
    if leaps:
        cmd.append("-L")
        cmd.append(_to_wsl_path(leaps) if use_wsl else str(leaps))
    cmd.extend(_to_wsl_path(path) if use_wsl else str(path) for path in sources)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        _emit_failure_event(
            logger,
            "2A-S3-020",
            manifest_fingerprint,
            parameter_hash,
            run_id,
            {"detail": "zic_failed", "stderr": result.stderr.strip()},
        )
        raise EngineFailure(
            "F4",
            "2A-S3-020",
            STATE,
            MODULE_NAME,
            {"detail": "zic_failed"},
        )
    return output_dir, tmp_root


def _collect_tzif_paths(root: Path) -> dict[str, Path]:
    tzifs: dict[str, Path] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if not rel.parts:
            continue
        if rel.parts[0] in {"posix", "right"}:
            continue
        if rel.name in {"localtime", "posixrules"}:
            continue
        tzid = rel.as_posix()
        tzifs[tzid] = path
    return tzifs


def _offset_minutes(
    offset_seconds: int,
    tzid: str,
    instant: int,
    adjustments: list[dict],
) -> int:
    remainder = offset_seconds % 60
    if remainder:
        adjusted = int(round(offset_seconds / 60))
        adjustments.append(
            {
                "tzid": tzid,
                "transition_unix_utc": int(instant),
                "raw_seconds": int(offset_seconds),
                "adjusted_minutes": int(adjusted),
                "reasons": ["round_to_minutes"],
            }
        )
        return adjusted
    return int(offset_seconds // 60)


def _compile_tzid_index(
    tzid: str,
    tzif_path: Path,
    adjustments: list[dict],
) -> list[tuple[int, int]]:
    with tzif_path.open("rb") as handle:
        trans_idx, trans_list_utc, utcoff, _isdst, _abbr, _tz_str = tz_common.load_data(handle)
    if utcoff:
        base_seconds = int(utcoff[0])
    else:
        base_seconds = 0
    entries: list[tuple[int, int]] = []
    base_offset = _offset_minutes(base_seconds, tzid, MIN_INSTANT, adjustments)
    entries.append((MIN_INSTANT, base_offset))
    last_instant = MIN_INSTANT
    last_offset = base_offset
    for instant, idx in zip(trans_list_utc, trans_idx):
        if idx >= len(utcoff):
            raise EngineFailure(
                "F4",
                "2A-S3-020",
                STATE,
                MODULE_NAME,
                {"detail": "tzdb_transition_index_invalid", "tzid": tzid},
            )
        instant_value = int(instant)
        if instant_value <= last_instant:
            raise EngineFailure(
                "F4",
                "2A-S3-051",
                STATE,
                MODULE_NAME,
                {"detail": "transition_order_invalid", "tzid": tzid},
            )
        offset_minutes = _offset_minutes(int(utcoff[idx]), tzid, instant_value, adjustments)
        if offset_minutes == last_offset:
            continue
        entries.append((instant_value, offset_minutes))
        last_instant = instant_value
        last_offset = offset_minutes
    return entries


def _encode_index(entries: list[tuple[str, list[tuple[int, int]]]]) -> bytes:
    buffer = bytearray()
    buffer.extend(b"TZC1")
    buffer.extend(struct.pack("<H", 1))
    buffer.extend(struct.pack("<I", len(entries)))
    for tzid, transitions in entries:
        tzid_bytes = tzid.encode("ascii")
        buffer.extend(struct.pack("<H", len(tzid_bytes)))
        buffer.extend(tzid_bytes)
        buffer.extend(struct.pack("<I", len(transitions)))
        for instant, offset in transitions:
            buffer.extend(struct.pack("<q", int(instant)))
            buffer.extend(struct.pack("<i", int(offset)))
    return bytes(buffer)


def run_s3(config: EngineConfig, run_id: Optional[str] = None) -> S3Result:
    logger = get_logger("engine.layers.l1.seg_2A.s3_timetable.l2.runner")
    timer = _StepTimer(logger)
    started_monotonic = time.monotonic()
    started_utc = utc_now_rfc3339_micro()

    warnings: list[str] = []
    errors: list[dict] = []
    status = "fail"

    parameter_hash: Optional[str] = None
    manifest_fingerprint: Optional[str] = None
    receipt_path_text = ""
    tzdb_catalog_path = ""
    tz_world_catalog_path = ""
    output_catalog_path = ""
    receipt_verified_utc = ""

    output_root: Optional[Path] = None
    run_report_path: Optional[Path] = None
    adjustments: list[dict] = []
    adjustments_count = 0

    counts = {
        "tzid_count": 0,
        "transitions_total": 0,
        "offset_minutes_min": 0,
        "offset_minutes_max": 0,
        "rle_cache_bytes": 0,
    }
    coverage = {"world_tzids": 0, "cache_tzids": 0, "missing_count": 0, "missing_sample": []}

    try:
        receipt_path, receipt = _resolve_run_receipt(config.runs_root, run_id)
        run_id = receipt.get("run_id")
        if not run_id:
            raise InputResolutionError("run_receipt missing run_id.")
        if receipt_path.parent.name != run_id:
            raise InputResolutionError("run_receipt path does not match embedded run_id.")
        parameter_hash = receipt.get("parameter_hash")
        manifest_fingerprint = receipt.get("manifest_fingerprint")
        if manifest_fingerprint is None or parameter_hash is None:
            raise InputResolutionError("run_receipt missing manifest_fingerprint or parameter_hash.")

        run_paths = RunPaths(config.runs_root, run_id)
        run_log_path = run_paths.run_root / f"run_log_{run_id}.log"
        add_file_handler(run_log_path)
        logger.info("S3: run log initialized at %s", run_log_path)

        source = ContractSource(config.contracts_root, config.contracts_layout)
        dict_path, dictionary = load_dataset_dictionary(source, "2A")
        registry_path, registry = load_artefact_registry(source, "2A")
        schema_2a_path, schema_2a = load_schema_pack(source, "2A", "2A")
        schema_ingress_path, schema_ingress = load_schema_pack(source, "1A", "ingress.layer1")
        schema_layer1_path, schema_layer1 = load_schema_pack(source, "1A", "layer1")
        logger.info(
            "Contracts layout=%s root=%s dictionary=%s registry=%s schemas=%s,%s,%s",
            config.contracts_layout,
            config.contracts_root,
            dict_path,
            registry_path,
            schema_2a_path,
            schema_ingress_path,
            schema_layer1_path,
        )

        tokens = {
            "manifest_fingerprint": str(manifest_fingerprint),
            "fingerprint": str(manifest_fingerprint),
        }

        def _dataset_entry(dataset_id: str) -> dict:
            try:
                return find_dataset_entry(dictionary, dataset_id).entry
            except ContractError as exc:
                raise EngineFailure(
                    "F4",
                    "2A-S3-010",
                    STATE,
                    MODULE_NAME,
                    {"detail": "missing_dictionary_entry", "dataset_id": dataset_id},
                ) from exc

        def _registry_entry(name: str) -> dict:
            try:
                return find_artifact_entry(registry, name).entry
            except ContractError as exc:
                raise EngineFailure(
                    "F4",
                    "2A-S3-010",
                    STATE,
                    MODULE_NAME,
                    {"detail": "missing_registry_entry", "artifact": name},
                ) from exc

        entries = {
            "s0_gate_receipt_2A": _dataset_entry("s0_gate_receipt_2A"),
            "sealed_inputs_2A": _dataset_entry("sealed_inputs_2A"),
            "tzdb_release": _dataset_entry("tzdb_release"),
            "tz_world_2025a": _dataset_entry("tz_world_2025a"),
            "tz_timetable_cache": _dataset_entry("tz_timetable_cache"),
        }
        registry_entries = {
            "s0_gate_receipt_2A": _registry_entry("s0_gate_receipt_2A"),
            "tzdb_release": _registry_entry("tzdb_release"),
            "tz_world_2025a": _registry_entry("tz_world_2025a"),
            "tz_timetable_cache": _registry_entry("tz_timetable_cache"),
        }

        schema_packs = {
            "schemas.2A.yaml": schema_2a,
            "schemas.ingress.layer1.yaml": schema_ingress,
            "schemas.layer1.yaml": schema_layer1,
        }

        for dataset_id, entry in entries.items():
            registry_entry = registry_entries.get(dataset_id)
            schema_ref = _resolve_schema_ref(entry, registry_entry, dataset_id)
            _assert_schema_ref(
                schema_ref,
                schema_packs,
                dataset_id,
                logger,
                str(manifest_fingerprint),
                str(parameter_hash),
                run_id,
            )

        receipt_path = _resolve_dataset_path(
            entries["s0_gate_receipt_2A"],
            run_paths,
            config.external_roots,
            tokens,
        )
        receipt_path_text = _render_catalog_path(entries["s0_gate_receipt_2A"], tokens)
        try:
            receipt_payload = _load_json(receipt_path)
        except InputResolutionError as exc:
            _emit_failure_event(
                logger,
                "2A-S3-001",
                str(manifest_fingerprint),
                str(parameter_hash),
                run_id,
                {"detail": "missing_s0_receipt", "path": str(receipt_path)},
            )
            raise EngineFailure(
                "F4",
                "2A-S3-001",
                STATE,
                MODULE_NAME,
                {"detail": "missing_s0_receipt", "path": str(receipt_path)},
            ) from exc

        try:
            _validate_payload(
                schema_2a,
                "validation/s0_gate_receipt_v1",
                receipt_payload,
                ref_packs={"schemas.layer1.yaml": schema_layer1},
            )
        except SchemaValidationError as exc:
            _emit_failure_event(
                logger,
                "2A-S3-001",
                str(manifest_fingerprint),
                str(parameter_hash),
                run_id,
                {"detail": exc.errors},
            )
            raise EngineFailure(
                "F4",
                "2A-S3-001",
                STATE,
                MODULE_NAME,
                {"detail": exc.errors},
            ) from exc
        if receipt_payload.get("manifest_fingerprint") != str(manifest_fingerprint):
            _emit_failure_event(
                logger,
                "2A-S3-001",
                str(manifest_fingerprint),
                str(parameter_hash),
                run_id,
                {"detail": "receipt_fingerprint_mismatch"},
            )
            raise EngineFailure(
                "F4",
                "2A-S3-001",
                STATE,
                MODULE_NAME,
                {"detail": "receipt_fingerprint_mismatch"},
            )
        receipt_verified_utc = receipt_payload.get("verified_at_utc") or ""
        _emit_validation(logger, str(manifest_fingerprint), "V-01", "pass")

        sealed_inputs_path = _resolve_dataset_path(
            entries["sealed_inputs_2A"],
            run_paths,
            config.external_roots,
            tokens,
        )
        sealed_inputs_payload = _load_json(sealed_inputs_path)
        if not isinstance(sealed_inputs_payload, list):
            raise EngineFailure(
                "F4",
                "2A-S3-010",
                STATE,
                MODULE_NAME,
                {"detail": "sealed_inputs_invalid", "path": str(sealed_inputs_path)},
            )
        sealed_by_id = {row.get("asset_id"): row for row in sealed_inputs_payload if isinstance(row, dict)}
        tzdb_row = sealed_by_id.get("tzdb_release")
        tz_world_row = sealed_by_id.get("tz_world_2025a")
        if not tzdb_row:
            _emit_failure_event(
                logger,
                "2A-S3-010",
                str(manifest_fingerprint),
                str(parameter_hash),
                run_id,
                {"detail": "tzdb_release_not_sealed"},
            )
            raise EngineFailure(
                "F4",
                "2A-S3-010",
                STATE,
                MODULE_NAME,
                {"detail": "tzdb_release_not_sealed"},
            )
        if not tz_world_row:
            _emit_failure_event(
                logger,
                "2A-S3-012",
                str(manifest_fingerprint),
                str(parameter_hash),
                run_id,
                {"detail": "tz_world_not_sealed"},
            )
            raise EngineFailure(
                "F4",
                "2A-S3-012",
                STATE,
                MODULE_NAME,
                {"detail": "tz_world_not_sealed"},
            )

        release_tag = tzdb_row.get("version_tag") or tzdb_row.get("basename")
        if release_tag:
            tokens["release_tag"] = str(release_tag)

        tzdb_root = _resolve_dataset_path(entries["tzdb_release"], run_paths, config.external_roots, tokens)
        tz_world_path = _resolve_dataset_path(entries["tz_world_2025a"], run_paths, config.external_roots, tokens)
        tzdb_catalog_path = _render_catalog_path(entries["tzdb_release"], tokens)
        tz_world_catalog_path = _render_catalog_path(entries["tz_world_2025a"], tokens)

        release_dir, release_meta_path = _resolve_release_dir(tzdb_root)
        tzdb_payload = (
            _load_json(release_meta_path)
            if release_meta_path.suffix == ".json"
            else _load_yaml(release_meta_path)
        )
        try:
            _validate_payload(
                schema_2a,
                "ingress/tzdb_release_v1",
                tzdb_payload,
                ref_packs={"schemas.layer1.yaml": schema_layer1},
            )
        except SchemaValidationError as exc:
            _emit_failure_event(
                logger,
                "2A-S3-011",
                str(manifest_fingerprint),
                str(parameter_hash),
                run_id,
                {"detail": exc.errors},
            )
            raise EngineFailure(
                "F4",
                "2A-S3-011",
                STATE,
                MODULE_NAME,
                {"detail": exc.errors},
            ) from exc

        tzdb_release_tag = tzdb_payload.get("release_tag")
        tzdb_archive_sha256 = tzdb_payload.get("archive_sha256")
        if not tzdb_release_tag or not tzdb_archive_sha256:
            _emit_failure_event(
                logger,
                "2A-S3-011",
                str(manifest_fingerprint),
                str(parameter_hash),
                run_id,
                {"detail": "tzdb_release_tag_missing"},
            )
            raise EngineFailure(
                "F4",
                "2A-S3-011",
                STATE,
                MODULE_NAME,
                {"detail": "tzdb_release_tag_missing"},
            )
        if release_tag and str(tzdb_release_tag) != str(release_tag):
            _emit_failure_event(
                logger,
                "2A-S3-011",
                str(manifest_fingerprint),
                str(parameter_hash),
                run_id,
                {
                    "detail": "tzdb_release_tag_mismatch",
                    "sealed": str(release_tag),
                    "metadata": str(tzdb_release_tag),
                },
            )
            raise EngineFailure(
                "F4",
                "2A-S3-011",
                STATE,
                MODULE_NAME,
                {"detail": "tzdb_release_tag_mismatch"},
            )
        if not _hex64(str(tzdb_archive_sha256)):
            _emit_failure_event(
                logger,
                "2A-S3-013",
                str(manifest_fingerprint),
                str(parameter_hash),
                run_id,
                {"detail": "tzdb_archive_sha256_invalid", "archive_sha256": tzdb_archive_sha256},
            )
            raise EngineFailure(
                "F4",
                "2A-S3-013",
                STATE,
                MODULE_NAME,
                {"detail": "tzdb_archive_sha256_invalid"},
            )
        archive_candidates = list(release_dir.glob("*.tar.gz")) + list(release_dir.glob("*.tgz"))
        if len(archive_candidates) != 1:
            _emit_failure_event(
                logger,
                "2A-S3-010",
                str(manifest_fingerprint),
                str(parameter_hash),
                run_id,
                {"detail": "tzdb_archive_missing", "candidates": [p.name for p in archive_candidates]},
            )
            raise EngineFailure(
                "F4",
                "2A-S3-010",
                STATE,
                MODULE_NAME,
                {"detail": "tzdb_archive_missing"},
            )
        archive_path = archive_candidates[0]
        archive_digest = sha256_file(archive_path)
        if archive_digest.sha256_hex != str(tzdb_archive_sha256):
            _emit_failure_event(
                logger,
                "2A-S3-013",
                str(manifest_fingerprint),
                str(parameter_hash),
                run_id,
                {
                    "detail": "tzdb_archive_sha256_mismatch",
                    "expected": str(tzdb_archive_sha256),
                    "computed": archive_digest.sha256_hex,
                },
            )
            raise EngineFailure(
                "F4",
                "2A-S3-013",
                STATE,
                MODULE_NAME,
                {"detail": "tzdb_archive_sha256_mismatch"},
            )
        _emit_validation(logger, str(manifest_fingerprint), "V-03", "pass")

        tzid_set = _load_tzid_set(tz_world_path)
        coverage["world_tzids"] = len(tzid_set)
        _emit_validation(logger, str(manifest_fingerprint), "V-02b", "pass")

        _emit_event(
            logger,
            "INPUTS",
            str(manifest_fingerprint),
            "INFO",
            tzdb_release=tzdb_catalog_path,
            tz_world=tz_world_catalog_path,
        )

        cache_hit = False
        compiled_tzids: set[str] = set()
        cache_bytes: bytes = b""
        tz_index_digest = ""
        cache_payload = _try_load_s3_index_cache(
            run_paths.runs_root,
            str(tzdb_archive_sha256),
            logger,
            str(manifest_fingerprint),
        )
        if cache_payload is not None:
            cache_hit = True
            cache_bytes = cache_payload["cache_bytes"]
            tz_index_digest = cache_payload["tz_index_digest"]
            compiled_tzids = cache_payload["compiled_tzids"]
            counts["tzid_count"] = cache_payload["tzid_count"]
            counts["transitions_total"] = cache_payload["transitions_total"]
            counts["offset_minutes_min"] = cache_payload["offset_minutes_min"]
            counts["offset_minutes_max"] = cache_payload["offset_minutes_max"]
            counts["rle_cache_bytes"] = cache_payload["rle_cache_bytes"]
            adjustments = list(cache_payload.get("adjustments_sample", []))
            adjustments_count = int(cache_payload.get("adjustments_count", len(adjustments)))
            _emit_event(
                logger,
                "CACHE_HIT",
                str(manifest_fingerprint),
                "INFO",
                cache_key=str(tzdb_archive_sha256).lower(),
                tzid_count=counts["tzid_count"],
                rle_cache_bytes=counts["rle_cache_bytes"],
            )
            _emit_validation(logger, str(manifest_fingerprint), "V-04", "pass")
        else:
            tzdb_tmp_root: Optional[Path] = None
            compiled_entries: list[tuple[str, list[tuple[int, int]]]] = []
            offset_min: Optional[int] = None
            offset_max: Optional[int] = None
            transitions_total = 0
            try:
                output_dir, tzdb_tmp_root = _compile_tzdb(
                    archive_path,
                    run_paths.tmp_root,
                    logger,
                    str(manifest_fingerprint),
                    str(parameter_hash),
                    run_id,
                )
                tzifs = _collect_tzif_paths(output_dir)
                if not tzifs:
                    _emit_failure_event(
                        logger,
                        "2A-S3-021",
                        str(manifest_fingerprint),
                        str(parameter_hash),
                        run_id,
                        {"detail": "compiled_index_empty"},
                    )
                    raise EngineFailure(
                        "F4",
                        "2A-S3-021",
                        STATE,
                        MODULE_NAME,
                        {"detail": "compiled_index_empty"},
                    )

                _emit_event(
                    logger,
                    "TZDB_PARSE",
                    str(manifest_fingerprint),
                    "INFO",
                    tzid_count=len(tzifs),
                )
                _emit_validation(logger, str(manifest_fingerprint), "V-04", "pass")

                tzids_sorted = sorted(tzifs.keys())
                progress = _ProgressTracker(len(tzids_sorted), logger, "S3 tzids")
                for tzid in tzids_sorted:
                    tzif_path = tzifs[tzid]
                    transitions = _compile_tzid_index(tzid, tzif_path, adjustments)
                    for instant, offset in transitions:
                        if instant is None or offset is None:
                            raise EngineFailure(
                                "F4",
                                "2A-S3-055",
                                STATE,
                                MODULE_NAME,
                                {"detail": "nonfinite_value", "tzid": tzid},
                            )
                        is_sentinel = int(instant) == MIN_INSTANT
                        if not is_sentinel and (offset < -900 or offset > 900):
                            raise EngineFailure(
                                "F4",
                                "2A-S3-052",
                                STATE,
                                MODULE_NAME,
                                {"detail": "offset_out_of_range", "tzid": tzid, "offset_minutes": offset},
                            )
                        offset_min = offset if offset_min is None else min(offset_min, offset)
                        offset_max = offset if offset_max is None else max(offset_max, offset)
                    transitions_total += max(len(transitions) - 1, 0)
                    compiled_entries.append((tzid, transitions))
                    progress.update(1)
            finally:
                if tzdb_tmp_root is not None:
                    shutil.rmtree(tzdb_tmp_root, ignore_errors=True)

            compiled_tzids = {tzid for tzid, _ in compiled_entries}
            counts["tzid_count"] = len(compiled_entries)
            counts["transitions_total"] = transitions_total
            counts["offset_minutes_min"] = offset_min if offset_min is not None else 0
            counts["offset_minutes_max"] = offset_max if offset_max is not None else 0
            cache_bytes = _encode_index(compiled_entries)
            tz_index_digest = hashlib.sha256(cache_bytes).hexdigest()
            counts["rle_cache_bytes"] = len(cache_bytes)
            adjustments_count = len(adjustments)
            _write_s3_index_cache(
                run_paths.runs_root,
                str(tzdb_archive_sha256),
                cache_bytes,
                tz_index_digest=tz_index_digest,
                compiled_tzids=compiled_tzids,
                tzid_count=counts["tzid_count"],
                transitions_total=counts["transitions_total"],
                offset_minutes_min=counts["offset_minutes_min"],
                offset_minutes_max=counts["offset_minutes_max"],
                rle_cache_bytes=counts["rle_cache_bytes"],
                adjustments=adjustments,
            )
            _emit_event(
                logger,
                "CACHE_STORE",
                str(manifest_fingerprint),
                "INFO",
                cache_key=str(tzdb_archive_sha256).lower(),
                tzid_count=counts["tzid_count"],
                rle_cache_bytes=counts["rle_cache_bytes"],
            )

        _emit_event(
            logger,
            "COMPILE",
            str(manifest_fingerprint),
            "INFO",
            tzid_count=counts["tzid_count"],
            transitions_total=counts["transitions_total"],
            offset_minutes_min=counts["offset_minutes_min"],
            offset_minutes_max=counts["offset_minutes_max"],
            cache_hit=cache_hit,
        )
        _emit_validation(logger, str(manifest_fingerprint), "V-05", "pass")

        missing = sorted(tzid_set - compiled_tzids)
        coverage["cache_tzids"] = len(compiled_tzids)
        coverage["missing_count"] = len(missing)
        coverage["missing_sample"] = missing[:20]
        if missing:
            _emit_failure_event(
                logger,
                "2A-S3-053",
                str(manifest_fingerprint),
                str(parameter_hash),
                run_id,
                {"detail": "tzid_coverage_mismatch", "missing_sample": coverage["missing_sample"]},
            )
            raise EngineFailure(
                "F4",
                "2A-S3-053",
                STATE,
                MODULE_NAME,
                {"detail": "tzid_coverage_mismatch", "missing_sample": coverage["missing_sample"]},
            )
        _emit_event(
            logger,
            "COVERAGE",
            str(manifest_fingerprint),
            "INFO",
            world_tzids=coverage["world_tzids"],
            cache_tzids=coverage["cache_tzids"],
            missing_count=coverage["missing_count"],
        )
        _emit_validation(logger, str(manifest_fingerprint), "V-15", "pass")
        _emit_event(
            logger,
            "CANONICALISE",
            str(manifest_fingerprint),
            "INFO",
            tz_index_digest=tz_index_digest,
            rle_cache_bytes=counts["rle_cache_bytes"],
        )

        output_root = _resolve_dataset_path(
            entries["tz_timetable_cache"],
            run_paths,
            config.external_roots,
            tokens,
        )
        output_catalog_path = _render_catalog_path(entries["tz_timetable_cache"], tokens)
        tmp_root = run_paths.tmp_root / f"s3_timetable_{uuid.uuid4().hex}"
        tmp_root.mkdir(parents=True, exist_ok=True)

        cache_name = "tz_cache_v1.bin"
        cache_path = tmp_root / cache_name
        cache_path.write_bytes(cache_bytes)
        if counts["rle_cache_bytes"] <= 0:
            raise EngineFailure(
                "F4",
                "2A-S3-060",
                STATE,
                MODULE_NAME,
                {"detail": "cache_bytes_missing"},
            )
        if not cache_path.exists():
            raise EngineFailure(
                "F4",
                "2A-S3-061",
                STATE,
                MODULE_NAME,
                {"detail": "cache_file_missing", "path": str(cache_path)},
            )
        if cache_path.stat().st_size != counts["rle_cache_bytes"]:
            raise EngineFailure(
                "F4",
                "2A-S3-062",
                STATE,
                MODULE_NAME,
                {
                    "detail": "cache_size_mismatch",
                    "expected": counts["rle_cache_bytes"],
                    "actual": cache_path.stat().st_size,
                },
            )

        created_utc = receipt_verified_utc
        if not created_utc:
            raise EngineFailure(
                "F4",
                "2A-S3-042",
                STATE,
                MODULE_NAME,
                {"detail": "missing_created_utc"},
            )

        manifest = {
            "manifest_fingerprint": str(manifest_fingerprint),
            "tzdb_release_tag": str(tzdb_release_tag),
            "tzdb_archive_sha256": str(tzdb_archive_sha256),
            "tz_index_digest": tz_index_digest,
            "rle_cache_bytes": counts["rle_cache_bytes"],
            "created_utc": created_utc,
        }
        try:
            _validate_payload(
                schema_2a,
                "cache/tz_timetable_cache",
                manifest,
                ref_packs={"schemas.layer1.yaml": schema_layer1},
            )
        except SchemaValidationError as exc:
            raise EngineFailure(
                "F4",
                "2A-S3-030",
                STATE,
                MODULE_NAME,
                {"detail": exc.errors},
            ) from exc
        if manifest["manifest_fingerprint"] != str(manifest_fingerprint):
            raise EngineFailure(
                "F4",
                "2A-S3-040",
                STATE,
                MODULE_NAME,
                {"detail": "path_embed_mismatch"},
            )
        if manifest["created_utc"] != receipt_verified_utc:
            raise EngineFailure(
                "F4",
                "2A-S3-042",
                STATE,
                MODULE_NAME,
                {"detail": "created_utc_mismatch"},
            )

        manifest_path = tmp_root / "tz_timetable_cache.json"
        _write_json(manifest_path, manifest)

        _emit_validation(logger, str(manifest_fingerprint), "V-06", "pass")
        _emit_validation(logger, str(manifest_fingerprint), "V-07", "pass")
        _emit_validation(logger, str(manifest_fingerprint), "V-08", "pass")
        _emit_validation(logger, str(manifest_fingerprint), "V-09", "pass")
        _emit_validation(logger, str(manifest_fingerprint), "V-10", "pass")
        _emit_validation(logger, str(manifest_fingerprint), "V-11", "pass")
        _emit_validation(logger, str(manifest_fingerprint), "V-12", "pass")
        _emit_validation(logger, str(manifest_fingerprint), "V-13", "pass")
        _emit_validation(logger, str(manifest_fingerprint), "V-14", "pass")

        _atomic_publish_dir(tmp_root, output_root, logger, "tz_timetable_cache")
        _emit_validation(logger, str(manifest_fingerprint), "V-16", "pass")
        _emit_event(
            logger,
            "EMIT",
            str(manifest_fingerprint),
            "INFO",
            output_path=output_catalog_path,
            format="files",
        )
        status = "pass"
        return S3Result(
            run_id=run_id,
            parameter_hash=str(parameter_hash),
            manifest_fingerprint=str(manifest_fingerprint),
            output_root=output_root,
            run_report_path=run_report_path,
        )
    except EngineFailure as exc:
        errors.append({"code": exc.failure_code, "message": str(exc), "context": exc.detail})
        raise
    finally:
        finished_utc = utc_now_rfc3339_micro()
        if run_id and manifest_fingerprint:
            run_paths = RunPaths(config.runs_root, run_id)
            run_report_path = (
                run_paths.run_root
                / "reports"
                / "layer1"
                / "2A"
                / "state=S3"
                / f"manifest_fingerprint={manifest_fingerprint}"
                / "s3_run_report.json"
            )
            run_report = {
                "segment": SEGMENT,
                "state": STATE,
                "status": status,
                "manifest_fingerprint": str(manifest_fingerprint),
                "started_utc": started_utc,
                "finished_utc": finished_utc,
                "durations": {"wall_ms": int((time.monotonic() - started_monotonic) * 1000)},
                "s0": {"receipt_path": receipt_path_text, "verified_at_utc": receipt_verified_utc},
                "tzdb": {
                    "release_tag": str(tzdb_release_tag) if "tzdb_release_tag" in locals() else "",
                    "archive_sha256": str(tzdb_archive_sha256) if "tzdb_archive_sha256" in locals() else "",
                    "digest_verified": True,
                },
                "inputs": {
                    "tzdb_release": {"path": tzdb_catalog_path},
                    "tz_world": {"path": tz_world_catalog_path},
                },
                "compiled": {
                    "tzid_count": counts["tzid_count"],
                    "transitions_total": counts["transitions_total"],
                    "offset_minutes_min": counts["offset_minutes_min"],
                    "offset_minutes_max": counts["offset_minutes_max"],
                    "tz_index_digest": locals().get("tz_index_digest", ""),
                    "rle_cache_bytes": counts["rle_cache_bytes"],
                },
                "coverage": coverage,
                "output": {
                    "path": output_catalog_path,
                    "created_utc": receipt_verified_utc,
                    "files": [{"name": "tz_cache_v1.bin", "bytes": counts["rle_cache_bytes"]}],
                },
                "warnings": warnings,
                "errors": errors,
            }
            if adjustments_count > 0:
                run_report["adjustments"] = {
                    "count": int(adjustments_count),
                    "sample": adjustments[:10],
                }
            _write_json(run_report_path, run_report)
            logger.info("S3: run-report written %s", run_report_path)
