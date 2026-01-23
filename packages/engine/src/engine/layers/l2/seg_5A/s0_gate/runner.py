"""S0 gate-in runner for Segment 5A."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import polars as pl
import yaml
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
from engine.core.run_receipt import pick_latest_run_receipt


MODULE_NAME = "5A.s0_gate"
SEGMENT = "5A"
STATE = "S0"
_FLAG_PATTERN = re.compile(r"^sha256_hex = ([a-f0-9]{64})\s*$")
_HEX64_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_PLACEHOLDER_MARKERS = {"TBD", "null", "unknown", ""}


@dataclass(frozen=True)
class S0GateResult:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    receipt_path: Path
    sealed_inputs_path: Path
    scenario_manifest_path: Optional[Path]


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


def _emit_event(logger, event: str, manifest_fingerprint: Optional[str], severity: str, **fields: object) -> None:
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
    payload = {"validator_id": validator_id, "result": result}
    if error_code:
        payload["error_code"] = error_code
    if detail is not None:
        payload["detail"] = detail
    _emit_event(logger, "VALIDATION", manifest_fingerprint, severity, **payload)


def _abort(code: str, validator_id: str, message: str, context: dict, manifest_fingerprint: Optional[str]) -> None:
    logger = get_logger("engine.layers.l2.seg_5A.s0_gate.runner")
    _emit_validation(logger, manifest_fingerprint, validator_id, "fail", code, context)
    raise EngineFailure("F4", code, STATE, MODULE_NAME, context)


def _load_json(path: Path) -> object:
    if not path.exists():
        raise InputResolutionError(f"Missing JSON file: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise InputResolutionError(f"Invalid JSON at {path}: {exc}") from exc


def _load_yaml(path: Path) -> object:
    if not path.exists():
        raise InputResolutionError(f"Missing YAML file: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _schema_from_pack(schema_pack: dict, path: str) -> dict:
    node: dict = schema_pack
    for part in path.split("/"):
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
                unevaluated = subschema["unevaluatedProperties"]
            subschema.pop("unevaluatedProperties", None)
    if unevaluated is not None and "unevaluatedProperties" not in schema:
        schema["unevaluatedProperties"] = unevaluated
    return normalize_nullable_schema(schema)


def _schema_anchor_exists(schema_pack: dict, ref: str) -> None:
    if "#/" not in ref:
        raise ContractError(f"Invalid schema_ref (missing anchor): {ref}")
    path = ref.split("#", 1)[1]
    node: dict = schema_pack
    for part in path.strip("/").split("/"):
        if part not in node:
            raise ContractError(f"Schema section not found: {ref}")
        node = node[part]


def _validate_schema_ref(
    schema_ref: str | None,
    schema_5a: dict,
    schema_layer2: dict,
    schema_ingress_layer2: dict,
    schema_3b: dict,
    schema_3a: dict,
    schema_2b: dict,
    schema_2a: dict,
    schema_1b: dict,
    schema_1a: dict,
    schema_layer1: dict,
    schema_ingress_layer1: dict,
) -> str:
    if not schema_ref:
        raise ContractError("Missing schema_ref.")
    if schema_ref.startswith("schemas.5A.yaml#"):
        _schema_anchor_exists(schema_5a, schema_ref)
    elif schema_ref.startswith("schemas.layer2.yaml#"):
        _schema_anchor_exists(schema_layer2, schema_ref)
    elif schema_ref.startswith("schemas.ingress.layer2.yaml#"):
        _schema_anchor_exists(schema_ingress_layer2, schema_ref)
    elif schema_ref.startswith("schemas.3B.yaml#"):
        _schema_anchor_exists(schema_3b, schema_ref)
    elif schema_ref.startswith("schemas.3A.yaml#"):
        _schema_anchor_exists(schema_3a, schema_ref)
    elif schema_ref.startswith("schemas.2B.yaml#"):
        _schema_anchor_exists(schema_2b, schema_ref)
    elif schema_ref.startswith("schemas.2A.yaml#"):
        _schema_anchor_exists(schema_2a, schema_ref)
    elif schema_ref.startswith("schemas.1B.yaml#"):
        _schema_anchor_exists(schema_1b, schema_ref)
    elif schema_ref.startswith("schemas.1A.yaml#"):
        _schema_anchor_exists(schema_1a, schema_ref)
    elif schema_ref.startswith("schemas.layer1.yaml#"):
        _schema_anchor_exists(schema_layer1, schema_ref)
    elif schema_ref.startswith("schemas.ingress.layer1.yaml#"):
        _schema_anchor_exists(schema_ingress_layer1, schema_ref)
    else:
        raise ContractError(f"Unknown schema ref: {schema_ref}")
    return schema_ref


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


def _is_placeholder(value: Optional[str]) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    if not text:
        return True
    if text in _PLACEHOLDER_MARKERS:
        return True
    if "{" in text or "}" in text:
        return True
    return False


def _normalize_semver(value: Optional[str]) -> str:
    text = str(value or "").strip()
    if text.lower().startswith("v") and len(text) > 1:
        return text[1:]
    return text


def _policy_version_from_payload(payload: object) -> Optional[str]:
    if not isinstance(payload, dict):
        return None
    for key in ("version", "policy_version", "prior_pack_version", "version_tag"):
        if key in payload and payload[key] is not None:
            return str(payload[key])
    return None


def _parse_pass_flag(path: Path) -> str:
    if not path.exists():
        raise InputResolutionError(f"Missing PASS flag: {path}")
    content = path.read_text(encoding="utf-8").strip()
    line = content.splitlines()[0] if content else ""
    match = _FLAG_PATTERN.match(line)
    if not match:
        raise EngineFailure(
            "F4",
            "S0_IO_READ_FAILED",
            STATE,
            MODULE_NAME,
            {"detail": "invalid _passed.flag format", "path": str(path)},
        )
    return match.group(1)


def _hash_partition(root: Path, logger, label: str) -> tuple[str, int]:
    files = sorted(
        [path for path in root.rglob("*") if path.is_file()],
        key=lambda path: path.relative_to(root).as_posix(),
    )
    if not files:
        raise HashingError(f"No files found under dataset path: {root}")
    total_bytes = sum(path.stat().st_size for path in files)
    tracker = _ProgressTracker(total_bytes, logger, label)
    hasher = hashlib.sha256()
    processed = 0
    for path in files:
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                processed += len(chunk)
                hasher.update(chunk)
                tracker.update(len(chunk))
    return hasher.hexdigest(), processed


def _hash_file_with_progress(path: Path, logger, label: str) -> tuple[str, int]:
    total_bytes = path.stat().st_size
    tracker = _ProgressTracker(total_bytes, logger, label)
    hasher = hashlib.sha256()
    processed = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            processed += len(chunk)
            hasher.update(chunk)
            tracker.update(len(chunk))
    return hasher.hexdigest(), processed


def _bundle_hash(bundle_root: Path, index_entries: list[dict]) -> tuple[str, int]:
    paths = sorted(entry["path"] for entry in index_entries if entry.get("path"))
    hasher = hashlib.sha256()
    total_bytes = 0
    for path in paths:
        file_path = bundle_root / path
        if not file_path.exists():
            raise EngineFailure(
                "F4",
                "S0_IO_READ_FAILED",
                STATE,
                MODULE_NAME,
                {"detail": f"bundle file missing: {path}", "bundle_root": str(bundle_root)},
            )
        with file_path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                total_bytes += len(chunk)
                hasher.update(chunk)
    return hasher.hexdigest(), total_bytes


def _bundle_hash_from_index(run_root: Path, index_entries: list[dict]) -> tuple[str, int]:
    paths = sorted(entry["path"] for entry in index_entries if entry.get("path"))
    hasher = hashlib.sha256()
    total_bytes = 0
    for rel_path in paths:
        file_path = run_root / rel_path
        if not file_path.exists():
            raise EngineFailure(
                "F4",
                "S0_IO_READ_FAILED",
                STATE,
                MODULE_NAME,
                {"detail": f"bundle file missing: {rel_path}", "run_root": str(run_root)},
            )
        with file_path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                total_bytes += len(chunk)
                hasher.update(chunk)
    return hasher.hexdigest(), total_bytes


def _sha256_concat_hex(parts: Iterable[str]) -> str:
    hasher = hashlib.sha256()
    for part in parts:
        hasher.update(part.encode("ascii"))
    return hasher.hexdigest()


def _bundle_digest_from_members(
    index_payload: dict,
    schema_layer1: dict,
    logger,
    manifest_fingerprint: str,
    index_path: Path,
) -> str:
    schema = _schema_from_pack(schema_layer1, "validation/validation_bundle_index_3A")
    _inline_external_refs(schema, schema_layer1, "schemas.layer1.yaml#")
    errors = list(Draft202012Validator(schema).iter_errors(index_payload))
    if errors:
        raise EngineFailure(
            "F4",
            "S0_IO_READ_FAILED",
            STATE,
            MODULE_NAME,
            {"detail": str(errors[0]), "path": str(index_path)},
        )
    members = index_payload.get("members")
    if not isinstance(members, list) or not members:
        raise EngineFailure(
            "F4",
            "S0_IO_READ_FAILED",
            STATE,
            MODULE_NAME,
            {"detail": "bundle index missing members", "path": str(index_path)},
        )
    for member in members:
        sha256_hex = member.get("sha256_hex") if isinstance(member, dict) else None
        if not isinstance(sha256_hex, str) or not _HEX64_PATTERN.match(sha256_hex):
            raise EngineFailure(
                "F4",
                "S0_IO_READ_FAILED",
                STATE,
                MODULE_NAME,
                {"detail": "member sha256_hex invalid", "path": str(index_path)},
            )
    members_sorted = sorted(members, key=lambda item: str(item.get("logical_id", "")))
    digest = _sha256_concat_hex([member["sha256_hex"] for member in members_sorted])
    logger.info(
        "S0: 3A bundle index validated (members=%d) for manifest_fingerprint=%s",
        len(members_sorted),
        manifest_fingerprint,
    )
    return digest


def _bundle_digest_from_member_files(
    bundle_root: Path,
    index_payload: dict,
    schema_layer1: dict,
    logger,
    manifest_fingerprint: str,
    index_path: Path,
) -> str:
    schema = _schema_from_pack(schema_layer1, "validation/validation_bundle_index_3B")
    _inline_external_refs(schema, schema_layer1, "schemas.layer1.yaml#")
    errors = list(Draft202012Validator(schema).iter_errors(index_payload))
    if errors:
        raise EngineFailure(
            "F4",
            "S0_IO_READ_FAILED",
            STATE,
            MODULE_NAME,
            {"detail": str(errors[0]), "path": str(index_path)},
        )
    members = index_payload.get("members")
    if not isinstance(members, list) or not members:
        raise EngineFailure(
            "F4",
            "S0_IO_READ_FAILED",
            STATE,
            MODULE_NAME,
            {"detail": "bundle index missing members", "path": str(index_path)},
        )
    _validate_index_entries(members, index_path)
    bundle_digest, _ = _bundle_hash(bundle_root, members)
    logger.info(
        "S0: 3B bundle index validated (members=%d) for manifest_fingerprint=%s",
        len(members),
        manifest_fingerprint,
    )
    return bundle_digest


def _validate_index_entries(index_entries: list[dict], index_path: Path) -> list[str]:
    paths = []
    for entry in index_entries:
        path = entry.get("path")
        if not isinstance(path, str) or not path:
            raise EngineFailure(
                "F4",
                "S0_IO_READ_FAILED",
                STATE,
                MODULE_NAME,
                {"detail": "index entry missing path", "path": str(index_path)},
            )
        try:
            path.encode("ascii")
        except UnicodeEncodeError as exc:
            raise EngineFailure(
                "F4",
                "S0_IO_READ_FAILED",
                STATE,
                MODULE_NAME,
                {"detail": f"non-ascii path: {path}", "path": str(index_path)},
            ) from exc
        if "\\" in path or path.startswith(("/", "\\")) or ".." in Path(path).parts or ":" in path:
            raise EngineFailure(
                "F4",
                "S0_IO_READ_FAILED",
                STATE,
                MODULE_NAME,
                {"detail": f"invalid index path: {path}", "path": str(index_path)},
            )
        paths.append(path)
    if len(set(paths)) != len(paths):
        raise EngineFailure(
            "F4",
            "S0_IO_READ_FAILED",
            STATE,
            MODULE_NAME,
            {"detail": "duplicate path entries in index.json", "path": str(index_path)},
        )
    return paths


def _validate_index(
    bundle_root: Path,
    index_path: Path,
    schema_pack: dict,
    schema_anchor: str,
    schema_layer1: dict,
    logger,
    manifest_fingerprint: str,
) -> list[dict]:
    payload = _load_json(index_path)
    entries: list[dict]
    if isinstance(payload, list):
        pack, table_name = _table_pack(schema_pack, schema_anchor)
        try:
            validate_dataframe(payload, pack, table_name)
        except SchemaValidationError as exc:
            detail = exc.errors[0] if exc.errors else {}
            raise EngineFailure(
                "F4",
                "S0_IO_READ_FAILED",
                STATE,
                MODULE_NAME,
                {"detail": detail, "path": str(index_path)},
            ) from exc
        entries = payload
    elif isinstance(payload, dict) and isinstance(payload.get("files"), list):
        schema = _schema_from_pack(schema_pack, schema_anchor)
        _inline_external_refs(schema, schema_layer1, "schemas.layer1.yaml#")
        errors = list(Draft202012Validator(schema).iter_errors(payload))
        if errors:
            raise EngineFailure(
                "F4",
                "S0_IO_READ_FAILED",
                STATE,
                MODULE_NAME,
                {"detail": str(errors[0]), "path": str(index_path)},
            )
        entries = list(payload.get("files", []))
    else:
        raise EngineFailure(
            "F4",
            "S0_IO_READ_FAILED",
            STATE,
            MODULE_NAME,
            {"detail": "index.json has unsupported shape", "path": str(index_path)},
        )

    paths = _validate_index_entries(entries, index_path)
    bundle_files = [
        path
        for path in bundle_root.rglob("*")
        if path.is_file() and path.name != "_passed.flag"
    ]
    bundle_rel = {path.relative_to(bundle_root).as_posix() for path in bundle_files}
    index_paths = set(paths)
    if "index.json" not in index_paths:
        bundle_rel.discard("index.json")
    missing = sorted(bundle_rel - index_paths)
    extra = sorted(index_paths - bundle_rel)
    if missing or extra:
        raise EngineFailure(
            "F4",
            "S0_IO_READ_FAILED",
            STATE,
            MODULE_NAME,
            {"detail": {"missing": missing, "extra": extra}, "path": str(index_path)},
        )
    logger.info(
        "S0: index.json validated (entries=%d, files=%d) for manifest_fingerprint=%s",
        len(paths),
        len(bundle_rel),
        manifest_fingerprint,
    )
    return entries


def _pick_latest_run_receipt(runs_root: Path) -> Path:
    return pick_latest_run_receipt(runs_root)


def _resolve_run_receipt(runs_root: Path, run_id: Optional[str]) -> tuple[Path, dict]:
    if run_id:
        receipt_path = runs_root / run_id / "run_receipt.json"
    else:
        receipt_path = _pick_latest_run_receipt(runs_root)
    receipt = _load_json(receipt_path)
    return receipt_path, receipt


def _resolve_merchant_ids_version(
    dictionary_1a: dict,
    schema_1a: dict,
    schema_layer1: dict,
    run_paths: RunPaths,
    external_roots: Iterable[Path],
    tokens: dict[str, str],
    manifest_fingerprint: str,
) -> str:
    entry = find_dataset_entry(dictionary_1a, "sealed_inputs_1A").entry
    sealed_path = _resolve_dataset_path(entry, run_paths, external_roots, tokens)
    payload = _load_json(sealed_path)
    schema = _schema_from_pack(schema_1a, "validation/sealed_inputs_1A")
    _inline_external_refs(schema, schema_layer1, "schemas.layer1.yaml#")
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    if errors:
        _abort(
            "S0_IO_READ_FAILED",
            "V-02A",
            "sealed_inputs_1a_schema_invalid",
            {"detail": str(errors[0]), "path": str(sealed_path)},
            manifest_fingerprint,
        )
    if not isinstance(payload, list):
        _abort(
            "S0_IO_READ_FAILED",
            "V-02A",
            "sealed_inputs_1a_invalid",
            {"detail": "sealed_inputs_1A payload is not a list", "path": str(sealed_path)},
            manifest_fingerprint,
        )
    for row in payload:
        if not isinstance(row, dict):
            continue
        if row.get("asset_id") != "transaction_schema_merchant_ids":
            continue
        partition = row.get("partition") if isinstance(row.get("partition"), dict) else {}
        version = partition.get("version")
        if version:
            return str(version)
    _abort(
        "S0_IO_READ_FAILED",
        "V-02A",
        "merchant_ids_version_missing",
        {"detail": "transaction_schema_merchant_ids version missing from sealed_inputs_1A"},
        manifest_fingerprint,
    )
    return "unknown"


def _resolve_dataset_path(
    entry: dict,
    run_paths: RunPaths,
    external_roots: Iterable[Path],
    tokens: dict[str, str],
) -> Path:
    path_template = entry.get("path")
    if not path_template:
        raise InputResolutionError("Dataset entry missing path.")
    resolved = str(path_template).strip()
    for key, value in tokens.items():
        resolved = resolved.replace(f"{{{key}}}", value)
    if resolved.startswith(("data/", "logs/", "reports/")):
        return run_paths.run_root / resolved
    if resolved.startswith("artefacts/"):
        return resolve_input_path(resolved, run_paths, external_roots, allow_run_local=False)
    return resolve_input_path(resolved, run_paths, external_roots, allow_run_local=True)


def _render_catalog_path(entry: dict, tokens: dict[str, str]) -> str:
    path_template = entry.get("path") or ""
    rendered = str(path_template).strip()
    for key, value in tokens.items():
        rendered = rendered.replace(f"{{{key}}}", value)
    return rendered


def _render_version(entry: dict, tokens: dict[str, str], registry_entry: dict) -> str:
    version = str(entry.get("version") or "")
    for key, value in tokens.items():
        version = version.replace(f"{{{key}}}", value)
    if _is_placeholder(version):
        version = str(registry_entry.get("semver") or "unknown")
        for key, value in tokens.items():
            version = version.replace(f"{{{key}}}", value)
    return version


def _maybe_catalogue_mismatch(entry: dict, upstream_entry: dict, fields: Iterable[str]) -> list[tuple[str, str, str]]:
    mismatches = []
    for field in fields:
        left = str(entry.get(field) or "")
        right = str(upstream_entry.get(field) or "")
        if left != right:
            mismatches.append((field, left, right))
    return mismatches


def _check_catalogue_consistency(
    dictionary_5a: dict,
    upstream_dicts: dict[str, dict],
    logger,
    manifest_fingerprint: str,
) -> None:
    allowed = {
        ("validation_bundle_2B", "path"),
        ("validation_bundle_2B", "schema_ref"),
    }
    checked = 0
    for section, items in dictionary_5a.items():
        if not isinstance(items, list):
            continue
        for entry in items:
            if not isinstance(entry, dict):
                continue
            dataset_id = entry.get("id")
            owner = entry.get("owner_subsegment")
            if not dataset_id or owner not in upstream_dicts:
                continue
            try:
                upstream_entry = find_dataset_entry(upstream_dicts[owner], dataset_id).entry
            except ContractError:
                _abort(
                    "S0_CONTRACT_RESOLUTION_FAILED",
                    "V-02",
                    "upstream_dataset_missing",
                    {"dataset_id": dataset_id, "owner": owner},
                    manifest_fingerprint,
                )
            mismatches = _maybe_catalogue_mismatch(entry, upstream_entry, ("path", "schema_ref"))
            for field, left, right in mismatches:
                if (dataset_id, field) in allowed:
                    logger.warning(
                        "S0: catalogue deviation approved (dataset_id=%s field=%s 5A=%s upstream=%s)",
                        dataset_id,
                        field,
                        left,
                        right,
                    )
                    continue
                _abort(
                    "S0_CONTRACT_RESOLUTION_FAILED",
                    "V-02",
                    "catalogue_mismatch",
                    {"dataset_id": dataset_id, "field": field, "5A": left, "upstream": right},
                    manifest_fingerprint,
                )
            checked += 1
    logger.info("S0: catalogue cross-checks passed for %d dataset IDs", checked)


def _validate_payload(
    schema_pack: dict,
    schema_layer1: dict,
    schema_layer2: dict,
    schema_ingress_layer2: dict,
    anchor: str,
    payload: object,
    manifest_fingerprint: str,
    context: dict,
) -> None:
    schema = _schema_from_pack(schema_pack, anchor)
    _inline_external_refs(schema, schema_layer1, "schemas.layer1.yaml#")
    _inline_external_refs(schema, schema_layer2, "schemas.layer2.yaml#")
    _inline_external_refs(schema, schema_ingress_layer2, "schemas.ingress.layer2.yaml#")
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    if errors:
        raise EngineFailure(
            "F4",
            "S0_SEALED_INPUT_SCHEMA_MISMATCH",
            STATE,
            MODULE_NAME,
            {"detail": str(errors[0]), "context": context},
        )


def _role_for_dataset(dataset_id: str) -> str:
    if dataset_id.startswith("validation_bundle_"):
        return "validation_bundle"
    if dataset_id.startswith("validation_passed_flag_"):
        return "validation_flag"
    if dataset_id in {
        "merchant_class_policy_5A",
        "demand_scale_policy_5A",
        "baseline_intensity_policy_5A",
        "shape_library_5A",
        "shape_time_grid_policy_5A",
        "zone_shape_modifiers_5A",
        "scenario_overlay_policy_5A",
        "overlay_ordering_policy_5A",
        "scenario_overlay_validation_policy_5A",
        "validation_policy_5A",
        "spec_compatibility_config_5A",
    }:
        return "policy"
    if dataset_id in {"scenario_horizon_config_5A", "scenario_metadata", "scenario_calendar_5A"}:
        return "scenario_config"
    if dataset_id == "tz_timetable_cache":
        return "reference_data"
    return "upstream_egress"


def _read_scope_for_dataset(dataset_id: str) -> str:
    if dataset_id.startswith("validation_bundle_") or dataset_id.startswith("validation_passed_flag_"):
        return "METADATA_ONLY"
    if dataset_id in {
        "s2_alias_blob",
        "edge_alias_blob_3B",
        "edge_alias_index_3B",
        "s2_alias_index",
        "zone_alloc_universe_hash",
        "edge_universe_hash_3B",
        "virtual_settlement_3B",
        "tz_timetable_cache",
    }:
        return "METADATA_ONLY"
    if dataset_id in {
        "merchant_class_policy_5A",
        "demand_scale_policy_5A",
        "baseline_intensity_policy_5A",
        "shape_library_5A",
        "shape_time_grid_policy_5A",
        "zone_shape_modifiers_5A",
        "scenario_horizon_config_5A",
        "scenario_metadata",
        "scenario_overlay_policy_5A",
        "overlay_ordering_policy_5A",
        "scenario_overlay_validation_policy_5A",
        "validation_policy_5A",
        "spec_compatibility_config_5A",
    }:
        return "METADATA_ONLY"
    return "ROW_LEVEL"


def _owner_layer(owner_segment: str) -> str:
    if owner_segment in {"1A", "1B", "2A", "2B", "3A", "3B", "4A", "4B"}:
        return "layer1"
    if owner_segment in {"5A", "5B"}:
        return "layer2"
    if owner_segment in {"6A", "6B"}:
        return "layer3"
    return "engine"


def _hash_scenario_calendars(
    entry: dict,
    scenario_ids: list[str],
    run_paths: RunPaths,
    external_roots: Iterable[Path],
    tokens: dict[str, str],
    logger,
) -> tuple[str, int]:
    if not scenario_ids:
        raise EngineFailure(
            "F4",
            "S0_INTERNAL_INVARIANT_VIOLATION",
            STATE,
            MODULE_NAME,
            {"detail": "scenario_ids missing while hashing scenario_calendar_5A"},
        )
    resolved_paths: list[Path] = []
    for scenario_id in sorted(set(scenario_ids)):
        tokens_with_scenario = dict(tokens)
        tokens_with_scenario["scenario_id"] = scenario_id
        resolved = _resolve_dataset_path(entry, run_paths, external_roots, tokens_with_scenario)
        if not resolved.exists():
            raise EngineFailure(
                "F4",
                "S0_REQUIRED_SCENARIO_MISSING",
                STATE,
                MODULE_NAME,
                {"detail": "scenario_calendar_5A missing", "path": str(resolved), "scenario_id": scenario_id},
            )
        resolved_paths.append(resolved)
    total_bytes = sum(path.stat().st_size for path in resolved_paths)
    tracker = _ProgressTracker(total_bytes, logger, "S0: hash scenario_calendar_5A bytes")
    hasher = hashlib.sha256()
    processed = 0
    for path in resolved_paths:
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                processed += len(chunk)
                hasher.update(chunk)
                tracker.update(len(chunk))
    return hasher.hexdigest(), processed


def _hash_scenario_partitions(
    entry: dict,
    scenario_ids: list[str],
    run_paths: RunPaths,
    external_roots: Iterable[Path],
    tokens: dict[str, str],
    logger,
    label: str,
    required: bool,
    missing_code: str,
) -> Optional[tuple[str, int]]:
    if not scenario_ids:
        raise EngineFailure(
            "F4",
            "S0_INTERNAL_INVARIANT_VIOLATION",
            STATE,
            MODULE_NAME,
            {"detail": "scenario_ids missing while hashing scenario-scoped dataset"},
        )
    file_entries: list[tuple[str, str, Path]] = []
    for scenario_id in sorted(set(scenario_ids)):
        tokens_with_scenario = dict(tokens)
        tokens_with_scenario["scenario_id"] = scenario_id
        resolved = _resolve_dataset_path(entry, run_paths, external_roots, tokens_with_scenario)
        if not resolved.exists():
            if required:
                raise EngineFailure(
                    "F4",
                    missing_code,
                    STATE,
                    MODULE_NAME,
                    {"detail": "scenario partition missing", "path": str(resolved), "scenario_id": scenario_id},
                )
            return None
        if resolved.is_dir():
            files = sorted(
                [path for path in resolved.rglob("*") if path.is_file()],
                key=lambda path: path.relative_to(resolved).as_posix(),
            )
            if not files:
                raise HashingError(f"No files found under dataset path: {resolved}")
            for path in files:
                file_entries.append((scenario_id, path.relative_to(resolved).as_posix(), path))
        else:
            file_entries.append((scenario_id, resolved.name, resolved))
    total_bytes = sum(path.stat().st_size for _, _, path in file_entries)
    tracker = _ProgressTracker(total_bytes, logger, label)
    hasher = hashlib.sha256()
    processed = 0
    for _, _, path in sorted(file_entries):
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                processed += len(chunk)
                hasher.update(chunk)
                tracker.update(len(chunk))
    return hasher.hexdigest(), processed


def _sealed_inputs_digest(rows: list[dict]) -> str:
    ordered_fields = (
        "manifest_fingerprint",
        "parameter_hash",
        "owner_layer",
        "owner_segment",
        "artifact_id",
        "manifest_key",
        "role",
        "schema_ref",
        "path_template",
        "partition_keys",
        "sha256_hex",
        "version",
        "source_dictionary",
        "source_registry",
        "status",
        "read_scope",
    )
    hasher = hashlib.sha256()
    for row in rows:
        payload = {field: row.get(field) for field in ordered_fields}
        hasher.update(
            json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=False).encode("utf-8")
        )
    return hasher.hexdigest()


def _atomic_publish_json(path: Path, payload: object) -> None:
    payload_bytes = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    tmp_dir = path.parent / f"_tmp.{uuid.uuid4().hex}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / path.name
    tmp_path.write_bytes(payload_bytes)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        tmp_path.replace(path)
    except OSError as exc:
        raise EngineFailure(
            "F4",
            "S0_IO_WRITE_FAILED",
            STATE,
            MODULE_NAME,
            {"detail": "atomic publish failed", "path": str(path), "error": str(exc)},
        ) from exc
    try:
        tmp_dir.rmdir()
    except OSError:
        pass


def run_s0(config: EngineConfig, run_id: Optional[str] = None) -> S0GateResult:
    logger = get_logger("engine.layers.l2.seg_5A.s0_gate.runner")
    timer = _StepTimer(logger)
    started = time.monotonic()

    receipt_path, receipt = _resolve_run_receipt(config.runs_root, run_id)
    run_id_value = str(receipt.get("run_id") or "")
    if not run_id_value:
        _abort(
            "S0_RUN_CONTEXT_INVALID",
            "V-01",
            "run_receipt_missing_run_id",
            {"path": str(receipt_path)},
            None,
        )
    if receipt_path.parent.name != run_id_value:
        _abort(
            "S0_RUN_CONTEXT_INVALID",
            "V-01",
            "run_receipt_path_mismatch",
            {"path": str(receipt_path), "run_id": run_id_value},
            None,
        )

    seed = receipt.get("seed")
    parameter_hash = str(receipt.get("parameter_hash") or "")
    manifest_fingerprint = str(receipt.get("manifest_fingerprint") or "")
    if seed is None or not parameter_hash or not manifest_fingerprint:
        _abort(
            "S0_RUN_CONTEXT_INVALID",
            "V-01",
            "run_receipt_missing_fields",
            {"seed": seed, "parameter_hash": parameter_hash, "manifest_fingerprint": manifest_fingerprint},
            manifest_fingerprint or None,
        )
    if not _HEX64_PATTERN.match(parameter_hash) or not _HEX64_PATTERN.match(manifest_fingerprint):
        _abort(
            "S0_RUN_CONTEXT_INVALID",
            "V-01",
            "run_receipt_invalid_hashes",
            {"parameter_hash": parameter_hash, "manifest_fingerprint": manifest_fingerprint},
            manifest_fingerprint,
        )

    run_paths = RunPaths(config.runs_root, run_id_value)
    run_log_path = run_paths.run_root / f"run_log_{run_id_value}.log"
    add_file_handler(run_log_path)
    timer.info(f"S0: run log initialized at {run_log_path}")

    source = ContractSource(config.contracts_root, config.contracts_layout)
    try:
        dict_5a_path, dictionary_5a = load_dataset_dictionary(source, "5A")
        dict_3b_path, dictionary_3b = load_dataset_dictionary(source, "3B")
        dict_3a_path, dictionary_3a = load_dataset_dictionary(source, "3A")
        dict_2b_path, dictionary_2b = load_dataset_dictionary(source, "2B")
        dict_2a_path, dictionary_2a = load_dataset_dictionary(source, "2A")
        dict_1b_path, dictionary_1b = load_dataset_dictionary(source, "1B")
        dict_1a_path, dictionary_1a = load_dataset_dictionary(source, "1A")
        reg_5a_path, registry_5a = load_artefact_registry(source, "5A")
        schema_5a_path, schema_5a = load_schema_pack(source, "5A", "5A")
        schema_layer2_path, schema_layer2 = load_schema_pack(source, "5A", "layer2")
        schema_ingress_layer2_path, schema_ingress_layer2 = load_schema_pack(source, "5A", "ingress.layer2")
        schema_3b_path, schema_3b = load_schema_pack(source, "3B", "3B")
        schema_3a_path, schema_3a = load_schema_pack(source, "3A", "3A")
        schema_2b_path, schema_2b = load_schema_pack(source, "2B", "2B")
        schema_2a_path, schema_2a = load_schema_pack(source, "2A", "2A")
        schema_1b_path, schema_1b = load_schema_pack(source, "1B", "1B")
        schema_1a_path, schema_1a = load_schema_pack(source, "1A", "1A")
        schema_layer1_path, schema_layer1 = load_schema_pack(source, "1A", "layer1")
        schema_ingress_layer1_path, schema_ingress_layer1 = load_schema_pack(source, "1A", "ingress.layer1")
    except ContractError as exc:
        _abort(
            "S0_CONTRACT_RESOLUTION_FAILED",
            "V-01",
            "contract_load_failed",
            {"detail": str(exc)},
            manifest_fingerprint,
        )

    logger.info(
        "Contracts layout=%s root=%s dictionary=%s registry=%s schemas=%s,%s,%s",
        config.contracts_layout,
        str(config.contracts_root),
        str(dict_5a_path),
        str(reg_5a_path),
        str(schema_5a_path),
        str(schema_layer2_path),
        str(schema_layer1_path),
    )

    logger.info(
        "S0: objective=gate 1A-3B and seal inputs (L1 egress + 5A policies + scenarios) -> outputs (s0_gate_receipt_5A, sealed_inputs_5A, scenario_manifest_5A)"
    )

    tokens = {
        "seed": str(seed),
        "parameter_hash": parameter_hash,
        "manifest_fingerprint": manifest_fingerprint,
        "run_id": run_id_value,
    }

    merchant_version = _resolve_merchant_ids_version(
        dictionary_1a,
        schema_1a,
        schema_layer1,
        run_paths,
        config.external_roots,
        tokens,
        manifest_fingerprint,
    )
    tokens["version"] = merchant_version
    logger.info(
        "S0: resolved transaction_schema_merchant_ids version=%s from sealed_inputs_1A",
        merchant_version,
    )

    _check_catalogue_consistency(
        dictionary_5a,
        {
            "1A": dictionary_1a,
            "1B": dictionary_1b,
            "2A": dictionary_2a,
            "2B": dictionary_2b,
            "3A": dictionary_3a,
            "3B": dictionary_3b,
        },
        logger,
        manifest_fingerprint,
    )
    _emit_validation(logger, manifest_fingerprint, "V-02", "pass")

    upstream_gates: dict[str, dict] = {}
    bundle_digests: dict[str, str] = {}

    gate_map = {
        "1A": ("validation_bundle_1A", "validation_passed_flag_1A", schema_1a, "validation/validation_bundle_index_1A"),
        "1B": ("validation_bundle_1B", "validation_passed_flag_1B", schema_1b, "validation/validation_bundle_index_1B"),
        "2A": ("validation_bundle_2A", "validation_passed_flag_2A", schema_2a, "validation/validation_bundle_index_2A"),
    }

    for segment_id, (bundle_id, flag_id, schema_pack, index_anchor) in gate_map.items():
        bundle_entry = find_dataset_entry(dictionary_5a, bundle_id).entry
        flag_entry = find_dataset_entry(dictionary_5a, flag_id).entry
        bundle_root = _resolve_dataset_path(bundle_entry, run_paths, config.external_roots, tokens)
        flag_path = _resolve_dataset_path(flag_entry, run_paths, config.external_roots, tokens)
        if not bundle_root.exists():
            _abort(
                "S0_IO_READ_FAILED",
                "V-03",
                "validation_bundle_missing",
                {"bundle_id": bundle_id, "path": str(bundle_root)},
                manifest_fingerprint,
            )
        index_path = bundle_root / "index.json"
        index_entries = _validate_index(
            bundle_root,
            index_path,
            schema_pack,
            index_anchor,
            schema_layer1,
            logger,
            manifest_fingerprint,
        )
        bundle_digest, _ = _bundle_hash(bundle_root, index_entries)
        flag_digest = _parse_pass_flag(flag_path)
        if bundle_digest != flag_digest:
            _abort(
                "S0_IO_READ_FAILED",
                "V-03",
                "hashgate_mismatch",
                {"bundle_id": bundle_id, "expected": bundle_digest, "actual": flag_digest},
                manifest_fingerprint,
            )
        bundle_digests[bundle_id] = bundle_digest
        upstream_gates[segment_id] = {
            "status": "PASS",
            "bundle_id": bundle_id,
            "bundle_path": _render_catalog_path(bundle_entry, tokens),
            "bundle_sha256_hex": bundle_digest,
            "flag_sha256_hex": flag_digest,
        }
        logger.info(
            "S0: segment_%s gate verified (bundle=%s, digest=%s)",
            segment_id,
            bundle_root.as_posix(),
            bundle_digest,
        )

    bundle_entry = find_dataset_entry(dictionary_5a, "validation_bundle_3B").entry
    flag_entry = find_dataset_entry(dictionary_5a, "validation_passed_flag_3B").entry
    bundle_root = _resolve_dataset_path(bundle_entry, run_paths, config.external_roots, tokens)
    flag_path = _resolve_dataset_path(flag_entry, run_paths, config.external_roots, tokens)
    if not bundle_root.exists():
        _abort(
            "S0_IO_READ_FAILED",
            "V-03",
            "validation_bundle_missing",
            {"bundle_id": "validation_bundle_3B", "path": str(bundle_root)},
            manifest_fingerprint,
        )
    index_path = bundle_root / "index.json"
    index_payload = _load_json(index_path)
    bundle_digest = _bundle_digest_from_member_files(
        bundle_root,
        index_payload,
        schema_layer1,
        logger,
        manifest_fingerprint,
        index_path,
    )
    flag_digest = _parse_pass_flag(flag_path)
    if bundle_digest != flag_digest:
        _abort(
            "S0_IO_READ_FAILED",
            "V-03",
            "hashgate_mismatch",
            {"bundle_id": "validation_bundle_3B", "expected": bundle_digest, "actual": flag_digest},
            manifest_fingerprint,
        )
    bundle_digests["validation_bundle_3B"] = bundle_digest
    upstream_gates["3B"] = {
        "status": "PASS",
        "bundle_id": "validation_bundle_3B",
        "bundle_path": _render_catalog_path(bundle_entry, tokens),
        "bundle_sha256_hex": bundle_digest,
        "flag_sha256_hex": flag_digest,
    }
    logger.info(
        "S0: segment_3B gate verified (bundle=%s, digest=%s, law=members_bytes)",
        bundle_root.as_posix(),
        bundle_digest,
    )

    bundle_entry = find_dataset_entry(dictionary_5a, "validation_bundle_2B").entry
    flag_entry = find_dataset_entry(dictionary_5a, "validation_passed_flag_2B").entry
    index_path = _resolve_dataset_path(bundle_entry, run_paths, config.external_roots, tokens)
    flag_path = _resolve_dataset_path(flag_entry, run_paths, config.external_roots, tokens)
    if not index_path.exists():
        _abort(
            "S0_IO_READ_FAILED",
            "V-03",
            "validation_bundle_missing",
            {"bundle_id": "validation_bundle_2B", "path": str(index_path)},
            manifest_fingerprint,
        )
    index_payload = _load_json(index_path)
    schema = _schema_from_pack(schema_2b, "validation/validation_bundle_index_2B")
    _inline_external_refs(schema, schema_layer1, "schemas.layer1.yaml#")
    errors = list(Draft202012Validator(schema).iter_errors(index_payload))
    if errors:
        _abort(
            "S0_IO_READ_FAILED",
            "V-03",
            "validation_bundle_schema_invalid",
            {"detail": str(errors[0]), "path": str(index_path)},
            manifest_fingerprint,
        )
    if not isinstance(index_payload, list):
        _abort(
            "S0_IO_READ_FAILED",
            "V-03",
            "validation_bundle_shape_invalid",
            {"detail": "2B index.json is not a list", "path": str(index_path)},
            manifest_fingerprint,
        )
    _validate_index_entries(index_payload, index_path)
    bundle_digest, _ = _bundle_hash_from_index(run_paths.run_root, index_payload)
    flag_digest = _parse_pass_flag(flag_path)
    if bundle_digest != flag_digest:
        _abort(
            "S0_IO_READ_FAILED",
            "V-03",
            "hashgate_mismatch",
            {"bundle_id": "validation_bundle_2B", "expected": bundle_digest, "actual": flag_digest},
            manifest_fingerprint,
        )
    bundle_digests["validation_bundle_2B"] = bundle_digest
    upstream_gates["2B"] = {
        "status": "PASS",
        "bundle_id": "validation_bundle_2B",
        "bundle_path": _render_catalog_path(bundle_entry, tokens),
        "bundle_sha256_hex": bundle_digest,
        "flag_sha256_hex": flag_digest,
    }
    logger.info(
        "S0: segment_2B gate verified (bundle=%s, digest=%s, law=index_paths)",
        index_path.as_posix(),
        bundle_digest,
    )

    bundle_entry = find_dataset_entry(dictionary_5a, "validation_bundle_3A").entry
    flag_entry = find_dataset_entry(dictionary_5a, "validation_passed_flag_3A").entry
    bundle_root = _resolve_dataset_path(bundle_entry, run_paths, config.external_roots, tokens)
    flag_path = _resolve_dataset_path(flag_entry, run_paths, config.external_roots, tokens)
    if not bundle_root.exists():
        _abort(
            "S0_IO_READ_FAILED",
            "V-03",
            "validation_bundle_missing",
            {"bundle_id": "validation_bundle_3A", "path": str(bundle_root)},
            manifest_fingerprint,
        )
    index_path = bundle_root / "index.json"
    index_payload = _load_json(index_path)
    bundle_digest = _bundle_digest_from_members(index_payload, schema_layer1, logger, manifest_fingerprint, index_path)
    flag_digest = _parse_pass_flag(flag_path)
    if bundle_digest != flag_digest:
        _abort(
            "S0_IO_READ_FAILED",
            "V-03",
            "hashgate_mismatch",
            {"bundle_id": "validation_bundle_3A", "expected": bundle_digest, "actual": flag_digest},
            manifest_fingerprint,
        )
    bundle_digests["validation_bundle_3A"] = bundle_digest
    upstream_gates["3A"] = {
        "status": "PASS",
        "bundle_id": "validation_bundle_3A",
        "bundle_path": _render_catalog_path(bundle_entry, tokens),
        "bundle_sha256_hex": bundle_digest,
        "flag_sha256_hex": flag_digest,
    }
    logger.info(
        "S0: segment_3A gate verified (bundle=%s, digest=%s, law=index_only)",
        bundle_root.as_posix(),
        bundle_digest,
    )

    required_ids = [
        "validation_bundle_1A",
        "validation_passed_flag_1A",
        "validation_bundle_1B",
        "validation_passed_flag_1B",
        "validation_bundle_2A",
        "validation_passed_flag_2A",
        "validation_bundle_2B",
        "validation_passed_flag_2B",
        "validation_bundle_3A",
        "validation_passed_flag_3A",
        "validation_bundle_3B",
        "validation_passed_flag_3B",
        "transaction_schema_merchant_ids",
        "outlet_catalogue",
        "site_locations",
        "site_timezones",
        "s1_site_weights",
        "s2_alias_index",
        "s2_alias_blob",
        "s3_day_effects",
        "s4_group_weights",
        "zone_alloc",
        "zone_alloc_universe_hash",
        "virtual_classification_3B",
        "edge_catalogue_3B",
        "edge_alias_index_3B",
        "edge_alias_blob_3B",
        "edge_universe_hash_3B",
        "scenario_horizon_config_5A",
        "scenario_metadata",
        "scenario_calendar_5A",
        "merchant_class_policy_5A",
        "demand_scale_policy_5A",
        "baseline_intensity_policy_5A",
        "shape_library_5A",
        "shape_time_grid_policy_5A",
        "scenario_overlay_policy_5A",
    ]
    optional_ids = [
        "tz_timetable_cache",
        "virtual_settlement_3B",
        "zone_shape_modifiers_5A",
        "merchant_class_profile_5A",
        "class_shape_catalogue_5A",
        "class_zone_baseline_local_5A",
        "merchant_zone_baseline_utc_5A",
        "overlay_ordering_policy_5A",
        "scenario_overlay_validation_policy_5A",
        "validation_policy_5A",
        "spec_compatibility_config_5A",
    ]
    scenario_partitioned_ids = {
        "scenario_calendar_5A",
        "class_shape_catalogue_5A",
        "class_zone_baseline_local_5A",
        "merchant_zone_baseline_utc_5A",
    }
    required_input_ids = {
    }

    sealed_rows: list[dict] = []
    digest_map: dict[str, str] = {}
    sealed_optional_missing: list[str] = []
    scenario_config: Optional[dict] = None
    scenario_metadata: Optional[dict] = None
    scenario_ids: list[str] = []

    for dataset_id in required_ids + optional_ids:
        entry = find_dataset_entry(dictionary_5a, dataset_id).entry
        reg_entry = find_artifact_entry(registry_5a, dataset_id).entry
        try:
            schema_ref = _validate_schema_ref(
                entry.get("schema_ref"),
                schema_5a,
                schema_layer2,
                schema_ingress_layer2,
                schema_3b,
                schema_3a,
                schema_2b,
                schema_2a,
                schema_1b,
                schema_1a,
                schema_layer1,
                schema_ingress_layer1,
            )
        except ContractError as exc:
            _abort(
                "S0_SCHEMA_ANCHOR_INVALID",
                "V-04",
                "schema_ref_invalid",
                {"dataset_id": dataset_id, "detail": str(exc)},
                manifest_fingerprint,
            )

        if dataset_id in scenario_partitioned_ids:
            missing_code = "S0_REQUIRED_INPUT_MISSING"
            if dataset_id == "scenario_calendar_5A":
                missing_code = "S0_REQUIRED_SCENARIO_MISSING"
            digest_result = _hash_scenario_partitions(
                entry,
                scenario_ids,
                run_paths,
                config.external_roots,
                tokens,
                logger,
                f"S0: hash {dataset_id} bytes",
                dataset_id in required_ids,
                missing_code,
            )
            if digest_result is None:
                sealed_optional_missing.append(dataset_id)
                continue
            digest_hex, _ = digest_result
        else:
            try:
                resolved_path = _resolve_dataset_path(entry, run_paths, config.external_roots, tokens)
            except InputResolutionError as exc:
                if dataset_id in optional_ids:
                    sealed_optional_missing.append(dataset_id)
                    continue
                error_code = "S0_REQUIRED_POLICY_MISSING"
                if dataset_id in {
                    "scenario_horizon_config_5A",
                    "scenario_metadata",
                    "scenario_calendar_5A",
                }:
                    error_code = "S0_REQUIRED_SCENARIO_MISSING"
                if dataset_id in required_input_ids:
                    error_code = "S0_REQUIRED_INPUT_MISSING"
                _abort(
                    error_code,
                    "V-05",
                    "required_input_missing",
                    {"dataset_id": dataset_id, "path": str(entry.get("path") or ""), "error": str(exc)},
                    manifest_fingerprint,
                )
            if not resolved_path.exists():
                if dataset_id in optional_ids:
                    sealed_optional_missing.append(dataset_id)
                    continue
                error_code = "S0_REQUIRED_POLICY_MISSING"
                if dataset_id in {
                    "scenario_horizon_config_5A",
                    "scenario_metadata",
                    "scenario_calendar_5A",
                }:
                    error_code = "S0_REQUIRED_SCENARIO_MISSING"
                if dataset_id in required_input_ids:
                    error_code = "S0_REQUIRED_INPUT_MISSING"
                _abort(
                    error_code,
                    "V-05",
                    "required_input_missing",
                    {"dataset_id": dataset_id, "path": str(resolved_path)},
                    manifest_fingerprint,
                )

            if dataset_id in {
                "merchant_class_policy_5A",
                "demand_scale_policy_5A",
                "baseline_intensity_policy_5A",
                "shape_library_5A",
                "shape_time_grid_policy_5A",
                "zone_shape_modifiers_5A",
                "scenario_horizon_config_5A",
                "scenario_metadata",
                "scenario_overlay_policy_5A",
                "overlay_ordering_policy_5A",
                "scenario_overlay_validation_policy_5A",
                "validation_policy_5A",
                "spec_compatibility_config_5A",
            }:
                payload = _load_yaml(resolved_path) if resolved_path.suffix.lower() in {".yaml", ".yml"} else _load_json(resolved_path)
                if dataset_id == "scenario_horizon_config_5A":
                    _validate_payload(
                        schema_5a,
                        schema_layer1,
                        schema_layer2,
                        schema_ingress_layer2,
                        "scenario/scenario_horizon_config_5A",
                        payload,
                        manifest_fingerprint,
                        {"dataset_id": dataset_id},
                    )
                    scenario_config = payload if isinstance(payload, dict) else None
                    scenarios = scenario_config.get("scenarios") if isinstance(scenario_config, dict) else None
                    if not isinstance(scenarios, list) or not scenarios:
                        _abort(
                            "S0_REQUIRED_SCENARIO_MISSING",
                            "V-05",
                            "scenario_horizon_missing_scenarios",
                            {"dataset_id": dataset_id},
                            manifest_fingerprint,
                        )
                    scenario_ids = [str(item.get("scenario_id")) for item in scenarios if isinstance(item, dict)]
                elif dataset_id == "scenario_metadata":
                    _validate_payload(
                        schema_5a,
                        schema_layer1,
                        schema_layer2,
                        schema_ingress_layer2,
                        "scenario/scenario_metadata",
                        payload,
                        manifest_fingerprint,
                        {"dataset_id": dataset_id},
                    )
                    scenario_metadata = payload if isinstance(payload, dict) else None
                else:
                    anchor = schema_ref.split("#", 1)[1].strip("/")
                    _validate_payload(
                        schema_5a if schema_ref.startswith("schemas.5A.yaml#") else schema_layer2,
                        schema_layer1,
                        schema_layer2,
                        schema_ingress_layer2,
                        anchor,
                        payload,
                        manifest_fingerprint,
                        {"dataset_id": dataset_id},
                    )
                policy_version = _policy_version_from_payload(payload)
                version_decl = entry.get("version")
                if _is_placeholder(version_decl):
                    if policy_version is None:
                        _abort(
                            "S0_REQUIRED_POLICY_MISSING",
                            "V-06",
                            "policy_version_missing",
                            {"dataset_id": dataset_id, "path": str(resolved_path)},
                            manifest_fingerprint,
                        )
                else:
                    resolved_version = str(version_decl).replace("{parameter_hash}", parameter_hash)
                    if policy_version and resolved_version != policy_version:
                        _abort(
                            "S0_REQUIRED_POLICY_MISSING",
                            "V-06",
                            "policy_version_mismatch",
                            {"dataset_id": dataset_id, "expected": resolved_version, "actual": policy_version},
                            manifest_fingerprint,
                        )

            bundle_digest = None
            if dataset_id.startswith("validation_bundle_"):
                bundle_digest = bundle_digests.get(dataset_id)
            if dataset_id.startswith("validation_passed_flag_"):
                bundle_id = dataset_id.replace("validation_passed_flag", "validation_bundle")
                bundle_digest = bundle_digests.get(bundle_id)

            if bundle_digest:
                digest_hex = bundle_digest
            elif resolved_path.is_dir():
                digest_hex, _ = _hash_partition(resolved_path, logger, f"S0: hash {dataset_id} bytes")
            else:
                digest_hex = sha256_file(resolved_path).sha256_hex

        registry_digest = reg_entry.get("digest")
        if registry_digest and _HEX64_PATTERN.match(str(registry_digest)) and registry_digest != digest_hex:
            _abort(
                "S0_SEALED_INPUT_DIGEST_MISMATCH",
                "V-07",
                "sealed_digest_mismatch",
                {"dataset_id": dataset_id, "computed": digest_hex, "registry": registry_digest},
                manifest_fingerprint,
            )
        digest_map[dataset_id] = digest_hex

        owner_segment = str(entry.get("owner_subsegment") or SEGMENT)
        role = _role_for_dataset(dataset_id)
        license_class = str(entry.get("licence") or reg_entry.get("license") or "unknown")
        owner_team = ""
        owner_entry = reg_entry.get("owner")
        if isinstance(owner_entry, dict):
            owner_team = str(owner_entry.get("team") or owner_entry.get("owner_team") or "")
        manifest_key = str(reg_entry.get("manifest_key") or "")
        catalog_path = entry.get("path") or ""
        partition_keys = list(entry.get("partitioning") or [])
        status = "REQUIRED" if dataset_id in required_ids else "OPTIONAL"
        notes = ""
        if dataset_id == "scenario_calendar_5A":
            notes = f"scenario_ids={','.join(sorted(set(scenario_ids)))}"

        sealed_rows.append(
            {
                "manifest_fingerprint": manifest_fingerprint,
                "parameter_hash": parameter_hash,
                "owner_layer": _owner_layer(owner_segment),
                "owner_segment": owner_segment,
                "artifact_id": dataset_id,
                "manifest_key": manifest_key,
                "role": role,
                "schema_ref": schema_ref,
                "path_template": catalog_path,
                "partition_keys": partition_keys,
                "sha256_hex": digest_hex,
                "version": _render_version(entry, tokens, reg_entry),
                "source_dictionary": str(dict_5a_path),
                "source_registry": str(reg_5a_path),
                "status": status,
                "read_scope": _read_scope_for_dataset(dataset_id),
                "notes": notes,
                "license_class": license_class,
                "owner_team": owner_team,
            }
        )

    if sealed_optional_missing:
        logger.info("S0: optional inputs missing (not sealed): %s", ", ".join(sealed_optional_missing))

    sealed_rows_sorted = sorted(
        sealed_rows,
        key=lambda row: (row.get("owner_layer"), row.get("owner_segment"), row.get("role"), row.get("artifact_id")),
    )

    sealed_schema = _schema_from_pack(schema_5a, "validation/sealed_inputs_5A")
    _inline_external_refs(sealed_schema, schema_layer1, "schemas.layer1.yaml#")
    _inline_external_refs(sealed_schema, schema_layer2, "schemas.layer2.yaml#")
    _inline_external_refs(sealed_schema, schema_ingress_layer2, "schemas.ingress.layer2.yaml#")
    errors = list(Draft202012Validator(sealed_schema).iter_errors(sealed_rows_sorted))
    if errors:
        _abort(
            "S0_INTERNAL_INVARIANT_VIOLATION",
            "V-08",
            "sealed_inputs_schema_invalid",
            {"error": str(errors[0])},
            manifest_fingerprint,
        )

    sealed_inputs_digest = _sealed_inputs_digest(sealed_rows_sorted)
    role_counts: dict[str, int] = {}
    for row in sealed_rows_sorted:
        role_counts[row["role"]] = role_counts.get(row["role"], 0) + 1

    logger.info(
        "S0: sealed_inputs_digest=%s sealed_inputs_count_total=%d sealed_inputs_count_by_role=%s",
        sealed_inputs_digest,
        len(sealed_rows_sorted),
        role_counts,
    )

    receipt_entry = find_dataset_entry(dictionary_5a, "s0_gate_receipt_5A").entry
    sealed_entry = find_dataset_entry(dictionary_5a, "sealed_inputs_5A").entry
    manifest_entry = find_dataset_entry(dictionary_5a, "scenario_manifest_5A").entry
    receipt_path = _resolve_dataset_path(receipt_entry, run_paths, config.external_roots, tokens)
    sealed_inputs_path = _resolve_dataset_path(sealed_entry, run_paths, config.external_roots, tokens)
    scenario_manifest_path = _resolve_dataset_path(manifest_entry, run_paths, config.external_roots, tokens)

    if f"manifest_fingerprint={manifest_fingerprint}" not in sealed_inputs_path.as_posix():
        _abort(
            "S0_INTERNAL_INVARIANT_VIOLATION",
            "V-09",
            "sealed_inputs_path_missing_manifest",
            {"path": str(sealed_inputs_path)},
            manifest_fingerprint,
        )

    existing_receipt = None
    if receipt_path.exists():
        try:
            existing_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing_receipt = None

    created_utc = utc_now_rfc3339_micro()
    if isinstance(existing_receipt, dict) and existing_receipt.get("created_utc"):
        created_utc = str(existing_receipt["created_utc"])

    if scenario_config is None:
        _abort(
            "S0_REQUIRED_SCENARIO_MISSING",
            "V-10",
            "scenario_horizon_config_missing",
            {"dataset_id": "scenario_horizon_config_5A"},
            manifest_fingerprint,
        )
    scenarios = scenario_config.get("scenarios") if isinstance(scenario_config, dict) else None
    if not isinstance(scenarios, list) or not scenarios:
        _abort(
            "S0_REQUIRED_SCENARIO_MISSING",
            "V-10",
            "scenario_horizon_missing_scenarios",
            {"dataset_id": "scenario_horizon_config_5A"},
            manifest_fingerprint,
        )

    scenario_ids = [str(item.get("scenario_id")) for item in scenarios if isinstance(item, dict)]
    scenario_id_value: object = scenario_ids if len(scenario_ids) != 1 else scenario_ids[0]
    scenario_pack_id = None
    if isinstance(scenario_metadata, dict):
        scenario_pack_id = scenario_metadata.get("scenario_pack_id") or scenario_metadata.get("pack_id")

    receipt_registry = find_artifact_entry(registry_5a, "s0_gate_receipt_5A").entry
    receipt_version = _normalize_semver(receipt_registry.get("semver") or "1.0.0")

    receipt_payload = {
        "manifest_fingerprint": manifest_fingerprint,
        "parameter_hash": parameter_hash,
        "run_id": run_id_value,
        "created_utc": created_utc,
        "s0_spec_version": receipt_version,
        "verified_upstream_segments": upstream_gates,
        "scenario_id": scenario_id_value,
        "sealed_inputs_digest": sealed_inputs_digest,
    }
    if scenario_pack_id:
        receipt_payload["scenario_pack_id"] = scenario_pack_id

    receipt_schema = _schema_from_pack(schema_5a, "validation/s0_gate_receipt_5A")
    _inline_external_refs(receipt_schema, schema_layer1, "schemas.layer1.yaml#")
    _inline_external_refs(receipt_schema, schema_layer2, "schemas.layer2.yaml#")
    _inline_external_refs(receipt_schema, schema_ingress_layer2, "schemas.ingress.layer2.yaml#")
    errors = list(Draft202012Validator(receipt_schema).iter_errors(receipt_payload))
    if errors:
        _abort(
            "S0_INTERNAL_INVARIANT_VIOLATION",
            "V-11",
            "receipt_schema_invalid",
            {"error": str(errors[0])},
            manifest_fingerprint,
        )

    scenario_config_ids = [
        "scenario_horizon_config_5A",
        "scenario_metadata",
        "scenario_calendar_5A",
        "scenario_overlay_policy_5A",
    ]
    if "overlay_ordering_policy_5A" not in sealed_optional_missing:
        scenario_config_ids.append("overlay_ordering_policy_5A")
    if "scenario_overlay_validation_policy_5A" not in sealed_optional_missing:
        scenario_config_ids.append("scenario_overlay_validation_policy_5A")

    scenario_manifest_rows = []
    for scenario in scenarios:
        if not isinstance(scenario, dict):
            continue
        scenario_manifest_rows.append(
            {
                "manifest_fingerprint": manifest_fingerprint,
                "scenario_id": scenario.get("scenario_id"),
                "scenario_version": scenario.get("scenario_version"),
                "horizon_start_utc": scenario.get("horizon_start_utc"),
                "horizon_end_utc": scenario.get("horizon_end_utc"),
                "is_baseline": scenario.get("is_baseline"),
                "is_stress": scenario.get("is_stress"),
                "labels": scenario.get("labels") or [],
                "scenario_config_ids": scenario_config_ids,
            }
        )

    scenario_manifest_schema = _schema_from_pack(schema_5a, "validation/scenario_manifest_5A")
    _inline_external_refs(scenario_manifest_schema, schema_layer1, "schemas.layer1.yaml#")
    _inline_external_refs(scenario_manifest_schema, schema_layer2, "schemas.layer2.yaml#")
    _inline_external_refs(scenario_manifest_schema, schema_ingress_layer2, "schemas.ingress.layer2.yaml#")
    errors = list(Draft202012Validator(scenario_manifest_schema).iter_errors(scenario_manifest_rows))
    if errors:
        _abort(
            "S0_INTERNAL_INVARIANT_VIOLATION",
            "V-12",
            "scenario_manifest_schema_invalid",
            {"error": str(errors[0])},
            manifest_fingerprint,
        )

    if sealed_inputs_path.exists() or receipt_path.exists():
        if not sealed_inputs_path.exists() or not receipt_path.exists():
            _abort(
                "S0_OUTPUT_CONFLICT",
                "V-13",
                "partial_outputs_exist",
                {"sealed_inputs_path": str(sealed_inputs_path), "receipt_path": str(receipt_path)},
                manifest_fingerprint,
            )
        existing_rows = _load_json(sealed_inputs_path)
        if not isinstance(existing_rows, list):
            _abort(
                "S0_OUTPUT_CONFLICT",
                "V-13",
                "sealed_inputs_existing_invalid",
                {"path": str(sealed_inputs_path)},
                manifest_fingerprint,
            )
        existing_sorted = sorted(
            existing_rows,
            key=lambda row: (row.get("owner_layer"), row.get("owner_segment"), row.get("role"), row.get("artifact_id")),
        )
        existing_digest = _sealed_inputs_digest(existing_sorted)
        if existing_digest != sealed_inputs_digest:
            _abort(
                "S0_OUTPUT_CONFLICT",
                "V-13",
                "sealed_inputs_digest_mismatch",
                {"expected": sealed_inputs_digest, "actual": existing_digest},
                manifest_fingerprint,
            )
        existing_receipt_payload = _load_json(receipt_path)
        if json.dumps(existing_receipt_payload, sort_keys=True, separators=(",", ":")) != json.dumps(
            receipt_payload, sort_keys=True, separators=(",", ":")
        ):
            _abort(
                "S0_OUTPUT_CONFLICT",
                "V-13",
                "receipt_payload_mismatch",
                {"receipt_path": str(receipt_path)},
                manifest_fingerprint,
            )
        logger.info("S0: outputs already exist and are identical; skipping publish.")
        return S0GateResult(
            run_id=run_id_value,
            parameter_hash=parameter_hash,
            manifest_fingerprint=manifest_fingerprint,
            receipt_path=receipt_path,
            sealed_inputs_path=sealed_inputs_path,
            scenario_manifest_path=scenario_manifest_path,
        )

    _atomic_publish_json(sealed_inputs_path, sealed_rows_sorted)
    _atomic_publish_json(receipt_path, receipt_payload)
    scenario_manifest_df = pl.DataFrame(scenario_manifest_rows)
    _atomic_publish_parquet(scenario_manifest_path, scenario_manifest_df)

    elapsed = time.monotonic() - started
    timer.info(f"S0: completed gate and sealed inputs (elapsed={elapsed:.2f}s)")

    return S0GateResult(
        run_id=run_id_value,
        parameter_hash=parameter_hash,
        manifest_fingerprint=manifest_fingerprint,
        receipt_path=receipt_path,
        sealed_inputs_path=sealed_inputs_path,
        scenario_manifest_path=scenario_manifest_path,
    )


def _atomic_publish_parquet(path: Path, df: pl.DataFrame) -> None:
    tmp_dir = path.parent / f"_tmp.{uuid.uuid4().hex}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / path.name
    df.write_parquet(tmp_path, compression="zstd")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        tmp_path.replace(path)
    except OSError as exc:
        raise EngineFailure(
            "F4",
            "S0_IO_WRITE_FAILED",
            STATE,
            MODULE_NAME,
            {"detail": "atomic parquet publish failed", "path": str(path), "error": str(exc)},
        ) from exc
    try:
        tmp_dir.rmdir()
    except OSError:
        pass
