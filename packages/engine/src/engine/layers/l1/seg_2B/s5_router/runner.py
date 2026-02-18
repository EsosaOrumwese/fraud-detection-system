"""S5 router runner for Segment 2B."""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import shutil
import subprocess
import time
import uuid
from datetime import datetime, timedelta, timezone
from collections import OrderedDict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import polars as pl
from jsonschema import Draft202012Validator

from engine.contracts.jsonschema_adapter import validate_dataframe
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
from engine.core.time import parse_rfc3339, utc_now_rfc3339_micro
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
    _hash_partition,
    _inline_external_refs,
    _render_catalog_path,
    _resolve_dataset_path,
    _resolve_run_receipt,
    _schema_from_pack,
)


MODULE_NAME = "2B.S5.router"
SEGMENT = "2B"
STATE = "S5"

EPSILON = 1e-9
UINT64_MASK = 0xFFFFFFFFFFFFFFFF

GROUP_CACHE_MAX = 10_000
SITE_CACHE_MAX = 20_000
VALIDATION_SAMPLE_ROWS_DEFAULT = 2_048


@dataclass(frozen=True)
class S5Result:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    run_report_path: Path
    selection_log_enabled: bool


@dataclass
class AliasTable:
    items: list
    prob: list[float]
    alias: list[int]
    weights: Optional[list[float]] = None


@dataclass(frozen=True)
class SiteRecord:
    site_id: int
    tzid: str
    legal_country_iso: str
    site_order: int


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
        "event": "S5_ERROR",
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
    logger.error("S5_ERROR %s", json.dumps(payload, ensure_ascii=True, sort_keys=True))


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
        "s1_site_weights",
        "s2_alias_index",
        "s2_alias_blob",
        "s4_group_weights",
        "site_timezones",
        "route_rng_policy_v1",
        "alias_layout_policy_v1",
        "s5_arrival_roster",
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


def _atomic_publish_dir(tmp_root: Path, final_root: Path, logger, label: str) -> bool:
    if final_root.exists():
        tmp_hash, _ = _hash_partition(tmp_root)
        final_hash, _ = _hash_partition(final_root)
        if tmp_hash != final_hash:
            raise EngineFailure(
                "F4",
                "2B-S5-080",
                STATE,
                MODULE_NAME,
                {"detail": "non-identical output exists", "partition": str(final_root), "label": label},
            )
        shutil.rmtree(tmp_root)
        logger.info("S5: %s partition already exists and is identical; skipping publish.", label)
        return True
    final_root.parent.mkdir(parents=True, exist_ok=True)
    try:
        tmp_root.replace(final_root)
    except OSError as exc:
        raise EngineFailure(
            "F4",
            "2B-S5-082",
            STATE,
            MODULE_NAME,
            {"detail": "atomic publish failed", "partition": str(final_root), "error": str(exc)},
        ) from exc
    return False


def _atomic_publish_file(tmp_path: Path, final_path: Path, logger, label: str) -> bool:
    if final_path.exists():
        tmp_hash = sha256_file(tmp_path).sha256_hex
        final_hash = sha256_file(final_path).sha256_hex
        if tmp_hash != final_hash:
            # S6 appends additional trace rows to the shared rng_trace_log path.
            # On replay, accept byte-prefix equality for the S5-produced prefix.
            if label == "rng_trace_log" and _file_prefix_matches(tmp_path, final_path):
                tmp_path.unlink(missing_ok=True)
                logger.info(
                    "S5: %s already exists with downstream append; replay prefix verified, skipping publish.",
                    label,
                )
                return True
            raise EngineFailure(
                "F4",
                "2B-S5-080",
                STATE,
                MODULE_NAME,
                {"detail": "non-identical output exists", "path": str(final_path), "label": label},
            )
        tmp_path.unlink(missing_ok=True)
        logger.info("S5: %s already exists and is identical; skipping publish.", label)
        return True
    final_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        tmp_path.replace(final_path)
    except OSError as exc:
        raise EngineFailure(
            "F4",
            "2B-S5-082",
            STATE,
            MODULE_NAME,
            {"detail": "atomic publish failed", "path": str(final_path), "error": str(exc)},
        ) from exc
    return False


def _file_prefix_matches(prefix_path: Path, target_path: Path, chunk_size: int = 1 << 20) -> bool:
    prefix_size = prefix_path.stat().st_size
    target_size = target_path.stat().st_size
    if target_size < prefix_size:
        return False
    with prefix_path.open("rb") as p_handle, target_path.open("rb") as t_handle:
        remaining = prefix_size
        while remaining > 0:
            to_read = chunk_size if remaining > chunk_size else remaining
            p_chunk = p_handle.read(to_read)
            t_chunk = t_handle.read(to_read)
            if p_chunk != t_chunk:
                return False
            remaining -= len(p_chunk)
            if len(p_chunk) == 0:
                return False
    return True


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


def _render_output_path(run_paths: RunPaths, catalog_path: str) -> Path:
    rendered = catalog_path
    if "*" in rendered:
        rendered = rendered.replace("*", "00000")
    return run_paths.run_root / rendered


def _list_parquet_paths(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    if not root.exists():
        raise InputResolutionError(f"Missing parquet directory: {root}")
    paths = sorted(root.glob("*.parquet"))
    if not paths:
        raise InputResolutionError(f"No parquet files found under {root}")
    return paths


def _count_jsonl_rows(path: Path) -> int:
    count = 0
    with path.open("r", encoding="utf-8") as handle:
        for _ in handle:
            count += 1
    return count


def _format_rfc3339_micro(value: datetime) -> str:
    value_utc = value.astimezone(timezone.utc)
    return value_utc.isoformat(timespec="microseconds").replace("+00:00", "Z")


class _DeterministicTimestampSequence:
    def __init__(self, anchor_utc: str) -> None:
        parsed = parse_rfc3339(anchor_utc)
        if parsed is None:
            raise InputResolutionError(f"Invalid created_utc timestamp: {anchor_utc!r}")
        self._base = parsed.astimezone(timezone.utc)
        self._offset_micro = 0

    def next(self) -> str:
        ts = self._base + timedelta(microseconds=self._offset_micro)
        self._offset_micro += 1
        return _format_rfc3339_micro(ts)


def _env_str(name: str, default: str) -> str:
    value = os.environ.get(name)
    if value is None:
        return default
    value = value.strip()
    return value if value else default


def _env_int(name: str, default: int, minimum: int = 0) -> int:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return parsed if parsed >= minimum else minimum


def _required_columns_from_table(schema_pack: dict, table_name: str) -> list[str]:
    table = schema_pack.get(table_name)
    if not isinstance(table, dict):
        raise ContractError(f"Schema table not found for required-column extraction: {table_name}")
    columns = table.get("columns")
    if not isinstance(columns, list):
        raise ContractError(f"Schema table has no columns: {table_name}")
    required: list[str] = []
    for column in columns:
        if not isinstance(column, dict):
            continue
        name = column.get("name")
        if isinstance(name, str) and name:
            required.append(name)
    if not required:
        raise ContractError(f"Schema table has empty column names: {table_name}")
    return required


def _validate_input_dataframe(
    dataframe: pl.DataFrame,
    schema_pack: dict,
    table_name: str,
    mode: str,
    sample_rows: int,
) -> None:
    required_columns = _required_columns_from_table(schema_pack, table_name)
    missing_columns = [name for name in required_columns if name not in dataframe.columns]
    if missing_columns:
        raise SchemaValidationError(
            f"{table_name} missing required columns: {missing_columns}",
            [{"field": name, "message": "missing required column"} for name in missing_columns],
        )
    if mode == "strict":
        validate_dataframe(dataframe.iter_rows(named=True), schema_pack, table_name)
        return
    if mode == "sample":
        if dataframe.height == 0:
            return
        rows_to_validate = min(sample_rows, dataframe.height)
        validate_dataframe(dataframe.head(rows_to_validate).iter_rows(named=True), schema_pack, table_name)
        return
    raise ContractError(f"Unsupported input validation mode: {mode}")


def _first_validation_error(validator: Draft202012Validator, payload: dict) -> Optional[object]:
    return next(validator.iter_errors(payload), None)


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


def _site_id_from_key(merchant_id: int, legal_country_iso: str, site_order: int) -> int:
    payload = f"{merchant_id}:{legal_country_iso}:{site_order}".encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    return low64(digest)


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
        output = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_root)
        return _git_hex_to_bytes(output.decode("utf-8").strip()).hex()
    except Exception as exc:  # pragma: no cover - fallback when git unavailable
        raise InputResolutionError("Unable to resolve git commit hash.") from exc


def run_s5(config: EngineConfig, run_id: Optional[str] = None) -> S5Result:
    logger = get_logger("engine.layers.l1.seg_2B.s5_router.l2.runner")
    timer = _StepTimer(logger)
    started_monotonic = time.monotonic()
    runs_root_norm = str(config.runs_root).replace("\\", "/")
    input_validation_mode_default = (
        "sample" if "runs/fix-data-engine" in runs_root_norm else "strict"
    )
    input_validation_mode = _env_str(
        "ENGINE_2B_S5_INPUT_VALIDATION_MODE",
        input_validation_mode_default,
    ).lower()
    if input_validation_mode not in ("strict", "sample"):
        input_validation_mode = input_validation_mode_default
    input_validation_sample_rows = _env_int(
        "ENGINE_2B_S5_INPUT_VALIDATION_SAMPLE_ROWS",
        VALIDATION_SAMPLE_ROWS_DEFAULT,
        minimum=1,
    )
    logger.info(
        "S5: input_validation_mode=%s input_validation_sample_rows=%d",
        input_validation_mode,
        input_validation_sample_rows,
    )

    manifest_fingerprint = ""
    parameter_hash = ""
    seed = 0
    run_id_value = ""
    created_utc = ""

    dictionary_version = "unknown"
    registry_version = "unknown"

    arrivals_total = 0
    selections_emitted = 0
    selections_failed = 0
    rng_events_group = 0
    rng_events_site = 0
    rng_trace_rows = 0

    selection_log_enabled = False
    selection_log_written = 0

    policy_digest = ""
    alias_policy_digest = ""
    policy_version_tag = ""
    rng_engine = ""
    draws_per_selection = 0

    rng_stream_id = ""
    rng_domain_master = "mlr:2B.routing.master"
    rng_domain_stream = "mlr:2B.routing.stream"

    first_counter: Optional[tuple[int, int]] = None
    last_counter: Optional[tuple[int, int]] = None

    samples_selections: list[dict] = []

    validators = {
        f"V-{idx:02d}": {"id": f"V-{idx:02d}", "status": "PASS", "codes": []}
        for idx in range(1, 17)
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
    timer.info(f"S5: run log initialized at {run_log_path}")

    logger.info(
        "S5: objective=route arrivals via group/site alias; gated inputs (s0_receipt, sealed_inputs, policies, s1/s4/site_timezones, arrivals) -> outputs (rng logs, optional selection log)"
    )

    source = ContractSource(config.contracts_root, config.contracts_layout)
    dict_path, dictionary = load_dataset_dictionary(source, SEGMENT)
    registry_path, registry = load_artefact_registry(source, SEGMENT)
    schema_2b_path, schema_2b = load_schema_pack(source, "2B", "2B")
    schema_2a_path, schema_2a = load_schema_pack(source, "2A", "2A")
    schema_layer1_path, schema_layer1 = load_schema_pack(source, "1A", "layer1")

    dictionary_version = str(dictionary.get("version") or "unknown")
    registry_version = str(registry.get("version") or "unknown")

    entries = _resolve_entries(dictionary)
    selection_entry = None
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
        receipt_path = _resolve_dataset_path(receipt_entry, run_paths, config.external_roots, {"manifest_fingerprint": manifest_fingerprint})
        receipt_payload = _load_json(receipt_path)
        _validate_payload(
            schema_2b,
            "validation/s0_gate_receipt_v1",
            receipt_payload,
            {"schemas.layer1.yaml#/$defs/": schema_layer1},
        )
    except (InputResolutionError, SchemaValidationError) as exc:
        _abort("2B-S5-001", "V-01", "invalid_s0_receipt", {"error": str(exc)})

    if str(receipt_payload.get("manifest_fingerprint")) != manifest_fingerprint:
        _abort(
            "2B-S5-001",
            "V-01",
            "manifest_fingerprint_mismatch",
            {"receipt": receipt_payload.get("manifest_fingerprint"), "expected": manifest_fingerprint},
        )
    created_utc = str(receipt_payload.get("verified_at_utc") or "")
    if not created_utc:
        _abort("2B-S5-086", "V-14", "created_utc_missing", {"receipt_path": str(receipt_path)})
    _record_validator("V-01", "pass")
    timer.info(f"S5: S0 receipt verified; created_utc={created_utc}")

    sealed_entry = entries["sealed_inputs_2B"]
    sealed_path = _resolve_dataset_path(sealed_entry, run_paths, config.external_roots, {"manifest_fingerprint": manifest_fingerprint})
    if not sealed_path.exists():
        _abort("2B-S5-020", "V-02", "sealed_inputs_missing", {"path": str(sealed_path)})
    sealed_payload = _load_json(sealed_path)
    sealed_schema = _schema_from_pack(schema_2b, "validation/sealed_inputs_2B")
    sealed_errors = list(Draft202012Validator(sealed_schema).iter_errors(sealed_payload))
    if sealed_errors:
        _abort("2B-S5-020", "V-02", "sealed_inputs_invalid", {"error": str(sealed_errors[0])})

    sealed_by_id = {item.get("asset_id"): item for item in sealed_payload if isinstance(item, dict)}
    sealed_required_assets = (
        "route_rng_policy_v1",
        "alias_layout_policy_v1",
        "site_timezones",
        "s5_arrival_roster",
    )
    for asset_id in sealed_required_assets:
        if asset_id not in sealed_by_id:
            _abort("2B-S5-020", "V-02", "required_asset_missing", {"asset_id": asset_id})
    timer.info(
        "S5: sealed inputs verified (policies, site_timezones, arrival roster); run-local outputs validated by path/schema checks"
    )

    policy_entry = entries["route_rng_policy_v1"]
    policy_catalog_path = _render_catalog_path(policy_entry, {})
    policy_path = _resolve_dataset_path(policy_entry, run_paths, config.external_roots, {})
    sealed_policy = sealed_by_id["route_rng_policy_v1"]
    if sealed_policy.get("path") and str(sealed_policy.get("path")) != policy_catalog_path:
        _abort(
            "2B-S5-070",
            "V-02",
            "policy_path_mismatch",
            {"sealed": sealed_policy.get("path"), "dictionary": policy_catalog_path},
        )
    policy_digest = str(sealed_policy.get("sha256_hex") or "")
    policy_version_tag = str(sealed_policy.get("version_tag") or "")
    if policy_digest:
        computed_digest = sha256_file(policy_path).sha256_hex
        if computed_digest != policy_digest:
            _abort(
                "2B-S5-020",
                "V-02",
                "policy_digest_mismatch",
                {"sealed": policy_digest, "computed": computed_digest},
            )
    else:
        _abort("2B-S5-020", "V-02", "policy_digest_missing", {"path": str(policy_path)})

    policy_payload = _load_json(policy_path)
    policy_schema = _schema_from_pack(schema_2b, "policy/route_rng_policy_v1")
    _inline_external_refs(policy_schema, schema_layer1, "schemas.layer1.yaml#/$defs/")
    policy_errors = list(Draft202012Validator(policy_schema).iter_errors(policy_payload))
    if policy_errors:
        _abort("2B-S5-053", "V-10", "policy_schema_invalid", {"error": str(policy_errors[0])})

    rng_engine = str(policy_payload.get("rng_engine") or "")
    if rng_engine != "philox2x64-10":
        _abort("2B-S5-053", "V-10", "rng_engine_invalid", {"rng_engine": rng_engine})

    rng_selection = policy_payload.get("streams", {}).get("routing_selection", {})
    rng_stream_id = str(rng_selection.get("rng_stream_id") or "")
    if not rng_stream_id:
        _abort("2B-S5-053", "V-10", "rng_stream_id_missing", {})

    basis = rng_selection.get("basis", {})
    if basis.get("key_basis") != ["seed", "parameter_hash", "run_id"]:
        _abort("2B-S5-053", "V-10", "rng_key_basis_invalid", {"key_basis": basis.get("key_basis")})
    if int(basis.get("counter_step_per_event") or 0) != 1:
        _abort(
            "2B-S5-053",
            "V-10",
            "rng_counter_step_invalid",
            {"counter_step_per_event": basis.get("counter_step_per_event")},
        )
    if basis.get("counter_wrap_policy") != "abort_on_wrap":
        _abort(
            "2B-S5-053",
            "V-10",
            "rng_counter_wrap_policy_invalid",
            {"counter_wrap_policy": basis.get("counter_wrap_policy")},
        )

    families = rng_selection.get("event_families", {})
    for label in ("alias_pick_group", "alias_pick_site"):
        family = families.get(label) or {}
        if family.get("blocks") != 1 or family.get("draws") != "1":
            _abort(
                "2B-S5-053",
                "V-10",
                "rng_family_invalid",
                {"family": label, "blocks": family.get("blocks"), "draws": family.get("draws")},
            )
    draws_per_selection = int(rng_selection.get("draws_per_unit", {}).get("draws_per_selection") or 0)
    if draws_per_selection != 2:
        _abort(
            "2B-S5-053",
            "V-10",
            "draws_per_selection_invalid",
            {"draws_per_selection": draws_per_selection},
        )

    alias_policy_entry = entries["alias_layout_policy_v1"]
    alias_policy_catalog_path = _render_catalog_path(alias_policy_entry, {})
    alias_policy_path = _resolve_dataset_path(alias_policy_entry, run_paths, config.external_roots, {})
    sealed_alias_policy = sealed_by_id["alias_layout_policy_v1"]
    if sealed_alias_policy.get("path") and str(sealed_alias_policy.get("path")) != alias_policy_catalog_path:
        _abort(
            "2B-S5-070",
            "V-02",
            "alias_policy_path_mismatch",
            {"sealed": sealed_alias_policy.get("path"), "dictionary": alias_policy_catalog_path},
        )
    alias_policy_digest = str(sealed_alias_policy.get("sha256_hex") or "")
    if alias_policy_digest:
        alias_computed = sha256_file(alias_policy_path).sha256_hex
        if alias_computed != alias_policy_digest:
            _abort(
                "2B-S5-020",
                "V-02",
                "alias_policy_digest_mismatch",
                {"sealed": alias_policy_digest, "computed": alias_computed},
            )
    else:
        _abort("2B-S5-020", "V-02", "alias_policy_digest_missing", {"path": str(alias_policy_path)})

    alias_policy_payload = _load_json(alias_policy_path)
    alias_policy_schema = _schema_from_pack(schema_2b, "policy/alias_layout_policy_v1")
    _inline_external_refs(alias_policy_schema, schema_layer1, "schemas.layer1.yaml#/$defs/")
    alias_policy_errors = list(Draft202012Validator(alias_policy_schema).iter_errors(alias_policy_payload))
    if alias_policy_errors:
        _abort("2B-S5-053", "V-10", "alias_policy_schema_invalid", {"error": str(alias_policy_errors[0])})

    selection_log_enabled = bool(
        policy_payload.get("extensions", {}).get("selection_log_enabled", False)
    )
    if not selection_entry:
        selection_log_enabled = False
    logger.info(
        "S5: selection_log_enabled=%s (policy flag + dictionary presence)",
        selection_log_enabled,
    )

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
        _abort("2B-S5-053", "V-10", "rng_derivation_invalid", {"error": str(exc)})

    counter_start = basis.get("counter_start", {})
    if counter_start:
        counter_hi = int(counter_start.get("hi", counter_hi))
        counter_lo = int(counter_start.get("lo", counter_lo))

    _record_validator("V-02", "pass")
    _record_validator("V-10", "pass")
    timer.info(
        "S5: policy digests validated; rng_stream_id=%s draws_per_selection=%s",
        rng_stream_id,
        draws_per_selection,
    )

    arrival_entry = entries["s5_arrival_roster"]
    arrival_catalog_path = _render_catalog_path(arrival_entry, tokens)
    arrival_sealed = sealed_by_id.get("s5_arrival_roster")
    if not arrival_sealed:
        _abort("2B-S5-020", "V-02", "arrival_roster_not_sealed", {"asset_id": "s5_arrival_roster"})
    if arrival_sealed.get("path") and str(arrival_sealed.get("path")) != arrival_catalog_path:
        _abort(
            "2B-S5-070",
            "V-03",
            "arrival_path_mismatch",
            {"sealed": arrival_sealed.get("path"), "dictionary": arrival_catalog_path},
        )
    sealed_partition = arrival_sealed.get("partition") or {}
    if sealed_partition and (
        str(sealed_partition.get("seed")) != str(seed)
        or str(sealed_partition.get("parameter_hash")) != parameter_hash
        or str(sealed_partition.get("run_id")) != run_id_value
    ):
        _abort(
            "2B-S5-070",
            "V-03",
            "arrival_partition_mismatch",
            {"sealed": sealed_partition, "expected": tokens},
        )
    if (
        f"seed={seed}" not in arrival_catalog_path
        or f"parameter_hash={parameter_hash}" not in arrival_catalog_path
        or f"run_id={run_id_value}" not in arrival_catalog_path
    ):
        _abort(
            "2B-S5-070",
            "V-03",
            "arrival_path_embed_mismatch",
            {"path": arrival_catalog_path, "seed": seed, "parameter_hash": parameter_hash, "run_id": run_id_value},
        )
    arrival_path = _resolve_dataset_path(arrival_entry, run_paths, config.external_roots, tokens)
    if not arrival_path.exists():
        _abort("2B-S5-020", "V-03", "arrival_roster_missing", {"path": str(arrival_path)})
    arrival_digest = sha256_file(arrival_path).sha256_hex
    if arrival_sealed.get("sha256_hex") and str(arrival_sealed.get("sha256_hex")) != arrival_digest:
        _abort(
            "2B-S5-020",
            "V-03",
            "arrival_digest_mismatch",
            {"sealed": arrival_sealed.get("sha256_hex"), "computed": arrival_digest},
        )

    arrival_schema = _schema_from_pack(schema_2b, "trace/s5_arrival_roster_row")
    _inline_external_refs(arrival_schema, schema_layer1, "schemas.layer1.yaml#/$defs/")
    arrival_validator = Draft202012Validator(arrival_schema)

    arrivals_total = _count_jsonl_rows(arrival_path)
    timer.info("S5: arrival roster loaded rows=%s (run-scoped batch input)", arrivals_total)
    progress = _ProgressTracker(
        arrivals_total,
        logger,
        "S5 routing progress arrivals_routed (group->site selections)",
    )
    timer.info("S5: starting arrival router loop (group -> site)")

    weights_entry = entries["s1_site_weights"]
    weights_path = _resolve_dataset_path(weights_entry, run_paths, config.external_roots, tokens)
    if not weights_path.exists():
        _abort("2B-S5-020", "V-03", "s1_site_weights_missing", {"path": str(weights_path)})
    weight_files = _list_parquet_paths(weights_path)
    weights_df = pl.concat([pl.read_parquet(path) for path in weight_files], how="vertical")
    weights_df = weights_df.sort(["merchant_id", "legal_country_iso", "site_order"])
    weights_pack, weights_table = _table_pack(schema_2b, "plan/s1_site_weights")
    _inline_external_refs(weights_pack, schema_layer1, "schemas.layer1.yaml#/$defs/")
    _validate_input_dataframe(
        weights_df,
        weights_pack,
        weights_table,
        input_validation_mode,
        input_validation_sample_rows,
    )

    if "created_utc" in weights_df.columns:
        weights_created = weights_df.get_column("created_utc").unique().to_list()
        if any(value != created_utc for value in weights_created):
            _abort("2B-S5-086", "V-14", "created_utc_mismatch", {"dataset": "s1_site_weights"})

    timezones_entry = entries["site_timezones"]
    timezones_path = _resolve_dataset_path(timezones_entry, run_paths, config.external_roots, tokens)
    if not timezones_path.exists():
        _abort("2B-S5-020", "V-03", "site_timezones_missing", {"path": str(timezones_path)})
    timezones_files = _list_parquet_paths(timezones_path)
    timezones_df = pl.concat([pl.read_parquet(path) for path in timezones_files], how="vertical")
    timezones_df = timezones_df.sort(["merchant_id", "legal_country_iso", "site_order"])
    timezones_pack, timezones_table = _table_pack(schema_2a, "egress/site_timezones")
    _inline_external_refs(timezones_pack, schema_layer1, "schemas.layer1.yaml#/$defs/")
    _validate_input_dataframe(
        timezones_df,
        timezones_pack,
        timezones_table,
        input_validation_mode,
        input_validation_sample_rows,
    )

    weights_joined = weights_df.join(
        timezones_df.select(["merchant_id", "legal_country_iso", "site_order", "tzid"]),
        on=["merchant_id", "legal_country_iso", "site_order"],
        how="left",
    )
    if weights_joined.get_column("tzid").null_count() > 0:
        sample = weights_joined.filter(pl.col("tzid").is_null()).head(5).to_dicts()
        _abort("2B-S5-041", "V-06", "site_timezones_missing", {"sample": sample})

    weights_joined = weights_joined.sort(["merchant_id", "legal_country_iso", "site_order"])

    site_rows_by_key: dict[tuple[int, str], list[tuple[SiteRecord, float]]] = {}
    site_id_tzid_map: dict[tuple[int, int], str] = {}
    for row in weights_joined.iter_rows(named=True):
        merchant_id = int(row.get("merchant_id"))
        legal_country_iso = str(row.get("legal_country_iso"))
        site_order = int(row.get("site_order"))
        tzid = str(row.get("tzid"))
        p_weight = float(row.get("p_weight"))
        site_id = _site_id_from_key(merchant_id, legal_country_iso, site_order)
        site_key = (merchant_id, site_id)
        mapped_tzid = site_id_tzid_map.get(site_key)
        if mapped_tzid is not None and mapped_tzid != tzid:
            _abort(
                "2B-S5-060",
                "V-07",
                "site_id_tzid_collision",
                {"merchant_id": merchant_id, "site_id": site_id},
            )
        site_id_tzid_map[site_key] = tzid
        record = SiteRecord(site_id=site_id, tzid=tzid, legal_country_iso=legal_country_iso, site_order=site_order)
        site_rows_by_key.setdefault((merchant_id, tzid), []).append((record, p_weight))

    group_entry = entries["s4_group_weights"]
    group_path = _resolve_dataset_path(group_entry, run_paths, config.external_roots, tokens)
    if not group_path.exists():
        _abort("2B-S5-020", "V-03", "s4_group_weights_missing", {"path": str(group_path)})
    group_files = _list_parquet_paths(group_path)
    group_df = pl.concat([pl.read_parquet(path) for path in group_files], how="vertical")
    group_df = group_df.sort(["merchant_id", "utc_day", "tz_group_id"])
    group_pack, group_table = _table_pack(schema_2b, "plan/s4_group_weights")
    _inline_external_refs(group_pack, schema_layer1, "schemas.layer1.yaml#/$defs/")
    _validate_input_dataframe(
        group_df,
        group_pack,
        group_table,
        input_validation_mode,
        input_validation_sample_rows,
    )
    logger.info(
        "S5: inputs loaded rows (s1_site_weights=%s, site_timezones=%s, s4_group_weights=%s)",
        weights_df.height,
        timezones_df.height,
        group_df.height,
    )

    if "created_utc" in group_df.columns:
        group_created = group_df.get_column("created_utc").unique().to_list()
        if any(value != created_utc for value in group_created):
            _abort("2B-S5-086", "V-14", "created_utc_mismatch", {"dataset": "s4_group_weights"})

    group_rows_by_key: dict[tuple[int, str], list[tuple[str, float]]] = {}
    for row in group_df.iter_rows(named=True):
        merchant_id = int(row.get("merchant_id"))
        utc_day = str(row.get("utc_day"))
        tz_group_id = str(row.get("tz_group_id"))
        p_group = float(row.get("p_group"))
        group_rows_by_key.setdefault((merchant_id, utc_day), []).append((tz_group_id, p_group))

    alias_entry = entries["s2_alias_index"]
    alias_index_path = _resolve_dataset_path(alias_entry, run_paths, config.external_roots, tokens)
    if not alias_index_path.exists():
        _abort("2B-S5-020", "V-04", "alias_index_missing", {"path": str(alias_index_path)})
    alias_index_payload = _load_json(alias_index_path)
    _validate_payload(schema_2b, "plan/s2_alias_index", alias_index_payload, {"schemas.layer1.yaml#/$defs/": schema_layer1})

    blob_entry = entries["s2_alias_blob"]
    blob_path = _resolve_dataset_path(blob_entry, run_paths, config.external_roots, tokens)
    if not blob_path.exists():
        _abort("2B-S5-020", "V-04", "alias_blob_missing", {"path": str(blob_path)})

    blob_sha256 = sha256_file(blob_path).sha256_hex
    blob_size_bytes = int(blob_path.stat().st_size)
    if str(alias_index_payload.get("blob_sha256")) != blob_sha256:
        _abort(
            "2B-S5-041",
            "V-04",
            "alias_blob_digest_mismatch",
            {"index": alias_index_payload.get("blob_sha256"), "computed": blob_sha256},
        )
    index_blob_size = int(alias_index_payload.get("blob_size_bytes") or -1)
    if index_blob_size != blob_size_bytes:
        _abort(
            "2B-S5-041",
            "V-04",
            "alias_blob_size_mismatch",
            {"index": index_blob_size, "computed": blob_size_bytes},
        )
    if str(alias_index_payload.get("policy_digest")) != alias_policy_digest:
        _abort(
            "2B-S5-041",
            "V-04",
            "alias_policy_digest_mismatch",
            {"index": alias_index_payload.get("policy_digest"), "policy": alias_policy_digest},
        )
    for field in ("layout_version", "endianness", "alignment_bytes", "quantised_bits"):
        if alias_index_payload.get(field) != alias_policy_payload.get(field):
            _abort(
                "2B-S5-041",
                "V-04",
                "alias_layout_mismatch",
                {"field": field, "index": alias_index_payload.get(field), "policy": alias_policy_payload.get(field)},
            )

    _record_validator("V-04", "pass")
    timer.info("S5: alias index parity verified (layout + blob digest)")

    group_cache: OrderedDict[tuple[int, str], AliasTable] = OrderedDict()
    site_cache: OrderedDict[tuple[int, str], AliasTable] = OrderedDict()

    tmp_root = run_paths.tmp_root / f"s5_router_{uuid.uuid4().hex}"
    event_group_tmp_dir = tmp_root / "rng_event_alias_pick_group"
    event_site_tmp_dir = tmp_root / "rng_event_alias_pick_site"
    selection_tmp = tmp_root / "selection_log"
    tmp_root.mkdir(parents=True, exist_ok=True)
    event_group_tmp_dir.mkdir(parents=True, exist_ok=True)
    event_site_tmp_dir.mkdir(parents=True, exist_ok=True)
    if selection_log_enabled:
        selection_tmp.mkdir(parents=True, exist_ok=True)

    event_group_tmp = event_group_tmp_dir / "part-00000.jsonl"
    event_site_tmp = event_site_tmp_dir / "part-00000.jsonl"
    trace_tmp_path = tmp_root / "rng_trace_log.jsonl"

    event_schema_group = _schema_from_pack(schema_layer1, "rng/events/alias_pick_group")
    event_schema_site = _schema_from_pack(schema_layer1, "rng/events/alias_pick_site")
    trace_schema = _schema_from_pack(schema_layer1, "rng/core/rng_trace_log/record")
    audit_schema = _schema_from_pack(schema_layer1, "rng/core/rng_audit_log/record")
    selection_schema = None
    if selection_log_enabled and selection_entry:
        selection_schema = _schema_from_pack(schema_2b, "trace/s5_selection_log_row")
        _inline_external_refs(selection_schema, schema_layer1, "schemas.layer1.yaml#/$defs/")

    event_group_validator = Draft202012Validator(event_schema_group)
    event_site_validator = Draft202012Validator(event_schema_site)
    trace_validator = Draft202012Validator(trace_schema)
    audit_validator = Draft202012Validator(audit_schema)
    selection_validator = Draft202012Validator(selection_schema) if selection_schema else None

    def _get_group_alias(merchant_id: int, utc_day: str) -> AliasTable:
        key = (merchant_id, utc_day)
        if key in group_cache:
            group_cache.move_to_end(key)
            return group_cache[key]
        rows = group_rows_by_key.get(key, [])
        if not rows:
            _abort("2B-S5-040", "V-05", "group_weights_missing", {"merchant_id": merchant_id, "utc_day": utc_day})
        tzids = [row[0] for row in rows]
        p_groups = [row[1] for row in rows]
        sum_p = float(sum(p_groups))
        if not math.isfinite(sum_p) or abs(sum_p - 1.0) > EPSILON:
            _abort(
                "2B-S5-040",
                "V-05",
                "group_probabilities_mismatch",
                {"merchant_id": merchant_id, "utc_day": utc_day, "sum_p": sum_p},
            )
        prob, alias = _build_alias(p_groups)
        table = AliasTable(items=tzids, prob=prob, alias=alias, weights=p_groups)
        group_cache[key] = table
        if len(group_cache) > GROUP_CACHE_MAX:
            group_cache.popitem(last=False)
        return table

    def _get_site_alias(merchant_id: int, tz_group_id: str) -> AliasTable:
        key = (merchant_id, tz_group_id)
        if key in site_cache:
            site_cache.move_to_end(key)
            return site_cache[key]
        rows = site_rows_by_key.get(key, [])
        if not rows:
            _abort(
                "2B-S5-041",
                "V-06",
                "site_slice_empty",
                {"merchant_id": merchant_id, "tz_group_id": tz_group_id},
            )
        records = [row[0] for row in rows]
        weights = [row[1] for row in rows]
        prob, alias = _build_alias(weights)
        table = AliasTable(items=records, prob=prob, alias=alias)
        site_cache[key] = table
        if len(site_cache) > SITE_CACHE_MAX:
            site_cache.popitem(last=False)
        return table

    trace_acc = RngTraceAccumulator()
    deterministic_ts = _DeterministicTimestampSequence(created_utc)

    selection_handles: dict[str, tuple[Path, object]] = {}
    json_dumps = json.dumps

    with (
        event_group_tmp.open("w", encoding="utf-8") as group_handle,
        event_site_tmp.open("w", encoding="utf-8") as site_handle,
        trace_tmp_path.open("w", encoding="utf-8") as trace_handle,
    ):
        with arrival_path.open("r", encoding="utf-8") as arrivals_handle:
            for line in arrivals_handle:
                if not line.strip():
                    continue
                try:
                    arrival = json.loads(line)
                except json.JSONDecodeError as exc:
                    _abort("2B-S5-020", "V-03", "arrival_json_invalid", {"error": str(exc)})
                arrival_error = _first_validation_error(arrival_validator, arrival)
                if arrival_error:
                    _abort("2B-S5-020", "V-03", "arrival_schema_invalid", {"error": arrival_error.message})

                merchant_id = int(arrival["merchant_id"])
                utc_timestamp = str(arrival["utc_timestamp"])
                utc_day = str(arrival["utc_day"])

                group_alias = _get_group_alias(merchant_id, utc_day)
                before_hi = counter_hi
                before_lo = counter_lo
                out0, _out1 = philox2x64_10(before_hi, before_lo, rng_key)
                u_group = u01(out0)
                group_index = _alias_pick(group_alias.prob, group_alias.alias, u_group)
                tz_group_id = str(group_alias.items[group_index])
                if not group_alias.weights:
                    _abort(
                        "2B-S5-040",
                        "V-05",
                        "group_alias_weights_missing",
                        {"merchant_id": merchant_id, "utc_day": utc_day},
                    )
                p_group = float(group_alias.weights[group_index])
                after_hi, after_lo = add_u128(before_hi, before_lo, 1)
                if (after_hi, after_lo) <= (before_hi, before_lo):
                    _abort("2B-S5-051", "V-09", "rng_counter_not_monotone", {"before": [before_hi, before_lo], "after": [after_hi, after_lo]})

                event_group = {
                    "ts_utc": deterministic_ts.next(),
                    "run_id": run_id_value,
                    "seed": seed,
                    "parameter_hash": parameter_hash,
                    "manifest_fingerprint": manifest_fingerprint,
                    "module": MODULE_NAME,
                    "substream_label": "alias_pick_group",
                    "rng_counter_before_lo": before_lo,
                    "rng_counter_before_hi": before_hi,
                    "rng_counter_after_lo": after_lo,
                    "rng_counter_after_hi": after_hi,
                    "draws": "1",
                    "blocks": 1,
                    "merchant_id": merchant_id,
                    "utc_day": utc_day,
                    "tz_group_id": tz_group_id,
                    "p_group": p_group,
                }
                event_group_error = _first_validation_error(event_group_validator, event_group)
                if event_group_error:
                    _abort("2B-S5-050", "V-08", "rng_event_invalid", {"error": event_group_error.message})
                trace_row = trace_acc.append_event(event_group)
                trace_row["ts_utc"] = deterministic_ts.next()
                trace_error = _first_validation_error(trace_validator, trace_row)
                if trace_error:
                    _abort("2B-S5-050", "V-11", "rng_trace_invalid", {"error": trace_error.message})
                group_handle.write(json_dumps(event_group, ensure_ascii=True, sort_keys=True))
                group_handle.write("\n")
                trace_handle.write(json_dumps(trace_row, ensure_ascii=True, sort_keys=True))
                trace_handle.write("\n")
                rng_events_group += 1
                rng_trace_rows += 1

                counter_hi, counter_lo = after_hi, after_lo

                site_alias = _get_site_alias(merchant_id, tz_group_id)
                before_hi = counter_hi
                before_lo = counter_lo
                out0, _out1 = philox2x64_10(before_hi, before_lo, rng_key)
                u_site = u01(out0)
                site_index = _alias_pick(site_alias.prob, site_alias.alias, u_site)
                site_record: SiteRecord = site_alias.items[site_index]
                site_id = int(site_record.site_id)
                after_hi, after_lo = add_u128(before_hi, before_lo, 1)
                if (after_hi, after_lo) <= (before_hi, before_lo):
                    _abort("2B-S5-051", "V-09", "rng_counter_not_monotone", {"before": [before_hi, before_lo], "after": [after_hi, after_lo]})

                event_site = {
                    "ts_utc": deterministic_ts.next(),
                    "run_id": run_id_value,
                    "seed": seed,
                    "parameter_hash": parameter_hash,
                    "manifest_fingerprint": manifest_fingerprint,
                    "module": MODULE_NAME,
                    "substream_label": "alias_pick_site",
                    "rng_counter_before_lo": before_lo,
                    "rng_counter_before_hi": before_hi,
                    "rng_counter_after_lo": after_lo,
                    "rng_counter_after_hi": after_hi,
                    "draws": "1",
                    "blocks": 1,
                    "merchant_id": merchant_id,
                    "utc_day": utc_day,
                    "tz_group_id": tz_group_id,
                    "site_id": site_id,
                }
                event_site_error = _first_validation_error(event_site_validator, event_site)
                if event_site_error:
                    _abort("2B-S5-050", "V-08", "rng_event_invalid", {"error": event_site_error.message})
                trace_row = trace_acc.append_event(event_site)
                trace_row["ts_utc"] = deterministic_ts.next()
                trace_error = _first_validation_error(trace_validator, trace_row)
                if trace_error:
                    _abort("2B-S5-050", "V-11", "rng_trace_invalid", {"error": trace_error.message})
                site_handle.write(json_dumps(event_site, ensure_ascii=True, sort_keys=True))
                site_handle.write("\n")
                trace_handle.write(json_dumps(trace_row, ensure_ascii=True, sort_keys=True))
                trace_handle.write("\n")
                rng_events_site += 1
                rng_trace_rows += 1

                counter_hi, counter_lo = after_hi, after_lo
                last_counter = (after_hi, after_lo)
                if first_counter is None:
                    first_counter = (event_group["rng_counter_before_hi"], event_group["rng_counter_before_lo"])

                if site_record.tzid != tz_group_id:
                    _abort(
                        "2B-S5-060",
                        "V-07",
                        "tz_group_site_mismatch",
                        {"merchant_id": merchant_id, "site_id": site_id, "tzid": site_record.tzid, "expected": tz_group_id},
                    )

                if selection_log_enabled and selection_entry:
                    selection_row = {
                        "merchant_id": merchant_id,
                        "utc_timestamp": utc_timestamp,
                        "utc_day": utc_day,
                        "tz_group_id": tz_group_id,
                        "site_id": site_id,
                        "rng_stream_id": rng_stream_id,
                        "ctr_group_hi": event_group["rng_counter_before_hi"],
                        "ctr_group_lo": event_group["rng_counter_before_lo"],
                        "ctr_site_hi": event_site["rng_counter_before_hi"],
                        "ctr_site_lo": event_site["rng_counter_before_lo"],
                        "manifest_fingerprint": manifest_fingerprint,
                        "created_utc": created_utc,
                    }
                    if selection_validator:
                        selection_error = _first_validation_error(selection_validator, selection_row)
                        if selection_error:
                            _abort("2B-S5-071", "V-12", "selection_log_schema_invalid", {"error": selection_error.message})
                    if utc_day not in selection_handles:
                        tmp_path = selection_tmp / f"{utc_day}.jsonl"
                        handle = tmp_path.open("w", encoding="utf-8")
                        selection_handles[utc_day] = (tmp_path, handle)
                    tmp_path, handle = selection_handles[utc_day]
                    handle.write(json_dumps(selection_row, ensure_ascii=True, sort_keys=True))
                    handle.write("\n")
                    selection_log_written += 1

                selections_emitted += 1
                if len(samples_selections) < 20:
                    samples_selections.append(
                        {
                            "merchant_id": merchant_id,
                            "utc_day": utc_day,
                            "tz_group_id": tz_group_id,
                            "site_id": site_id,
                        }
                    )
                progress.update(1)

    for _day, (_path, handle) in selection_handles.items():
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
        _abort("2B-S5-050", "V-11", "rng_audit_invalid", {"error": audit_errors[0].message})
    # rng_audit_log is append-only across states; only add a row if missing.

    rng_events_total = rng_events_group + rng_events_site
    rng_draws_total = selections_emitted * 2
    if rng_events_total != rng_draws_total:
        _abort(
            "2B-S5-050",
            "V-08",
            "rng_draws_mismatch",
            {"events": rng_events_total, "selections": selections_emitted},
        )

    event_group_catalog = _render_catalog_path(
        find_dataset_entry(dictionary, "rng_event_alias_pick_group").entry, tokens
    )
    event_site_catalog = _render_catalog_path(
        find_dataset_entry(dictionary, "rng_event_alias_pick_site").entry, tokens
    )
    trace_catalog = _render_catalog_path(find_dataset_entry(dictionary, "rng_trace_log").entry, tokens)
    audit_catalog = _render_catalog_path(find_dataset_entry(dictionary, "rng_audit_log").entry, tokens)

    for label, path in (
        ("rng_event_alias_pick_group", event_group_catalog),
        ("rng_event_alias_pick_site", event_site_catalog),
        ("rng_trace_log", trace_catalog),
        ("rng_audit_log", audit_catalog),
    ):
        if (
            f"seed={seed}" not in path
            or f"parameter_hash={parameter_hash}" not in path
            or f"run_id={run_id_value}" not in path
        ):
            _abort("2B-S5-071", "V-15", "output_partition_mismatch", {"id": label, "path": path})

    event_group_output = _render_output_path(run_paths, event_group_catalog)
    event_site_output = _render_output_path(run_paths, event_site_catalog)
    trace_output = _render_output_path(run_paths, trace_catalog)
    audit_output = _render_output_path(run_paths, audit_catalog)

    _atomic_publish_file(event_group_tmp, event_group_output, logger, "rng_event_alias_pick_group")
    _atomic_publish_file(event_site_tmp, event_site_output, logger, "rng_event_alias_pick_site")
    _atomic_publish_file(trace_tmp_path, trace_output, logger, "rng_trace_log")
    _ensure_rng_audit(audit_output, audit_payload, logger, "S5")

    if selection_log_enabled and selection_entry:
        for utc_day, (tmp_path, _handle) in selection_handles.items():
            selection_tokens = dict(tokens)
            selection_tokens["utc_day"] = utc_day
            selection_catalog = _render_catalog_path(selection_entry, selection_tokens)
            selection_output = _render_output_path(run_paths, selection_catalog)
            _atomic_publish_file(tmp_path, selection_output, logger, f"s5_selection_log {utc_day}")

    shutil.rmtree(tmp_root, ignore_errors=True)
    timer.info("S5: published rng logs (events/trace/audit) and selection log if enabled")

    elapsed_total = time.monotonic() - started_monotonic

    inputs_summary = {
        "group_weights_path": _render_catalog_path(group_entry, tokens),
        "site_weights_path": _render_catalog_path(weights_entry, tokens),
        "site_timezones_path": _render_catalog_path(timezones_entry, tokens),
        "alias_index_path": _render_catalog_path(alias_entry, tokens),
        "alias_blob_path": _render_catalog_path(blob_entry, tokens),
    }
    validators_list = list(validators.values())
    warn_count = sum(1 for item in validators_list if item.get("status") == "WARN")
    fail_count = sum(1 for item in validators_list if item.get("status") == "FAIL")
    overall_status = "FAIL" if fail_count else "PASS"
    if first_counter is None:
        first_counter = (counter_hi, counter_lo)
    if last_counter is None:
        last_counter = (counter_hi, counter_lo)

    logging_payload = {"selection_log_enabled": selection_log_enabled}
    if selection_log_enabled:
        logging_payload["selection_log_partition"] = "[seed,parameter_hash,run_id,utc_day]"

    run_report = {
        "component": "2B.S5",
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
            "draws_per_selection": draws_per_selection,
        },
        "inputs_summary": inputs_summary,
        "rng_accounting": {
            "events_group": rng_events_group,
            "events_site": rng_events_site,
            "events_total": rng_events_total,
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
        },
        "samples": {"selections": samples_selections, "inputs": inputs_summary},
    }

    run_report_path = (
        run_paths.run_root
        / "reports"
        / "layer1"
        / "2B"
        / "state=S5"
        / f"seed={seed}"
        / f"manifest_fingerprint={manifest_fingerprint}"
        / "s5_run_report.json"
    )
    _write_json(run_report_path, run_report)
    logger.info("S5 run-report %s", json.dumps(run_report, ensure_ascii=True, sort_keys=True))

    timer.info("S5: completed routing run")

    return S5Result(
        run_id=run_id_value,
        parameter_hash=parameter_hash,
        manifest_fingerprint=manifest_fingerprint,
        run_report_path=run_report_path,
        selection_log_enabled=selection_log_enabled,
    )
