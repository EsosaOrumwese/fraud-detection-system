"""S6 virtual-edge router runner for Segment 2B."""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import shutil
import time
import uuid
from collections import OrderedDict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from jsonschema import Draft202012Validator

from engine.contracts.loader import (
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
from engine.layers.l1.seg_1A.s0_foundations.rng import RngTraceAccumulator
from engine.layers.l1.seg_1A.s1_hurdle.rng import (
    add_u128,
    low64,
    philox2x64_10,
    ser_u64,
    u01,
    uer_string,
)
from engine.layers.l1.seg_2B.s0_gate.runner import (
    _inline_external_refs,
    _render_catalog_path,
    _resolve_dataset_path,
    _resolve_run_receipt,
    _schema_from_pack,
)


MODULE_NAME = "2B.S6.edge_router"
EVENT_MODULE = "2B.virtual_edge"
SEGMENT = "2B"
STATE = "S6"

EPSILON = 1e-9
EDGE_CACHE_MAX = 20_000


@dataclass(frozen=True)
class S6Result:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    run_report_path: Path
    edge_log_enabled: bool


@dataclass
class AliasTable:
    items: list[str]
    prob: list[float]
    alias: list[int]


@dataclass(frozen=True)
class EdgeMeta:
    edge_id: str
    ip_country: str
    edge_lat: float
    edge_lon: float


class _StepTimer:
    def __init__(self, logger) -> None:
        self._logger = logger
        self._start = time.monotonic()
        self._last = self._start

    def info(self, message: str, *args: object) -> None:
        now = time.monotonic()
        elapsed = now - self._start
        delta = now - self._last
        self._last = now
        if args:
            message = message % args
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
        if self._total is not None and self._total > 0:
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
    payload: dict[str, object] = {"validator_id": validator_id, "result": result}
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
    validator: str,
    message: str,
    context: dict,
) -> None:
    payload = {
        "event": "S6_ERROR",
        "code": code,
        "severity": "ERROR",
        "message": message,
        "manifest_fingerprint": manifest_fingerprint,
        "seed": seed,
        "validator": validator,
        "context": context,
        "run_id": run_id,
        "parameter_hash": parameter_hash,
        "at": utc_now_rfc3339_micro(),
    }
    logger.error("S6_ERROR %s", json.dumps(payload, ensure_ascii=True, sort_keys=True))


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise InputResolutionError(f"Missing JSON file: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _table_pack(schema_pack: dict, path: str) -> tuple[dict, str]:
    node: dict = schema_pack
    parts = path.strip("#/").split("/")
    for part in parts[:-1]:
        if part not in node or not isinstance(node[part], dict):
            raise ContractError(f"Schema section not found: {path}")
        node = node[part]
    table_name = parts[-1]
    table_def = node.get(table_name)
    if not isinstance(table_def, dict):
        raise ContractError(f"Schema section not found: {path}")
    pack = {"$id": schema_pack.get("$id", ""), "$defs": schema_pack.get("$defs", {})}
    pack[table_name] = table_def
    return pack, table_name


def _validate_payload(
    schema_pack: dict,
    schema_path: str,
    payload: dict,
    ref_packs: Optional[dict[str, dict]] = None,
) -> None:
    schema = _schema_from_pack(schema_pack, schema_path)
    if ref_packs:
        for prefix, pack in ref_packs.items():
            _inline_external_refs(schema, pack, prefix)
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    if errors:
        raise SchemaValidationError(schema_path, errors)


def _resolve_entries(dictionary: dict) -> dict[str, dict]:
    required_ids = (
        "s0_gate_receipt_2B",
        "sealed_inputs_2B",
        "route_rng_policy_v1",
        "virtual_edge_policy_v1",
        "s5_arrival_roster",
        "rng_event_cdn_edge_pick",
        "rng_trace_log",
        "rng_audit_log",
    )
    entries: dict[str, dict] = {}
    for dataset_id in required_ids:
        entries[dataset_id] = find_dataset_entry(dictionary, dataset_id).entry
    return entries


def _find_sealed_asset(sealed_inputs: list[dict], asset_id: str) -> Optional[dict]:
    for item in sealed_inputs:
        if isinstance(item, dict) and item.get("asset_id") == asset_id:
            return item
    return None


def _render_output_path(run_paths: RunPaths, catalog_path: str) -> Path:
    rendered = catalog_path
    if "*" in rendered:
        rendered = rendered.replace("*", "00000")
    return run_paths.run_root / rendered

def _atomic_publish_file(tmp_path: Path, final_path: Path, logger, label: str) -> bool:
    if final_path.exists():
        tmp_hash = sha256_file(tmp_path).sha256_hex
        final_hash = sha256_file(final_path).sha256_hex
        if tmp_hash != final_hash:
            raise EngineFailure(
                "F4",
                "2B-S6-080",
                STATE,
                MODULE_NAME,
                {"detail": "non-identical output exists", "path": str(final_path), "label": label},
            )
        tmp_path.unlink(missing_ok=True)
        logger.info("S6: %s already exists and is identical; skipping publish.", label)
        return True
    final_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        tmp_path.replace(final_path)
    except OSError as exc:
        raise EngineFailure(
            "F4",
            "2B-S6-082",
            STATE,
            MODULE_NAME,
            {"detail": "atomic publish failed", "path": str(final_path), "error": str(exc)},
        ) from exc
    return False


def _ensure_rng_audit(audit_path: Path, audit_entry: dict, logger, state_label: str) -> None:
    if audit_path.exists():
        with audit_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                payload = json.loads(line)
                if (
                    payload.get("run_id") == audit_entry.get("run_id")
                    and payload.get("seed") == audit_entry.get("seed")
                    and payload.get("parameter_hash") == audit_entry.get("parameter_hash")
                    and payload.get("manifest_fingerprint") == audit_entry.get("manifest_fingerprint")
                ):
                    logger.info(
                        "%s: rng_audit_log already contains audit row for run_id=%s",
                        state_label,
                        audit_entry["run_id"],
                    )
                    return
        with audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(audit_entry, ensure_ascii=True, sort_keys=True))
            handle.write("\n")
        logger.info("%s: appended rng_audit_log entry for run_id=%s", state_label, audit_entry["run_id"])
        return
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(
        json.dumps(audit_entry, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    logger.info("%s: wrote rng_audit_log entry for run_id=%s", state_label, audit_entry["run_id"])


def _read_last_json_line(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    with path.open("rb") as handle:
        handle.seek(0, os.SEEK_END)
        size = handle.tell()
        if size == 0:
            return None
        chunk_size = 4096
        buffer = b""
        while size > 0:
            read_size = chunk_size if size >= chunk_size else size
            size -= read_size
            handle.seek(size)
            buffer = handle.read(read_size) + buffer
            if b"\n" in buffer:
                break
        lines = buffer.split(b"\n")
        for line in reversed(lines):
            if line:
                try:
                    return json.loads(line.decode("utf-8"))
                except json.JSONDecodeError:
                    return None
        return None


def _atomic_append_file(tmp_path: Path, final_path: Path, logger, label: str) -> bool:
    if not tmp_path.exists():
        return True
    if tmp_path.stat().st_size == 0:
        tmp_path.unlink(missing_ok=True)
        logger.info("S6: %s no new rows; skipping append.", label)
        return True
    if final_path.exists():
        tmp_bytes = tmp_path.read_bytes()
        final_size = final_path.stat().st_size
        if final_size >= len(tmp_bytes):
            with final_path.open("rb") as handle:
                handle.seek(final_size - len(tmp_bytes))
                tail = handle.read()
            if tail == tmp_bytes:
                tmp_path.unlink(missing_ok=True)
                logger.info("S6: %s already includes append; skipping.", label)
                return True
        last_row = _read_last_json_line(final_path)
        if last_row and last_row.get("module") == EVENT_MODULE:
            raise EngineFailure(
                "F4",
                "2B-S6-081",
                STATE,
                MODULE_NAME,
                {"detail": "non-idempotent append detected", "path": str(final_path), "label": label},
            )
        combined_path = final_path.parent / f"{label}.append.{uuid.uuid4().hex}.jsonl"
        combined_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with final_path.open("rb") as src, combined_path.open("wb") as dst:
                dst.write(src.read())
                dst.write(tmp_bytes)
            combined_path.replace(final_path)
        except OSError as exc:
            raise EngineFailure(
                "F4",
                "2B-S6-082",
                STATE,
                MODULE_NAME,
                {"detail": "atomic append failed", "path": str(final_path), "error": str(exc)},
            ) from exc
        tmp_path.unlink(missing_ok=True)
        return False
    final_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        tmp_path.replace(final_path)
    except OSError as exc:
        raise EngineFailure(
            "F4",
            "2B-S6-082",
            STATE,
            MODULE_NAME,
            {"detail": "atomic publish failed", "path": str(final_path), "error": str(exc)},
        ) from exc
    return False


def _count_jsonl_rows(path: Path) -> int:
    count = 0
    with path.open("r", encoding="utf-8") as handle:
        for _ in handle:
            count += 1
    return count


def _build_alias(weights: list[float]) -> tuple[list[float], list[int]]:
    n = len(weights)
    if n == 0:
        raise ValueError("alias_weights_empty")
    total = float(sum(weights))
    if total <= 0.0 or not math.isfinite(total):
        raise ValueError("alias_weight_sum_invalid")
    probs = [float(weight) / total for weight in weights]
    scaled = [p * n for p in probs]
    small = deque([idx for idx, value in enumerate(scaled) if value < 1.0])
    large = deque([idx for idx, value in enumerate(scaled) if value >= 1.0])
    prob = [0.0] * n
    alias = [0] * n
    while small and large:
        s_idx = small.popleft()
        l_idx = large.popleft()
        prob[s_idx] = scaled[s_idx]
        alias[s_idx] = l_idx
        scaled[l_idx] = scaled[l_idx] - (1.0 - prob[s_idx])
        if scaled[l_idx] < 1.0:
            small.append(l_idx)
        else:
            large.append(l_idx)
    for idx in list(small) + list(large):
        prob[idx] = 1.0
        alias[idx] = idx
    return prob, alias


def _alias_pick(prob: list[float], alias: list[int], u_value: float) -> int:
    n = len(prob)
    scaled = u_value * n
    j = int(scaled)
    r = scaled - j
    if r < prob[j]:
        return j
    return alias[j]


def _derive_rng_key_counter(
    parameter_hash_hex: str,
    run_id_hex: str,
    seed: int,
    rng_stream_id: str,
    domain_master: str,
    domain_stream: str,
) -> tuple[int, int, int]:
    parameter_bytes = bytes.fromhex(parameter_hash_hex)
    run_id_bytes = bytes.fromhex(run_id_hex)
    if len(parameter_bytes) != 32:
        raise ValueError("parameter_hash must be 32 bytes.")
    if len(run_id_bytes) != 16:
        raise ValueError("run_id must be 16 bytes.")
    master_payload = uer_string(domain_master) + parameter_bytes + run_id_bytes + ser_u64(seed)
    master_digest = hashlib.sha256(master_payload).digest()
    stream_payload = uer_string(domain_stream) + uer_string(rng_stream_id)
    digest = hashlib.sha256(master_digest + stream_payload).digest()
    key = low64(digest)
    counter_hi = int.from_bytes(digest[16:24], "big", signed=False)
    counter_lo = int.from_bytes(digest[24:32], "big", signed=False)
    return key, counter_hi, counter_lo


def _git_hex_to_bytes(git_hex: str) -> bytes:
    git_hex = git_hex.strip().lower()
    raw = bytes.fromhex(git_hex)
    if len(raw) == 20:
        return b"\x00" * 12 + raw
    if len(raw) == 32:
        return raw
    raise InputResolutionError("Unexpected git hash length; expected SHA-1 or SHA-256.")


def _resolve_git_hash(repo_root: Path) -> str:
    env_hash = os.environ.get("ENGINE_GIT_COMMIT")
    if env_hash:
        return _git_hex_to_bytes(env_hash).hex()
    git_file = repo_root / "ci" / "manifests" / "git_commit_hash.txt"
    if git_file.exists():
        return _git_hex_to_bytes(git_file.read_text(encoding="utf-8").strip()).hex()
    try:
        output = os.popen(f"git -C \"{repo_root}\" rev-parse HEAD").read().strip()
        if output:
            return _git_hex_to_bytes(output).hex()
    except Exception:
        pass
    raise InputResolutionError("Unable to resolve git commit hash.")


def _normalize_edges(
    edges: list[dict],
    geo_metadata: dict,
) -> tuple[AliasTable, dict[str, EdgeMeta]]:
    if not edges:
        raise ValueError("edge_list_empty")
    meta_by_id: dict[str, EdgeMeta] = {}
    weights: list[float] = []
    edge_ids: list[str] = []
    for raw in edges:
        edge_id = str(raw.get("edge_id") or "")
        if not edge_id:
            raise ValueError("edge_id_missing")
        if edge_id in meta_by_id:
            raise ValueError("edge_id_duplicate")
        ip_country = str(raw.get("ip_country") or "")
        meta = geo_metadata.get(edge_id, {}) if isinstance(geo_metadata, dict) else {}
        edge_lat = raw.get("edge_lat", meta.get("edge_lat"))
        edge_lon = raw.get("edge_lon", meta.get("edge_lon"))
        if not ip_country:
            raise ValueError("edge_ip_country_missing")
        if edge_lat is None or edge_lon is None:
            raise ValueError("edge_geo_missing")
        edge_lat = float(edge_lat)
        edge_lon = float(edge_lon)
        if not (-90.0 <= edge_lat <= 90.0):
            raise ValueError("edge_lat_out_of_range")
        if not (-180.0 < edge_lon <= 180.0):
            raise ValueError("edge_lon_out_of_range")
        weight = None
        if "weight" in raw and raw.get("weight") is not None:
            weight = float(raw.get("weight") or 0.0)
        elif "country_weights" in raw and raw.get("country_weights") is not None:
            country_weights = raw.get("country_weights")
            if not isinstance(country_weights, dict) or not country_weights:
                raise ValueError("edge_country_weights_invalid")
            weight = float(country_weights.get(ip_country, 0.0))
        else:
            weight = 0.0
        if weight <= 0.0 or not math.isfinite(weight):
            raise ValueError("edge_weight_invalid")
        meta_by_id[edge_id] = EdgeMeta(
            edge_id=edge_id,
            ip_country=ip_country,
            edge_lat=edge_lat,
            edge_lon=edge_lon,
        )
        weights.append(weight)
        edge_ids.append(edge_id)
    weight_sum = float(sum(weights))
    if not math.isfinite(weight_sum) or abs(weight_sum - 1.0) > EPSILON:
        raise ValueError("edge_weight_sum_invalid")
    prob, alias = _build_alias(weights)
    return AliasTable(edge_ids, prob, alias), meta_by_id


def run_s6(config: EngineConfig, run_id: Optional[str] = None) -> S6Result:
    logger = get_logger("engine.layers.l1.seg_2B.s6_edge_router.l2.runner")
    timer = _StepTimer(logger)
    started_monotonic = time.monotonic()

    manifest_fingerprint = ""
    parameter_hash = ""
    seed = 0
    run_id_value = ""
    created_utc = ""

    dictionary_version = "unknown"
    registry_version = "unknown"

    arrivals_total = 0
    virtual_total = 0
    rng_events = 0
    rng_trace_rows = 0
    edge_log_written = 0

    policy_digest = ""
    policy_version_tag = ""
    edge_policy_digest = ""
    edge_policy_version = ""
    rng_engine = ""
    rng_stream_id = ""
    draws_per_virtual = 0

    first_counter: Optional[tuple[int, int]] = None
    last_counter: Optional[tuple[int, int]] = None
    missing_is_virtual_logged = False

    samples_edges: list[dict] = []

    validators = {
        f"V-{idx:02d}": {"id": f"V-{idx:02d}", "status": "PASS", "codes": []}
        for idx in range(1, 16)
    }

    def _record_validator(
        validator_id: str,
        result: str,
        code: Optional[str] = None,
        detail: Optional[object] = None,
    ) -> None:
        entry = validators[validator_id]
        if code and code not in entry["codes"]:
            entry["codes"].append(code)
        if result == "fail":
            entry["status"] = "FAIL"
        elif result == "warn" and entry["status"] != "FAIL":
            entry["status"] = "WARN"
        _emit_validation(logger, seed, manifest_fingerprint, validator_id, result, error_code=code, detail=detail)

    def _abort(code: str, validator_id: str, message: str, context: dict) -> None:
        _record_validator(validator_id, "fail", code=code, detail=context)
        _emit_failure_event(
            logger,
            code,
            seed,
            manifest_fingerprint,
            parameter_hash,
            run_id_value,
            validator_id,
            message,
            context,
        )
        raise EngineFailure("F4", code, STATE, MODULE_NAME, context)

    receipt_path, receipt = _resolve_run_receipt(config.runs_root, run_id)
    run_id_value = str(receipt.get("run_id") or "")
    if not run_id_value:
        raise InputResolutionError("run_receipt missing run_id.")
    seed = int(receipt.get("seed") or 0)
    parameter_hash = str(receipt.get("parameter_hash") or "")
    manifest_fingerprint = str(receipt.get("manifest_fingerprint") or "")
    if not parameter_hash or not manifest_fingerprint:
        raise InputResolutionError("run_receipt missing seed, parameter_hash, or manifest_fingerprint.")

    run_paths = RunPaths(config.runs_root, run_id_value)
    run_log_path = run_paths.run_root / f"run_log_{run_id_value}.log"
    add_file_handler(run_log_path)
    timer.info(f"S6: run log initialized at {run_log_path}")

    logger.info(
        "S6: objective=route virtual arrivals to edges; gated inputs (s0_receipt, sealed_inputs, "
        "route_rng_policy_v1, virtual_edge_policy_v1, s5_arrival_roster, optional s5_selection_log) "
        "-> outputs (rng_event_cdn_edge_pick, rng_trace_log, rng_audit_log, optional s6_edge_log)"
    )

    source = ContractSource(config.contracts_root, config.contracts_layout)
    _dict_path, dictionary = load_dataset_dictionary(source, SEGMENT)
    _registry_path, registry = load_artefact_registry(source, SEGMENT)
    _schema_2b_path, schema_2b = load_schema_pack(source, "2B", "2B")
    _schema_layer1_path, schema_layer1 = load_schema_pack(source, "1A", "layer1")

    dictionary_version = str(dictionary.get("version") or "unknown")
    registry_version = str(registry.get("version") or "unknown")

    entries = _resolve_entries(dictionary)
    edge_log_entry = None
    selection_entry = None
    try:
        edge_log_entry = find_dataset_entry(dictionary, "s6_edge_log").entry
    except KeyError:
        edge_log_entry = None
    try:
        selection_entry = find_dataset_entry(dictionary, "s5_selection_log").entry
    except KeyError:
        selection_entry = None

    tokens = {
        "seed": str(seed),
        "parameter_hash": parameter_hash,
        "manifest_fingerprint": manifest_fingerprint,
        "run_id": run_id_value,
    }

    try:
        receipt_entry = entries["s0_gate_receipt_2B"]
        receipt_catalog_path = _render_catalog_path(receipt_entry, {"manifest_fingerprint": manifest_fingerprint})
        receipt_path = _resolve_dataset_path(
            receipt_entry,
            run_paths,
            config.external_roots,
            {"manifest_fingerprint": manifest_fingerprint},
        )
        if not receipt_path.exists():
            _abort("2B-S6-001", "V-01", "s0_receipt_missing", {"path": str(receipt_path)})
        receipt_payload = _load_json(receipt_path)
        _validate_payload(schema_2b, "validation/s0_gate_receipt_v1", receipt_payload, {"schemas.layer1.yaml#/$defs/": schema_layer1})
        if str(receipt_payload.get("manifest_fingerprint")) != manifest_fingerprint:
            _abort(
                "2B-S6-001",
                "V-01",
                "manifest_fingerprint_mismatch",
                {"receipt": receipt_payload.get("manifest_fingerprint"), "expected": manifest_fingerprint},
            )
        created_utc = str(receipt_payload.get("verified_at_utc") or "")
        if not created_utc:
            _abort("2B-S6-001", "V-01", "created_utc_missing", {"receipt_path": str(receipt_path)})
        timer.info("S6: S0 receipt verified; created_utc=%s", created_utc or "unknown")
        _record_validator("V-01", "pass")
    except (ContractError, SchemaValidationError) as exc:
        _abort("2B-S6-001", "V-01", "s0_receipt_invalid", {"error": str(exc)})

    sealed_entry = entries["sealed_inputs_2B"]
    sealed_path = _resolve_dataset_path(
        sealed_entry,
        run_paths,
        config.external_roots,
        {"manifest_fingerprint": manifest_fingerprint},
    )
    if not sealed_path.exists():
        _abort("2B-S6-020", "V-02", "sealed_inputs_missing", {"path": str(sealed_path)})
    sealed_inputs = _load_json(sealed_path)
    sealed_schema = _schema_from_pack(schema_2b, "validation/sealed_inputs_2B")
    sealed_errors = list(Draft202012Validator(sealed_schema).iter_errors(sealed_inputs))
    if sealed_errors:
        _abort("2B-S6-020", "V-02", "sealed_inputs_invalid", {"error": sealed_errors[0].message})

    sealed_by_id: dict[str, dict] = {}
    for item in sealed_inputs:
        if isinstance(item, dict) and item.get("asset_id"):
            sealed_by_id[str(item["asset_id"])] = item

    def _require_sealed_asset(
        asset_id: str,
        entry: dict,
        token_values: dict[str, str],
        require_partition: Optional[dict[str, str]],
        validator_id: str,
    ) -> tuple[Path, dict, str]:
        sealed = _find_sealed_asset(sealed_inputs, asset_id)
        if not sealed:
            _abort("2B-S6-020", validator_id, "sealed_asset_missing", {"asset_id": asset_id})
        catalog_path = _render_catalog_path(entry, token_values)
        sealed_path_value = str(sealed.get("path") or "")
        if sealed_path_value and sealed_path_value != catalog_path:
            _abort(
                "2B-S6-070",
                validator_id,
                "sealed_path_mismatch",
                {"asset_id": asset_id, "sealed": sealed_path_value, "dictionary": catalog_path},
            )
        partition = sealed.get("partition") or {}
        if require_partition is not None and partition != require_partition:
            _abort(
                "2B-S6-070",
                validator_id,
                "partition_mismatch",
                {"asset_id": asset_id, "sealed": partition, "expected": require_partition},
            )
        resolved = _resolve_dataset_path(entry, run_paths, config.external_roots, token_values)
        if not resolved.exists():
            _abort("2B-S6-020", validator_id, "required_asset_missing", {"asset_id": asset_id, "path": str(resolved)})
        digest = sha256_file(resolved).sha256_hex
        sealed_digest = str(sealed.get("sha256_hex") or "")
        if sealed_digest and sealed_digest != digest:
            _abort(
                "2B-S6-020",
                validator_id,
                "sealed_digest_mismatch",
                {"asset_id": asset_id, "sealed": sealed_digest, "computed": digest},
            )
        return resolved, sealed, catalog_path

    route_policy_entry = entries["route_rng_policy_v1"]
    route_policy_path, route_policy_sealed, _route_policy_catalog = _require_sealed_asset(
        "route_rng_policy_v1",
        route_policy_entry,
        {},
        {},
        "V-02",
    )
    policy_digest = str(route_policy_sealed.get("sha256_hex") or "")

    edge_policy_entry = entries["virtual_edge_policy_v1"]
    edge_policy_path, edge_policy_sealed, _edge_policy_catalog = _require_sealed_asset(
        "virtual_edge_policy_v1",
        edge_policy_entry,
        {},
        {},
        "V-02",
    )
    edge_policy_digest = str(edge_policy_sealed.get("sha256_hex") or "")

    arrival_entry = entries["s5_arrival_roster"]
    arrival_path, arrival_sealed, arrival_catalog = _require_sealed_asset(
        "s5_arrival_roster",
        arrival_entry,
        tokens,
        {"seed": str(seed), "parameter_hash": parameter_hash, "run_id": run_id_value},
        "V-02",
    )
    if (
        f"seed={seed}" not in arrival_catalog
        or f"parameter_hash={parameter_hash}" not in arrival_catalog
        or f"run_id={run_id_value}" not in arrival_catalog
    ):
        _abort(
            "2B-S6-071",
            "V-12",
            "arrival_path_embed_mismatch",
            {"path": arrival_catalog, "seed": seed, "parameter_hash": parameter_hash, "run_id": run_id_value},
        )

    route_policy_payload = _load_json(route_policy_path)
    route_policy_schema = _schema_from_pack(schema_2b, "policy/route_rng_policy_v1")
    _inline_external_refs(route_policy_schema, schema_layer1, "schemas.layer1.yaml#/$defs/")
    route_errors = list(Draft202012Validator(route_policy_schema).iter_errors(route_policy_payload))
    if route_errors:
        _abort("2B-S6-030", "V-04", "route_policy_schema_invalid", {"error": route_errors[0].message})

    edge_policy_payload = _load_json(edge_policy_path)
    edge_policy_schema = _schema_from_pack(schema_2b, "policy/virtual_edge_policy_v1")
    _inline_external_refs(edge_policy_schema, schema_layer1, "schemas.layer1.yaml#/$defs/")
    edge_errors = list(Draft202012Validator(edge_policy_schema).iter_errors(edge_policy_payload))
    if edge_errors:
        _abort("2B-S6-030", "V-04", "edge_policy_schema_invalid", {"error": edge_errors[0].message})

    policy_version_tag = str(route_policy_payload.get("policy_version") or route_policy_payload.get("version_tag") or "")
    edge_policy_version = str(edge_policy_payload.get("policy_version") or edge_policy_payload.get("version_tag") or "")

    rng_engine = str(route_policy_payload.get("rng_engine") or "")
    if rng_engine != "philox2x64-10":
        _abort("2B-S6-053", "V-10", "rng_engine_invalid", {"rng_engine": rng_engine})

    routing_edge = route_policy_payload.get("streams", {}).get("routing_edge", {})
    rng_stream_id = str(routing_edge.get("rng_stream_id") or "")
    if not rng_stream_id:
        _abort("2B-S6-053", "V-10", "rng_stream_id_missing", {})

    basis = routing_edge.get("basis", {})
    if basis.get("key_basis") != ["seed", "parameter_hash", "run_id"]:
        _abort("2B-S6-053", "V-10", "rng_key_basis_invalid", {"key_basis": basis.get("key_basis")})
    if int(basis.get("counter_step_per_event") or 0) != 1:
        _abort(
            "2B-S6-053",
            "V-10",
            "rng_counter_step_invalid",
            {"counter_step_per_event": basis.get("counter_step_per_event")},
        )
    if basis.get("counter_wrap_policy") != "abort_on_wrap":
        _abort(
            "2B-S6-053",
            "V-10",
            "rng_counter_wrap_policy_invalid",
            {"counter_wrap_policy": basis.get("counter_wrap_policy")},
        )

    family = routing_edge.get("event_families", {}).get("cdn_edge_pick", {})
    if family.get("substream_label") not in (None, "cdn_edge_pick"):
        _abort("2B-S6-053", "V-10", "rng_family_label_invalid", {"label": family.get("substream_label")})
    if family.get("blocks") != 1 or family.get("draws") != "1":
        _abort(
            "2B-S6-053",
            "V-10",
            "rng_family_invalid",
            {"blocks": family.get("blocks"), "draws": family.get("draws")},
        )
    draws_per_virtual = int(routing_edge.get("draws_per_unit", {}).get("draws_per_virtual") or 0)
    if draws_per_virtual != 1:
        _abort(
            "2B-S6-053",
            "V-10",
            "draws_per_virtual_invalid",
            {"draws_per_virtual": draws_per_virtual},
        )

    rng_domain_master = "mlr:2B.routing_edge.master"
    rng_domain_stream = "mlr:2B.routing_edge.stream"
    try:
        rng_key, counter_hi, counter_lo = _derive_rng_key_counter(
            parameter_hash,
            run_id_value,
            seed,
            rng_stream_id,
            rng_domain_master,
            rng_domain_stream,
        )
    except ValueError as exc:
        _abort("2B-S6-053", "V-10", "rng_derivation_invalid", {"error": str(exc)})

    counter_start = basis.get("counter_start", {})
    if counter_start:
        counter_hi = int(counter_start.get("hi", counter_hi))
        counter_lo = int(counter_start.get("lo", counter_lo))

    edge_log_enabled = bool(edge_policy_payload.get("extensions", {}).get("edge_log_enabled", False))
    if not edge_log_entry:
        edge_log_enabled = False
    logger.info(
        "S6: edge_log_enabled=%s (policy flag + dictionary presence)",
        edge_log_enabled,
    )

    _record_validator("V-02", "pass")
    _record_validator("V-04", "pass")
    _record_validator("V-10", "pass")
    timer.info("S6: sealed policies loaded (route_rng_policy_v1, virtual_edge_policy_v1)")

    edge_defaults = []
    if "edges" in edge_policy_payload:
        edge_defaults = edge_policy_payload.get("edges") or []
    else:
        edge_defaults = edge_policy_payload.get("default_edges") or []
    if not edge_defaults:
        _abort("2B-S6-031", "V-04", "edge_policy_empty", {})

    geo_metadata = edge_policy_payload.get("geo_metadata") or {}
    try:
        default_alias, default_meta = _normalize_edges(edge_defaults, geo_metadata)
    except ValueError as exc:
        _abort("2B-S6-031", "V-04", "edge_policy_minima_invalid", {"error": str(exc)})

    overrides_raw = edge_policy_payload.get("merchant_overrides") or {}
    overrides: dict[str, list[dict]] = {}
    if isinstance(overrides_raw, dict):
        for key, value in overrides_raw.items():
            if isinstance(value, list):
                overrides[str(key)] = value

    edge_cache: OrderedDict[str, tuple[AliasTable, dict[str, EdgeMeta]]] = OrderedDict()
    edge_cache["__default__"] = (default_alias, default_meta)

    def _get_edge_alias(merchant_id: int) -> tuple[AliasTable, dict[str, EdgeMeta]]:
        key = str(merchant_id)
        if key in edge_cache:
            edge_cache.move_to_end(key)
            return edge_cache[key]
        if key in overrides:
            try:
                table, meta = _normalize_edges(overrides[key], geo_metadata)
            except ValueError as exc:
                _abort("2B-S6-031", "V-04", "edge_override_invalid", {"merchant_id": merchant_id, "error": str(exc)})
            edge_cache[key] = (table, meta)
            if len(edge_cache) > EDGE_CACHE_MAX:
                edge_cache.popitem(last=False)
            return table, meta
        return edge_cache["__default__"]

    arrival_schema = _schema_from_pack(schema_2b, "trace/s5_arrival_roster_row")
    _inline_external_refs(arrival_schema, schema_layer1, "schemas.layer1.yaml#/$defs/")
    arrival_validator = Draft202012Validator(arrival_schema)

    arrivals_total = _count_jsonl_rows(arrival_path)
    timer.info("S6: arrival roster loaded rows=%s (run-scoped batch input)", arrivals_total)
    progress = _ProgressTracker(arrivals_total, logger, "S6 routing progress virtual arrivals")
    timer.info("S6: starting virtual-edge routing loop (virtual arrivals only)")

    event_schema = _schema_from_pack(schema_layer1, "rng/events/cdn_edge_pick")
    trace_schema = _schema_from_pack(schema_layer1, "rng/core/rng_trace_log/record")
    audit_schema = _schema_from_pack(schema_layer1, "rng/core/rng_audit_log/record")

    event_validator = Draft202012Validator(event_schema)
    trace_validator = Draft202012Validator(trace_schema)
    audit_validator = Draft202012Validator(audit_schema)

    selection_schema = None
    selection_validator = None
    if edge_log_enabled:
        if not selection_entry:
            _abort("2B-S6-020", "V-12", "selection_log_dict_missing", {"asset_id": "s5_selection_log"})
        selection_schema = _schema_from_pack(schema_2b, "trace/s5_selection_log_row")
        _inline_external_refs(selection_schema, schema_layer1, "schemas.layer1.yaml#/$defs/")
        selection_validator = Draft202012Validator(selection_schema)

    edge_log_schema = None
    edge_log_validator = None
    if edge_log_enabled and edge_log_entry:
        edge_log_schema = _schema_from_pack(schema_2b, "trace/s6_edge_log_row")
        _inline_external_refs(edge_log_schema, schema_layer1, "schemas.layer1.yaml#/$defs/")
        edge_log_validator = Draft202012Validator(edge_log_schema)

    selection_cache: dict[str, dict[tuple[int, str, str], tuple[str, int]]] = {}

    def _load_selection_day(utc_day: str) -> dict[tuple[int, str, str], tuple[str, int]]:
        if utc_day in selection_cache:
            return selection_cache[utc_day]
        selection_tokens = dict(tokens)
        selection_tokens["utc_day"] = utc_day
        selection_catalog = _render_catalog_path(selection_entry, selection_tokens)
        if (
            f"seed={seed}" not in selection_catalog
            or f"parameter_hash={parameter_hash}" not in selection_catalog
            or f"run_id={run_id_value}" not in selection_catalog
            or f"utc_day={utc_day}" not in selection_catalog
        ):
            _abort(
                "2B-S6-071",
                "V-12",
                "selection_log_path_embed_mismatch",
                {"path": selection_catalog, "utc_day": utc_day},
            )
        selection_path = _resolve_dataset_path(selection_entry, run_paths, config.external_roots, selection_tokens)
        if not selection_path.exists():
            _abort("2B-S6-020", "V-12", "selection_log_missing", {"path": str(selection_path)})
        selection_map: dict[tuple[int, str, str], tuple[str, int]] = {}
        with selection_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    selection_row = json.loads(line)
                except json.JSONDecodeError as exc:
                    _abort("2B-S6-071", "V-12", "selection_log_json_invalid", {"error": str(exc)})
                if selection_validator:
                    errors = list(selection_validator.iter_errors(selection_row))
                    if errors:
                        _abort("2B-S6-071", "V-12", "selection_log_schema_invalid", {"error": errors[0].message})
                key = (
                    int(selection_row["merchant_id"]),
                    str(selection_row["utc_timestamp"]),
                    str(selection_row["utc_day"]),
                )
                selection_map[key] = (str(selection_row["tz_group_id"]), int(selection_row["site_id"]))
        selection_cache[utc_day] = selection_map
        return selection_map

    tmp_root = run_paths.tmp_root / f"s6_edge_router_{uuid.uuid4().hex}"
    event_tmp_dir = tmp_root / "rng_event_cdn_edge_pick"
    edge_tmp_dir = tmp_root / "s6_edge_log"
    tmp_root.mkdir(parents=True, exist_ok=True)
    event_tmp_dir.mkdir(parents=True, exist_ok=True)
    if edge_log_enabled:
        edge_tmp_dir.mkdir(parents=True, exist_ok=True)

    event_tmp = event_tmp_dir / "part-00000.jsonl"
    trace_tmp_path = tmp_root / "rng_trace_log.jsonl"

    trace_acc = RngTraceAccumulator()
    edge_handles: dict[str, tuple[Path, object]] = {}

    with (
        event_tmp.open("w", encoding="utf-8") as event_handle,
        trace_tmp_path.open("w", encoding="utf-8") as trace_handle,
    ):
        with arrival_path.open("r", encoding="utf-8") as arrivals_handle:
            for line in arrivals_handle:
                if not line.strip():
                    continue
                try:
                    arrival = json.loads(line)
                except json.JSONDecodeError as exc:
                    _abort("2B-S6-020", "V-03", "arrival_json_invalid", {"error": str(exc)})
                errors = list(arrival_validator.iter_errors(arrival))
                if errors:
                    _abort("2B-S6-020", "V-03", "arrival_schema_invalid", {"error": errors[0].message})

                merchant_id = int(arrival["merchant_id"])
                utc_timestamp = str(arrival["utc_timestamp"])
                utc_day = str(arrival["utc_day"])
                if "is_virtual" not in arrival:
                    if not missing_is_virtual_logged:
                        logger.warning(
                            "S6: arrival roster missing is_virtual; defaulting to false for unspecified rows."
                        )
                        missing_is_virtual_logged = True
                    is_virtual = False
                else:
                    is_virtual = bool(arrival.get("is_virtual", False))

                if not is_virtual:
                    progress.update(1)
                    continue

                virtual_total += 1
                edge_alias, edge_meta = _get_edge_alias(merchant_id)

                before_hi = counter_hi
                before_lo = counter_lo
                out0, _out1 = philox2x64_10(before_hi, before_lo, rng_key)
                u_edge = u01(out0)
                edge_index = _alias_pick(edge_alias.prob, edge_alias.alias, u_edge)
                edge_id = str(edge_alias.items[edge_index])
                meta = edge_meta.get(edge_id)
                if not meta:
                    _abort("2B-S6-060", "V-07", "edge_meta_missing", {"edge_id": edge_id})

                after_hi, after_lo = add_u128(before_hi, before_lo, 1)
                if (after_hi, after_lo) <= (before_hi, before_lo):
                    _abort(
                        "2B-S6-051",
                        "V-09",
                        "rng_counter_not_monotone",
                        {"before": [before_hi, before_lo], "after": [after_hi, after_lo]},
                    )

                event_payload = {
                    "ts_utc": utc_now_rfc3339_micro(),
                    "run_id": run_id_value,
                    "seed": seed,
                    "parameter_hash": parameter_hash,
                    "manifest_fingerprint": manifest_fingerprint,
                    "module": EVENT_MODULE,
                    "substream_label": "cdn_edge_pick",
                    "rng_counter_before_lo": before_lo,
                    "rng_counter_before_hi": before_hi,
                    "rng_counter_after_lo": after_lo,
                    "rng_counter_after_hi": after_hi,
                    "draws": "1",
                    "blocks": 1,
                    "merchant_id": merchant_id,
                }
                event_errors = list(event_validator.iter_errors(event_payload))
                if event_errors:
                    _abort("2B-S6-050", "V-08", "rng_event_invalid", {"error": event_errors[0].message})

                trace_row = trace_acc.append_event(event_payload)
                trace_errors = list(trace_validator.iter_errors(trace_row))
                if trace_errors:
                    _abort("2B-S6-050", "V-11", "rng_trace_invalid", {"error": trace_errors[0].message})

                event_handle.write(json.dumps(event_payload, ensure_ascii=True, sort_keys=True))
                event_handle.write("\n")
                trace_handle.write(json.dumps(trace_row, ensure_ascii=True, sort_keys=True))
                trace_handle.write("\n")

                rng_events += 1
                rng_trace_rows += 1

                counter_hi, counter_lo = after_hi, after_lo
                last_counter = (after_hi, after_lo)
                if first_counter is None:
                    first_counter = (before_hi, before_lo)

                if edge_log_enabled and edge_log_entry:
                    selection_map = _load_selection_day(utc_day)
                    selection_key = (merchant_id, utc_timestamp, utc_day)
                    if selection_key not in selection_map:
                        _abort(
                            "2B-S6-071",
                            "V-12",
                            "selection_log_missing_key",
                            {"merchant_id": merchant_id, "utc_timestamp": utc_timestamp, "utc_day": utc_day},
                        )
                    tz_group_id, site_id = selection_map[selection_key]
                    edge_log_row = {
                        "merchant_id": merchant_id,
                        "is_virtual": True,
                        "utc_timestamp": utc_timestamp,
                        "utc_day": utc_day,
                        "tz_group_id": tz_group_id,
                        "site_id": site_id,
                        "edge_id": meta.edge_id,
                        "ip_country": meta.ip_country,
                        "edge_lat": meta.edge_lat,
                        "edge_lon": meta.edge_lon,
                        "rng_stream_id": rng_stream_id,
                        "ctr_edge_hi": before_hi,
                        "ctr_edge_lo": before_lo,
                        "manifest_fingerprint": manifest_fingerprint,
                        "created_utc": created_utc,
                    }
                    if edge_log_validator:
                        errors = list(edge_log_validator.iter_errors(edge_log_row))
                        if errors:
                            _abort("2B-S6-071", "V-12", "edge_log_schema_invalid", {"error": errors[0].message})
                    if utc_day not in edge_handles:
                        tmp_path = edge_tmp_dir / f"{utc_day}.jsonl"
                        handle = tmp_path.open("w", encoding="utf-8")
                        edge_handles[utc_day] = (tmp_path, handle)
                    tmp_path, handle = edge_handles[utc_day]
                    handle.write(json.dumps(edge_log_row, ensure_ascii=True, sort_keys=True))
                    handle.write("\n")
                    edge_log_written += 1

                if len(samples_edges) < 20:
                    samples_edges.append(
                        {
                            "merchant_id": merchant_id,
                            "utc_day": utc_day,
                            "edge_id": meta.edge_id,
                            "ip_country": meta.ip_country,
                        }
                    )

                progress.update(1)

    for _day, (_path, handle) in edge_handles.items():
        handle.close()

    engine_commit = _resolve_git_hash(config.repo_root)
    audit_payload = {
        "ts_utc": utc_now_rfc3339_micro(),
        "run_id": run_id_value,
        "seed": seed,
        "manifest_fingerprint": manifest_fingerprint,
        "parameter_hash": parameter_hash,
        "algorithm": "philox2x64-10",
        "build_commit": engine_commit,
        "code_digest": None,
        "hostname": platform.node() or None,
        "platform": platform.platform(),
        "notes": None,
    }
    audit_errors = list(audit_validator.iter_errors(audit_payload))
    if audit_errors:
        _abort("2B-S6-050", "V-11", "rng_audit_invalid", {"error": audit_errors[0].message})
    # rng_audit_log is append-only across states; only add a row if missing.

    rng_draws_total = rng_events
    if rng_events != virtual_total:
        _abort(
            "2B-S6-050",
            "V-08",
            "rng_draws_mismatch",
            {"events": rng_events, "virtual_arrivals": virtual_total},
        )

    event_catalog = _render_catalog_path(entries["rng_event_cdn_edge_pick"], tokens)
    trace_catalog = _render_catalog_path(entries["rng_trace_log"], tokens)
    audit_catalog = _render_catalog_path(entries["rng_audit_log"], tokens)

    for label, path in (
        ("rng_event_cdn_edge_pick", event_catalog),
        ("rng_trace_log", trace_catalog),
        ("rng_audit_log", audit_catalog),
    ):
        if (
            f"seed={seed}" not in path
            or f"parameter_hash={parameter_hash}" not in path
            or f"run_id={run_id_value}" not in path
        ):
            _abort("2B-S6-071", "V-12", "output_partition_mismatch", {"id": label, "path": path})
        if not path.startswith("logs/"):
            _abort("2B-S6-090", "V-14", "prohibited_output_surface", {"id": label, "path": path})

    event_output = _render_output_path(run_paths, event_catalog)
    trace_output = _render_output_path(run_paths, trace_catalog)
    audit_output = _render_output_path(run_paths, audit_catalog)

    if rng_events > 0:
        _atomic_publish_file(event_tmp, event_output, logger, "rng_event_cdn_edge_pick")
    else:
        if event_output.exists() and event_output.stat().st_size > 0:
            _abort(
                "2B-S6-095",
                "V-15",
                "replay_mismatch_no_virtual_events",
                {"path": str(event_output)},
            )
        event_tmp.unlink(missing_ok=True)

    _atomic_append_file(trace_tmp_path, trace_output, logger, "rng_trace_log")
    _ensure_rng_audit(audit_output, audit_payload, logger, "S6")

    if edge_log_enabled and edge_log_entry:
        for utc_day, (tmp_path, _handle) in edge_handles.items():
            edge_tokens = dict(tokens)
            edge_tokens["utc_day"] = utc_day
            edge_catalog = _render_catalog_path(edge_log_entry, edge_tokens)
            if (
                f"seed={seed}" not in edge_catalog
                or f"parameter_hash={parameter_hash}" not in edge_catalog
                or f"run_id={run_id_value}" not in edge_catalog
                or f"utc_day={utc_day}" not in edge_catalog
            ):
                _abort("2B-S6-071", "V-12", "edge_log_path_embed_mismatch", {"path": edge_catalog})
            if not edge_catalog.startswith("logs/"):
                _abort("2B-S6-090", "V-14", "prohibited_output_surface", {"path": edge_catalog})
            edge_output = _render_output_path(run_paths, edge_catalog)
            if edge_log_written == 0 and edge_output.exists() and edge_output.stat().st_size > 0:
                _abort(
                    "2B-S6-095",
                    "V-15",
                    "replay_mismatch_no_edge_log_rows",
                    {"path": str(edge_output)},
                )
            _atomic_publish_file(tmp_path, edge_output, logger, f"s6_edge_log {utc_day}")

    shutil.rmtree(tmp_root, ignore_errors=True)
    timer.info("S6: published rng logs (events/trace/audit) and edge log if enabled")

    elapsed_total = time.monotonic() - started_monotonic
    if first_counter is None:
        first_counter = (counter_hi, counter_lo)
    if last_counter is None:
        last_counter = (counter_hi, counter_lo)

    validators_list = list(validators.values())
    warn_count = sum(1 for item in validators_list if item.get("status") == "WARN")
    fail_count = sum(1 for item in validators_list if item.get("status") == "FAIL")
    overall_status = "FAIL" if fail_count else "PASS"

    logging_payload = {"edge_log_enabled": edge_log_enabled}
    if edge_log_enabled:
        logging_payload["edge_log_partition"] = "[seed,parameter_hash,run_id,utc_day]"

    run_report = {
        "component": "2B.S6",
        "manifest_fingerprint": manifest_fingerprint,
        "seed": seed,
        "parameter_hash": parameter_hash,
        "run_id": run_id_value,
        "created_utc": created_utc,
        "catalogue_resolution": {
            "dictionary_version": dictionary_version,
            "registry_version": registry_version,
        },
        "policy": {
            "id": "route_rng_policy_v1",
            "version_tag": policy_version_tag,
            "sha256_hex": policy_digest,
            "rng_engine": rng_engine,
            "rng_stream_id": rng_stream_id,
            "draws_per_virtual": draws_per_virtual,
        },
        "edge_policy": {
            "id": "virtual_edge_policy_v1",
            "version_tag": edge_policy_version,
            "sha256_hex": edge_policy_digest,
        },
        "rng_accounting": {
            "virtual_arrivals": virtual_total,
            "events_total": rng_events,
            "draws_total": rng_draws_total,
            "first_counter": {"hi": first_counter[0], "lo": first_counter[1]},
            "last_counter": {"hi": last_counter[0], "lo": last_counter[1]},
        },
        "logging": logging_payload,
        "validators": validators_list,
        "summary": {
            "overall_status": overall_status,
            "warn_count": warn_count,
            "fail_count": fail_count,
        },
        "environment": {
            "engine_commit": engine_commit,
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "network_io_detected": 0,
            "elapsed_seconds": round(elapsed_total, 2),
        },
        "samples": {"edges": samples_edges},
    }

    run_report_path = (
        run_paths.run_root
        / "reports"
        / "layer1"
        / "2B"
        / "state=S6"
        / f"seed={seed}"
        / f"manifest_fingerprint={manifest_fingerprint}"
        / "s6_run_report.json"
    )
    _write_json(run_report_path, run_report)
    logger.info("S6 run-report %s", json.dumps(run_report, ensure_ascii=True, sort_keys=True))

    timer.info("S6: completed routing run")

    return S6Result(
        run_id=run_id_value,
        parameter_hash=parameter_hash,
        manifest_fingerprint=manifest_fingerprint,
        run_report_path=run_report_path,
        edge_log_enabled=edge_log_enabled,
    )
