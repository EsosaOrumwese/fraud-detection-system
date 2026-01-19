"""S0 gate-in runner for Segment 3B."""

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


MODULE_NAME = "3B.s0_gate"
SEGMENT = "3B"
STATE = "S0"
_FLAG_PATTERN = re.compile(r"^sha256_hex = ([a-f0-9]{64})\s*$")
_HEX64_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_PLACEHOLDER_MARKERS = {"TBD", "null", "unknown", ""}


@dataclass(frozen=True)
class GateStatus:
    bundle_id: str
    bundle_path: str
    flag_path: str
    sha256_hex: str
    status: str


@dataclass(frozen=True)
class SealedAsset:
    logical_id: str
    owner_segment: str
    artefact_kind: str
    path: str
    schema_ref: str
    sha256_hex: str
    role: str
    license_class: str


@dataclass(frozen=True)
class S0GateResult:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    receipt_path: Path
    sealed_inputs_path: Path


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
    logger = get_logger("engine.layers.l1.seg_3B.s0_gate.l2.runner")
    _emit_validation(logger, manifest_fingerprint, validator_id, "fail", code, context)
    raise EngineFailure("F4", code, STATE, MODULE_NAME, context)


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise InputResolutionError(f"Missing JSON file: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_yaml(path: Path) -> object:
    if not path.exists():
        raise InputResolutionError(f"Missing YAML file: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)

def _schema_from_pack(schema_pack: dict, path: str) -> dict:
    node: dict = schema_pack
    anchor = path
    if "#/" in path:
        anchor = path.split("#", 1)[1]
    for part in anchor.strip("/").split("/"):
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
    schema_3b: dict,
    schema_3a: dict,
    schema_2b: dict,
    schema_2a: dict,
    schema_1b: dict,
    schema_1a: dict,
    schema_layer1: dict,
    schema_ingress: dict,
) -> str:
    if not schema_ref:
        raise ContractError("Missing schema_ref.")
    if schema_ref.startswith("schemas.3B.yaml#"):
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
        _schema_anchor_exists(schema_ingress, schema_ref)
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
            "E3B_S0_001_UPSTREAM_GATE_FAILED",
            STATE,
            MODULE_NAME,
            {"detail": "invalid _passed.flag format", "path": str(path)},
        )
    return match.group(1)


def _hash_partition(root: Path) -> tuple[str, int]:
    files = sorted(
        [path for path in root.rglob("*") if path.is_file()],
        key=lambda path: path.relative_to(root).as_posix(),
    )
    if not files:
        raise HashingError(f"No files found under dataset path: {root}")
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
                "E3B_S0_001_UPSTREAM_GATE_FAILED",
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
            "E3B_S0_001_UPSTREAM_GATE_FAILED",
            STATE,
            MODULE_NAME,
            {"detail": str(errors[0]), "path": str(index_path)},
        )
    members = index_payload.get("members")
    if not isinstance(members, list) or not members:
        raise EngineFailure(
            "F4",
            "E3B_S0_001_UPSTREAM_GATE_FAILED",
            STATE,
            MODULE_NAME,
            {"detail": "bundle index missing members", "path": str(index_path)},
        )
    for member in members:
        sha256_hex = member.get("sha256_hex") if isinstance(member, dict) else None
        if not isinstance(sha256_hex, str) or not _HEX64_PATTERN.match(sha256_hex):
            raise EngineFailure(
                "F4",
                "E3B_S0_001_UPSTREAM_GATE_FAILED",
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
                "E3B_S0_001_UPSTREAM_GATE_FAILED",
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
                "E3B_S0_001_UPSTREAM_GATE_FAILED",
                STATE,
                MODULE_NAME,
                {"detail": str(errors[0]), "path": str(index_path)},
            )
        entries = list(payload.get("files", []))
    else:
        raise EngineFailure(
            "F4",
            "E3B_S0_001_UPSTREAM_GATE_FAILED",
            STATE,
            MODULE_NAME,
            {"detail": "index.json has unsupported shape", "path": str(index_path)},
        )

    paths = []
    for entry in entries:
        path = entry.get("path")
        if not isinstance(path, str) or not path:
            raise EngineFailure(
                "F4",
                "E3B_S0_001_UPSTREAM_GATE_FAILED",
                STATE,
                MODULE_NAME,
                {"detail": "index entry missing path", "path": str(index_path)},
            )
        try:
            path.encode("ascii")
        except UnicodeEncodeError as exc:
            raise EngineFailure(
                "F4",
                "E3B_S0_001_UPSTREAM_GATE_FAILED",
                STATE,
                MODULE_NAME,
                {"detail": f"non-ascii path: {path}", "path": str(index_path)},
            ) from exc
        if "\\" in path or path.startswith(("/", "\\")) or ".." in Path(path).parts or ":" in path:
            raise EngineFailure(
                "F4",
                "E3B_S0_001_UPSTREAM_GATE_FAILED",
                STATE,
                MODULE_NAME,
                {"detail": f"invalid index path: {path}", "path": str(index_path)},
            )
        paths.append(path)
    if len(set(paths)) != len(paths):
        raise EngineFailure(
            "F4",
            "E3B_S0_001_UPSTREAM_GATE_FAILED",
            STATE,
            MODULE_NAME,
            {"detail": "duplicate path entries in index.json", "path": str(index_path)},
        )
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
            "E3B_S0_001_UPSTREAM_GATE_FAILED",
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


def _load_tz_cache_manifest(
    cache_root: Path,
    schema_2a: dict,
    schema_layer1: dict,
    manifest_fingerprint: str,
) -> dict:
    manifest_path = cache_root / "tz_timetable_cache.json"
    payload = _load_json(manifest_path)
    schema = _schema_from_pack(schema_2a, "cache/tz_timetable_cache")
    _inline_external_refs(schema, schema_layer1, "schemas.layer1.yaml#")
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    if errors:
        raise EngineFailure(
            "F4",
            "E3B_S0_005_SEALED_INPUT_RESOLUTION_FAILED",
            STATE,
            MODULE_NAME,
            {"detail": str(errors[0]), "path": str(manifest_path)},
        )
    if payload.get("manifest_fingerprint") != manifest_fingerprint:
        raise EngineFailure(
            "F4",
            "E3B_S0_005_SEALED_INPUT_RESOLUTION_FAILED",
            STATE,
            MODULE_NAME,
            {
                "detail": "tz_timetable_cache manifest_fingerprint mismatch",
                "path": str(manifest_path),
                "manifest_fingerprint": payload.get("manifest_fingerprint"),
            },
        )
    return payload


def _validate_pelias_bundle(
    bundle_path: Path,
    sqlite_digest: str,
    schema_3b: dict,
    schema_layer1: dict,
) -> dict:
    payload = _load_json(bundle_path)
    schema = _schema_from_pack(schema_3b, "reference/pelias_cached_bundle_v1")
    _inline_external_refs(schema, schema_layer1, "schemas.layer1.yaml#")
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    if errors:
        raise EngineFailure(
            "F4",
            "E3B_S0_005_SEALED_INPUT_RESOLUTION_FAILED",
            STATE,
            MODULE_NAME,
            {"detail": str(errors[0]), "path": str(bundle_path)},
        )
    bundle_digest = str(payload.get("sha256_hex") or "")
    if bundle_digest != sqlite_digest:
        raise EngineFailure(
            "F4",
            "E3B_S0_006_SEALED_INPUT_DIGEST_MISMATCH",
            STATE,
            MODULE_NAME,
            {"detail": "pelias_cached_bundle digest mismatch", "bundle": bundle_digest, "sqlite": sqlite_digest},
        )
    return payload


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
        raise EngineFailure(
            "F4",
            "E3B_S0_005_SEALED_INPUT_RESOLUTION_FAILED",
            STATE,
            MODULE_NAME,
            {"detail": str(errors[0]), "path": str(sealed_path)},
        )
    if not isinstance(payload, list):
        raise EngineFailure(
            "F4",
            "E3B_S0_005_SEALED_INPUT_RESOLUTION_FAILED",
            STATE,
            MODULE_NAME,
            {"detail": "sealed_inputs_1A payload is not a list", "path": str(sealed_path)},
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
    raise EngineFailure(
        "F4",
        "E3B_S0_005_SEALED_INPUT_RESOLUTION_FAILED",
        STATE,
        MODULE_NAME,
        {
            "detail": "transaction_schema_merchant_ids version missing from sealed_inputs_1A",
            "manifest_fingerprint": manifest_fingerprint,
        },
    )


def _pick_latest_run_receipt(runs_root: Path) -> Path:
    receipts = sorted(
        runs_root.glob("*/run_receipt.json"),
        key=lambda path: path.stat().st_mtime,
    )
    if not receipts:
        raise InputResolutionError(f"No run_receipt.json found under {runs_root}")
    return receipts[-1]


def _resolve_run_receipt(runs_root: Path, run_id: Optional[str]) -> tuple[Path, dict]:
    if run_id:
        receipt_path = runs_root / run_id / "run_receipt.json"
    else:
        receipt_path = _pick_latest_run_receipt(runs_root)
    receipt = _load_json(receipt_path)
    return receipt_path, receipt


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


def _append_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True, sort_keys=True))
        handle.write("\n")


def _segment_state_runs_path(run_paths: RunPaths, dictionary: dict, utc_day: str) -> Path:
    entry = find_dataset_entry(dictionary, "segment_state_runs").entry
    path_template = entry["path"]
    path = path_template.replace("{utc_day}", utc_day)
    return run_paths.run_root / path


def _atomic_publish_json(path: Path, payload: object, logger, label: str) -> None:
    payload_bytes = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if path.exists():
        existing = path.read_bytes()
        if existing == payload_bytes:
            logger.info("S0: %s already exists and is identical; skipping publish.", label)
            return
        raise EngineFailure(
            "F4",
            "E3B_S0_009_IMMUTABILITY_VIOLATION",
            STATE,
            MODULE_NAME,
            {"detail": "non-identical output exists", "path": str(path), "label": label},
        )
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
            "E3B_S0_010_INFRASTRUCTURE_IO_ERROR",
            STATE,
            MODULE_NAME,
            {"detail": "atomic publish failed", "path": str(path), "error": str(exc)},
        ) from exc
    try:
        tmp_dir.rmdir()
    except OSError:
        pass


def _maybe_catalogue_mismatch(left: dict, right: dict, keys: tuple[str, ...]) -> bool:
    for key in keys:
        if str(left.get(key)) != str(right.get(key)):
            return True
    return False


def _check_catalogue_consistency(
    dictionary_3b: dict,
    dictionary_upstream: dict[str, dict],
    logger,
    manifest_fingerprint: str,
) -> None:
    cross_layer_ids = [
        "validation_bundle_1A",
        "validation_passed_flag_1A",
        "validation_bundle_1B",
        "validation_passed_flag_1B",
        "validation_bundle_2A",
        "validation_passed_flag_2A",
        "validation_bundle_3A",
        "validation_passed_flag_3A",
        "outlet_catalogue",
        "site_locations",
        "site_timezones",
        "tz_timetable_cache",
        "zone_alloc",
        "zone_alloc_universe_hash",
        "transaction_schema_merchant_ids",
        "route_rng_policy_v1",
        "alias_layout_policy_v1",
        "day_effect_policy_v1",
    ]
    for dataset_id in cross_layer_ids:
        entry_3b = find_dataset_entry(dictionary_3b, dataset_id).entry
        upstream_entry = None
        for dictionary in dictionary_upstream.values():
            try:
                upstream_entry = find_dataset_entry(dictionary, dataset_id).entry
                break
            except ContractError:
                continue
        if upstream_entry is None:
            _abort(
                "E3B_S0_002_CATALOGUE_MALFORMED",
                "V-02",
                "missing_upstream_dictionary_entry",
                {"dataset_id": dataset_id},
                manifest_fingerprint,
            )
        if _maybe_catalogue_mismatch(entry_3b, upstream_entry, ("path", "schema_ref")):
            _abort(
                "E3B_S0_002_CATALOGUE_MALFORMED",
                "V-02",
                "dictionary_mismatch",
                {
                    "dataset_id": dataset_id,
                    "path_3B": entry_3b.get("path"),
                    "path_upstream": upstream_entry.get("path"),
                    "schema_3B": entry_3b.get("schema_ref"),
                    "schema_upstream": upstream_entry.get("schema_ref"),
                },
                manifest_fingerprint,
            )
    logger.info("S0: catalogue cross-checks passed for %d dataset IDs", len(cross_layer_ids))


def _hash_for_asset(
    asset_id: str,
    resolved_path: Path,
    logger,
    bundle_digest: Optional[str] = None,
) -> tuple[str, int]:
    if asset_id.startswith("validation_bundle_"):
        if bundle_digest is None:
            raise HashingError(f"Missing bundle digest for {asset_id}")
        return bundle_digest, 0
    if asset_id.startswith("validation_passed_flag_"):
        if bundle_digest is None:
            raise HashingError(f"Missing bundle digest for {asset_id}")
        return bundle_digest, 0
    if resolved_path.is_dir():
        return _hash_partition(resolved_path)
    if asset_id == "hrsl_raster":
        return _hash_file_with_progress(resolved_path, logger, "S0: hash hrsl_raster bytes")
    digest = sha256_file(resolved_path)
    return digest.sha256_hex, digest.size_bytes

def run_s0(config: EngineConfig, run_id: Optional[str] = None) -> S0GateResult:
    logger = get_logger("engine.layers.l1.seg_3B.s0_gate.l2.runner")
    timer = _StepTimer(logger)
    started = time.monotonic()

    receipt_path, receipt = _resolve_run_receipt(config.runs_root, run_id)
    run_id = str(receipt.get("run_id") or "")
    if not run_id:
        raise InputResolutionError("run_receipt missing run_id.")
    if receipt_path.parent.name != run_id:
        raise InputResolutionError("run_receipt path does not match embedded run_id.")

    seed = receipt.get("seed")
    parameter_hash = str(receipt.get("parameter_hash") or "")
    manifest_fingerprint = str(receipt.get("manifest_fingerprint") or "")
    if seed is None or not parameter_hash or not manifest_fingerprint:
        raise InputResolutionError("run_receipt missing seed, parameter_hash, or manifest_fingerprint.")
    if not _HEX64_PATTERN.match(parameter_hash) or not _HEX64_PATTERN.match(manifest_fingerprint):
        raise InputResolutionError("run_receipt has invalid parameter_hash or manifest_fingerprint.")

    run_paths = RunPaths(config.runs_root, run_id)
    run_log_path = run_paths.run_root / f"run_log_{run_id}.log"
    add_file_handler(run_log_path)
    timer.info(f"S0: run log initialized at {run_log_path}")

    source = ContractSource(config.contracts_root, config.contracts_layout)
    try:
        dict_3b_path, dictionary_3b = load_dataset_dictionary(source, "3B")
        dict_3a_path, dictionary_3a = load_dataset_dictionary(source, "3A")
        dict_2b_path, dictionary_2b = load_dataset_dictionary(source, "2B")
        dict_2a_path, dictionary_2a = load_dataset_dictionary(source, "2A")
        dict_1b_path, dictionary_1b = load_dataset_dictionary(source, "1B")
        dict_1a_path, dictionary_1a = load_dataset_dictionary(source, "1A")
        reg_3b_path, registry_3b = load_artefact_registry(source, "3B")
        reg_3a_path, registry_3a = load_artefact_registry(source, "3A")
        reg_2b_path, registry_2b = load_artefact_registry(source, "2B")
        reg_2a_path, registry_2a = load_artefact_registry(source, "2A")
        reg_1b_path, registry_1b = load_artefact_registry(source, "1B")
        reg_1a_path, registry_1a = load_artefact_registry(source, "1A")
        schema_3b_path, schema_3b = load_schema_pack(source, "3B", "3B")
        schema_3a_path, schema_3a = load_schema_pack(source, "3A", "3A")
        schema_2b_path, schema_2b = load_schema_pack(source, "2B", "2B")
        schema_2a_path, schema_2a = load_schema_pack(source, "2A", "2A")
        schema_1b_path, schema_1b = load_schema_pack(source, "1B", "1B")
        schema_1a_path, schema_1a = load_schema_pack(source, "1A", "1A")
        schema_layer1_path, schema_layer1 = load_schema_pack(source, "1A", "layer1")
        schema_ingress_path, schema_ingress = load_schema_pack(source, "1A", "ingress.layer1")
    except ContractError as exc:
        _abort(
            "E3B_S0_002_CATALOGUE_MALFORMED",
            "V-01",
            "contract_load_failed",
            {"detail": str(exc)},
            manifest_fingerprint,
        )

    logger.info(
        "Contracts layout=%s root=%s dictionary=%s registry=%s schemas=%s,%s,%s",
        config.contracts_layout,
        str(config.contracts_root),
        str(dict_3b_path),
        str(reg_3b_path),
        str(schema_3b_path),
        str(schema_layer1_path),
        str(schema_ingress_path),
    )

    logger.info(
        "S0: objective=gate 1A/1B/2A/3A and seal inputs (virtual policies + upstream egress + externals) -> outputs (s0_gate_receipt_3B, sealed_inputs_3B)"
    )

    tokens = {
        "seed": str(seed),
        "parameter_hash": parameter_hash,
        "manifest_fingerprint": manifest_fingerprint,
        "run_id": run_id,
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
        dictionary_3b,
        {
            "1A": dictionary_1a,
            "1B": dictionary_1b,
            "2A": dictionary_2a,
            "2B": dictionary_2b,
            "3A": dictionary_3a,
        },
        logger,
        manifest_fingerprint,
    )
    _emit_validation(logger, manifest_fingerprint, "V-02", "pass")

    upstream_gates: dict[str, dict] = {}
    bundle_digests: dict[str, str] = {}

    gate_map = {
        "segment_1A": ("validation_bundle_1A", "validation_passed_flag_1A", schema_1a, "validation/validation_bundle_index_1A"),
        "segment_1B": ("validation_bundle_1B", "validation_passed_flag_1B", schema_1b, "validation/validation_bundle_index_1B"),
        "segment_2A": ("validation_bundle_2A", "validation_passed_flag_2A", schema_2a, "validation/validation_bundle_index_2A"),
    }

    for segment_key, (bundle_id, flag_id, schema_pack, index_anchor) in gate_map.items():
        bundle_entry = find_dataset_entry(dictionary_3b, bundle_id).entry
        flag_entry = find_dataset_entry(dictionary_3b, flag_id).entry
        bundle_root = _resolve_dataset_path(bundle_entry, run_paths, config.external_roots, tokens)
        flag_path = _resolve_dataset_path(flag_entry, run_paths, config.external_roots, tokens)
        if not bundle_root.exists():
            _abort(
                "E3B_S0_001_UPSTREAM_GATE_FAILED",
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
                "E3B_S0_001_UPSTREAM_GATE_FAILED",
                "V-03",
                "hashgate_mismatch",
                {"bundle_id": bundle_id, "expected": bundle_digest, "actual": flag_digest},
                manifest_fingerprint,
            )
        bundle_digests[bundle_id] = bundle_digest
        upstream_gates[segment_key] = {
            "bundle_id": bundle_id,
            "flag_path": _render_catalog_path(flag_entry, tokens),
            "sha256_hex": bundle_digest,
            "status": "PASS",
        }
        logger.info(
            "S0: %s gate verified (bundle=%s, digest=%s)",
            segment_key,
            bundle_root.as_posix(),
            bundle_digest,
        )

    bundle_entry = find_dataset_entry(dictionary_3b, "validation_bundle_3A").entry
    flag_entry = find_dataset_entry(dictionary_3b, "validation_passed_flag_3A").entry
    bundle_root = _resolve_dataset_path(bundle_entry, run_paths, config.external_roots, tokens)
    flag_path = _resolve_dataset_path(flag_entry, run_paths, config.external_roots, tokens)
    if not bundle_root.exists():
        _abort(
            "E3B_S0_001_UPSTREAM_GATE_FAILED",
            "V-03",
            "validation_bundle_missing",
            {"bundle_id": "validation_bundle_3A", "path": str(bundle_root)},
            manifest_fingerprint,
        )
    index_path = bundle_root / "index.json"
    index_payload = _load_json(index_path)
    bundle_digest = _bundle_digest_from_members(
        index_payload,
        schema_layer1,
        logger,
        manifest_fingerprint,
        index_path,
    )
    flag_digest = _parse_pass_flag(flag_path)
    if bundle_digest != flag_digest:
        _abort(
            "E3B_S0_001_UPSTREAM_GATE_FAILED",
            "V-03",
            "hashgate_mismatch",
            {"bundle_id": "validation_bundle_3A", "expected": bundle_digest, "actual": flag_digest},
            manifest_fingerprint,
        )
    bundle_digests["validation_bundle_3A"] = bundle_digest
    upstream_gates["segment_3A"] = {
        "bundle_id": "validation_bundle_3A",
        "flag_path": _render_catalog_path(flag_entry, tokens),
        "sha256_hex": bundle_digest,
        "status": "PASS",
    }
    logger.info(
        "S0: segment_3A gate verified (bundle=%s, digest=%s, law=index_only)",
        bundle_root.as_posix(),
        bundle_digest,
    )

    sealed_policy_set = []
    sealed_assets: list[SealedAsset] = []

    digest_map: dict[str, str] = {}

    policy_ids = [
        "route_rng_policy_v1",
        "alias_layout_policy_v1",
        "day_effect_policy_v1",
        "cdn_key_digest",
        "mcc_channel_rules",
        "cdn_country_weights",
        "virtual_validation_policy",
        "virtual_routing_fields_v1",
        "virtual_logging_policy",
    ]
    policy_2b_ids = {"route_rng_policy_v1", "alias_layout_policy_v1", "day_effect_policy_v1"}
    for dataset_id in policy_ids:
        entry = find_dataset_entry(dictionary_3b, dataset_id).entry
        reg_entry = find_artifact_entry(registry_3b, dataset_id).entry
        schema_ref = _validate_schema_ref(
            entry.get("schema_ref"),
            schema_3b,
            schema_3a,
            schema_2b,
            schema_2a,
            schema_1b,
            schema_1a,
            schema_layer1,
            schema_ingress,
        )
        policy_path = _resolve_dataset_path(entry, run_paths, config.external_roots, tokens)
        if not policy_path.exists():
            _abort(
                "E3B_S0_003_POLICY_SET_INCOMPLETE",
                "V-04",
                "policy_missing",
                {"dataset_id": dataset_id, "path": str(policy_path)},
                manifest_fingerprint,
            )
        payload = _load_yaml(policy_path) if policy_path.suffix.lower() in {".yaml", ".yml"} else _load_json(policy_path)
        version = _policy_version_from_payload(payload)
        if _is_placeholder(version):
            _abort(
                "E3B_S0_003_POLICY_SET_INCOMPLETE",
                "V-04",
                "policy_version_missing",
                {"dataset_id": dataset_id, "path": str(policy_path)},
                manifest_fingerprint,
            )
        semver = reg_entry.get("semver")
        if semver and not _is_placeholder(str(semver)):
            normalized_semver = _normalize_semver(str(semver))
            normalized_version = _normalize_semver(str(version))
            if normalized_semver != normalized_version:
                _abort(
                    "E3B_S0_003_POLICY_SET_INCOMPLETE",
                    "V-04",
                "policy_version_mismatch",
                {"dataset_id": dataset_id, "file_version": version, "registry_semver": semver},
                manifest_fingerprint,
            )
        if dataset_id in policy_2b_ids:
            schema = _schema_from_pack(schema_2b, schema_ref)
        else:
            schema = _schema_from_pack(schema_3b, schema_ref)
        _inline_external_refs(schema, schema_layer1, "schemas.layer1.yaml#")
        errors = list(Draft202012Validator(schema).iter_errors(payload))
        if errors:
            _abort(
                "E3B_S0_004_POLICY_SCHEMA_INVALID",
                "V-05",
                "policy_schema_invalid",
                {"dataset_id": dataset_id, "error": str(errors[0])},
                manifest_fingerprint,
            )
        digest = sha256_file(policy_path)
        registry_digest = reg_entry.get("digest")
        if registry_digest and _HEX64_PATTERN.match(str(registry_digest)) and registry_digest != digest.sha256_hex:
            _abort(
                "E3B_S0_006_SEALED_INPUT_DIGEST_MISMATCH",
                "V-06",
                "policy_digest_mismatch",
                {"dataset_id": dataset_id, "computed": digest.sha256_hex, "registry": registry_digest},
                manifest_fingerprint,
            )
        digest_map[dataset_id] = digest.sha256_hex
        role = reg_entry.get("role") or entry.get("description") or "policy"
        owner = str(entry.get("owner_subsegment") or "unknown")
        license_class = str(reg_entry.get("license") or entry.get("licence") or "unknown")
        catalog_path = _render_catalog_path(entry, tokens)
        sealed_policy_set.append(
            {
                "logical_id": dataset_id,
                "owner_segment": owner,
                "role": role,
                "sha256_hex": digest.sha256_hex,
                "schema_ref": schema_ref,
                "path": catalog_path,
            }
        )
        sealed_assets.append(
            SealedAsset(
                logical_id=dataset_id,
                owner_segment=owner,
                artefact_kind=str(reg_entry.get("type") or "policy"),
                path=catalog_path,
                schema_ref=schema_ref,
                sha256_hex=digest.sha256_hex,
                role=role,
                license_class=license_class,
            )
        )

    required_ids = [
        "validation_bundle_1A",
        "validation_passed_flag_1A",
        "validation_bundle_1B",
        "validation_passed_flag_1B",
        "validation_bundle_2A",
        "validation_passed_flag_2A",
        "validation_bundle_3A",
        "validation_passed_flag_3A",
        "outlet_catalogue",
        "site_locations",
        "site_timezones",
        "zone_alloc",
        "zone_alloc_universe_hash",
        "transaction_schema_merchant_ids",
        "virtual_settlement_coords",
        "cdn_weights_ext_yaml",
        "world_countries",
        "tile_index",
        "tile_weights",
        "tile_bounds",
        "tz_world_2025a",
        "tz_nudge",
        "tz_overrides",
        "hrsl_raster",
        "pelias_cached_sqlite",
        "pelias_cached_bundle",
    ]
    optional_ids = ["tz_timetable_cache"]

    sealed_optional_missing: list[str] = []
    tz_cache_manifest: Optional[dict] = None
    pelias_sqlite_digest: Optional[str] = None

    for dataset_id in required_ids + optional_ids:
        entry = find_dataset_entry(dictionary_3b, dataset_id).entry
        reg_entry = find_artifact_entry(registry_3b, dataset_id).entry
        schema_ref = _validate_schema_ref(
            entry.get("schema_ref"),
            schema_3b,
            schema_3a,
            schema_2b,
            schema_2a,
            schema_1b,
            schema_1a,
            schema_layer1,
            schema_ingress,
        )
        resolved_path = _resolve_dataset_path(entry, run_paths, config.external_roots, tokens)
        if not resolved_path.exists():
            if dataset_id in optional_ids:
                sealed_optional_missing.append(dataset_id)
                continue
            _abort(
                "E3B_S0_005_SEALED_INPUT_RESOLUTION_FAILED",
                "V-07",
                "required_input_missing",
                {"dataset_id": dataset_id, "path": str(resolved_path)},
                manifest_fingerprint,
            )
        if dataset_id == "tz_timetable_cache":
            tz_cache_manifest = _load_tz_cache_manifest(
                resolved_path,
                schema_2a,
                schema_layer1,
                manifest_fingerprint,
            )
            logger.info(
                "S0: tz_timetable_cache manifest validated (tzdb_archive_sha256=%s, tz_index_digest=%s)",
                tz_cache_manifest.get("tzdb_archive_sha256"),
                tz_cache_manifest.get("tz_index_digest"),
            )
        if dataset_id == "pelias_cached_bundle":
            if pelias_sqlite_digest is None:
                _abort(
                    "E3B_S0_005_SEALED_INPUT_RESOLUTION_FAILED",
                    "V-07",
                    "pelias_sqlite_digest_missing",
                    {"dataset_id": dataset_id},
                    manifest_fingerprint,
                )
            _validate_pelias_bundle(resolved_path, pelias_sqlite_digest, schema_3b, schema_layer1)
            logger.info(
                "S0: pelias_cached_bundle digest verified against sqlite digest=%s",
                pelias_sqlite_digest,
            )
        if dataset_id == "hrsl_raster":
            logger.info("S0: hashing hrsl_raster bytes for manifest_fingerprint=%s", manifest_fingerprint)
        bundle_digest = None
        if dataset_id.startswith("validation_bundle_"):
            bundle_digest = bundle_digests.get(dataset_id)
        if dataset_id.startswith("validation_passed_flag_"):
            bundle_id = dataset_id.replace("validation_passed_flag", "validation_bundle")
            bundle_digest = bundle_digests.get(bundle_id)
        digest_hex, _ = _hash_for_asset(dataset_id, resolved_path, logger, bundle_digest)
        if dataset_id == "pelias_cached_sqlite":
            pelias_sqlite_digest = digest_hex
        registry_digest = reg_entry.get("digest")
        if registry_digest and _HEX64_PATTERN.match(str(registry_digest)) and registry_digest != digest_hex:
            _abort(
                "E3B_S0_006_SEALED_INPUT_DIGEST_MISMATCH",
                "V-07",
                "sealed_digest_mismatch",
                {"dataset_id": dataset_id, "computed": digest_hex, "registry": registry_digest},
                manifest_fingerprint,
            )
        digest_map[dataset_id] = digest_hex
        role = reg_entry.get("role") or entry.get("description") or "input"
        owner = str(entry.get("owner_subsegment") or "unknown")
        license_class = str(reg_entry.get("license") or entry.get("licence") or "unknown")
        catalog_path = _render_catalog_path(entry, tokens)
        sealed_assets.append(
            SealedAsset(
                logical_id=dataset_id,
                owner_segment=owner,
                artefact_kind=str(reg_entry.get("type") or "dataset"),
                path=catalog_path,
                schema_ref=schema_ref,
                sha256_hex=digest_hex,
                role=role,
                license_class=license_class,
            )
        )

    if sealed_optional_missing:
        logger.info("S0: optional inputs missing (not sealed): %s", ", ".join(sealed_optional_missing))

    sealed_assets_sorted = sorted(
        sealed_assets,
        key=lambda asset: (asset.owner_segment, asset.artefact_kind, asset.logical_id, asset.path),
    )

    sealed_inputs_rows = []
    for asset in sealed_assets_sorted:
        sealed_inputs_rows.append(
            {
                "manifest_fingerprint": manifest_fingerprint,
                "owner_segment": asset.owner_segment,
                "artefact_kind": asset.artefact_kind,
                "logical_id": asset.logical_id,
                "path": asset.path,
                "schema_ref": asset.schema_ref,
                "sha256_hex": asset.sha256_hex,
                "role": asset.role,
                "license_class": asset.license_class,
            }
        )

    sealed_schema = _schema_from_pack(schema_3b, "validation/sealed_inputs_3B")
    _inline_external_refs(sealed_schema, schema_layer1, "schemas.layer1.yaml#")
    for row in sealed_inputs_rows:
        errors = list(Draft202012Validator(sealed_schema).iter_errors(row))
        if errors:
            _abort(
                "E3B_S0_007_OUTPUT_SCHEMA_INVALID",
                "V-08",
                "sealed_inputs_schema_invalid",
                {"error": str(errors[0]), "row": row},
                manifest_fingerprint,
            )

    policy_ids_in_inputs = {row["logical_id"] for row in sealed_inputs_rows}
    for policy in sealed_policy_set:
        if policy.get("logical_id") not in policy_ids_in_inputs:
            _abort(
                "E3B_S0_008_OUTPUT_SELF_INCONSISTENT",
                "V-09",
                "policy_missing_from_sealed_inputs",
                {"logical_id": policy.get("logical_id")},
                manifest_fingerprint,
            )

    receipt_entry = find_dataset_entry(dictionary_3b, "s0_gate_receipt_3B").entry
    sealed_entry = find_dataset_entry(dictionary_3b, "sealed_inputs_3B").entry
    receipt_path = _resolve_dataset_path(receipt_entry, run_paths, config.external_roots, tokens)
    sealed_inputs_path = _resolve_dataset_path(sealed_entry, run_paths, config.external_roots, tokens)

    existing_verified_at = None
    if receipt_path.exists():
        try:
            existing_payload = json.loads(receipt_path.read_text(encoding="utf-8"))
            existing_verified_at = existing_payload.get("verified_at_utc")
        except (OSError, json.JSONDecodeError):
            existing_verified_at = None

    verified_at_utc = existing_verified_at or receipt.get("created_utc")
    if not verified_at_utc:
        _abort(
            "E3B_S0_010_INFRASTRUCTURE_IO_ERROR",
            "V-10",
            "missing_created_utc",
            {"receipt_path": str(receipt_path)},
            manifest_fingerprint,
        )

    receipt_registry = find_artifact_entry(registry_3b, "s0_gate_receipt_3B").entry
    receipt_version = receipt_registry.get("semver") or "1.0.0"

    receipt_digests: dict[str, str] = {}

    def _require_digest(dataset_id: str, key: str) -> None:
        digest = digest_map.get(dataset_id)
        if not digest:
            _abort(
                "E3B_S0_008_OUTPUT_SELF_INCONSISTENT",
                "V-09",
                "digest_missing",
                {"dataset_id": dataset_id, "digest_key": key},
                manifest_fingerprint,
            )
        receipt_digests[key] = digest

    _require_digest("mcc_channel_rules", "virtual_rules_digest")
    _require_digest("virtual_settlement_coords", "settlement_coord_digest")
    _require_digest("cdn_country_weights", "cdn_weights_digest")
    _require_digest("hrsl_raster", "hrsl_digest")
    _require_digest("virtual_validation_policy", "virtual_validation_digest")
    _require_digest("cdn_key_digest", "cdn_key_digest")

    if tz_cache_manifest:
        tz_archive = tz_cache_manifest.get("tzdb_archive_sha256")
        tz_index = tz_cache_manifest.get("tz_index_digest")
        if not tz_archive or not tz_index:
            _abort(
                "E3B_S0_008_OUTPUT_SELF_INCONSISTENT",
                "V-09",
                "tz_cache_digest_missing",
                {"tzdb_archive_sha256": tz_archive, "tz_index_digest": tz_index},
                manifest_fingerprint,
            )
        receipt_digests["tzdata_archive_digest"] = str(tz_archive)
        receipt_digests["tz_index_digest"] = str(tz_index)

    receipt_notes = None
    if sealed_optional_missing:
        receipt_notes = f"optional_missing={','.join(sealed_optional_missing)}"

    receipt_payload = {
        "version": str(receipt_version),
        "manifest_fingerprint": manifest_fingerprint,
        "parameter_hash": parameter_hash,
        "seed": int(seed),
        "verified_at_utc": verified_at_utc,
        "upstream_gates": upstream_gates,
        "sealed_policy_set": sealed_policy_set,
        "digests": receipt_digests,
    }
    if receipt_notes:
        receipt_payload["notes"] = receipt_notes

    receipt_schema = _schema_from_pack(schema_3b, "validation/s0_gate_receipt_3B")
    _inline_external_refs(receipt_schema, schema_layer1, "schemas.layer1.yaml#")
    errors = list(Draft202012Validator(receipt_schema).iter_errors(receipt_payload))
    if errors:
        _abort(
            "E3B_S0_007_OUTPUT_SCHEMA_INVALID",
            "V-11",
            "receipt_schema_invalid",
            {"error": str(errors[0])},
            manifest_fingerprint,
        )

    if f"manifest_fingerprint={manifest_fingerprint}" not in receipt_path.as_posix():
        _abort(
            "E3B_S0_008_OUTPUT_SELF_INCONSISTENT",
            "V-12",
            "receipt_path_missing_manifest",
            {"path": str(receipt_path)},
            manifest_fingerprint,
        )
    if f"manifest_fingerprint={manifest_fingerprint}" not in sealed_inputs_path.as_posix():
        _abort(
            "E3B_S0_008_OUTPUT_SELF_INCONSISTENT",
            "V-12",
            "sealed_inputs_path_missing_manifest",
            {"path": str(sealed_inputs_path)},
            manifest_fingerprint,
        )

    _atomic_publish_json(sealed_inputs_path, sealed_inputs_rows, logger, "sealed_inputs_3B")
    _atomic_publish_json(receipt_path, receipt_payload, logger, "s0_gate_receipt_3B")
    elapsed = time.monotonic() - started
    timer.info(f"S0: completed gate and sealed inputs (elapsed={elapsed:.2f}s)")

    return S0GateResult(
        run_id=run_id,
        parameter_hash=parameter_hash,
        manifest_fingerprint=manifest_fingerprint,
        receipt_path=receipt_path,
        sealed_inputs_path=sealed_inputs_path,
    )
