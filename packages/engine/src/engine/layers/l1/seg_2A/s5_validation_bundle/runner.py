"""S5 validation bundle runner for Segment 2A."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from engine.contracts.loader import (
    find_artifact_entry,
    find_dataset_entry,
    load_artefact_registry,
    load_dataset_dictionary,
    load_schema_pack,
)
from engine.contracts.source import ContractSource
from engine.core.config import EngineConfig
from engine.core.errors import (
    ContractError,
    EngineFailure,
    InputResolutionError,
    SchemaValidationError,
)
from engine.core.logging import add_file_handler, get_logger
from engine.core.paths import RunPaths
from engine.core.time import utc_now_rfc3339_micro
from engine.layers.l1.seg_2A.s0_gate.runner import (
    _load_json,
    _render_catalog_path,
    _resolve_dataset_path,
    _resolve_run_receipt,
    _validate_payload,
)


MODULE_NAME = "2A.S5.validation_bundle"
SEGMENT = "2A"
STATE = "S5"

DATASET_RECEIPT = "s0_gate_receipt_2A"
DATASET_CACHE = "tz_timetable_cache"
DATASET_SITE_TZ = "site_timezones"
DATASET_S4 = "s4_legality_report"
DATASET_BUNDLE = "validation_bundle_2A"
DATASET_INDEX = "validation_bundle_index_2A"
DATASET_FLAG = "validation_passed_flag_2A"

INDEX_FILENAME = "index.json"
CHECKS_FILENAME = "checks.json"
PASS_FLAG = "_passed.flag"

HEX64_RE = re.compile(r"^[a-f0-9]{64}$")


@dataclass(frozen=True)
class S5Result:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    decision: str
    bundle_root: Path
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


class _FailureTracker:
    def __init__(
        self,
        logger,
        seed: int,
        manifest_fingerprint: str,
        parameter_hash: str,
        run_id: str,
    ) -> None:
        self._logger = logger
        self._seed = seed
        self._manifest_fingerprint = manifest_fingerprint
        self._parameter_hash = parameter_hash
        self._run_id = run_id
        self.errors: list[dict] = []
        self._log_counts: dict[str, int] = {}

    def record(self, code: str, message: str, context: Optional[dict] = None) -> None:
        self.errors.append({"code": code, "message": message, "context": context or {}})
        count = self._log_counts.get(code, 0)
        if count < 5:
            payload = {
                "event": "S5_ERROR",
                "code": code,
                "at": utc_now_rfc3339_micro(),
                "seed": self._seed,
                "manifest_fingerprint": self._manifest_fingerprint,
                "parameter_hash": self._parameter_hash,
                "run_id": self._run_id,
            }
            if context:
                payload.update(context)
            self._logger.error("S5_ERROR %s", json.dumps(payload, ensure_ascii=True, sort_keys=True))
        self._log_counts[code] = count + 1


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


def _json_bytes(payload: object) -> bytes:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_json_bytes(payload))


def _hex64(value: str) -> bool:
    return bool(HEX64_RE.fullmatch(value or ""))


def _root_scoped(path: str) -> bool:
    if not path or path.startswith(("/", "\\")) or ":" in path:
        return False
    parts = Path(path).parts
    if any(part in (".", "..") for part in parts):
        return False
    return True


def _hash_partition(root: Path) -> tuple[str, int]:
    files = sorted(
        [path for path in root.rglob("*") if path.is_file()],
        key=lambda path: path.relative_to(root).as_posix(),
    )
    h = hashlib.sha256()
    total_bytes = 0
    for path in files:
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                total_bytes += len(chunk)
                h.update(chunk)
    return h.hexdigest(), total_bytes


def _atomic_publish_dir(tmp_root: Path, final_root: Path, logger, label: str) -> None:
    if final_root.exists():
        tmp_hash, _ = _hash_partition(tmp_root)
        final_hash, _ = _hash_partition(final_root)
        if tmp_hash != final_hash:
            raise EngineFailure(
                "F4",
                "2A-S5-060",
                STATE,
                MODULE_NAME,
                {"detail": "non-identical output exists", "partition": str(final_root), "label": label},
            )
        if tmp_root.exists():
            shutil.rmtree(tmp_root)
        logger.info("S5: %s partition already exists and is identical; skipping publish.", label)
        return
    final_root.parent.mkdir(parents=True, exist_ok=True)
    tmp_root.replace(final_root)


def _bundle_hash(bundle_root: Path, index_entries: list[dict]) -> str:
    h = hashlib.sha256()
    for entry in sorted(index_entries, key=lambda item: item["path"]):
        path = bundle_root / entry["path"]
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                h.update(chunk)
    return h.hexdigest()


def _copy_verbatim(source: Path, target: Path) -> tuple[str, int, bool]:
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = source.read_bytes()
    target.write_bytes(payload)
    written = target.read_bytes()
    return hashlib.sha256(payload).hexdigest(), len(payload), written == payload


def _discover_seeds(
    run_paths: RunPaths,
    entry: dict,
    manifest_fingerprint: str,
) -> list[int]:
    template = entry.get("path") or ""
    if "{seed}" not in template or "{manifest_fingerprint}" not in template:
        raise InputResolutionError("site_timezones path missing seed or fingerprint token.")
    pattern = template.replace("{manifest_fingerprint}", manifest_fingerprint).replace("{seed}", "*")
    if not pattern.startswith(("data/", "logs/", "reports/")):
        raise InputResolutionError("site_timezones discovery must be run-local data path.")
    seeds: set[int] = set()
    for match in run_paths.run_root.glob(pattern):
        if not match.exists():
            continue
        for part in match.parts:
            if part.startswith("seed="):
                seed_str = part.split("=", 1)[1]
                if seed_str.isdigit():
                    seeds.add(int(seed_str))
    return sorted(seeds)


def _resolve_schema_ref(entry: dict, registry_entry: Optional[dict], dataset_id: str) -> str:
    dict_ref = entry.get("schema_ref")
    registry_ref = None
    if registry_entry:
        registry_ref = registry_entry.get("schema")
        if isinstance(registry_ref, dict):
            registry_ref = registry_ref.get("index_schema_ref") or registry_ref.get("schema_ref")
    if dict_ref and registry_ref and dict_ref != registry_ref:
        bundle_ok = (
            dataset_id in {DATASET_BUNDLE, DATASET_INDEX}
            and dict_ref.endswith("/validation/validation_bundle_2A")
            and registry_ref.endswith("/validation/bundle_index_v1")
        )
        if not bundle_ok:
            raise EngineFailure(
                "F4",
                "2A-S5-010",
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


def _assert_schema_ref(schema_ref: str, schema_packs: dict[str, dict], dataset_id: str) -> None:
    if not schema_ref:
        raise ContractError(f"Schema ref missing for {dataset_id}.")
    for prefix, pack in schema_packs.items():
        if schema_ref.startswith(f"{prefix}#"):
            path = schema_ref.split("#", 1)[1]
            _schema_from_pack(pack, path)
            return
    raise ContractError(f"Unsupported schema_ref: {schema_ref}")


def run_s5(config: EngineConfig, run_id: Optional[str] = None) -> S5Result:
    logger = get_logger("engine.layers.l1.seg_2A.s5_validation_bundle.l2.runner")
    receipt_path, receipt = _resolve_run_receipt(config.runs_root, run_id)
    run_id = str(receipt.get("run_id") or "")
    if not run_id:
        raise InputResolutionError("run_receipt.json missing run_id")
    seed = int(receipt.get("seed", 0))
    parameter_hash = str(receipt.get("parameter_hash") or "")
    manifest_fingerprint = str(receipt.get("manifest_fingerprint") or "")
    run_paths = RunPaths(config.runs_root, run_id)

    add_file_handler(run_paths.run_root / f"run_log_{run_id}.log")
    timer = _StepTimer(logger)
    logger.info("S5: run log initialized at %s (elapsed=0.00s, delta=0.00s)", run_paths.run_root / f"run_log_{run_id}.log")

    source = ContractSource(config.contracts_root, config.contracts_layout)
    _dict_path, dictionary = load_dataset_dictionary(source, "2A")
    _reg_path, registry = load_artefact_registry(source, "2A")
    _, schema_2a = load_schema_pack(source, "2A", "2A")
    _, schema_1b = load_schema_pack(source, "1B", "1B")
    _, schema_layer1 = load_schema_pack(source, "1A", "layer1")
    schema_packs = {
        "schemas.2A.yaml": schema_2a,
        "schemas.1B.yaml": schema_1b,
        "schemas.layer1.yaml": schema_layer1,
    }

    tracker = _FailureTracker(logger, seed, manifest_fingerprint, parameter_hash, run_id)
    decision = "PASS"
    abort_reads = False

    receipt_entry = None
    cache_entry = None
    site_entry = None
    s4_entry = None
    bundle_entry = None
    index_entry = None
    flag_entry = None
    try:
        receipt_entry = find_dataset_entry(dictionary, DATASET_RECEIPT).entry
        cache_entry = find_dataset_entry(dictionary, DATASET_CACHE).entry
        site_entry = find_dataset_entry(dictionary, DATASET_SITE_TZ).entry
        s4_entry = find_dataset_entry(dictionary, DATASET_S4).entry
        bundle_entry = find_dataset_entry(dictionary, DATASET_BUNDLE).entry
        index_entry = find_dataset_entry(dictionary, DATASET_INDEX).entry
        flag_entry = find_dataset_entry(dictionary, DATASET_FLAG).entry
    except ContractError as exc:
        tracker.record("2A-S5-010", "dictionary_entry_missing", {"detail": str(exc)})
        decision = "FAIL"
        abort_reads = True

    try:
        receipt_reg = find_artifact_entry(registry, DATASET_RECEIPT).entry
        cache_reg = find_artifact_entry(registry, DATASET_CACHE).entry
        site_reg = find_artifact_entry(registry, DATASET_SITE_TZ).entry
        s4_reg = find_artifact_entry(registry, DATASET_S4).entry
        bundle_reg = find_artifact_entry(registry, DATASET_BUNDLE).entry
        index_reg = find_artifact_entry(registry, DATASET_INDEX).entry
        flag_reg = find_artifact_entry(registry, DATASET_FLAG).entry
    except ContractError as exc:
        tracker.record("2A-S5-010", "registry_entry_missing", {"detail": str(exc)})
        decision = "FAIL"
        abort_reads = True
        receipt_reg = cache_reg = site_reg = s4_reg = bundle_reg = index_reg = flag_reg = None

    try:
        for entry, reg_entry, dataset_id in (
            (receipt_entry, receipt_reg, DATASET_RECEIPT),
            (cache_entry, cache_reg, DATASET_CACHE),
            (site_entry, site_reg, DATASET_SITE_TZ),
            (s4_entry, s4_reg, DATASET_S4),
            (bundle_entry, bundle_reg, DATASET_BUNDLE),
            (index_entry, index_reg, DATASET_INDEX),
            (flag_entry, flag_reg, DATASET_FLAG),
        ):
            if entry is None:
                raise ContractError(f"Missing dataset entry for {dataset_id}")
            schema_ref = _resolve_schema_ref(entry, reg_entry, dataset_id)
            _assert_schema_ref(schema_ref, schema_packs, dataset_id)
    except (ContractError, EngineFailure) as exc:
        tracker.record("2A-S5-010", "authority_conflict", {"detail": str(exc)})
        decision = "FAIL"
        abort_reads = True

    tokens = {"manifest_fingerprint": manifest_fingerprint, "seed": str(seed)}
    receipt_catalog_path = _render_catalog_path(receipt_entry, tokens) if receipt_entry else ""
    cache_catalog_path = _render_catalog_path(cache_entry, tokens) if cache_entry else ""
    bundle_catalog_path = _render_catalog_path(bundle_entry, tokens) if bundle_entry else ""

    if abort_reads:
        _emit_validation(
            logger,
            seed,
            manifest_fingerprint,
            "V-02",
            "fail",
            error_code="2A-S5-010",
            detail="input_resolution_failed",
        )
    else:
        _emit_validation(logger, seed, manifest_fingerprint, "V-02", "pass")

    receipt_verified_at = receipt.get("created_utc") or receipt.get("created_utc_ns")
    if not receipt_verified_at:
        receipt_verified_at = receipt.get("verified_at_utc") or utc_now_rfc3339_micro()

    s0_receipt = None
    if not abort_reads and receipt_entry:
        try:
            receipt_path = _resolve_dataset_path(receipt_entry, run_paths, config.external_roots, tokens)
            s0_receipt = _load_json(receipt_path)
            _validate_payload(
                schema_2a,
                "validation/s0_gate_receipt_v1",
                s0_receipt,
                ref_packs={"schemas.layer1.yaml": schema_layer1},
            )
            if s0_receipt.get("manifest_fingerprint") != manifest_fingerprint:
                raise SchemaValidationError("manifest_fingerprint_mismatch", [])
            receipt_verified_at = s0_receipt.get("verified_at_utc", receipt_verified_at)
            _emit_validation(logger, seed, manifest_fingerprint, "V-01", "pass")
            _emit_event(
                logger,
                "GATE",
                seed,
                manifest_fingerprint,
                "INFO",
                receipt_path=receipt_catalog_path,
                verified_at_utc=receipt_verified_at,
            )
        except (InputResolutionError, SchemaValidationError, EngineFailure) as exc:
            tracker.record("2A-S5-001", "missing_or_invalid_receipt", {"detail": str(exc)})
            decision = "FAIL"
            abort_reads = True
            _emit_validation(
                logger,
                seed,
                manifest_fingerprint,
                "V-01",
                "fail",
                error_code="2A-S5-001",
                detail="missing_or_invalid_receipt",
            )

    seeds: list[int] = []
    if not abort_reads and site_entry:
        try:
            seeds = _discover_seeds(run_paths, site_entry, manifest_fingerprint)
            _emit_validation(logger, seed, manifest_fingerprint, "V-03", "pass")
        except InputResolutionError as exc:
            tracker.record("2A-S5-011", "seed_discovery_failed", {"detail": str(exc)})
            decision = "FAIL"
            _emit_validation(
                logger,
                seed,
                manifest_fingerprint,
                "V-03",
                "fail",
                error_code="2A-S5-011",
                detail="seed_discovery_failed",
            )

    if seeds:
        _emit_event(
            logger,
            "DISCOVERY",
            seed,
            manifest_fingerprint,
            "INFO",
            seeds_discovered=len(seeds),
            seeds=seeds,
        )
    else:
        _emit_event(
            logger,
            "DISCOVERY",
            seed,
            manifest_fingerprint,
            "INFO",
            seeds_discovered=0,
            seeds=[],
        )

    evidence_verbatim_ok = True
    cache_manifest = None
    cache_manifest_path: Optional[Path] = None
    cache_payload_ok = False
    if not abort_reads and cache_entry:
        try:
            cache_root = _resolve_dataset_path(cache_entry, run_paths, config.external_roots, tokens)
            cache_manifest_path = cache_root / "tz_timetable_cache.json"
            cache_manifest = _load_json(cache_manifest_path)
            _validate_payload(
                schema_2a,
                "cache/tz_timetable_cache",
                cache_manifest,
                ref_packs={"schemas.layer1.yaml": schema_layer1},
            )
            if cache_manifest.get("manifest_fingerprint") != manifest_fingerprint:
                raise SchemaValidationError("cache_manifest_fingerprint_mismatch", [])
            rle_bytes = int(cache_manifest.get("rle_cache_bytes", 0))
            cache_bin = cache_root / "tz_cache_v1.bin"
            if rle_bytes <= 0 or not cache_bin.exists():
                raise InputResolutionError("cache payload missing or empty")
            cache_payload_ok = True
            _emit_validation(logger, seed, manifest_fingerprint, "V-04", "pass")
        except (InputResolutionError, SchemaValidationError, EngineFailure) as exc:
            tracker.record("2A-S5-020", "cache_invalid", {"detail": str(exc)})
            decision = "FAIL"
            _emit_validation(
                logger,
                seed,
                manifest_fingerprint,
                "V-04",
                "fail",
                error_code="2A-S5-020",
                detail="cache_invalid",
            )

    evidence_records: list[dict] = []
    evidence_hashes: dict[str, str] = {}
    evidence_sizes: dict[str, int] = {}
    missing_s4: list[int] = []
    failing_s4: list[int] = []

    tmp_root = run_paths.tmp_root / f"s5_validation_bundle_{uuid.uuid4().hex}"
    if tmp_root.exists():
        shutil.rmtree(tmp_root)
    tmp_root.mkdir(parents=True, exist_ok=True)

    if cache_manifest_path and cache_manifest and cache_payload_ok:
        dest = tmp_root / "evidence" / "s3" / "tz_timetable_cache.json"
        sha_hex, size_bytes, matches = _copy_verbatim(cache_manifest_path, dest)
        if not matches:
            evidence_verbatim_ok = False
            tracker.record(
                "2A-S5-046",
                "evidence_not_verbatim",
                {"path": dest.relative_to(tmp_root).as_posix()},
            )
            decision = "FAIL"
        evidence_records.append({"path": dest.relative_to(tmp_root).as_posix(), "sha256_hex": sha_hex})
        evidence_hashes[dest.relative_to(tmp_root).as_posix()] = sha_hex
        evidence_sizes[dest.relative_to(tmp_root).as_posix()] = size_bytes
    else:
        decision = "FAIL"

    if not abort_reads and s4_entry:
        for seed_value in seeds:
            seed_tokens = {"seed": str(seed_value), "manifest_fingerprint": manifest_fingerprint}
            try:
                report_path = _resolve_dataset_path(s4_entry, run_paths, config.external_roots, seed_tokens)
                report = _load_json(report_path)
                _validate_payload(
                    schema_2a,
                    "validation/s4_legality_report",
                    report,
                    ref_packs={"schemas.layer1.yaml": schema_layer1},
                )
                if report.get("manifest_fingerprint") != manifest_fingerprint or int(
                    report.get("seed", -1)
                ) != seed_value:
                    raise SchemaValidationError("s4_path_embed_mismatch", [])
                status = report.get("status")
                if status != "PASS":
                    failing_s4.append(seed_value)
                    tracker.record(
                        "2A-S5-030",
                        "s4_report_not_pass",
                        {"seed": seed_value, "status": status},
                    )
                    decision = "FAIL"
                dest = tmp_root / "evidence" / "s4" / f"seed={seed_value}" / "s4_legality_report.json"
                sha_hex, size_bytes, matches = _copy_verbatim(report_path, dest)
                if not matches:
                    evidence_verbatim_ok = False
                    tracker.record(
                        "2A-S5-046",
                        "evidence_not_verbatim",
                        {"seed": seed_value, "path": dest.relative_to(tmp_root).as_posix()},
                    )
                    decision = "FAIL"
                evidence_records.append(
                    {"path": dest.relative_to(tmp_root).as_posix(), "sha256_hex": sha_hex}
                )
                evidence_hashes[dest.relative_to(tmp_root).as_posix()] = sha_hex
                evidence_sizes[dest.relative_to(tmp_root).as_posix()] = size_bytes
            except (InputResolutionError, SchemaValidationError) as exc:
                missing_s4.append(seed_value)
                tracker.record(
                    "2A-S5-030",
                    "s4_report_missing_or_invalid",
                    {"seed": seed_value, "detail": str(exc)},
                )
                decision = "FAIL"

    if missing_s4 or failing_s4:
        _emit_validation(
            logger,
            seed,
            manifest_fingerprint,
            "V-05",
            "fail",
            error_code="2A-S5-030",
            detail="missing_or_failing_s4",
        )
    else:
        _emit_validation(logger, seed, manifest_fingerprint, "V-05", "pass")

    if evidence_verbatim_ok:
        _emit_validation(logger, seed, manifest_fingerprint, "V-11", "pass")
    else:
        _emit_validation(
            logger,
            seed,
            manifest_fingerprint,
            "V-11",
            "fail",
            error_code="2A-S5-046",
            detail="evidence_not_verbatim",
        )

    checks_payload = {
        "manifest_fingerprint": manifest_fingerprint,
        "generated_at_utc": receipt_verified_at,
        "overall_status": "PASS" if decision == "PASS" else "FAIL",
        "datasets": [
            {
                "id": DATASET_RECEIPT,
                "status": "PASS" if s0_receipt else "FAIL",
                "notes": "gate receipt validation",
            },
            {
                "id": DATASET_CACHE,
                "status": "PASS" if cache_payload_ok else "FAIL",
                "notes": "cache manifest + payload readiness",
            },
            {
                "id": DATASET_S4,
                "status": "PASS" if not missing_s4 and not failing_s4 else "FAIL",
                "notes": f"missing={len(missing_s4)} failing={len(failing_s4)}",
            },
        ],
    }

    try:
        _validate_payload(
            schema_2a,
            "validation/checks_v1",
            checks_payload,
            ref_packs={"schemas.layer1.yaml": schema_layer1},
        )
    except SchemaValidationError as exc:
        tracker.record("2A-S5-040", "checks_schema_invalid", {"detail": str(exc)})
        decision = "FAIL"

    checks_path = tmp_root / CHECKS_FILENAME
    _write_json(checks_path, checks_payload)
    checks_hash = hashlib.sha256(checks_path.read_bytes()).hexdigest()
    checks_size = checks_path.stat().st_size
    evidence_records.append({"path": CHECKS_FILENAME, "sha256_hex": checks_hash})
    evidence_hashes[CHECKS_FILENAME] = checks_hash
    evidence_sizes[CHECKS_FILENAME] = checks_size

    _emit_event(
        logger,
        "EVIDENCE",
        seed,
        manifest_fingerprint,
        "INFO",
        files=len(evidence_records),
        bytes_total=sum(evidence_sizes.values()),
    )

    index_entries = sorted(evidence_records, key=lambda item: item["path"])
    index_paths = [entry["path"] for entry in index_entries]
    duplicates = {path for path in index_paths if index_paths.count(path) > 1}
    if duplicates:
        tracker.record(
            "2A-S5-043",
            "duplicate_index_entries",
            {"paths": sorted(duplicates)},
        )
        decision = "FAIL"

    root_scoped = all(_root_scoped(path) for path in index_paths)
    if not root_scoped:
        tracker.record("2A-S5-042", "index_path_out_of_root", {})
        decision = "FAIL"

    if any(path == PASS_FLAG for path in index_paths):
        tracker.record("2A-S5-045", "flag_listed_in_index", {})
        decision = "FAIL"

    index_payload = {"files": index_entries}
    try:
        _validate_payload(
            schema_2a,
            "validation/bundle_index_v1",
            index_payload,
            ref_packs={"schemas.layer1.yaml": schema_layer1},
        )
        _emit_validation(logger, seed, manifest_fingerprint, "V-06", "pass")
    except SchemaValidationError as exc:
        tracker.record("2A-S5-040", "index_schema_invalid", {"detail": str(exc)})
        decision = "FAIL"
        _emit_validation(
            logger,
            seed,
            manifest_fingerprint,
            "V-06",
            "fail",
            error_code="2A-S5-040",
            detail="index_schema_invalid",
        )

    _write_json(tmp_root / INDEX_FILENAME, index_payload)

    bundle_files = [
        path.relative_to(tmp_root).as_posix()
        for path in tmp_root.rglob("*")
        if path.is_file()
    ]
    indexed_set = set(index_paths)
    unlisted = sorted(
        path for path in bundle_files if path not in indexed_set and path not in {INDEX_FILENAME, PASS_FLAG}
    )
    if unlisted:
        tracker.record("2A-S5-044", "index_unlisted_file", {"paths": unlisted[:5]})
        decision = "FAIL"

    index_sorted = index_paths == sorted(index_paths)
    if not index_sorted:
        tracker.record("2A-S5-041", "index_not_ascii_lex", {})
        decision = "FAIL"

    index_hex_ok = all(_hex64(entry["sha256_hex"]) for entry in index_entries)
    if not index_hex_ok:
        tracker.record("2A-S5-051", "index_hex_invalid", {})
        decision = "FAIL"

    _emit_event(
        logger,
        "INDEX",
        seed,
        manifest_fingerprint,
        "INFO",
        entries=len(index_entries),
    )

    if index_sorted and not duplicates:
        _emit_validation(logger, seed, manifest_fingerprint, "V-07", "pass")
    else:
        error_code = "2A-S5-041" if not index_sorted else "2A-S5-043"
        _emit_validation(
            logger,
            seed,
            manifest_fingerprint,
            "V-07",
            "fail",
            error_code=error_code,
            detail="index_order_or_duplicates",
        )

    if root_scoped:
        _emit_validation(logger, seed, manifest_fingerprint, "V-08", "pass")
    else:
        _emit_validation(
            logger,
            seed,
            manifest_fingerprint,
            "V-08",
            "fail",
            error_code="2A-S5-042",
            detail="index_path_out_of_root",
        )

    if not unlisted:
        _emit_validation(logger, seed, manifest_fingerprint, "V-09", "pass")
    else:
        _emit_validation(
            logger,
            seed,
            manifest_fingerprint,
            "V-09",
            "fail",
            error_code="2A-S5-044",
            detail="index_unlisted_file",
        )

    if PASS_FLAG not in index_paths:
        _emit_validation(logger, seed, manifest_fingerprint, "V-10", "pass")
    else:
        _emit_validation(
            logger,
            seed,
            manifest_fingerprint,
            "V-10",
            "fail",
            error_code="2A-S5-045",
            detail="flag_listed_in_index",
        )

    bundle_hash = _bundle_hash(tmp_root, index_entries)
    flag_value = ""
    flag_format_ok = False
    digest_matches_flag = False
    if decision == "PASS":
        flag_payload = f"sha256_hex = {bundle_hash}"
        (tmp_root / PASS_FLAG).write_text(flag_payload + "\n", encoding="ascii")
        flag_value = bundle_hash
        flag_format_ok = bool(re.fullmatch(r"sha256_hex = [a-f0-9]{64}", flag_payload))
        if not flag_format_ok:
            tracker.record("2A-S5-052", "flag_format_invalid", {})
            decision = "FAIL"
        digest_matches_flag = flag_format_ok and flag_value == bundle_hash
        if not digest_matches_flag:
            tracker.record("2A-S5-050", "flag_digest_mismatch", {})
            decision = "FAIL"
    else:
        digest_matches_flag = False

    flag_hex_ok = bool(flag_value and _hex64(flag_value))
    if not flag_hex_ok:
        tracker.record("2A-S5-051", "flag_hex_invalid_or_missing", {})
        decision = "FAIL"

    if index_hex_ok and flag_hex_ok:
        _emit_validation(logger, seed, manifest_fingerprint, "V-12", "pass")
    else:
        _emit_validation(
            logger,
            seed,
            manifest_fingerprint,
            "V-12",
            "fail",
            error_code="2A-S5-051",
            detail="index_or_flag_hex_invalid",
        )

    if flag_format_ok:
        _emit_validation(logger, seed, manifest_fingerprint, "V-13", "pass")
    else:
        _emit_validation(
            logger,
            seed,
            manifest_fingerprint,
            "V-13",
            "fail",
            error_code="2A-S5-052",
            detail="flag_format_invalid_or_missing",
        )

    if digest_matches_flag:
        _emit_validation(logger, seed, manifest_fingerprint, "V-14", "pass")
    else:
        _emit_validation(
            logger,
            seed,
            manifest_fingerprint,
            "V-14",
            "fail",
            error_code="2A-S5-050",
            detail="flag_missing_or_digest_mismatch",
        )

    _emit_event(
        logger,
        "DIGEST",
        seed,
        manifest_fingerprint,
        "INFO",
        sha256=bundle_hash,
        flag_written=decision == "PASS",
    )

    bundle_partition_ok = True
    if bundle_entry:
        partitioning = bundle_entry.get("partitioning") or []
        template_path = bundle_entry.get("path") or ""
        if partitioning != ["manifest_fingerprint"] or "{seed}" in template_path or "seed=" in template_path:
            tracker.record(
                "2A-S5-012",
                "partition_purity_violation",
                {"partitioning": partitioning, "path": template_path},
            )
            decision = "FAIL"
            bundle_partition_ok = False
    else:
        bundle_partition_ok = False
        tracker.record("2A-S5-012", "partition_purity_violation", {"detail": "missing_bundle_entry"})
        decision = "FAIL"

    if bundle_partition_ok:
        _emit_validation(logger, seed, manifest_fingerprint, "V-15", "pass")
    else:
        _emit_validation(
            logger,
            seed,
            manifest_fingerprint,
            "V-15",
            "fail",
            error_code="2A-S5-012",
            detail="partition_purity_violation",
        )

    bundle_root = (
        _resolve_dataset_path(bundle_entry, run_paths, config.external_roots, tokens)
        if bundle_entry
        else Path("")
    )
    if bundle_entry:
        try:
            _atomic_publish_dir(tmp_root, bundle_root, logger, "validation_bundle_2A")
            _emit_validation(logger, seed, manifest_fingerprint, "V-16", "pass")
        except EngineFailure as exc:
            tracker.record("2A-S5-060", "immutable_partition_overwrite", {"detail": str(exc)})
            decision = "FAIL"
            _emit_validation(
                logger,
                seed,
                manifest_fingerprint,
                "V-16",
                "fail",
                error_code="2A-S5-060",
                detail="immutable_partition_overwrite",
            )

    bytes_indexed = sum(evidence_sizes.get(path, 0) for path in index_paths)
    missing_sample = missing_s4[:10]
    run_report = {
        "segment": SEGMENT,
        "state": STATE,
        "status": "pass" if decision == "PASS" else "fail",
        "manifest_fingerprint": manifest_fingerprint,
        "started_utc": receipt_verified_at,
        "finished_utc": receipt_verified_at,
        "durations": {"wall_ms": 0},
        "s0": {"receipt_path": receipt_catalog_path, "verified_at_utc": receipt_verified_at},
        "inputs": {
            "cache": {
                "path": cache_catalog_path,
                "tzdb_release_tag": (cache_manifest or {}).get("tzdb_release_tag", ""),
                "rle_cache_bytes": int((cache_manifest or {}).get("rle_cache_bytes", 0)),
                "tz_index_digest": (cache_manifest or {}).get("tz_index_digest", ""),
            }
        },
        "seeds": {"discovered": len(seeds), "list": seeds},
        "s4": {
            "covered": len(seeds) - len(missing_s4),
            "missing": len(missing_s4),
            "failing": len(failing_s4),
            "sample_missing": missing_sample,
        },
        "bundle": {
            "path": bundle_catalog_path,
            "files_indexed": len(index_entries),
            "bytes_indexed": bytes_indexed,
            "index_sorted_ascii_lex": index_sorted,
            "index_path_root_scoped": root_scoped,
            "includes_flag_in_index": PASS_FLAG in index_paths,
        },
        "digest": {
            "computed_sha256": bundle_hash,
            "matches_flag": digest_matches_flag,
        },
        "flag": {"value": flag_value, "format_exact": flag_format_ok},
        "warnings": [],
        "errors": tracker.errors,
    }

    run_report_path = (
        run_paths.run_root
        / "reports"
        / "layer1"
        / "2A"
        / "state=S5"
        / f"manifest_fingerprint={manifest_fingerprint}"
        / "s5_run_report.json"
    )
    _write_json(run_report_path, run_report)
    timer.info(f"S5: run-report written {run_report_path}")

    _emit_event(
        logger,
        "EMIT",
        seed,
        manifest_fingerprint,
        "INFO",
        output_path=bundle_catalog_path,
        decision=decision,
    )

    return S5Result(
        run_id=run_id,
        parameter_hash=parameter_hash,
        manifest_fingerprint=manifest_fingerprint,
        decision=decision,
        bundle_root=bundle_root,
        run_report_path=run_report_path,
    )


__all__ = ["S5Result", "run_s5"]
