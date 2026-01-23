"""S4 legality (DST gaps/folds) runner for Segment 2A."""

from __future__ import annotations

import json
import shutil
import struct
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

from engine.contracts.loader import (
    find_artifact_entry,
    find_dataset_entry,
    load_artefact_registry,
    load_dataset_dictionary,
    load_schema_pack,
)
from engine.contracts.source import ContractSource
from engine.core.config import EngineConfig
from engine.core.errors import EngineFailure, InputResolutionError, SchemaValidationError
from engine.core.logging import add_file_handler, get_logger
from engine.core.paths import RunPaths
from engine.core.time import utc_now_rfc3339_micro
from engine.layers.l1.seg_2A.s0_gate.runner import (
    _hash_partition,
    _load_json,
    _render_catalog_path,
    _resolve_dataset_path,
    _resolve_run_receipt,
    _validate_payload,
)


MODULE_NAME = "2A.S4.legality"
SEGMENT = "2A"
STATE = "S4"
MIN_INSTANT = -(2**63)
CACHE_MAGIC = b"TZC1"
CACHE_VERSION = 1
CACHE_FILE = "tz_cache_v1.bin"
CACHE_MANIFEST = "tz_timetable_cache.json"
OFFSET_MIN = -900
OFFSET_MAX = 900


@dataclass(frozen=True)
class S4Result:
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
        if now - self._last_log < 0.5 and not (
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
    seed: int,
    manifest_fingerprint: str,
    severity: str,
    **fields: object,
) -> None:
    payload = {
        "event": event,
        "segment": SEGMENT,
        "state": STATE,
        "seed": seed,
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
    seed: int,
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
    _emit_event(logger, "VALIDATION", seed, manifest_fingerprint, severity, **payload)


def _emit_failure_event(
    logger,
    code: str,
    seed: int,
    manifest_fingerprint: str,
    parameter_hash: str,
    run_id: str,
    detail: dict,
) -> None:
    payload = {
        "event": "S4_ERROR",
        "code": code,
        "at": utc_now_rfc3339_micro(),
        "seed": seed,
        "manifest_fingerprint": manifest_fingerprint,
        "parameter_hash": parameter_hash,
        "run_id": run_id,
    }
    payload.update(detail)
    logger.error("S4_ERROR %s", json.dumps(payload, ensure_ascii=True, sort_keys=True))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True), encoding="utf-8")


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
            "2A-S4-010",
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
    seed: int,
    manifest_fingerprint: str,
    parameter_hash: str,
    run_id: str,
) -> None:
    if not schema_ref:
        _emit_failure_event(
            logger,
            "2A-S4-010",
            seed,
            manifest_fingerprint,
            parameter_hash,
            run_id,
            {"detail": "missing_schema_ref", "dataset_id": dataset_id},
        )
        raise EngineFailure(
            "F4",
            "2A-S4-010",
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
                    "2A-S4-010",
                    seed,
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
                    "2A-S4-010",
                    STATE,
                    MODULE_NAME,
                    {"detail": "schema_ref_invalid", "dataset_id": dataset_id, "schema_ref": schema_ref},
                ) from exc
            return
    _emit_failure_event(
        logger,
        "2A-S4-010",
        seed,
        manifest_fingerprint,
        parameter_hash,
        run_id,
        {"detail": "schema_ref_unknown_prefix", "dataset_id": dataset_id, "schema_ref": schema_ref},
    )
    raise EngineFailure(
        "F4",
        "2A-S4-010",
        STATE,
        MODULE_NAME,
        {"detail": "schema_ref_unknown_prefix", "dataset_id": dataset_id, "schema_ref": schema_ref},
    )


def _list_parquet_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if not path.exists():
        raise InputResolutionError(f"site_timezones not found: {path}")
    return sorted(path.glob("*.parquet"))


def _scan_site_timezones(path: Path) -> tuple[int, set[str], bool]:
    files = _list_parquet_files(path)
    if not files:
        return 0, set(), False
    total = 0
    tzids: set[str] = set()
    if _HAVE_PYARROW:
        for file in files:
            pq_file = pq.ParquetFile(file)
            for batch in pq_file.iter_batches(columns=["tzid"]):
                total += batch.num_rows
                values = batch.column(0).to_pylist()
                for value in values:
                    if value is not None:
                        tzids.add(str(value))
        return total, tzids, True
    df = pl.read_parquet(files, columns=["tzid"])
    total = df.height
    tzids = {str(value) for value in df.get_column("tzid").to_list() if value is not None}
    return total, tzids, True


def _decode_cache(
    cache_bytes: bytes,
    tzids_used: set[str],
    logger,
    seed: int,
    manifest_fingerprint: str,
    parameter_hash: str,
    run_id: str,
) -> tuple[int, int, set[str], int]:
    view = memoryview(cache_bytes)
    pos = 0

    def _need(size: int) -> None:
        if pos + size > len(view):
            _emit_failure_event(
                logger,
                "2A-S4-022",
                seed,
                manifest_fingerprint,
                parameter_hash,
                run_id,
                {"detail": "cache_payload_invalid", "reason": "truncated"},
            )
            raise EngineFailure(
                "F4",
                "2A-S4-022",
                STATE,
                MODULE_NAME,
                {"detail": "cache_payload_invalid"},
            )

    def _read(fmt: str) -> tuple[int, int]:
        nonlocal pos
        size = struct.calcsize(fmt)
        _need(size)
        value = struct.unpack_from(fmt, view, pos)[0]
        pos += size
        return value, pos

    _need(10)
    magic = bytes(view[0:4])
    if magic != CACHE_MAGIC:
        _emit_failure_event(
            logger,
            "2A-S4-022",
            seed,
            manifest_fingerprint,
            parameter_hash,
            run_id,
            {"detail": "cache_payload_invalid", "reason": "bad_magic"},
        )
        raise EngineFailure(
            "F4",
            "2A-S4-022",
            STATE,
            MODULE_NAME,
            {"detail": "cache_payload_invalid"},
        )
    pos = 4
    version, pos = _read("<H")
    if version != CACHE_VERSION:
        _emit_failure_event(
            logger,
            "2A-S4-022",
            seed,
            manifest_fingerprint,
            parameter_hash,
            run_id,
            {"detail": "cache_payload_invalid", "reason": "version_mismatch", "version": version},
        )
        raise EngineFailure(
            "F4",
            "2A-S4-022",
            STATE,
            MODULE_NAME,
            {"detail": "cache_payload_invalid"},
        )
    tzid_count, pos = _read("<I")

    missing = set(tzids_used)
    gap_total = 0
    fold_total = 0
    processed = 0
    progress = _ProgressTracker(len(tzids_used), logger, "S4 tzids") if tzids_used else None

    for _ in range(tzid_count):
        name_len, pos = _read("<H")
        _need(name_len)
        tzid_bytes = bytes(view[pos : pos + name_len])
        pos += name_len
        try:
            tzid = tzid_bytes.decode("ascii")
        except UnicodeDecodeError as exc:
            _emit_failure_event(
                logger,
                "2A-S4-022",
                seed,
                manifest_fingerprint,
                parameter_hash,
                run_id,
                {"detail": "cache_payload_invalid", "reason": "tzid_decode"},
            )
            raise EngineFailure(
                "F4",
                "2A-S4-022",
                STATE,
                MODULE_NAME,
                {"detail": "cache_payload_invalid"},
            ) from exc
        transition_count, pos = _read("<I")
        bytes_needed = transition_count * 12
        _need(bytes_needed)
        if tzid in missing:
            missing.remove(tzid)
            processed += 1
            if progress:
                progress.update(1)
            prev_instant: Optional[int] = None
            prev_offset: Optional[int] = None
            for _ in range(transition_count):
                instant = struct.unpack_from("<q", view, pos)[0]
                offset = struct.unpack_from("<i", view, pos + 8)[0]
                pos += 12
                if prev_instant is not None and instant <= prev_instant:
                    raise EngineFailure(
                        "F4",
                        "2A-S4-061",
                        STATE,
                        MODULE_NAME,
                        {"detail": "non_monotone_transition", "tzid": tzid},
                    )
                if instant != MIN_INSTANT and (offset < OFFSET_MIN or offset > OFFSET_MAX):
                    raise EngineFailure(
                        "F4",
                        "2A-S4-050",
                        STATE,
                        MODULE_NAME,
                        {"detail": "offset_out_of_range", "tzid": tzid, "offset_minutes": offset},
                    )
                if prev_offset is not None:
                    delta = offset - prev_offset
                    if delta > 0:
                        gap_total += 1
                    elif delta < 0:
                        fold_total += 1
                prev_instant = instant
                prev_offset = offset
        else:
            pos += bytes_needed

    if processed != len(tzids_used) and progress:
        progress.update(len(tzids_used) - processed)

    return gap_total, fold_total, missing, int(tzid_count)


def _atomic_publish_dir(tmp_root: Path, final_root: Path, logger, label: str) -> None:
    if final_root.exists():
        tmp_hash, _ = _hash_partition(tmp_root)
        final_hash, _ = _hash_partition(final_root)
        if tmp_hash != final_hash:
            raise EngineFailure(
                "F4",
                "2A-S4-041",
                STATE,
                MODULE_NAME,
                {"detail": "non-identical output exists", "partition": str(final_root), "label": label},
            )
        if tmp_root.exists():
            shutil.rmtree(tmp_root)
        logger.info("S4: %s partition already exists and is identical; skipping publish.", label)
        return
    final_root.parent.mkdir(parents=True, exist_ok=True)
    tmp_root.replace(final_root)


def run_s4(config: EngineConfig, run_id: Optional[str] = None) -> S4Result:
    logger = get_logger("engine.layers.l1.seg_2A.s4_legality.l2.runner")
    timer = _StepTimer(logger)
    started_monotonic = time.monotonic()
    started_utc = utc_now_rfc3339_micro()

    warnings: list[str] = []
    errors: list[dict] = []
    status = "fail"

    seed: Optional[int] = None
    parameter_hash: Optional[str] = None
    manifest_fingerprint: Optional[str] = None
    receipt_verified_utc = ""
    receipt_path_text = ""
    site_timezones_catalog_path = ""
    cache_catalog_path = ""
    output_catalog_path = ""
    cache_manifest: dict = {}

    output_root: Optional[Path] = None
    run_report_path: Optional[Path] = None

    counts = {
        "sites_total": 0,
        "tzids_total": 0,
        "gap_windows_total": 0,
        "fold_windows_total": 0,
    }
    coverage = {
        "missing_tzids_count": 0,
        "missing_tzids_sample": [],
    }

    try:
        receipt_path, receipt = _resolve_run_receipt(config.runs_root, run_id)
        run_id = receipt.get("run_id")
        seed = receipt.get("seed")
        parameter_hash = receipt.get("parameter_hash")
        manifest_fingerprint = receipt.get("manifest_fingerprint")
        if not run_id or seed is None or not manifest_fingerprint or not parameter_hash:
            raise EngineFailure(
                "F4",
                "2A-S4-001",
                STATE,
                MODULE_NAME,
                {"detail": "run_receipt_missing_fields"},
            )
        run_paths = RunPaths(config.runs_root, run_id)
        run_log_path = run_paths.run_root / f"run_log_{run_id}.log"
        add_file_handler(run_log_path)
        logger.info("S4: run log initialized at %s", run_log_path)

        source = ContractSource(config.contracts_root, config.contracts_layout)
        _dict_path, dictionary = load_dataset_dictionary(source, "2A")
        _reg_path, registry = load_artefact_registry(source, "2A")
        _, schema_2a = load_schema_pack(source, "2A", "2A")
        _, schema_layer1 = load_schema_pack(source, "1A", "layer1")

        receipt_entry = find_dataset_entry(dictionary, "s0_gate_receipt_2A").entry
        site_entry = find_dataset_entry(dictionary, "site_timezones").entry
        cache_entry = find_dataset_entry(dictionary, "tz_timetable_cache").entry
        report_entry = find_dataset_entry(dictionary, "s4_legality_report").entry

        receipt_reg = find_artifact_entry(registry, "s0_gate_receipt_2A").entry
        site_reg = find_artifact_entry(registry, "site_timezones").entry
        cache_reg = find_artifact_entry(registry, "tz_timetable_cache").entry
        report_reg = find_artifact_entry(registry, "s4_legality_report").entry

        schema_packs = {
            "schemas.2A.yaml": schema_2a,
            "schemas.layer1.yaml": schema_layer1,
        }
        _assert_schema_ref(
            _resolve_schema_ref(receipt_entry, receipt_reg, "s0_gate_receipt_2A"),
            schema_packs,
            "s0_gate_receipt_2A",
            logger,
            seed,
            manifest_fingerprint,
            parameter_hash,
            run_id,
        )
        _assert_schema_ref(
            _resolve_schema_ref(site_entry, site_reg, "site_timezones"),
            schema_packs,
            "site_timezones",
            logger,
            seed,
            manifest_fingerprint,
            parameter_hash,
            run_id,
        )
        _assert_schema_ref(
            _resolve_schema_ref(cache_entry, cache_reg, "tz_timetable_cache"),
            schema_packs,
            "tz_timetable_cache",
            logger,
            seed,
            manifest_fingerprint,
            parameter_hash,
            run_id,
        )
        _assert_schema_ref(
            _resolve_schema_ref(report_entry, report_reg, "s4_legality_report"),
            schema_packs,
            "s4_legality_report",
            logger,
            seed,
            manifest_fingerprint,
            parameter_hash,
            run_id,
        )
        _emit_validation(logger, seed, manifest_fingerprint, "V-02", "pass")

        tokens = {
            "seed": str(seed),
            "manifest_fingerprint": str(manifest_fingerprint),
        }
        receipt_path_text = _render_catalog_path(receipt_entry, tokens)
        try:
            receipt_path = _resolve_dataset_path(
                receipt_entry,
                run_paths,
                config.external_roots,
                tokens,
            )
            receipt_payload = _load_json(receipt_path)
        except InputResolutionError as exc:
            _emit_failure_event(
                logger,
                "2A-S4-001",
                seed,
                manifest_fingerprint,
                parameter_hash,
                run_id,
                {"detail": str(exc)},
            )
            raise EngineFailure(
                "F4",
                "2A-S4-001",
                STATE,
                MODULE_NAME,
                {"detail": str(exc)},
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
                "2A-S4-001",
                seed,
                manifest_fingerprint,
                parameter_hash,
                run_id,
                {"detail": exc.errors},
            )
            raise EngineFailure(
                "F4",
                "2A-S4-001",
                STATE,
                MODULE_NAME,
                {"detail": exc.errors},
            ) from exc
        receipt_verified_utc = receipt_payload.get("verified_at_utc", "")
        if receipt_payload.get("manifest_fingerprint") != str(manifest_fingerprint):
            _emit_failure_event(
                logger,
                "2A-S4-001",
                seed,
                manifest_fingerprint,
                parameter_hash,
                run_id,
                {"detail": "receipt_manifest_fingerprint_mismatch"},
            )
            raise EngineFailure(
                "F4",
                "2A-S4-001",
                STATE,
                MODULE_NAME,
                {"detail": "receipt_manifest_fingerprint_mismatch"},
            )
        _emit_event(
            logger,
            "GATE",
            seed,
            manifest_fingerprint,
            "INFO",
            receipt_path=receipt_path_text,
            verified_at_utc=receipt_verified_utc,
        )
        _emit_validation(logger, seed, manifest_fingerprint, "V-01", "pass")
        timer.info("S4: gate receipt verified")

        try:
            site_timezones_path = _resolve_dataset_path(
                site_entry,
                run_paths,
                config.external_roots,
                tokens,
            )
        except InputResolutionError as exc:
            _emit_failure_event(
                logger,
                "2A-S4-010",
                seed,
                manifest_fingerprint,
                parameter_hash,
                run_id,
                {"detail": str(exc), "dataset_id": "site_timezones"},
            )
            raise EngineFailure(
                "F4",
                "2A-S4-010",
                STATE,
                MODULE_NAME,
                {"detail": str(exc), "dataset_id": "site_timezones"},
            ) from exc
        site_timezones_catalog_path = _render_catalog_path(site_entry, tokens)
        try:
            cache_path = _resolve_dataset_path(
                cache_entry,
                run_paths,
                config.external_roots,
                tokens,
            )
        except InputResolutionError as exc:
            _emit_failure_event(
                logger,
                "2A-S4-010",
                seed,
                manifest_fingerprint,
                parameter_hash,
                run_id,
                {"detail": str(exc), "dataset_id": "tz_timetable_cache"},
            )
            raise EngineFailure(
                "F4",
                "2A-S4-010",
                STATE,
                MODULE_NAME,
                {"detail": str(exc), "dataset_id": "tz_timetable_cache"},
            ) from exc
        cache_catalog_path = _render_catalog_path(cache_entry, tokens)
        output_path = _resolve_dataset_path(
            report_entry,
            run_paths,
            config.external_roots,
            tokens,
        )
        output_catalog_path = _render_catalog_path(report_entry, tokens)

        _emit_event(
            logger,
            "INPUTS",
            seed,
            manifest_fingerprint,
            "INFO",
            site_timezones=site_timezones_catalog_path,
            tz_timetable_cache=cache_catalog_path,
        )
        _emit_validation(logger, seed, manifest_fingerprint, "V-03", "pass")

        try:
            sites_total, tzids_used, has_files = _scan_site_timezones(site_timezones_path)
        except InputResolutionError as exc:
            _emit_failure_event(
                logger,
                "2A-S4-010",
                seed,
                manifest_fingerprint,
                parameter_hash,
                run_id,
                {"detail": str(exc), "dataset_id": "site_timezones"},
            )
            raise EngineFailure(
                "F4",
                "2A-S4-010",
                STATE,
                MODULE_NAME,
                {"detail": str(exc), "dataset_id": "site_timezones"},
            ) from exc
        if not has_files:
            logger.warning("S4: site_timezones contains no parquet files; treating as empty dataset.")
        counts["sites_total"] = int(sites_total)
        counts["tzids_total"] = int(len(tzids_used))
        timer.info(
            f"S4: site_timezones scanned sites_total={counts['sites_total']} "
            f"tzids_total={counts['tzids_total']}"
        )

        cache_manifest_path = cache_path / CACHE_MANIFEST
        try:
            cache_manifest = _load_json(cache_manifest_path)
        except InputResolutionError as exc:
            _emit_failure_event(
                logger,
                "2A-S4-020",
                seed,
                manifest_fingerprint,
                parameter_hash,
                run_id,
                {"detail": str(exc)},
            )
            raise EngineFailure(
                "F4",
                "2A-S4-020",
                STATE,
                MODULE_NAME,
                {"detail": str(exc)},
            ) from exc
        try:
            _validate_payload(
                schema_2a,
                "cache/tz_timetable_cache",
                cache_manifest,
                ref_packs={"schemas.layer1.yaml": schema_layer1},
            )
        except SchemaValidationError as exc:
            _emit_failure_event(
                logger,
                "2A-S4-020",
                seed,
                manifest_fingerprint,
                parameter_hash,
                run_id,
                {"detail": exc.errors},
            )
            raise EngineFailure(
                "F4",
                "2A-S4-020",
                STATE,
                MODULE_NAME,
                {"detail": exc.errors},
            ) from exc
        if cache_manifest.get("manifest_fingerprint") != str(manifest_fingerprint):
            raise EngineFailure(
                "F4",
                "2A-S4-021",
                STATE,
                MODULE_NAME,
                {"detail": "cache_path_embed_mismatch"},
            )
        cache_bytes_expected = int(cache_manifest.get("rle_cache_bytes", 0))
        if cache_bytes_expected <= 0:
            raise EngineFailure(
                "F4",
                "2A-S4-022",
                STATE,
                MODULE_NAME,
                {"detail": "cache_bytes_missing"},
            )
        cache_file_path = cache_path / CACHE_FILE
        if not cache_file_path.exists():
            raise EngineFailure(
                "F4",
                "2A-S4-023",
                STATE,
                MODULE_NAME,
                {"detail": "cache_file_missing", "path": str(cache_file_path)},
            )
        if cache_file_path.stat().st_size != cache_bytes_expected:
            raise EngineFailure(
                "F4",
                "2A-S4-022",
                STATE,
                MODULE_NAME,
                {
                    "detail": "cache_bytes_mismatch",
                    "expected": cache_bytes_expected,
                    "actual": cache_file_path.stat().st_size,
                },
            )
        _emit_validation(logger, seed, manifest_fingerprint, "V-04", "pass")
        _emit_validation(logger, seed, manifest_fingerprint, "V-05", "pass")
        _emit_validation(logger, seed, manifest_fingerprint, "V-06", "pass")

        if tzids_used:
            cache_bytes = cache_file_path.read_bytes()
            gap_total, fold_total, missing_tzids, tzid_count = _decode_cache(
                cache_bytes,
                tzids_used,
                logger,
                seed,
                str(manifest_fingerprint),
                str(parameter_hash),
                run_id,
            )
        else:
            gap_total = 0
            fold_total = 0
            missing_tzids = set()
            tzid_count = 0

        counts["gap_windows_total"] = int(gap_total)
        counts["fold_windows_total"] = int(fold_total)
        coverage["missing_tzids_count"] = int(len(missing_tzids))
        missing_sorted = sorted(missing_tzids)
        coverage["missing_tzids_sample"] = missing_sorted[:20]

        _emit_event(
            logger,
            "CHECK",
            seed,
            manifest_fingerprint,
            "INFO",
            sites_total=counts["sites_total"],
            tzids_total=counts["tzids_total"],
            gap_windows_total=counts["gap_windows_total"],
            fold_windows_total=counts["fold_windows_total"],
            missing_tzids_count=coverage["missing_tzids_count"],
            cache_tzids=tzid_count,
        )

        if missing_sorted:
            _emit_validation(
                logger,
                seed,
                manifest_fingerprint,
                "V-10",
                "fail",
                error_code="2A-S4-024",
                detail={"missing_sample": coverage["missing_tzids_sample"]},
            )
            status = "fail"
            errors.append(
                {
                    "code": "2A-S4-024",
                    "message": "tzids missing from cache",
                    "context": {"missing_count": coverage["missing_tzids_count"]},
                }
            )
        else:
            _emit_validation(logger, seed, manifest_fingerprint, "V-10", "pass")

        if counts["sites_total"] < 0 or counts["tzids_total"] < 0:
            raise EngineFailure(
                "F4",
                "2A-S4-060",
                STATE,
                MODULE_NAME,
                {"detail": "count_negative"},
            )
        _emit_validation(logger, seed, manifest_fingerprint, "V-11", "pass")
        _emit_validation(logger, seed, manifest_fingerprint, "V-12", "pass")
        _emit_validation(logger, seed, manifest_fingerprint, "V-13", "pass")

        if not receipt_verified_utc:
            raise EngineFailure(
                "F4",
                "2A-S4-042",
                STATE,
                MODULE_NAME,
                {"detail": "missing_verified_utc"},
            )

        report = {
            "manifest_fingerprint": str(manifest_fingerprint),
            "seed": int(seed),
            "generated_utc": receipt_verified_utc,
            "status": "FAIL" if missing_sorted else "PASS",
            "counts": {
                "sites_total": int(counts["sites_total"]),
                "tzids_total": int(counts["tzids_total"]),
                "gap_windows_total": int(counts["gap_windows_total"]),
                "fold_windows_total": int(counts["fold_windows_total"]),
            },
        }
        if missing_sorted:
            report["missing_tzids"] = missing_sorted

        try:
            _validate_payload(
                schema_2a,
                "validation/s4_legality_report",
                report,
                ref_packs={"schemas.layer1.yaml": schema_layer1},
            )
        except SchemaValidationError as exc:
            raise EngineFailure(
                "F4",
                "2A-S4-030",
                STATE,
                MODULE_NAME,
                {"detail": exc.errors},
            ) from exc
        if report["manifest_fingerprint"] != str(manifest_fingerprint):
            raise EngineFailure(
                "F4",
                "2A-S4-040",
                STATE,
                MODULE_NAME,
                {"detail": "path_embed_mismatch"},
            )
        if report["seed"] != int(seed):
            raise EngineFailure(
                "F4",
                "2A-S4-040",
                STATE,
                MODULE_NAME,
                {"detail": "seed_path_embed_mismatch"},
            )
        if report["generated_utc"] != receipt_verified_utc:
            raise EngineFailure(
                "F4",
                "2A-S4-042",
                STATE,
                MODULE_NAME,
                {"detail": "generated_utc_mismatch"},
            )

        _emit_validation(logger, seed, manifest_fingerprint, "V-07", "pass")
        _emit_validation(logger, seed, manifest_fingerprint, "V-08", "pass")
        _emit_validation(logger, seed, manifest_fingerprint, "V-09", "pass")

        output_root = output_path.parent
        tmp_root = run_paths.tmp_root / f"s4_legality_{uuid.uuid4().hex}"
        tmp_root.mkdir(parents=True, exist_ok=True)
        output_file = tmp_root / output_path.name
        _write_json(output_file, report)

        _atomic_publish_dir(tmp_root, output_root, logger, "s4_legality_report")
        _emit_validation(logger, seed, manifest_fingerprint, "V-14", "pass")

        _emit_event(
            logger,
            "EMIT",
            seed,
            manifest_fingerprint,
            "INFO",
            output_path=output_catalog_path,
            generated_utc=receipt_verified_utc,
            status=report["status"],
        )

        if not missing_sorted:
            status = "pass"

        return S4Result(
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
        if run_id and manifest_fingerprint is not None and seed is not None:
            run_paths = RunPaths(config.runs_root, run_id)
            run_report_path = (
                run_paths.run_root
                / "reports"
                / "layer1"
                / "2A"
                / "state=S4"
                / f"seed={seed}"
                / f"manifest_fingerprint={manifest_fingerprint}"
                / "s4_run_report.json"
            )
            run_report = {
                "segment": SEGMENT,
                "state": STATE,
                "status": status,
                "manifest_fingerprint": str(manifest_fingerprint),
                "seed": int(seed),
                "started_utc": started_utc,
                "finished_utc": finished_utc,
                "durations": {"wall_ms": int((time.monotonic() - started_monotonic) * 1000)},
                "s0": {"receipt_path": receipt_path_text, "verified_at_utc": receipt_verified_utc},
                "inputs": {
                    "site_timezones": {"path": site_timezones_catalog_path},
                    "cache": {
                        "path": cache_catalog_path,
                        "tzdb_release_tag": cache_manifest.get("tzdb_release_tag", ""),
                        "tz_index_digest": cache_manifest.get("tz_index_digest", ""),
                        "rle_cache_bytes": cache_manifest.get("rle_cache_bytes", 0),
                    },
                },
                "counts": {
                    "sites_total": counts["sites_total"],
                    "tzids_total": counts["tzids_total"],
                    "gap_windows_total": counts["gap_windows_total"],
                    "fold_windows_total": counts["fold_windows_total"],
                },
                "coverage": coverage,
                "output": {
                    "path": output_catalog_path,
                    "generated_utc": receipt_verified_utc,
                    "catalogue": {"writer_order_ok": True},
                },
                "warnings": warnings,
                "errors": errors,
            }
            _write_json(run_report_path, run_report)
            logger.info("S4: run-report written %s", run_report_path)
