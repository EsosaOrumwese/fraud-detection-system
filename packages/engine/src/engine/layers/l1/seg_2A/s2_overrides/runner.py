"""S2 overrides & finalisation runner for Segment 2A."""

from __future__ import annotations

import json
import shutil
import time
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Iterator, Optional

import polars as pl
from jsonschema import Draft202012Validator

try:
    import pyarrow.parquet as pq

    _HAVE_PYARROW = True
except Exception:  # pragma: no cover - optional dependency.
    pq = None
    _HAVE_PYARROW = False

from engine.contracts.jsonschema_adapter import validate_dataframe
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
    _prepare_row_schema_with_layer1_defs,
    _prepare_table_pack_with_layer1_defs,
    _render_catalog_path,
    _resolve_dataset_path,
    _resolve_run_receipt,
    _validate_payload,
)


MODULE_NAME = "2A.S2.overrides"
SEGMENT = "2A"
STATE = "S2"
BATCH_SIZE = 200_000


@dataclass(frozen=True)
class S2Result:
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
    severity = "INFO"
    if result == "fail":
        severity = "ERROR"
    elif result == "warn":
        severity = "WARN"
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
        "event": "S2_ERROR",
        "code": code,
        "at": utc_now_rfc3339_micro(),
        "seed": seed,
        "manifest_fingerprint": manifest_fingerprint,
        "parameter_hash": parameter_hash,
        "run_id": run_id,
    }
    payload.update(detail)
    logger.error("S2_ERROR %s", json.dumps(payload, ensure_ascii=True, sort_keys=True))

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
            "2A-S2-080",
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
            "2A-S2-080",
            seed,
            manifest_fingerprint,
            parameter_hash,
            run_id,
            {"detail": "missing_schema_ref", "dataset_id": dataset_id},
        )
        raise EngineFailure(
            "F4",
            "2A-S2-080",
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
                    "2A-S2-080",
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
                    "2A-S2-080",
                    STATE,
                    MODULE_NAME,
                    {"detail": "schema_ref_invalid", "dataset_id": dataset_id, "schema_ref": schema_ref},
                ) from exc
            return
    _emit_failure_event(
        logger,
        "2A-S2-080",
        seed,
        manifest_fingerprint,
        parameter_hash,
        run_id,
        {"detail": "schema_ref_unknown_prefix", "dataset_id": dataset_id, "schema_ref": schema_ref},
    )
    raise EngineFailure(
        "F4",
        "2A-S2-080",
        STATE,
        MODULE_NAME,
        {"detail": "schema_ref_unknown_prefix", "dataset_id": dataset_id, "schema_ref": schema_ref},
    )


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True), encoding="utf-8")


def _close_parquet_reader(reader: object) -> None:
    if hasattr(reader, "close"):
        try:
            reader.close()
        except Exception:
            pass


def _list_parquet_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    if not root.exists():
        raise InputResolutionError(f"Dataset path does not exist: {root}")
    files = sorted([path for path in root.rglob("*.parquet") if path.is_file()])
    if files:
        return files
    raise InputResolutionError(f"No parquet files found under dataset path: {root}")


def _count_parquet_rows(paths: Iterable[Path]) -> Optional[int]:
    if not _HAVE_PYARROW:
        return None
    total = 0
    for path in paths:
        pf = pq.ParquetFile(path)
        try:
            total += pf.metadata.num_rows
        finally:
            _close_parquet_reader(pf)
    return total


def _iter_parquet_batches(paths: list[Path], columns: list[str]) -> Iterator[pl.DataFrame]:
    if _HAVE_PYARROW:
        for path in paths:
            pf = pq.ParquetFile(path)
            try:
                for batch in pf.iter_batches(columns=columns, batch_size=BATCH_SIZE):
                    yield pl.from_arrow(batch)
            finally:
                _close_parquet_reader(pf)
    else:
        for path in paths:
            df = pl.read_parquet(path, columns=columns)
            offset = 0
            while offset < df.height:
                chunk = df.slice(offset, BATCH_SIZE)
                offset += chunk.height
                yield chunk


def _write_batch(df: pl.DataFrame, batch_index: int, output_root: Path, logger) -> Path:
    output_path = output_root / f"part-{batch_index:05d}.parquet"
    df.write_parquet(output_path)
    logger.info("S2: wrote %s rows=%d", output_path, df.height)
    return output_path


def _atomic_publish_dir(tmp_root: Path, final_root: Path, logger, label: str) -> None:
    if final_root.exists():
        tmp_hash, _ = _hash_partition(tmp_root)
        final_hash, _ = _hash_partition(final_root)
        if tmp_hash != final_hash:
            raise EngineFailure(
                "F4",
                "2A-S2-041",
                STATE,
                MODULE_NAME,
                {"detail": "non-identical output exists", "partition": str(final_root), "label": label},
            )
        shutil.rmtree(tmp_root)
        logger.info("S2: %s partition already exists and is identical; skipping publish.", label)
        return
    final_root.parent.mkdir(parents=True, exist_ok=True)
    tmp_root.replace(final_root)


def _parse_cutoff_date(verified_at_utc: str, fallback_utc: str) -> date:
    source = verified_at_utc or fallback_utc
    if not source:
        raise ValueError("missing cutoff timestamp")
    if source.endswith("Z"):
        source = source[:-1] + "+00:00"
    return datetime.fromisoformat(source).date()


def _override_active(expiry: Optional[str], cutoff: date) -> bool:
    if expiry is None:
        return True
    expiry_str = str(expiry).strip()
    if not expiry_str:
        return True
    return date.fromisoformat(expiry_str) >= cutoff


def _load_tzid_set(path: Path) -> set[str]:
    if not path.exists():
        raise InputResolutionError(f"tz_world not found: {path}")
    if _HAVE_PYARROW:
        table = pq.read_table(path, columns=["tzid"])
        tzids = table.column("tzid").to_pylist()
        return {str(tzid) for tzid in tzids if tzid is not None}
    df = pl.read_parquet(path, columns=["tzid"])
    return {str(row["tzid"]) for row in df.iter_rows(named=True) if row.get("tzid") is not None}

def run_s2(config: EngineConfig, run_id: Optional[str] = None) -> S2Result:
    logger = get_logger("engine.layers.l1.seg_2A.s2_overrides.l2.runner")
    timer = _StepTimer(logger)
    started_monotonic = time.monotonic()
    started_utc = utc_now_rfc3339_micro()

    warnings: list[str] = []
    errors: list[dict] = []
    status = "fail"

    seed: Optional[int] = None
    manifest_fingerprint: Optional[str] = None
    parameter_hash: Optional[str] = None
    receipt_catalog_path = ""
    s1_catalog_path = ""
    output_catalog_path = ""
    receipt_verified_utc = ""
    tz_overrides_version = ""
    tz_overrides_digest = ""
    mcc_map_id: Optional[str] = None
    mcc_map_digest: Optional[str] = None
    output_root: Optional[Path] = None
    run_report_path: Optional[Path] = None
    writer_order_violation = False

    counts = {
        "sites_total": 0,
        "rows_emitted": 0,
        "overridden_total": 0,
        "overridden_by_scope": {"site": 0, "mcc": 0, "country": 0},
        "override_no_effect": 0,
        "expired_skipped": 0,
        "dup_scope_target": 0,
        "mcc_targets_missing": 0,
        "distinct_tzids": 0,
    }
    checks = {
        "pk_duplicates": 0,
        "coverage_mismatch": 0,
        "null_tzid": 0,
        "unknown_tzid": 0,
        "tzid_not_in_tz_world": 0,
    }

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
        seed = int(receipt.get("seed"))

        run_paths = RunPaths(config.runs_root, run_id)
        run_log_path = run_paths.run_root / f"run_log_{run_id}.log"
        add_file_handler(run_log_path)
        logger.info("S2: run log initialized at %s", run_log_path)

        source = ContractSource(config.contracts_root, config.contracts_layout)
        dict_path, dictionary = load_dataset_dictionary(source, "2A")
        registry_path, registry = load_artefact_registry(source, "2A")
        schema_2a_path, schema_2a = load_schema_pack(source, "2A", "2A")
        schema_1b_path, schema_1b = load_schema_pack(source, "1B", "1B")
        schema_ingress_path, schema_ingress = load_schema_pack(source, "1A", "ingress.layer1")
        schema_layer1_path, schema_layer1 = load_schema_pack(source, "1A", "layer1")
        logger.info(
            "Contracts layout=%s root=%s dictionary=%s registry=%s schemas=%s,%s,%s,%s",
            config.contracts_layout,
            config.contracts_root,
            dict_path,
            registry_path,
            schema_2a_path,
            schema_1b_path,
            schema_ingress_path,
            schema_layer1_path,
        )

        tokens = {
            "seed": str(seed),
            "manifest_fingerprint": str(manifest_fingerprint),
        }

        def _dataset_entry(dataset_id: str) -> dict:
            try:
                return find_dataset_entry(dictionary, dataset_id).entry
            except ContractError as exc:
                raise EngineFailure(
                    "F4",
                    "2A-S2-010",
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
                    "2A-S2-010",
                    STATE,
                    MODULE_NAME,
                    {"detail": "missing_registry_entry", "artifact": name},
                ) from exc

        entries = {
            "s0_gate_receipt_2A": _dataset_entry("s0_gate_receipt_2A"),
            "sealed_inputs_2A": _dataset_entry("sealed_inputs_2A"),
            "s1_tz_lookup": _dataset_entry("s1_tz_lookup"),
            "tz_overrides": _dataset_entry("tz_overrides"),
            "tz_world_2025a": _dataset_entry("tz_world_2025a"),
            "site_timezones": _dataset_entry("site_timezones"),
        }
        registry_entries = {
            "s0_gate_receipt_2A": _registry_entry("s0_gate_receipt_2A"),
            "s1_tz_lookup": _registry_entry("s1_tz_lookup"),
            "tz_overrides": _registry_entry("tz_overrides"),
            "tz_world_2025a": _registry_entry("tz_world_2025a"),
            "site_timezones": _registry_entry("site_timezones"),
        }

        schema_packs = {
            "schemas.2A.yaml": schema_2a,
            "schemas.1B.yaml": schema_1b,
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
                seed,
                str(manifest_fingerprint),
                str(parameter_hash),
                run_id,
            )

        receipt_path = _resolve_dataset_path(
            entries["s0_gate_receipt_2A"],
            run_paths,
            config.external_roots,
            {"manifest_fingerprint": str(manifest_fingerprint)},
        )
        sealed_inputs_path = _resolve_dataset_path(
            entries["sealed_inputs_2A"],
            run_paths,
            config.external_roots,
            {"manifest_fingerprint": str(manifest_fingerprint)},
        )
        s1_path = _resolve_dataset_path(entries["s1_tz_lookup"], run_paths, config.external_roots, tokens)
        tz_overrides_path = _resolve_dataset_path(entries["tz_overrides"], run_paths, config.external_roots, tokens)
        tz_world_path = _resolve_dataset_path(entries["tz_world_2025a"], run_paths, config.external_roots, tokens)
        output_root = _resolve_dataset_path(entries["site_timezones"], run_paths, config.external_roots, tokens)

        receipt_catalog_path = _render_catalog_path(
            entries["s0_gate_receipt_2A"], {"manifest_fingerprint": str(manifest_fingerprint)}
        )
        s1_catalog_path = _render_catalog_path(entries["s1_tz_lookup"], tokens)
        output_catalog_path = _render_catalog_path(entries["site_timezones"], tokens)
        run_report_path = (
            run_paths.run_root
            / "reports"
            / "layer1"
            / "2A"
            / "state=S2"
            / f"seed={seed}"
            / f"manifest_fingerprint={manifest_fingerprint}"
            / "s2_run_report.json"
        )
        if not receipt_path.exists():
            _emit_failure_event(
                logger,
                "2A-S2-001",
                seed,
                str(manifest_fingerprint),
                str(parameter_hash),
                run_id,
                {"detail": "missing_s0_receipt", "path": str(receipt_path)},
            )
            raise EngineFailure(
                "F4",
                "2A-S2-001",
                STATE,
                MODULE_NAME,
                {"detail": "missing_s0_receipt", "path": str(receipt_path)},
                dataset_id="s0_gate_receipt_2A",
            )

        receipt_payload = _load_json(receipt_path)
        receipt_schema = _prepare_row_schema_with_layer1_defs(
            schema_2a, "validation/s0_gate_receipt_v1", schema_layer1, "schemas.layer1.yaml"
        )
        validator = Draft202012Validator(receipt_schema)
        receipt_errors = list(validator.iter_errors(receipt_payload))
        if receipt_errors:
            detail = receipt_errors[0].message if receipt_errors else "receipt schema invalid"
            _emit_failure_event(
                logger,
                "2A-S2-001",
                seed,
                str(manifest_fingerprint),
                str(parameter_hash),
                run_id,
                {"detail": detail, "path": str(receipt_path)},
            )
            raise EngineFailure(
                "F4",
                "2A-S2-001",
                STATE,
                MODULE_NAME,
                {"detail": detail, "path": str(receipt_path)},
                dataset_id="s0_gate_receipt_2A",
            )

        receipt_manifest = receipt_payload.get("manifest_fingerprint")
        if str(receipt_manifest) != str(manifest_fingerprint):
            _emit_failure_event(
                logger,
                "2A-S2-001",
                seed,
                str(manifest_fingerprint),
                str(parameter_hash),
                run_id,
                {"detail": "receipt_manifest_mismatch", "path": str(receipt_path)},
            )
            raise EngineFailure(
                "F4",
                "2A-S2-001",
                STATE,
                MODULE_NAME,
                {"detail": "receipt_manifest_mismatch", "path": str(receipt_path)},
                dataset_id="s0_gate_receipt_2A",
            )

        receipt_verified_utc = str(receipt_payload.get("verified_at_utc", ""))
        _emit_event(
            logger,
            "GATE",
            seed,
            str(manifest_fingerprint),
            "INFO",
            receipt_path=receipt_catalog_path,
            result="verified",
        )
        _emit_validation(logger, seed, str(manifest_fingerprint), "V-01", "pass")
        sealed_inputs_payload = _load_json(sealed_inputs_path)
        sealed_index = {
            item.get("asset_id"): item for item in sealed_inputs_payload if isinstance(item, dict)
        }
        required_ids = ["tz_overrides", "tz_world_2025a"]
        missing = [asset_id for asset_id in required_ids if asset_id not in sealed_index]
        if missing:
            _emit_failure_event(
                logger,
                "2A-S2-010",
                seed,
                str(manifest_fingerprint),
                str(parameter_hash),
                run_id,
                {"detail": "missing_sealed_inputs", "missing": missing},
            )
            raise EngineFailure(
                "F4",
                "2A-S2-010",
                STATE,
                MODULE_NAME,
                {"detail": "missing_sealed_inputs", "missing": missing},
            )
        for dataset_id in required_ids:
            sealed_schema_ref = sealed_index[dataset_id].get("schema_ref")
            dict_schema_ref = entries[dataset_id].get("schema_ref")
            if sealed_schema_ref and dict_schema_ref and sealed_schema_ref != dict_schema_ref:
                _emit_failure_event(
                    logger,
                    "2A-S2-080",
                    seed,
                    str(manifest_fingerprint),
                    str(parameter_hash),
                    run_id,
                    {
                        "detail": "schema_ref_mismatch",
                        "dataset_id": dataset_id,
                        "sealed": sealed_schema_ref,
                        "dictionary": dict_schema_ref,
                    },
                )
                raise EngineFailure(
                    "F4",
                    "2A-S2-080",
                    STATE,
                    MODULE_NAME,
                    {
                        "detail": "schema_ref_mismatch",
                        "dataset_id": dataset_id,
                        "sealed": sealed_schema_ref,
                        "dictionary": dict_schema_ref,
                    },
                )

        tz_overrides_payload = _load_yaml(tz_overrides_path)
        try:
            _validate_payload(
                schema_2a,
                "policy/tz_overrides_v1",
                tz_overrides_payload,
                ref_packs={"schemas.layer1.yaml": schema_layer1},
            )
        except SchemaValidationError as exc:
            _emit_failure_event(
                logger,
                "2A-S2-020",
                seed,
                str(manifest_fingerprint),
                str(parameter_hash),
                run_id,
                {"detail": exc.errors, "path": str(tz_overrides_path)},
            )
            raise EngineFailure(
                "F4",
                "2A-S2-020",
                STATE,
                MODULE_NAME,
                {"detail": exc.errors, "path": str(tz_overrides_path)},
                dataset_id="tz_overrides",
            ) from exc
        if not isinstance(tz_overrides_payload, list):
            _emit_failure_event(
                logger,
                "2A-S2-020",
                seed,
                str(manifest_fingerprint),
                str(parameter_hash),
                run_id,
                {"detail": "tz_overrides_not_list", "path": str(tz_overrides_path)},
            )
            raise EngineFailure(
                "F4",
                "2A-S2-020",
                STATE,
                MODULE_NAME,
                {"detail": "tz_overrides_not_list", "path": str(tz_overrides_path)},
                dataset_id="tz_overrides",
            )
        _emit_validation(logger, seed, str(manifest_fingerprint), "V-04", "pass")

        try:
            cutoff_date = _parse_cutoff_date(receipt_verified_utc, started_utc)
        except ValueError as exc:
            _emit_failure_event(
                logger,
                "2A-S2-001",
                seed,
                str(manifest_fingerprint),
                str(parameter_hash),
                run_id,
                {"detail": "receipt_timestamp_invalid", "verified_at_utc": receipt_verified_utc},
            )
            raise EngineFailure(
                "F4",
                "2A-S2-001",
                STATE,
                MODULE_NAME,
                {"detail": "receipt_timestamp_invalid", "verified_at_utc": receipt_verified_utc},
                dataset_id="s0_gate_receipt_2A",
            ) from exc
        overrides_site: dict[str, str] = {}
        overrides_mcc: dict[str, str] = {}
        overrides_country: dict[str, str] = {}
        seen_scope_targets: set[tuple[str, str]] = set()
        for entry in tz_overrides_payload:
            if not isinstance(entry, dict):
                continue
            scope = str(entry.get("scope", "")).strip()
            target = str(entry.get("target", "")).strip()
            tzid = str(entry.get("tzid", "")).strip()
            if not _override_active(entry.get("expiry_yyyy_mm_dd"), cutoff_date):
                counts["expired_skipped"] += 1
                continue
            key = (scope, target)
            if key in seen_scope_targets:
                counts["dup_scope_target"] += 1
                _emit_failure_event(
                    logger,
                    "2A-S2-021",
                    seed,
                    str(manifest_fingerprint),
                    str(parameter_hash),
                    run_id,
                    {"detail": "duplicate_scope_target", "scope": scope, "target": target},
                )
                raise EngineFailure(
                    "F4",
                    "2A-S2-021",
                    STATE,
                    MODULE_NAME,
                    {"detail": "duplicate_scope_target", "scope": scope, "target": target},
                    dataset_id="tz_overrides",
                )
            seen_scope_targets.add(key)
            if scope == "site":
                overrides_site[target] = tzid
            elif scope == "mcc":
                overrides_mcc[target] = tzid
            elif scope == "country":
                overrides_country[target] = tzid
        _emit_validation(logger, seed, str(manifest_fingerprint), "V-05", "pass")
        _emit_validation(logger, seed, str(manifest_fingerprint), "V-07", "pass")

        tz_overrides_version = str(sealed_index.get("tz_overrides", {}).get("version_tag", ""))
        tz_overrides_digest = str(sealed_index.get("tz_overrides", {}).get("sha256_hex", ""))
        if not tz_overrides_digest:
            tz_overrides_digest = sha256_file(tz_overrides_path).sha256_hex

        mcc_lookup: dict[int, str] = {}
        mcc_map_version = ""
        if overrides_mcc:
            if "merchant_mcc_map" not in sealed_index:
                _emit_failure_event(
                    logger,
                    "2A-S2-022",
                    seed,
                    str(manifest_fingerprint),
                    str(parameter_hash),
                    run_id,
                    {"detail": "missing_mcc_mapping", "dataset_id": "merchant_mcc_map"},
                )
                raise EngineFailure(
                    "F4",
                    "2A-S2-022",
                    STATE,
                    MODULE_NAME,
                    {"detail": "missing_mcc_mapping", "dataset_id": "merchant_mcc_map"},
                )
            entries["merchant_mcc_map"] = _dataset_entry("merchant_mcc_map")
            registry_entries["merchant_mcc_map"] = _registry_entry("merchant_mcc_map")
            mcc_schema_ref = _resolve_schema_ref(
                entries["merchant_mcc_map"],
                registry_entries["merchant_mcc_map"],
                "merchant_mcc_map",
            )
            _assert_schema_ref(
                mcc_schema_ref,
                schema_packs,
                "merchant_mcc_map",
                logger,
                seed,
                str(manifest_fingerprint),
                str(parameter_hash),
                run_id,
            )
            mcc_map_version = str(sealed_index.get("merchant_mcc_map", {}).get("version_tag", ""))
            mcc_map_digest = str(sealed_index.get("merchant_mcc_map", {}).get("sha256_hex", ""))
            if mcc_map_digest:
                mcc_map_id = "merchant_mcc_map"
            mcc_tokens = dict(tokens)
            if mcc_map_version:
                mcc_tokens["version"] = mcc_map_version
            mcc_map_path = _resolve_dataset_path(
                entries["merchant_mcc_map"],
                run_paths,
                config.external_roots,
                mcc_tokens,
            )
            mcc_df = pl.read_parquet(mcc_map_path, columns=["merchant_id", "mcc"])
            mcc_lookup = {
                int(row["merchant_id"]): f"{int(row['mcc']):04d}"
                for row in mcc_df.iter_rows(named=True)
            }
            if not mcc_lookup:
                _emit_failure_event(
                    logger,
                    "2A-S2-022",
                    seed,
                    str(manifest_fingerprint),
                    str(parameter_hash),
                    run_id,
                    {"detail": "empty_mcc_mapping", "path": str(mcc_map_path)},
                )
                raise EngineFailure(
                    "F4",
                    "2A-S2-022",
                    STATE,
                    MODULE_NAME,
                    {"detail": "empty_mcc_mapping", "path": str(mcc_map_path)},
                )
        _emit_validation(logger, seed, str(manifest_fingerprint), "V-06", "pass")

        tzid_set = _load_tzid_set(tz_world_path)
        if not tzid_set:
            _emit_failure_event(
                logger,
                "2A-S2-010",
                seed,
                str(manifest_fingerprint),
                str(parameter_hash),
                run_id,
                {"detail": "tz_world_empty_tzid", "path": str(tz_world_path)},
            )
            raise EngineFailure(
                "F4",
                "2A-S2-010",
                STATE,
                MODULE_NAME,
                {"detail": "tz_world_empty_tzid", "path": str(tz_world_path)},
            )

        logger.info(
            "S2: overrides active (site=%d mcc=%d country=%d) expired_skipped=%d",
            len(overrides_site),
            len(overrides_mcc),
            len(overrides_country),
            counts["expired_skipped"],
        )
        _emit_event(
            logger,
            "INPUTS",
            seed,
            str(manifest_fingerprint),
            "INFO",
            s1_path=s1_catalog_path,
            tz_overrides_path=_render_catalog_path(entries["tz_overrides"], tokens),
            tz_world_path=_render_catalog_path(entries["tz_world_2025a"], tokens),
            mcc_mapping_id=mcc_map_id,
        )
        _emit_validation(logger, seed, str(manifest_fingerprint), "V-02", "pass")

        s1_files = _list_parquet_files(s1_path)
        total_rows = _count_parquet_rows(s1_files)
        progress = _ProgressTracker(total_rows, logger, "S2 progress sites_processed=")

        output_tmp = run_paths.run_root / "tmp" / f"s2_site_timezones_{uuid.uuid4().hex}"
        output_tmp.mkdir(parents=True, exist_ok=True)

        output_pack, output_table = _prepare_table_pack_with_layer1_defs(
            schema_2a,
            "egress/site_timezones",
            schema_layer1,
            "schemas.layer1.yaml",
        )

        tzid_schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$defs": schema_layer1.get("$defs", {}),
            "$ref": "#/$defs/iana_tzid",
        }
        tzid_validator = Draft202012Validator(tzid_schema)

        if not receipt_verified_utc:
            _emit_failure_event(
                logger,
                "2A-S2-042",
                seed,
                str(manifest_fingerprint),
                str(parameter_hash),
                run_id,
                {"detail": "missing_receipt_verified_at_utc"},
            )
            raise EngineFailure(
                "F4",
                "2A-S2-042",
                STATE,
                MODULE_NAME,
                {"detail": "missing_receipt_verified_at_utc"},
            )

        created_utc = receipt_verified_utc
        output_schema = [
            ("seed", pl.UInt64),
            ("manifest_fingerprint", pl.Utf8),
            ("merchant_id", pl.UInt64),
            ("legal_country_iso", pl.Utf8),
            ("site_order", pl.Int32),
            ("tzid", pl.Utf8),
            ("tzid_source", pl.Utf8),
            ("override_scope", pl.Utf8),
            ("nudge_lat_deg", pl.Float64),
            ("nudge_lon_deg", pl.Float64),
            ("created_utc", pl.Utf8),
        ]

        output_rows: list[dict] = []
        batch_index = 0
        seen_keys: set[tuple[int, str, int]] = set()
        last_key: Optional[tuple[int, str, int]] = None
        tzids_seen: set[str] = set()
        output_schema_validated = False
        partition_validated = False
        for batch in _iter_parquet_batches(
            s1_files,
            [
                "seed",
                "manifest_fingerprint",
                "merchant_id",
                "legal_country_iso",
                "site_order",
                "tzid_provisional",
                "tzid_provisional_source",
                "override_scope",
                "override_applied",
                "nudge_lat_deg",
                "nudge_lon_deg",
            ],
        ):
            if batch.height == 0:
                continue
            mismatch = batch.filter(
                (pl.col("seed") != seed) | (pl.col("manifest_fingerprint") != str(manifest_fingerprint))
            )
            if mismatch.height > 0:
                row = mismatch.row(0, named=True)
                _emit_failure_event(
                    logger,
                    "2A-S2-040",
                    seed,
                    str(manifest_fingerprint),
                    str(parameter_hash),
                    run_id,
                    {
                        "detail": "path_embed_mismatch",
                        "row_seed": row.get("seed"),
                        "row_manifest_fingerprint": row.get("manifest_fingerprint"),
                    },
                )
                raise EngineFailure(
                    "F4",
                    "2A-S2-040",
                    STATE,
                    MODULE_NAME,
                    {
                        "detail": "path_embed_mismatch",
                        "row_seed": row.get("seed"),
                        "row_manifest_fingerprint": row.get("manifest_fingerprint"),
                    },
                )

            for row in batch.iter_rows(named=True):
                merchant_id = int(row["merchant_id"])
                legal_country_iso = str(row["legal_country_iso"])
                site_order = int(row["site_order"])
                tzid_provisional = row["tzid_provisional"]
                tzid_provisional_source = str(row["tzid_provisional_source"])
                override_applied = bool(row["override_applied"])
                s1_override_scope = row["override_scope"]
                if s1_override_scope is not None:
                    s1_override_scope = str(s1_override_scope)
                key = (merchant_id, legal_country_iso, site_order)
                if key in seen_keys:
                    checks["pk_duplicates"] += 1
                    _emit_failure_event(
                        logger,
                        "2A-S2-051",
                        seed,
                        str(manifest_fingerprint),
                        str(parameter_hash),
                        run_id,
                        {
                            "detail": "pk_duplicate",
                            "merchant_id": merchant_id,
                            "legal_country_iso": legal_country_iso,
                            "site_order": site_order,
                        },
                    )
                    raise EngineFailure(
                        "F4",
                        "2A-S2-051",
                        STATE,
                        MODULE_NAME,
                        {
                            "detail": "pk_duplicate",
                            "merchant_id": merchant_id,
                            "legal_country_iso": legal_country_iso,
                            "site_order": site_order,
                        },
                    )
                seen_keys.add(key)
                if last_key is not None and key < last_key:
                    writer_order_violation = True
                last_key = key

                if override_applied:
                    if tzid_provisional_source != "override":
                        _emit_failure_event(
                            logger,
                            "2A-S2-054",
                            seed,
                            str(manifest_fingerprint),
                            str(parameter_hash),
                            run_id,
                            {
                                "detail": "override_applied_source_mismatch",
                                "merchant_id": merchant_id,
                                "legal_country_iso": legal_country_iso,
                                "site_order": site_order,
                                "tzid_provisional_source": tzid_provisional_source,
                            },
                        )
                        raise EngineFailure(
                            "F4",
                            "2A-S2-054",
                            STATE,
                            MODULE_NAME,
                            {
                                "detail": "override_applied_source_mismatch",
                                "merchant_id": merchant_id,
                                "legal_country_iso": legal_country_iso,
                                "site_order": site_order,
                                "tzid_provisional_source": tzid_provisional_source,
                            },
                        )
                    if s1_override_scope not in ("site", "mcc", "country"):
                        _emit_failure_event(
                            logger,
                            "2A-S2-054",
                            seed,
                            str(manifest_fingerprint),
                            str(parameter_hash),
                            run_id,
                            {
                                "detail": "override_scope_missing",
                                "merchant_id": merchant_id,
                                "legal_country_iso": legal_country_iso,
                                "site_order": site_order,
                            },
                        )
                        raise EngineFailure(
                            "F4",
                            "2A-S2-054",
                            STATE,
                            MODULE_NAME,
                            {
                                "detail": "override_scope_missing",
                                "merchant_id": merchant_id,
                                "legal_country_iso": legal_country_iso,
                                "site_order": site_order,
                            },
                        )
                else:
                    if tzid_provisional_source != "polygon":
                        _emit_failure_event(
                            logger,
                            "2A-S2-054",
                            seed,
                            str(manifest_fingerprint),
                            str(parameter_hash),
                            run_id,
                            {
                                "detail": "polygon_source_expected",
                                "merchant_id": merchant_id,
                                "legal_country_iso": legal_country_iso,
                                "site_order": site_order,
                                "tzid_provisional_source": tzid_provisional_source,
                            },
                        )
                        raise EngineFailure(
                            "F4",
                            "2A-S2-054",
                            STATE,
                            MODULE_NAME,
                            {
                                "detail": "polygon_source_expected",
                                "merchant_id": merchant_id,
                                "legal_country_iso": legal_country_iso,
                                "site_order": site_order,
                                "tzid_provisional_source": tzid_provisional_source,
                            },
                        )
                    if s1_override_scope is not None:
                        _emit_failure_event(
                            logger,
                            "2A-S2-054",
                            seed,
                            str(manifest_fingerprint),
                            str(parameter_hash),
                            run_id,
                            {
                                "detail": "override_scope_present_with_polygon",
                                "merchant_id": merchant_id,
                                "legal_country_iso": legal_country_iso,
                                "site_order": site_order,
                            },
                        )
                        raise EngineFailure(
                            "F4",
                            "2A-S2-054",
                            STATE,
                            MODULE_NAME,
                            {
                                "detail": "override_scope_present_with_polygon",
                                "merchant_id": merchant_id,
                                "legal_country_iso": legal_country_iso,
                                "site_order": site_order,
                            },
                        )

                override_scope: Optional[str] = None
                override_tzid: Optional[str] = None
                if override_applied:
                    site_key = f"{merchant_id}|{legal_country_iso}|{site_order}"
                    if site_key in overrides_site:
                        override_scope = "site"
                        override_tzid = overrides_site[site_key]
                    elif overrides_mcc:
                        mcc_key = mcc_lookup.get(merchant_id)
                        if mcc_key is None:
                            counts["mcc_targets_missing"] += 1
                            _emit_failure_event(
                                logger,
                                "2A-S2-023",
                                seed,
                                str(manifest_fingerprint),
                                str(parameter_hash),
                                run_id,
                                {"detail": "mcc_target_unknown", "merchant_id": merchant_id},
                            )
                            raise EngineFailure(
                                "F4",
                                "2A-S2-023",
                                STATE,
                                MODULE_NAME,
                                {"detail": "mcc_target_unknown", "merchant_id": merchant_id},
                            )
                        if mcc_key in overrides_mcc:
                            override_scope = "mcc"
                            override_tzid = overrides_mcc[mcc_key]
                    if override_scope is None and legal_country_iso in overrides_country:
                        override_scope = "country"
                        override_tzid = overrides_country[legal_country_iso]

                tzid_source = "polygon"
                tzid_final = tzid_provisional
                if override_applied:
                    if override_scope is None or override_tzid is None:
                        _emit_failure_event(
                            logger,
                            "2A-S2-024",
                            seed,
                            str(manifest_fingerprint),
                            str(parameter_hash),
                            run_id,
                            {
                                "detail": "override_missing_or_expired",
                                "merchant_id": merchant_id,
                                "legal_country_iso": legal_country_iso,
                                "site_order": site_order,
                            },
                        )
                        raise EngineFailure(
                            "F4",
                            "2A-S2-024",
                            STATE,
                            MODULE_NAME,
                            {
                                "detail": "override_missing_or_expired",
                                "merchant_id": merchant_id,
                                "legal_country_iso": legal_country_iso,
                                "site_order": site_order,
                            },
                        )
                    if override_scope != s1_override_scope or override_tzid != tzid_provisional:
                        _emit_failure_event(
                            logger,
                            "2A-S2-054",
                            seed,
                            str(manifest_fingerprint),
                            str(parameter_hash),
                            run_id,
                            {
                                "detail": "override_mismatch_s1",
                                "merchant_id": merchant_id,
                                "legal_country_iso": legal_country_iso,
                                "site_order": site_order,
                                "s1_override_scope": s1_override_scope,
                                "override_scope": override_scope,
                                "s1_tzid": tzid_provisional,
                                "override_tzid": override_tzid,
                            },
                        )
                        raise EngineFailure(
                            "F4",
                            "2A-S2-054",
                            STATE,
                            MODULE_NAME,
                            {
                                "detail": "override_mismatch_s1",
                                "merchant_id": merchant_id,
                                "legal_country_iso": legal_country_iso,
                                "site_order": site_order,
                                "s1_override_scope": s1_override_scope,
                                "override_scope": override_scope,
                                "s1_tzid": tzid_provisional,
                                "override_tzid": override_tzid,
                            },
                        )
                    tzid_source = "override"
                    tzid_final = override_tzid
                    counts["overridden_total"] += 1
                    counts["overridden_by_scope"][override_scope] += 1
                if not override_applied and tzid_source != "polygon":
                    counts["override_no_effect"] += 1
                    _emit_failure_event(
                        logger,
                        "2A-S2-055",
                        seed,
                        str(manifest_fingerprint),
                        str(parameter_hash),
                        run_id,
                        {
                            "detail": "override_no_effect",
                            "merchant_id": merchant_id,
                            "legal_country_iso": legal_country_iso,
                            "site_order": site_order,
                        },
                    )
                    raise EngineFailure(
                        "F4",
                        "2A-S2-055",
                        STATE,
                        MODULE_NAME,
                        {
                            "detail": "override_no_effect",
                            "merchant_id": merchant_id,
                            "legal_country_iso": legal_country_iso,
                            "site_order": site_order,
                        },
                    )
                if tzid_final is None or tzid_final == "":
                    checks["null_tzid"] += 1
                    _emit_failure_event(
                        logger,
                        "2A-S2-052",
                        seed,
                        str(manifest_fingerprint),
                        str(parameter_hash),
                        run_id,
                        {
                            "detail": "null_tzid",
                            "merchant_id": merchant_id,
                            "legal_country_iso": legal_country_iso,
                            "site_order": site_order,
                        },
                    )
                    raise EngineFailure(
                        "F4",
                        "2A-S2-052",
                        STATE,
                        MODULE_NAME,
                        {
                            "detail": "null_tzid",
                            "merchant_id": merchant_id,
                            "legal_country_iso": legal_country_iso,
                            "site_order": site_order,
                        },
                    )

                tzid_value = str(tzid_final)
                if list(tzid_validator.iter_errors(tzid_value)):
                    checks["unknown_tzid"] += 1
                    _emit_failure_event(
                        logger,
                        "2A-S2-053",
                        seed,
                        str(manifest_fingerprint),
                        str(parameter_hash),
                        run_id,
                        {
                            "detail": "unknown_tzid",
                            "tzid": tzid_value,
                            "merchant_id": merchant_id,
                            "legal_country_iso": legal_country_iso,
                            "site_order": site_order,
                        },
                    )
                    raise EngineFailure(
                        "F4",
                        "2A-S2-053",
                        STATE,
                        MODULE_NAME,
                        {
                            "detail": "unknown_tzid",
                            "tzid": tzid_value,
                            "merchant_id": merchant_id,
                            "legal_country_iso": legal_country_iso,
                            "site_order": site_order,
                        },
                    )

                if tzid_value not in tzid_set:
                    checks["tzid_not_in_tz_world"] += 1
                    _emit_failure_event(
                        logger,
                        "2A-S2-057",
                        seed,
                        str(manifest_fingerprint),
                        str(parameter_hash),
                        run_id,
                        {
                            "detail": "tzid_not_in_tz_world",
                            "tzid": tzid_value,
                            "merchant_id": merchant_id,
                            "legal_country_iso": legal_country_iso,
                            "site_order": site_order,
                        },
                    )
                    raise EngineFailure(
                        "F4",
                        "2A-S2-057",
                        STATE,
                        MODULE_NAME,
                        {
                            "detail": "tzid_not_in_tz_world",
                            "tzid": tzid_value,
                            "merchant_id": merchant_id,
                            "legal_country_iso": legal_country_iso,
                            "site_order": site_order,
                        },
                    )

                if tzid_source == "override" and override_scope not in ("site", "mcc", "country"):
                    _emit_failure_event(
                        logger,
                        "2A-S2-054",
                        seed,
                        str(manifest_fingerprint),
                        str(parameter_hash),
                        run_id,
                        {
                            "detail": "override_scope_missing",
                            "merchant_id": merchant_id,
                            "legal_country_iso": legal_country_iso,
                            "site_order": site_order,
                        },
                    )
                    raise EngineFailure(
                        "F4",
                        "2A-S2-054",
                        STATE,
                        MODULE_NAME,
                        {
                            "detail": "override_scope_missing",
                            "merchant_id": merchant_id,
                            "legal_country_iso": legal_country_iso,
                            "site_order": site_order,
                        },
                    )
                if tzid_source == "polygon" and override_scope is not None:
                    _emit_failure_event(
                        logger,
                        "2A-S2-054",
                        seed,
                        str(manifest_fingerprint),
                        str(parameter_hash),
                        run_id,
                        {
                            "detail": "override_scope_present_with_polygon",
                            "merchant_id": merchant_id,
                            "legal_country_iso": legal_country_iso,
                            "site_order": site_order,
                        },
                    )
                    raise EngineFailure(
                        "F4",
                        "2A-S2-054",
                        STATE,
                        MODULE_NAME,
                        {
                            "detail": "override_scope_present_with_polygon",
                            "merchant_id": merchant_id,
                            "legal_country_iso": legal_country_iso,
                            "site_order": site_order,
                        },
                    )

                nudge_lat = row["nudge_lat_deg"]
                nudge_lon = row["nudge_lon_deg"]
                if (nudge_lat is None) != (nudge_lon is None):
                    _emit_failure_event(
                        logger,
                        "2A-S2-056",
                        seed,
                        str(manifest_fingerprint),
                        str(parameter_hash),
                        run_id,
                        {
                            "detail": "nudge_pair_mismatch",
                            "merchant_id": merchant_id,
                            "legal_country_iso": legal_country_iso,
                            "site_order": site_order,
                        },
                    )
                    raise EngineFailure(
                        "F4",
                        "2A-S2-056",
                        STATE,
                        MODULE_NAME,
                        {
                            "detail": "nudge_pair_mismatch",
                            "merchant_id": merchant_id,
                            "legal_country_iso": legal_country_iso,
                            "site_order": site_order,
                        },
                    )

                if created_utc != receipt_verified_utc:
                    _emit_failure_event(
                        logger,
                        "2A-S2-042",
                        seed,
                        str(manifest_fingerprint),
                        str(parameter_hash),
                        run_id,
                        {
                            "detail": "created_utc_mismatch",
                            "created_utc": created_utc,
                            "receipt_verified_utc": receipt_verified_utc,
                        },
                    )
                    raise EngineFailure(
                        "F4",
                        "2A-S2-042",
                        STATE,
                        MODULE_NAME,
                        {
                            "detail": "created_utc_mismatch",
                            "created_utc": created_utc,
                            "receipt_verified_utc": receipt_verified_utc,
                        },
                    )

                counts["sites_total"] += 1
                counts["rows_emitted"] += 1
                tzids_seen.add(tzid_value)
                output_rows.append(
                    {
                        "seed": seed,
                        "manifest_fingerprint": str(manifest_fingerprint),
                        "merchant_id": merchant_id,
                        "legal_country_iso": legal_country_iso,
                        "site_order": site_order,
                        "tzid": tzid_value,
                        "tzid_source": tzid_source,
                        "override_scope": override_scope,
                        "nudge_lat_deg": nudge_lat,
                        "nudge_lon_deg": nudge_lon,
                        "created_utc": created_utc,
                    }
                )

            df = pl.DataFrame(output_rows, schema=output_schema, orient="row")
            try:
                validate_dataframe(df.iter_rows(named=True), output_pack, output_table)
            except SchemaValidationError as exc:
                _emit_failure_event(
                    logger,
                    "2A-S2-030",
                    seed,
                    str(manifest_fingerprint),
                    str(parameter_hash),
                    run_id,
                    {"detail": exc.errors},
                )
                raise EngineFailure(
                    "F4",
                    "2A-S2-030",
                    STATE,
                    MODULE_NAME,
                    {"detail": exc.errors},
                ) from exc
            if not output_schema_validated:
                _emit_validation(logger, seed, str(manifest_fingerprint), "V-08", "pass")
                output_schema_validated = True

            _write_batch(df, batch_index, output_tmp, logger)
            batch_index += 1
            output_rows.clear()
            progress.update(df.height)
            if not partition_validated:
                _emit_validation(logger, seed, str(manifest_fingerprint), "V-03", "pass")
                partition_validated = True

        counts["distinct_tzids"] = len(tzids_seen)

        if counts["rows_emitted"] != counts["sites_total"]:
            checks["coverage_mismatch"] = abs(counts["sites_total"] - counts["rows_emitted"])
            _emit_failure_event(
                logger,
                "2A-S2-050",
                seed,
                str(manifest_fingerprint),
                str(parameter_hash),
                run_id,
                {"detail": "coverage_mismatch", "sites_total": counts["sites_total"]},
            )
            raise EngineFailure(
                "F4",
                "2A-S2-050",
                STATE,
                MODULE_NAME,
                {"detail": "coverage_mismatch", "sites_total": counts["sites_total"]},
            )

        _emit_validation(logger, seed, str(manifest_fingerprint), "V-05", "pass")
        _emit_validation(logger, seed, str(manifest_fingerprint), "V-07", "pass")
        _emit_validation(logger, seed, str(manifest_fingerprint), "V-09", "pass")
        _emit_validation(logger, seed, str(manifest_fingerprint), "V-11", "pass")
        _emit_validation(logger, seed, str(manifest_fingerprint), "V-12", "pass")
        _emit_validation(logger, seed, str(manifest_fingerprint), "V-13", "pass")
        _emit_validation(logger, seed, str(manifest_fingerprint), "V-14", "pass")
        _emit_validation(logger, seed, str(manifest_fingerprint), "V-15", "pass")
        _emit_validation(logger, seed, str(manifest_fingerprint), "V-15b", "pass")
        _emit_validation(logger, seed, str(manifest_fingerprint), "V-16", "pass")
        _emit_validation(logger, seed, str(manifest_fingerprint), "V-17", "pass")
        _emit_validation(logger, seed, str(manifest_fingerprint), "V-18", "pass")
        if writer_order_violation:
            _emit_validation(
                logger,
                seed,
                str(manifest_fingerprint),
                "V-19",
                "warn",
                error_code="2A-S2-070",
            )
            warnings.append("2A-S2-070 WRITER_ORDER_NONCOMPLIANT")
        else:
            _emit_validation(logger, seed, str(manifest_fingerprint), "V-19", "pass")

        _atomic_publish_dir(output_tmp, output_root, logger, "site_timezones")
        _emit_validation(logger, seed, str(manifest_fingerprint), "V-10", "pass")
        _emit_event(
            logger,
            "EMIT",
            seed,
            str(manifest_fingerprint),
            "INFO",
            output_path=output_catalog_path,
            format="parquet",
        )
        status = "pass"
        return S2Result(
            run_id=run_id,
            parameter_hash=str(parameter_hash),
            manifest_fingerprint=str(manifest_fingerprint),
            output_root=output_root,
            run_report_path=run_report_path,
        )
    except EngineFailure as exc:
        errors.append(
            {
                "code": exc.failure_code,
                "message": str(exc),
                "context": exc.detail,
            }
        )
        raise
    finally:
        finished_utc = utc_now_rfc3339_micro()
        if run_report_path:
            inputs_block = {
                "s1_tz_lookup": {"path": s1_catalog_path},
                "tz_overrides": {"version_tag": tz_overrides_version, "sha256_digest": tz_overrides_digest},
                "tz_world": {"path": _render_catalog_path(entries["tz_world_2025a"], tokens)},
            }
            if mcc_map_id:
                inputs_block["merchant_mcc_map"] = {
                    "dataset_id": mcc_map_id,
                    "sha256_digest": mcc_map_digest,
                }
            run_report = {
                "segment": SEGMENT,
                "state": STATE,
                "status": status,
                "manifest_fingerprint": str(manifest_fingerprint) if manifest_fingerprint else "",
                "seed": int(seed) if seed is not None else 0,
                "started_utc": started_utc,
                "finished_utc": finished_utc,
                "durations": {"wall_ms": int((time.monotonic() - started_monotonic) * 1000)},
                "s0": {"receipt_path": receipt_catalog_path, "verified_at_utc": receipt_verified_utc},
                "inputs": inputs_block,
                "counts": counts,
                "checks": checks,
                "output": {"path": output_catalog_path, "format": "parquet"},
                "warnings": warnings,
                "errors": errors,
            }
            _write_json(run_report_path, run_report)
            logger.info("S2: run-report written %s", run_report_path)
