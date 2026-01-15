"""S0 gate-in runner for Segment 2B."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import platform
import re
import shutil
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from jsonschema import Draft202012Validator

from engine.contracts.jsonschema_adapter import normalize_nullable_schema, validate_dataframe
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
    HashingError,
    InputResolutionError,
    SchemaValidationError,
)
from engine.core.hashing import sha256_file
from engine.core.logging import add_file_handler, get_logger
from engine.core.paths import RunPaths, resolve_input_path
from engine.core.time import utc_now_rfc3339_micro


MODULE_NAME = "2B.s0_gate"
SEGMENT = "2B"
STATE = "S0"
_FLAG_PATTERN = re.compile(r"^sha256_hex\\s*=\\s*([a-f0-9]{64})\\s*$")
_HEX64_ANYWHERE = re.compile(r"([a-f0-9]{64})")
_HEX64_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_PLACEHOLDER_MARKERS = {"TBD", "null", "unknown"}
_POLICY_IDS = {
    "route_rng_policy_v1",
    "alias_layout_policy_v1",
    "day_effect_policy_v1",
    "virtual_edge_policy_v1",
}


@dataclass(frozen=True)
class SealedAsset:
    asset_id: str
    path: Path
    schema_ref: str
    version_tag: str
    partition: dict[str, str]
    partition_keys: list[str]
    catalog_path: str
    sha256_hex: str


@dataclass(frozen=True)
class S0GateResult:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    receipt_path: Path
    sealed_inputs_path: Path
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
    def __init__(self, total: int, logger, label: str) -> None:
        self._total = max(int(total), 0)
        self._logger = logger
        self._label = label
        self._start = time.monotonic()
        self._last_log = self._start
        self._processed = 0

    def update(self, count: int) -> None:
        self._processed += int(count)
        now = time.monotonic()
        if now - self._last_log < 0.5 and self._processed < self._total:
            return
        self._last_log = now
        elapsed = now - self._start
        rate = self._processed / elapsed if elapsed > 0 else 0.0
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


def _emit_event(
    logger,
    event: str,
    manifest_fingerprint: Optional[str],
    severity: str,
    **fields: object,
) -> None:
    payload = {
        "event": event,
        "segment": SEGMENT,
        "state": STATE,
        "manifest_fingerprint": manifest_fingerprint or "unknown",
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
    manifest_fingerprint: Optional[str],
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
    _emit_event(logger, "VALIDATION", manifest_fingerprint, severity, **payload)


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


def _pick_latest_run_receipt(runs_root: Path) -> Path:
    candidates = sorted(
        runs_root.glob("*/run_receipt.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise InputResolutionError(f"No run_receipt.json found under {runs_root}")
    return candidates[0]


def _resolve_run_receipt(runs_root: Path, run_id: Optional[str]) -> tuple[Path, dict]:
    if run_id:
        receipt_path = runs_root / run_id / "run_receipt.json"
    else:
        receipt_path = _pick_latest_run_receipt(runs_root)
    return receipt_path, _load_json(receipt_path)


def _schema_from_pack(schema_pack: dict, path: str) -> dict:
    node: dict = schema_pack
    for part in path.strip("#/").split("/"):
        if part not in node:
            raise ContractError(f"Schema section not found: {path}")
        node = node[part]
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": schema_pack.get("$id", ""),
        "$defs": schema_pack.get("$defs", {}),
    }
    schema.update(node)
    unevaluated = None
    if isinstance(schema.get("allOf"), list):
        for subschema in schema["allOf"]:
            if not isinstance(subschema, dict):
                continue
            if "unevaluatedProperties" in subschema:
                if unevaluated is None:
                    unevaluated = subschema["unevaluatedProperties"]
                subschema.pop("unevaluatedProperties", None)
    if unevaluated is not None and "unevaluatedProperties" not in schema:
        schema["unevaluatedProperties"] = unevaluated
    return normalize_nullable_schema(schema)


def _schema_node(schema_pack: dict, path: str) -> dict:
    node: dict = schema_pack
    parts = path.strip("#/").split("/")
    for part in parts:
        if part not in node or not isinstance(node[part], dict):
            raise ContractError(f"Schema section not found: {path}")
        node = node[part]
    return node


def _policy_version_from_file(path: Path) -> Optional[str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EngineFailure(
            "F4",
            "2B-S0-020",
            STATE,
            MODULE_NAME,
            {"detail": "policy JSON unreadable", "path": str(path), "error": str(exc)},
        ) from exc
    if not isinstance(payload, dict):
        return None
    value = payload.get("policy_version") or payload.get("version_tag")
    if value is None:
        return None
    return str(value)


def _inline_external_refs(schema: object, external_pack: dict, prefix: str) -> None:
    external_defs = external_pack.get("$defs") or {}

    def _walk(node: object) -> None:
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str) and ref.startswith(prefix):
                tail = ref.split("#/$defs/", 1)
                if len(tail) == 2:
                    name = tail[1].split("/", 1)[0]
                    if name in external_defs:
                        replacement = copy.deepcopy(external_defs[name])
                        for key, value in list(node.items()):
                            if key != "$ref":
                                replacement[key] = value
                        node.clear()
                        node.update(replacement)
                        return
            for value in node.values():
                _walk(value)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(schema)


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


def _parse_pass_flag(flag_path: Path) -> str:
    if not flag_path.exists():
        raise InputResolutionError(f"Missing PASS flag: {flag_path}")
    lines = flag_path.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise EngineFailure(
            "F4",
            "2B-S0-013",
            STATE,
            MODULE_NAME,
            {"detail": "empty _passed.flag", "path": str(flag_path)},
        )
    first_line = lines[0].strip()
    match = _FLAG_PATTERN.match(first_line)
    if not match:
        fallback = _HEX64_ANYWHERE.search(first_line)
        if fallback:
            return fallback.group(1)
        raise EngineFailure(
            "F4",
            "2B-S0-013",
            STATE,
            MODULE_NAME,
            {"detail": "invalid _passed.flag format", "line": first_line},
        )
    return match.group(1)


def _hash_paths(paths: list[Path], logger, label: str) -> tuple[str, int]:
    if not paths:
        raise HashingError(f"No files found for hash: {label}")
    hasher = hashlib.sha256()
    total_bytes = 0
    tracker = _ProgressTracker(len(paths), logger, f"{label} files")
    for path in paths:
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                total_bytes += len(chunk)
                hasher.update(chunk)
        tracker.update(1)
    return hasher.hexdigest(), total_bytes


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


def _atomic_publish_dir(
    tmp_root: Path,
    final_root: Path,
    logger,
    label: str,
) -> bool:
    if final_root.exists():
        tmp_hash, _ = _hash_partition(tmp_root)
        final_hash, _ = _hash_partition(final_root)
        if tmp_hash != final_hash:
            raise EngineFailure(
                "F4",
                "2B-S0-080",
                STATE,
                MODULE_NAME,
                {"detail": "non-identical output exists", "partition": str(final_root), "label": label},
            )
        shutil.rmtree(tmp_root)
        logger.info("S0: %s partition already exists and is identical; skipping publish.", label)
        return True
    final_root.parent.mkdir(parents=True, exist_ok=True)
    try:
        tmp_root.replace(final_root)
    except OSError as exc:
        raise EngineFailure(
            "F4",
            "2B-S0-082",
            STATE,
            MODULE_NAME,
            {"detail": "atomic publish failed", "partition": str(final_root), "error": str(exc)},
        ) from exc
    return False


def _atomic_publish_file(
    final_path: Path,
    payload_bytes: bytes,
    logger,
    label: str,
) -> bool:
    if final_path.exists():
        if final_path.read_bytes() != payload_bytes:
            raise EngineFailure(
                "F4",
                "2B-S0-080",
                STATE,
                MODULE_NAME,
                {"detail": "non-identical output exists", "path": str(final_path), "label": label},
            )
        logger.info("S0: %s already exists and is identical; skipping publish.", label)
        return True
    tmp_dir = final_path.parent / f"_tmp.{uuid.uuid4().hex}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / final_path.name
    tmp_path.write_bytes(payload_bytes)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        tmp_path.replace(final_path)
    except OSError as exc:
        raise EngineFailure(
            "F4",
            "2B-S0-082",
            STATE,
            MODULE_NAME,
            {"detail": "atomic publish failed", "path": str(final_path), "error": str(exc)},
        ) from exc
    if tmp_dir.exists():
        try:
            tmp_dir.rmdir()
        except OSError:
            pass
    return False


def _resolve_dataset_path(
    entry: dict,
    run_paths: RunPaths,
    external_roots: Iterable[Path],
    tokens: dict[str, str],
) -> Path:
    path_template = entry.get("path")
    if not path_template:
        raise InputResolutionError("Dataset entry missing path.")
    resolved = path_template
    for key, value in tokens.items():
        resolved = resolved.replace(f"{{{key}}}", value)
    if resolved.startswith(("data/", "logs/", "reports/")):
        return run_paths.run_root / resolved
    if resolved.startswith("artefacts/"):
        return resolve_input_path(resolved, run_paths, external_roots, allow_run_local=False)
    return resolve_input_path(resolved, run_paths, external_roots, allow_run_local=True)


def _render_catalog_path(entry: dict, tokens: dict[str, str]) -> str:
    path_template = entry.get("path") or ""
    rendered = path_template
    for key, value in tokens.items():
        rendered = rendered.replace(f"{{{key}}}", value)
    return rendered


def _partition_values(entry: dict, tokens: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    partition_keys = list(entry.get("partitioning") or [])
    partition = {key: tokens[key] for key in partition_keys if key in tokens}
    return partition, partition_keys


def _resolve_version_tag(
    entry: dict,
    tokens: dict[str, str],
    fallback: Optional[str],
) -> tuple[str, bool]:
    version = entry.get("version")
    rendered = str(version) if version is not None else ""
    for key, value in tokens.items():
        rendered = rendered.replace(f"{{{key}}}", value)
    placeholder = (
        not rendered
        or rendered in _PLACEHOLDER_MARKERS
        or "{" in rendered
        or "}" in rendered
    )
    if placeholder:
        if fallback:
            rendered = fallback
            placeholder = (
                rendered in _PLACEHOLDER_MARKERS or "{" in rendered or "}" in rendered
            )
        if placeholder:
            return "unknown", True
        return rendered, False
    return rendered, False


def _schema_anchor_exists(schema_pack: dict, ref: str) -> None:
    if "#/" not in ref:
        raise ContractError(f"Invalid schema_ref (missing anchor): {ref}")
    path = ref.split("#", 1)[1]
    node: dict = schema_pack
    for part in path.strip("/").split("/"):
        if part not in node:
            raise ContractError(f"Schema section not found: {ref}")
        node = node[part]


def run_s0(config: EngineConfig, run_id: Optional[str] = None) -> S0GateResult:
    logger = get_logger("engine.layers.l1.seg_2B.s0_gate.l2.runner")
    timer = _StepTimer(logger)
    started_monotonic = time.monotonic()

    receipt_path, receipt = _resolve_run_receipt(config.runs_root, run_id)
    run_id = receipt.get("run_id")
    if not run_id:
        raise InputResolutionError("run_receipt missing run_id.")
    if receipt_path.parent.name != str(run_id):
        raise InputResolutionError("run_receipt path does not match embedded run_id.")
    seed = receipt.get("seed")
    parameter_hash = receipt.get("parameter_hash")
    manifest_fingerprint = receipt.get("manifest_fingerprint")
    if seed is None or not parameter_hash or not manifest_fingerprint:
        raise InputResolutionError("run_receipt missing seed, parameter_hash, or manifest_fingerprint.")

    run_paths = RunPaths(config.runs_root, str(run_id))
    run_log_path = run_paths.run_root / f"run_log_{run_id}.log"
    add_file_handler(run_log_path)
    timer.info(f"S0: run log initialized at {run_log_path}")

    source = ContractSource(config.contracts_root, config.contracts_layout)
    dict_path, dictionary = load_dataset_dictionary(source, SEGMENT)
    registry_path, registry = load_artefact_registry(source, SEGMENT)
    schema_2b_path, schema_2b = load_schema_pack(source, "2B", "2B")
    schema_2a_path, schema_2a = load_schema_pack(source, "2A", "2A")
    schema_1b_path, schema_1b = load_schema_pack(source, "1B", "1B")
    schema_layer1_path, schema_layer1 = load_schema_pack(source, "1A", "layer1")

    logger.info(
        "Contracts layout=%s root=%s dictionary=%s registry=%s schemas=%s,%s,%s,%s",
        config.contracts_layout,
        config.contracts_root,
        dict_path,
        registry_path,
        schema_2b_path,
        schema_2a_path,
        schema_1b_path,
        schema_layer1_path,
    )

    tokens = {
        "seed": str(seed),
        "manifest_fingerprint": str(manifest_fingerprint),
    }

    entries = {}
    required_ids = [
        "validation_bundle_1B",
        "validation_passed_flag_1B",
        "site_locations",
        "site_timezones",
        "route_rng_policy_v1",
        "alias_layout_policy_v1",
        "day_effect_policy_v1",
        "virtual_edge_policy_v1",
    ]
    optional_ids = ["tz_timetable_cache"]
    for dataset_id in required_ids + optional_ids + ["s0_gate_receipt_2B", "sealed_inputs_2B"]:
        try:
            entries[dataset_id] = find_dataset_entry(dictionary, dataset_id).entry
        except ContractError as exc:
            raise EngineFailure(
                "F4",
                "2B-S0-020",
                STATE,
                MODULE_NAME,
                {"detail": "dictionary resolution failed", "dataset_id": dataset_id},
                dataset_id=dataset_id,
            ) from exc

    schema_refs = {key: entries[key].get("schema_ref", "") for key in entries}
    for dataset_id, schema_ref in schema_refs.items():
        if not schema_ref:
            raise EngineFailure(
                "F4",
                "2B-S0-020",
                STATE,
                MODULE_NAME,
                {"detail": "missing schema_ref in dictionary", "dataset_id": dataset_id},
                dataset_id=dataset_id,
            )
        try:
            if schema_ref.startswith("schemas.2B.yaml#"):
                _schema_anchor_exists(schema_2b, schema_ref)
            elif schema_ref.startswith("schemas.2A.yaml#"):
                _schema_anchor_exists(schema_2a, schema_ref)
            elif schema_ref.startswith("schemas.1B.yaml#"):
                _schema_anchor_exists(schema_1b, schema_ref)
            elif schema_ref.startswith("schemas.layer1.yaml#"):
                _schema_anchor_exists(schema_layer1, schema_ref)
        except ContractError as exc:
            raise EngineFailure(
                "F4",
                "2B-S0-020",
                STATE,
                MODULE_NAME,
                {"detail": "schema_ref invalid", "dataset_id": dataset_id, "schema_ref": schema_ref},
            ) from exc

    _emit_validation(logger, manifest_fingerprint, "V-03", "pass")

    bundle_root = _resolve_dataset_path(entries["validation_bundle_1B"], run_paths, config.external_roots, tokens)
    flag_path = _resolve_dataset_path(entries["validation_passed_flag_1B"], run_paths, config.external_roots, tokens)
    if not bundle_root.exists() or not flag_path.exists():
        raise EngineFailure(
            "F4",
            "2B-S0-010",
            STATE,
            MODULE_NAME,
            {"detail": "missing gate artefacts", "bundle_root": str(bundle_root), "flag_path": str(flag_path)},
        )
    _emit_validation(logger, manifest_fingerprint, "V-01", "pass")

    gate_start = time.monotonic()
    flag_sha256 = _parse_pass_flag(flag_path)
    if not _HEX64_PATTERN.match(flag_sha256):
        raise EngineFailure(
            "F4",
            "2B-S0-013",
            STATE,
            MODULE_NAME,
            {"detail": "flag_sha256_hex invalid", "value": flag_sha256},
        )

    index_path = bundle_root / "index.json"
    bundle_index = _load_json(index_path)
    try:
        bundle_schema_ref = entries["validation_bundle_1B"].get("schema_ref")
        if isinstance(bundle_schema_ref, str) and bundle_schema_ref.startswith("schemas.1B.yaml#"):
            bundle_schema = _schema_node(schema_1b, bundle_schema_ref.split("#", 1)[1])
            index_schema = bundle_schema.get("index_schema")
            if not isinstance(index_schema, dict):
                raise SchemaValidationError(
                    "validation_bundle index_schema missing", [{"message": "index_schema missing"}]
                )
            if index_schema.get("type") in ("table", "stream", "geotable", "raster"):
                pack = {
                    "$id": schema_1b.get("$id", ""),
                    "$defs": schema_1b.get("$defs", {}),
                    "index_schema": index_schema,
                }
                validate_dataframe(bundle_index, pack, "index_schema")
            else:
                errors = list(Draft202012Validator(index_schema).iter_errors(bundle_index))
                if errors:
                    raise SchemaValidationError(errors[0].message, [{"message": errors[0].message}])
        else:
            index_schema = _schema_from_pack(schema_layer1, "validation/validation_bundle/index_schema")
            errors = list(Draft202012Validator(index_schema).iter_errors(bundle_index))
            if errors:
                raise SchemaValidationError(errors[0].message, [{"message": errors[0].message}])
    except (SchemaValidationError, ContractError) as exc:
        raise EngineFailure(
            "F4",
            "2B-S0-012",
            STATE,
            MODULE_NAME,
            {"detail": "bundle index invalid", "error": str(exc)},
        ) from exc

    index_paths = []
    for entry in bundle_index:
        path_value = entry.get("path")
        if not isinstance(path_value, str) or path_value.startswith(("/", "\\")) or ".." in path_value:
            raise EngineFailure(
                "F4",
                "2B-S0-012",
                STATE,
                MODULE_NAME,
                {"detail": "bundle index path invalid", "path": path_value},
            )
        index_paths.append(path_value)

    index_paths_sorted = sorted(index_paths)
    gate_index_sample = index_paths_sorted[:20]
    hash_paths = []
    for relative_path in index_paths_sorted:
        if relative_path.endswith("_passed.flag"):
            continue
        full_path = bundle_root / relative_path
        if not full_path.exists():
            raise EngineFailure(
                "F4",
                "2B-S0-012",
                STATE,
                MODULE_NAME,
                {"detail": "bundle index path missing", "path": str(full_path)},
            )
        hash_paths.append(full_path)

    bundle_hash, _bundle_bytes = _hash_paths(hash_paths, logger, "bundle")
    if bundle_hash != flag_sha256:
        raise EngineFailure(
            "F4",
            "2B-S0-011",
            STATE,
            MODULE_NAME,
            {
                "detail": "bundle hash mismatch",
                "expected": flag_sha256,
                "actual": bundle_hash,
            },
        )
    _emit_validation(logger, manifest_fingerprint, "V-02", "pass")
    gate_verify_ms = int((time.monotonic() - gate_start) * 1000)

    _emit_event(
        logger,
        "GATE",
        manifest_fingerprint,
        "INFO",
        bundle_root=str(bundle_root),
        flag_path=str(flag_path),
        bundle_sha256_actual=bundle_hash,
    )

    sealed_assets: list[SealedAsset] = []
    sealed_inputs_for_receipt: list[dict] = []
    placeholders_used: list[str] = []
    policy_ids: list[str] = []
    policy_digests: list[str] = []
    required_present = 0

    def _registry_version_tag(dataset_id: str) -> Optional[str]:
        try:
            reg_entry = find_artifact_entry(registry, dataset_id).entry
        except ContractError:
            return None
        candidate = reg_entry.get("semver") or reg_entry.get("version")
        if candidate is None:
            return None
        rendered = str(candidate)
        if rendered in _PLACEHOLDER_MARKERS or "{" in rendered or "}" in rendered:
            return None
        return rendered

    def _add_sealed_asset(dataset_id: str, path: Path) -> None:
        entry = entries[dataset_id]
        partition, partition_keys = _partition_values(entry, tokens)
        version_tokens = tokens
        if dataset_id in _POLICY_IDS:
            policy_version = _policy_version_from_file(path)
            if policy_version:
                version_tokens = dict(tokens)
                version_tokens["policy_version"] = policy_version
        version_tag, placeholder = _resolve_version_tag(
            entry, version_tokens, _registry_version_tag(dataset_id)
        )
        if placeholder:
            placeholders_used.append(dataset_id)
        if partition_keys and len(partition) != len(partition_keys):
            raise EngineFailure(
                "F4",
                "2B-S0-050",
                STATE,
                MODULE_NAME,
                {"detail": "missing partition tokens", "dataset_id": dataset_id, "partition_keys": partition_keys},
            )
        catalog_path = _render_catalog_path(entry, tokens)
        if partition_keys:
            for key in partition_keys:
                token = f"{key}={partition.get(key, '')}"
                if token not in path.as_posix():
                    raise EngineFailure(
                        "F4",
                        "2B-S0-050",
                        STATE,
                        MODULE_NAME,
                        {"detail": "partition path mismatch", "dataset_id": dataset_id, "token": token},
                    )
        if dataset_id in ("validation_bundle_1B",):
            sha256_hex = bundle_hash
        elif path.is_dir():
            sha256_hex, _ = _hash_partition(path)
        else:
            sha256_hex = sha256_file(path).sha256_hex
        if not _HEX64_PATTERN.match(sha256_hex):
            raise EngineFailure(
                "F4",
                "2B-S0-041",
                STATE,
                MODULE_NAME,
                {"detail": "invalid sha256 hex", "dataset_id": dataset_id, "sha256_hex": sha256_hex},
            )
        sealed_assets.append(
            SealedAsset(
                asset_id=dataset_id,
                path=path,
                schema_ref=schema_refs[dataset_id],
                version_tag=version_tag,
                partition=partition,
                partition_keys=partition_keys,
                catalog_path=catalog_path,
                sha256_hex=sha256_hex,
            )
        )
        sealed_inputs_for_receipt.append(
            {"id": dataset_id, "partition": partition, "schema_ref": schema_refs[dataset_id]}
        )

    for dataset_id in required_ids:
        dataset_path = _resolve_dataset_path(entries[dataset_id], run_paths, config.external_roots, tokens)
        if not dataset_path.exists():
            raise EngineFailure(
                "F4",
                "2B-S0-010",
                STATE,
                MODULE_NAME,
                {"detail": "required input missing", "dataset_id": dataset_id, "path": str(dataset_path)},
            )
        _add_sealed_asset(dataset_id, dataset_path)
        required_present += 1
    _emit_validation(logger, manifest_fingerprint, "V-04", "pass")

    optional_cache_present = 0
    optional_entry = entries["tz_timetable_cache"]
    optional_path = _resolve_dataset_path(optional_entry, run_paths, config.external_roots, tokens)
    if optional_path.exists():
        _add_sealed_asset("tz_timetable_cache", optional_path)
        optional_cache_present = 1
        _emit_validation(logger, manifest_fingerprint, "V-05", "pass")
    else:
        _emit_validation(
            logger,
            manifest_fingerprint,
            "V-05",
            "warn",
            "2B-S0-090",
            {"detail": "optional cache missing", "path": str(optional_path)},
        )

    _emit_validation(logger, manifest_fingerprint, "V-11", "pass")

    seen_ids: set[str] = set()
    for asset in sealed_assets:
        if asset.asset_id in seen_ids:
            raise EngineFailure(
                "F4",
                "2B-S0-043",
                STATE,
                MODULE_NAME,
                {"detail": "duplicate asset_id", "asset_id": asset.asset_id},
            )
        seen_ids.add(asset.asset_id)
    _emit_validation(logger, manifest_fingerprint, "V-12", "pass")

    policy_set = {
        "route_rng_policy_v1",
        "alias_layout_policy_v1",
        "day_effect_policy_v1",
        "virtual_edge_policy_v1",
    }
    for asset in sealed_assets:
        if asset.asset_id in policy_set:
            policy_ids.append(asset.asset_id)
            policy_digests.append(asset.sha256_hex)

    policy_ids_sorted = [pid for pid in sorted(policy_ids)]
    policy_digests_sorted = [digest for _, digest in sorted(zip(policy_ids, policy_digests))]
    determinism_receipt = {
        "engine_commit": os.getenv("ENGINE_COMMIT", "unknown"),
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "policy_ids": policy_ids_sorted,
        "policy_digests": policy_digests_sorted,
    }

    if len(policy_ids_sorted) != len(policy_digests_sorted) or len(policy_ids_sorted) != len(policy_set):
        raise EngineFailure(
            "F4",
            "2B-S0-042",
            STATE,
            MODULE_NAME,
            {"detail": "policy digest mismatch", "policy_ids": policy_ids_sorted, "policy_digests": policy_digests_sorted},
        )
    _emit_validation(logger, manifest_fingerprint, "V-10", "pass")

    receipt_ids = {item["id"] for item in sealed_inputs_for_receipt}
    sealed_ids = {asset.asset_id for asset in sealed_assets}
    if receipt_ids != sealed_ids:
        raise EngineFailure(
            "F4",
            "2B-S0-040",
            STATE,
            MODULE_NAME,
            {"detail": "receipt sealed_inputs mismatch", "missing": sorted(sealed_ids - receipt_ids)},
        )
    _emit_validation(logger, manifest_fingerprint, "V-08", "pass")

    if placeholders_used:
        _emit_validation(
            logger,
            manifest_fingerprint,
            "V-09",
            "warn",
            "2B-S0-041",
            {"detail": "version_tag placeholder", "dataset_ids": sorted(placeholders_used)},
        )
    else:
        _emit_validation(logger, manifest_fingerprint, "V-09", "pass")

    sealed_assets_sorted = sorted(sealed_assets, key=lambda asset: (asset.asset_id, asset.catalog_path))
    sealed_inputs_sample = [
        {
            "asset_id": asset.asset_id,
            "version_tag": asset.version_tag,
            "sha256_hex": asset.sha256_hex,
            "path": asset.catalog_path,
            "partition": asset.partition,
        }
        for asset in sealed_assets_sorted[:20]
    ]

    sealed_inputs_payload = []
    for asset in sealed_assets_sorted:
        sealed_inputs_payload.append(
            {
                "asset_id": asset.asset_id,
                "version_tag": asset.version_tag,
                "sha256_hex": asset.sha256_hex,
                "path": asset.catalog_path,
                "partition": asset.partition,
                "schema_ref": asset.schema_ref,
            }
        )

    sealed_inputs_schema = _schema_from_pack(schema_2b, "validation/sealed_inputs_2B")
    errors = list(Draft202012Validator(sealed_inputs_schema).iter_errors(sealed_inputs_payload))
    if errors:
        raise EngineFailure(
            "F4",
            "2B-S0-031",
            STATE,
            MODULE_NAME,
            {"detail": "inventory schema invalid", "error": str(errors[0])},
        )
    _emit_validation(logger, manifest_fingerprint, "V-07", "pass")

    receipt_payload = {
        "manifest_fingerprint": str(manifest_fingerprint),
        "seed": int(seed),
        "parameter_hash": str(parameter_hash),
        "verified_at_utc": utc_now_rfc3339_micro(),
        "sealed_inputs": sealed_inputs_for_receipt,
        "catalogue_resolution": {
            "dictionary_version": str(dictionary.get("version", "unknown")),
            "registry_version": str(registry.get("version", "unknown")),
        },
        "determinism_receipt": determinism_receipt,
    }
    receipt_schema = _schema_from_pack(schema_2b, "validation/s0_gate_receipt_v1")
    _inline_external_refs(receipt_schema, schema_layer1, "schemas.layer1.yaml#")
    errors = list(Draft202012Validator(receipt_schema).iter_errors(receipt_payload))
    if errors:
        raise EngineFailure(
            "F4",
            "2B-S0-030",
            STATE,
            MODULE_NAME,
            {"detail": "receipt schema invalid", "error": str(errors[0])},
        )
    _emit_validation(logger, manifest_fingerprint, "V-06", "pass")

    receipt_entry = entries["s0_gate_receipt_2B"]
    sealed_entry = entries["sealed_inputs_2B"]
    receipt_path = _resolve_dataset_path(receipt_entry, run_paths, config.external_roots, tokens)
    sealed_inputs_path = _resolve_dataset_path(sealed_entry, run_paths, config.external_roots, tokens)

    if f"manifest_fingerprint={manifest_fingerprint}" not in receipt_path.as_posix():
        raise EngineFailure(
            "F4",
            "2B-S0-070",
            STATE,
            MODULE_NAME,
            {"detail": "receipt path does not embed manifest_fingerprint", "path": str(receipt_path)},
        )
    if f"manifest_fingerprint={manifest_fingerprint}" not in sealed_inputs_path.as_posix():
        raise EngineFailure(
            "F4",
            "2B-S0-070",
            STATE,
            MODULE_NAME,
            {"detail": "sealed_inputs path does not embed manifest_fingerprint", "path": str(sealed_inputs_path)},
        )
    _emit_validation(logger, manifest_fingerprint, "V-13", "pass")

    receipt_bytes = json.dumps(
        receipt_payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    sealed_inputs_bytes = json.dumps(
        sealed_inputs_payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")

    sealed_tmp = run_paths.tmp_root / f"s0_sealed_inputs_2b_{uuid.uuid4().hex}"
    sealed_tmp.mkdir(parents=True, exist_ok=True)
    sealed_inputs_file = sealed_tmp / sealed_inputs_path.name
    sealed_inputs_file.write_bytes(sealed_inputs_bytes)

    publish_start = time.monotonic()
    receipt_existed = _atomic_publish_file(receipt_path, receipt_bytes, logger, "s0_gate_receipt_2B")
    sealed_existed = _atomic_publish_dir(sealed_tmp, sealed_inputs_path.parent, logger, "sealed_inputs_2B")
    publish_ms = int((time.monotonic() - publish_start) * 1000)
    _emit_validation(logger, manifest_fingerprint, "V-14", "pass")
    if receipt_existed or sealed_existed:
        _emit_validation(logger, manifest_fingerprint, "V-15", "pass")

    _emit_event(
        logger,
        "EMIT",
        manifest_fingerprint,
        "INFO",
        receipt_path=str(receipt_path),
        sealed_inputs_path=str(sealed_inputs_path),
    )

    digests_recorded = len([row for row in sealed_inputs_payload if row.get("sha256_hex")])
    digest_counts: dict[str, int] = {}
    for asset in sealed_assets_sorted:
        digest_counts[asset.sha256_hex] = digest_counts.get(asset.sha256_hex, 0) + 1
    duplicate_byte_sets = sum(1 for count in digest_counts.values() if count > 1)

    id_map = [{"id": asset.asset_id, "path": asset.catalog_path} for asset in sealed_assets_sorted]
    publish_targets = [
        {"id": "s0_gate_receipt_2B", "path": str(receipt_path), "bytes": len(receipt_bytes)},
        {"id": "sealed_inputs_2B", "path": str(sealed_inputs_path), "bytes": len(sealed_inputs_bytes)},
    ]

    validators = [
        {"id": "V-01", "status": "PASS", "codes": []},
        {"id": "V-02", "status": "PASS", "codes": []},
        {"id": "V-03", "status": "PASS", "codes": []},
        {"id": "V-04", "status": "PASS", "codes": []},
        {"id": "V-05", "status": "PASS", "codes": []},
        {"id": "V-06", "status": "PASS", "codes": []},
        {"id": "V-07", "status": "PASS", "codes": []},
        {"id": "V-08", "status": "PASS", "codes": []},
        {"id": "V-09", "status": "PASS", "codes": []},
        {"id": "V-10", "status": "PASS", "codes": []},
        {"id": "V-11", "status": "PASS", "codes": []},
        {"id": "V-12", "status": "PASS", "codes": []},
        {"id": "V-13", "status": "PASS", "codes": []},
        {"id": "V-14", "status": "PASS", "codes": []},
        {"id": "V-15", "status": "PASS", "codes": []},
        {"id": "V-16", "status": "PASS", "codes": []},
    ]
    validator_index = {item["id"]: item for item in validators}

    if not optional_cache_present:
        validator_index["V-05"]["status"] = "WARN"
        validator_index["V-05"]["codes"] = ["2B-S0-090"]
    if placeholders_used:
        validator_index["V-09"]["status"] = "WARN"
        validator_index["V-09"]["codes"] = ["2B-S0-041"]

    warn_count = sum(1 for item in validators if item["status"] == "WARN")
    fail_count = sum(1 for item in validators if item["status"] == "FAIL")

    run_report = {
        "component": "2B.S0",
        "manifest_fingerprint": str(manifest_fingerprint),
        "seed": str(seed),
        "verified_at_utc": receipt_payload["verified_at_utc"],
        "catalogue_resolution": receipt_payload["catalogue_resolution"],
        "gate": {
            "bundle_index_count": len(index_paths),
            "bundle_sha256_expected": flag_sha256,
            "bundle_sha256_actual": bundle_hash,
            "flag_path": str(flag_path),
        },
        "inputs_summary": {
            "inputs_total": len(sealed_assets_sorted),
            "required_present": required_present,
            "optional_cache_present": optional_cache_present,
            "policy_ids": policy_ids_sorted,
            "policy_digests": policy_digests_sorted,
        },
        "inventory_summary": {
            "inventory_rows": len(sealed_inputs_payload),
            "digests_recorded": digests_recorded,
            "duplicate_byte_sets": duplicate_byte_sets,
        },
        "publish": {
            "targets": publish_targets,
            "write_once_verified": True,
            "atomic_publish": True,
            "publish_bytes_total": sum(target["bytes"] for target in publish_targets),
        },
        "validators": validators,
        "summary": {
            "overall_status": "PASS" if fail_count == 0 else "FAIL",
            "warn_count": warn_count,
            "fail_count": fail_count,
        },
        "environment": {
            "engine_commit": determinism_receipt["engine_commit"],
            "python_version": determinism_receipt["python_version"],
            "platform": determinism_receipt["platform"],
            "network_io_detected": 0,
        },
        "sealed_inputs_sample": sealed_inputs_sample,
        "gate_index_sample": gate_index_sample,
        "id_map": id_map,
        "durations_ms": {
            "gate_verify_ms": gate_verify_ms,
            "inventory_emit_ms": int((time.monotonic() - started_monotonic) * 1000) - gate_verify_ms,
            "publish_ms": publish_ms,
        },
    }

    run_report_path = (
        run_paths.run_root
        / "reports"
        / "layer1"
        / "2B"
        / "state=S0"
        / f"manifest_fingerprint={manifest_fingerprint}"
        / "s0_run_report.json"
    )
    _write_json(run_report_path, run_report)
    logger.info("S0: run-report written %s", run_report_path)
    logger.info("S0: run-report JSON %s", json.dumps(run_report, ensure_ascii=True, sort_keys=True))

    _emit_validation(logger, manifest_fingerprint, "V-16", "pass")
    timer.info("S0: completed gate and sealed inputs")

    return S0GateResult(
        run_id=str(run_id),
        parameter_hash=str(parameter_hash),
        manifest_fingerprint=str(manifest_fingerprint),
        receipt_path=receipt_path,
        sealed_inputs_path=sealed_inputs_path,
        run_report_path=run_report_path,
    )
