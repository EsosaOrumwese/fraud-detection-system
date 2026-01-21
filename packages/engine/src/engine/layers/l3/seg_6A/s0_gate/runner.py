"""S0 gate-in runner for Segment 6A."""

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


MODULE_NAME = "6A.s0_gate"
SEGMENT = "6A"
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
    logger = get_logger("engine.layers.l3.seg_6A.s0_gate.runner")
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
        if part in node:
            node = node[part]
            continue
        props = node.get("properties") if isinstance(node, dict) else None
        if isinstance(props, dict) and part in props:
            node = props[part]
            continue
        raise ContractError(f"Schema section not found: {path}")
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
        if part in node:
            node = node[part]
            continue
        props = node.get("properties") if isinstance(node, dict) else None
        if isinstance(props, dict) and part in props:
            node = props[part]
            continue
        raise ContractError(f"Schema section not found: {ref}")


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


def _validate_schema_ref(schema_ref: str | None, schema_packs: dict[str, dict]) -> str:
    if not schema_ref:
        raise ContractError("Missing schema_ref.")
    if "#/" not in schema_ref:
        raise ContractError(f"Invalid schema_ref (missing anchor): {schema_ref}")
    prefix = schema_ref.split("#", 1)[0]
    schema_pack = schema_packs.get(prefix)
    if not schema_pack:
        raise ContractError(f"Unknown schema ref: {schema_ref}")
    _schema_anchor_exists(schema_pack, schema_ref)
    return schema_ref


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
    for key in (
        "version",
        "prior_version",
        "config_version",
        "policy_version",
        "schema_version",
        "version_tag",
    ):
        if key in payload and payload[key] is not None:
            return str(payload[key])
    return None


def _policy_version_matches(expected: str, actual: str) -> bool:
    normalized_expected = _normalize_semver(expected)
    normalized_actual = _normalize_semver(actual)
    if not normalized_expected or not normalized_actual:
        return False
    expected_parts = normalized_expected.split(".")
    actual_parts = normalized_actual.split(".")
    if len(expected_parts) > len(actual_parts):
        return False
    return expected_parts == actual_parts[: len(expected_parts)]


def _parse_pass_flag_any(path: Path) -> str:
    if not path.exists():
        raise InputResolutionError(f"Missing PASS flag: {path}")
    content = path.read_text(encoding="utf-8").strip()
    if content.startswith("{"):
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            digest = payload.get("bundle_digest_sha256")
            if isinstance(digest, str) and _HEX64_PATTERN.match(digest):
                return digest
    line = content.splitlines()[0] if content else ""
    line = line.lstrip("\ufeff")
    match = _FLAG_PATTERN.match(line)
    if not match:
        raise InputResolutionError(f"Invalid _passed.flag format: {path}")
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


def _bundle_hash(bundle_root: Path, index_entries: list[dict]) -> tuple[str, int]:
    paths = sorted(entry["path"] for entry in index_entries if entry.get("path"))
    tracker = _ProgressTracker(len(paths), get_logger("engine.layers.l3.seg_6A.s0_gate.runner"), "S0: bundle_hash")
    hasher = hashlib.sha256()
    total_bytes = 0
    for path in paths:
        file_path = bundle_root / path
        if not file_path.exists():
            raise EngineFailure(
                "F4",
                "6A.S0.UPSTREAM_HASHGATE_MISSING",
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
        tracker.update(1)
    return hasher.hexdigest(), total_bytes


def _bundle_hash_from_index(run_root: Path, index_entries: list[dict]) -> tuple[str, int]:
    paths = sorted(entry["path"] for entry in index_entries if entry.get("path"))
    tracker = _ProgressTracker(
        len(paths), get_logger("engine.layers.l3.seg_6A.s0_gate.runner"), "S0: bundle_index_hash"
    )
    hasher = hashlib.sha256()
    total_bytes = 0
    for rel_path in paths:
        file_path = run_root / rel_path
        if not file_path.exists():
            raise EngineFailure(
                "F4",
                "6A.S0.UPSTREAM_HASHGATE_MISSING",
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
        tracker.update(1)
    return hasher.hexdigest(), total_bytes


def _sha256_concat_hex(parts: Iterable[str]) -> str:
    hasher = hashlib.sha256()
    for part in parts:
        hasher.update(part.encode("ascii"))
    return hasher.hexdigest()


def _validate_index_entries(index_entries: list[dict], index_path: Path) -> list[str]:
    paths = []
    for entry in index_entries:
        path = entry.get("path")
        if not isinstance(path, str) or not path:
            raise EngineFailure(
                "F4",
                "6A.S0.UPSTREAM_HASHGATE_SCHEMA_INVALID",
                STATE,
                MODULE_NAME,
                {"detail": "index entry missing path", "path": str(index_path)},
            )
        try:
            path.encode("ascii")
        except UnicodeEncodeError as exc:
            raise EngineFailure(
                "F4",
                "6A.S0.UPSTREAM_HASHGATE_SCHEMA_INVALID",
                STATE,
                MODULE_NAME,
                {"detail": f"non-ascii path: {path}", "path": str(index_path)},
            ) from exc
        if "\\" in path or path.startswith(("/", "\\")) or ".." in Path(path).parts or ":" in path:
            raise EngineFailure(
                "F4",
                "6A.S0.UPSTREAM_HASHGATE_SCHEMA_INVALID",
                STATE,
                MODULE_NAME,
                {"detail": f"invalid index path: {path}", "path": str(index_path)},
            )
        paths.append(path)
    if len(set(paths)) != len(paths):
        raise EngineFailure(
            "F4",
            "6A.S0.UPSTREAM_HASHGATE_SCHEMA_INVALID",
            STATE,
            MODULE_NAME,
            {"detail": "duplicate path entries in index.json", "path": str(index_path)},
        )
    return paths


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
                "6A.S0.UPSTREAM_HASHGATE_SCHEMA_INVALID",
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
                "6A.S0.UPSTREAM_HASHGATE_SCHEMA_INVALID",
                STATE,
                MODULE_NAME,
                {"detail": str(errors[0]), "path": str(index_path)},
            )
        entries = list(payload.get("files", []))
    else:
        raise EngineFailure(
            "F4",
            "6A.S0.UPSTREAM_HASHGATE_SCHEMA_INVALID",
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
            "6A.S0.UPSTREAM_HASHGATE_SCHEMA_INVALID",
            STATE,
            MODULE_NAME,
            {"detail": {"missing": missing, "extra": extra}, "path": str(index_path)},
        )
    logger.info(
        "S0: bundle index validated (entries=%d, files=%d) for manifest_fingerprint=%s",
        len(paths),
        len(bundle_rel),
        manifest_fingerprint,
    )
    return entries


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
            "6A.S0.UPSTREAM_HASHGATE_SCHEMA_INVALID",
            STATE,
            MODULE_NAME,
            {"detail": str(errors[0]), "path": str(index_path)},
        )
    members = index_payload.get("members")
    if not isinstance(members, list) or not members:
        raise EngineFailure(
            "F4",
            "6A.S0.UPSTREAM_HASHGATE_SCHEMA_INVALID",
            STATE,
            MODULE_NAME,
            {"detail": "bundle index missing members", "path": str(index_path)},
        )
    for member in members:
        sha256_hex = member.get("sha256_hex") if isinstance(member, dict) else None
        if not isinstance(sha256_hex, str) or not _HEX64_PATTERN.match(sha256_hex):
            raise EngineFailure(
                "F4",
                "6A.S0.UPSTREAM_HASHGATE_SCHEMA_INVALID",
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
            "6A.S0.UPSTREAM_HASHGATE_SCHEMA_INVALID",
            STATE,
            MODULE_NAME,
            {"detail": str(errors[0]), "path": str(index_path)},
        )
    members = index_payload.get("members")
    if not isinstance(members, list) or not members:
        raise EngineFailure(
            "F4",
            "6A.S0.UPSTREAM_HASHGATE_SCHEMA_INVALID",
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


def _bundle_digest_from_entries_with_sha(
    index_entries: list[dict],
    index_path: Path,
) -> str:
    paths = []
    sha_list = []
    for entry in index_entries:
        path = entry.get("path")
        sha256_hex = entry.get("sha256_hex")
        if not isinstance(path, str) or not path:
            raise EngineFailure(
                "F4",
                "6A.S0.UPSTREAM_HASHGATE_SCHEMA_INVALID",
                STATE,
                MODULE_NAME,
                {"detail": "bundle entry missing path", "path": str(index_path)},
            )
        if not isinstance(sha256_hex, str) or not _HEX64_PATTERN.match(sha256_hex):
            raise EngineFailure(
                "F4",
                "6A.S0.UPSTREAM_HASHGATE_SCHEMA_INVALID",
                STATE,
                MODULE_NAME,
                {"detail": "bundle entry sha256_hex invalid", "path": str(index_path)},
            )
        paths.append(path)
        sha_list.append((path, sha256_hex))
    if len(set(paths)) != len(paths):
        raise EngineFailure(
            "F4",
            "6A.S0.UPSTREAM_HASHGATE_SCHEMA_INVALID",
            STATE,
            MODULE_NAME,
            {"detail": "duplicate path entries in index.json", "path": str(index_path)},
        )
    sha_sorted = [sha for _, sha in sorted(sha_list, key=lambda item: item[0])]
    return _sha256_concat_hex(sha_sorted)


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


def _render_path_template(path_template: str, tokens: dict[str, str], allow_wildcards: bool = False) -> str:
    rendered = str(path_template).strip()
    for key, value in tokens.items():
        rendered = rendered.replace(f"{{{key}}}", value)
    if allow_wildcards:
        rendered = rendered.replace("{scenario_id}", "*")
    return rendered


def _resolve_dataset_path(
    entry: dict,
    run_paths: RunPaths,
    external_roots: Iterable[Path],
    tokens: dict[str, str],
    allow_wildcards: bool = False,
) -> Path:
    path_template = entry.get("path")
    if not path_template:
        raise InputResolutionError("Dataset entry missing path.")
    resolved = _render_path_template(path_template, tokens, allow_wildcards=allow_wildcards)
    if resolved.startswith(("data/", "logs/", "reports/")):
        return run_paths.run_root / resolved
    if resolved.startswith("artefacts/"):
        return resolve_input_path(resolved, run_paths, external_roots, allow_run_local=False)
    return resolve_input_path(resolved, run_paths, external_roots, allow_run_local=True)


def _render_catalog_path(entry: dict, tokens: dict[str, str]) -> str:
    path_template = entry.get("path") or ""
    return _render_path_template(path_template, tokens, allow_wildcards=False)


def _path_has_content(path: Path) -> bool:
    if "*" in str(path) or "?" in str(path):
        return bool(list(path.parent.glob(path.name)))
    if not path.exists():
        return False
    if path.is_dir():
        for item in path.rglob("*"):
            if item.is_file():
                return True
        return False
    return True


def _structural_digest(payload: dict) -> str:
    hasher = hashlib.sha256()
    hasher.update(json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    return hasher.hexdigest()


def _sealed_inputs_digest(rows: list[dict]) -> str:
    ordered_fields = (
        "manifest_fingerprint",
        "owner_layer",
        "owner_segment",
        "manifest_key",
        "path_template",
        "partition_keys",
        "schema_ref",
        "role",
        "status",
        "read_scope",
        "sha256_hex",
        "upstream_bundle_id",
        "notes",
    )
    hasher = hashlib.sha256()
    for row in rows:
        canonical = {field: row.get(field) for field in ordered_fields}
        hasher.update(
            json.dumps(canonical, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
        )
    return hasher.hexdigest()


def _normalize_status(value: Optional[str]) -> str:
    text = str(value or "").strip().lower()
    if text == "required":
        return "REQUIRED"
    if text == "optional":
        return "OPTIONAL"
    if text == "ignored":
        return "IGNORED"
    return "REQUIRED"


def _owner_layer(entry: dict, owner_segment: str) -> int:
    owner_value = entry.get("owner_layer")
    if isinstance(owner_value, int):
        return owner_value
    if owner_segment and owner_segment[0].isdigit():
        if owner_segment[0] in {"1", "2", "3"}:
            return int(owner_segment[0])
    if owner_segment.startswith("6"):
        return 3
    return 3


def _role_for_dataset(dataset_id: str, owner_segment: str, schema_ref: str) -> str:
    if dataset_id.startswith("validation_bundle_"):
        return "UPSTREAM_GATE_BUNDLE"
    if dataset_id.startswith("validation_passed_flag_"):
        return "UPSTREAM_GATE_FLAG"
    if schema_ref.startswith("schemas.6A.yaml#/prior/population"):
        return "POPULATION_PRIOR"
    if schema_ref.startswith("schemas.6A.yaml#/prior/segmentation"):
        return "SEGMENT_PRIOR"
    if schema_ref.startswith("schemas.6A.yaml#/prior/"):
        if "device" in dataset_id or "ip" in dataset_id:
            return "DEVICE_IP_PRIOR"
        if "role" in dataset_id:
            return "FRAUD_ROLE_PRIOR"
        return "PRODUCT_PRIOR"
    if schema_ref.startswith("schemas.6A.yaml#/taxonomy/"):
        return "TAXONOMY"
    if schema_ref.startswith("schemas.6A.yaml#/policy/"):
        return "POLICY"
    if owner_segment in {"1A", "1B", "2A", "2B", "3A", "3B", "5A", "5B"}:
        return "UPSTREAM_EGRESS"
    return "DATASET"


def _read_scope_for_role(role: str) -> str:
    if role in {"UPSTREAM_GATE_BUNDLE", "UPSTREAM_GATE_FLAG", "CONTRACT"}:
        return "METADATA_ONLY"
    return "ROW_LEVEL"


def _assert_schema_defs_consistent(schema_layer3: dict, schema_6a: dict) -> None:
    defs_layer3 = schema_layer3.get("$defs") or {}
    defs_6a = schema_6a.get("$defs") or {}
    conflicts = []
    for key in sorted(set(defs_layer3) & set(defs_6a)):
        left = defs_layer3[key]
        right = defs_6a[key]
        if json.dumps(left, sort_keys=True) == json.dumps(right, sort_keys=True):
            continue
        ref_target = f"schemas.layer3.yaml#/$defs/{key}"
        if isinstance(left, dict) and left.get("$ref") == ref_target and len(left) == 1:
            continue
        if isinstance(right, dict) and right.get("$ref") == ref_target and len(right) == 1:
            continue
        conflicts.append(key)
    if conflicts:
        raise ContractError(f"Conflicting $defs between layer3 and 6A schemas: {conflicts}")


def _relative_path(path: Path, repo_root: Path) -> str:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


def _validate_payload(
    payload: object,
    schema_pack: dict,
    schema_layer3: dict,
    schema_anchor: str,
    manifest_fingerprint: str,
    context: dict,
) -> None:
    schema = _schema_from_pack(schema_pack, schema_anchor)
    _inline_external_refs(schema, schema_layer3, "schemas.layer3.yaml#")
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    if errors:
        raise EngineFailure(
            "F4",
            "6A.S0.L3_SCHEMA_MISSING_OR_INVALID",
            STATE,
            MODULE_NAME,
            {"detail": str(errors[0]), "context": context, "manifest_fingerprint": manifest_fingerprint},
        )


def _validate_registry_alignment(entry: dict, reg_entry: dict) -> None:
    entry_path = str(entry.get("path") or "").strip().rstrip("/")
    registry_path = str(reg_entry.get("path") or "").strip().rstrip("/")
    if entry_path and registry_path and entry_path != registry_path:
        raise ContractError(f"Registry path mismatch: {entry_path} != {registry_path}")
    entry_schema = str(entry.get("schema_ref") or "").strip()
    registry_schema = str(reg_entry.get("schema") or reg_entry.get("schema_ref") or "").strip()
    if registry_schema and entry_schema and registry_schema != entry_schema:
        raise ContractError(f"Registry schema mismatch: {entry_schema} != {registry_schema}")


def _atomic_publish_json(path: Path, payload: object) -> None:
    tmp_dir = path.parent / f"_tmp.{uuid.uuid4().hex}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / path.name
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        tmp_path.replace(path)
    except OSError as exc:
        raise EngineFailure(
            "F4",
            "6A.S0.IO_WRITE_FAILED",
            STATE,
            MODULE_NAME,
            {"detail": "atomic publish failed", "path": str(path), "error": str(exc)},
        ) from exc
    try:
        tmp_dir.rmdir()
    except OSError:
        pass


def _s0_input_entries(dictionary: dict) -> list[dict]:
    entries = []
    for value in dictionary.values():
        if not isinstance(value, list):
            continue
        for entry in value:
            if not isinstance(entry, dict):
                continue
            lineage = entry.get("lineage") or {}
            consumed_by = lineage.get("consumed_by") or []
            if "6A.S0" in consumed_by:
                entries.append(entry)
    return entries


def run_s0(config: EngineConfig, run_id: Optional[str] = None) -> S0GateResult:
    logger = get_logger("engine.layers.l3.seg_6A.s0_gate.runner")
    timer = _StepTimer(logger)
    started = time.monotonic()
    started_utc = utc_now_rfc3339_micro()

    status = "FAIL"
    error_code: Optional[str] = None
    error_detail: Optional[dict] = None

    upstream_segments: dict[str, dict] = {}
    bundle_digests: dict[str, str] = {}
    sealed_rows: list[dict] = []
    sealed_inputs_digest: Optional[str] = None

    run_id_value = ""
    parameter_hash = ""
    manifest_fingerprint = ""
    seed: Optional[int] = None

    dictionary_6a: Optional[dict] = None
    registry_6a: Optional[dict] = None
    schema_6a: Optional[dict] = None
    schema_layer3: Optional[dict] = None
    schema_5b: Optional[dict] = None
    schema_5a: Optional[dict] = None
    schema_layer2: Optional[dict] = None
    schema_3b: Optional[dict] = None
    schema_3a: Optional[dict] = None
    schema_2b: Optional[dict] = None
    schema_2a: Optional[dict] = None
    schema_1b: Optional[dict] = None
    schema_1a: Optional[dict] = None
    schema_layer1: Optional[dict] = None

    try:
        receipt_path, receipt = _resolve_run_receipt(config.runs_root, run_id)
        run_id_value = str(receipt.get("run_id") or "")
        if not run_id_value:
            _abort(
                "6A.S0.IO_READ_FAILED",
                "V-01",
                "run_receipt_missing_run_id",
                {"path": str(receipt_path)},
                None,
            )
        if receipt_path.parent.name != run_id_value:
            _abort(
                "6A.S0.IO_READ_FAILED",
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
                "6A.S0.IO_READ_FAILED",
                "V-01",
                "run_receipt_missing_fields",
                {"seed": seed, "parameter_hash": parameter_hash, "manifest_fingerprint": manifest_fingerprint},
                manifest_fingerprint or None,
            )
        if not _HEX64_PATTERN.match(parameter_hash) or not _HEX64_PATTERN.match(manifest_fingerprint):
            _abort(
                "6A.S0.IO_READ_FAILED",
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
            dict_6a_path, dictionary_6a = load_dataset_dictionary(source, "6A")
            reg_6a_path, registry_6a = load_artefact_registry(source, "6A")
            schema_6a_path, schema_6a = load_schema_pack(source, "6A", "6A")
            schema_layer3_path, schema_layer3 = load_schema_pack(source, "6A", "layer3")
            schema_5b_path, schema_5b = load_schema_pack(source, "5B", "5B")
            schema_5a_path, schema_5a = load_schema_pack(source, "5A", "5A")
            schema_layer2_path, schema_layer2 = load_schema_pack(source, "5A", "layer2")
            schema_3b_path, schema_3b = load_schema_pack(source, "3B", "3B")
            schema_3a_path, schema_3a = load_schema_pack(source, "3A", "3A")
            schema_2b_path, schema_2b = load_schema_pack(source, "2B", "2B")
            schema_2a_path, schema_2a = load_schema_pack(source, "2A", "2A")
            schema_1b_path, schema_1b = load_schema_pack(source, "1B", "1B")
            schema_1a_path, schema_1a = load_schema_pack(source, "1A", "1A")
            schema_layer1_path, schema_layer1 = load_schema_pack(source, "1A", "layer1")
        except ContractError as exc:
            _abort(
                "6A.S0.L3_SCHEMA_MISSING_OR_INVALID",
                "V-02",
                "contract_load_failed",
                {"detail": str(exc)},
                manifest_fingerprint,
            )

        logger.info(
            "Contracts layout=%s root=%s dictionary=%s registry=%s schemas=%s,%s",
            config.contracts_layout,
            str(config.contracts_root),
            str(dict_6a_path),
            str(reg_6a_path),
            str(schema_6a_path),
            str(schema_layer3_path),
        )

        logger.info(
            "S0: story objective=gate upstream 1A-3B + 5A-5B and seal 6A inputs -> outputs (s0_gate_receipt_6A, sealed_inputs_6A)"
        )

        _assert_schema_defs_consistent(schema_layer3, schema_6a)

        schema_packs = {
            "schemas.layer3.yaml": schema_layer3,
            "schemas.6A.yaml": schema_6a,
            "schemas.5B.yaml": schema_5b,
            "schemas.5A.yaml": schema_5a,
            "schemas.layer2.yaml": schema_layer2,
            "schemas.3B.yaml": schema_3b,
            "schemas.3A.yaml": schema_3a,
            "schemas.2B.yaml": schema_2b,
            "schemas.2A.yaml": schema_2a,
            "schemas.1B.yaml": schema_1b,
            "schemas.1A.yaml": schema_1a,
            "schemas.layer1.yaml": schema_layer1,
        }

        tokens = {
            "seed": str(seed),
            "parameter_hash": parameter_hash,
            "manifest_fingerprint": manifest_fingerprint,
            "run_id": run_id_value,
        }

        gate_map = {
            "1A": ("validation_bundle_1A", "validation_passed_flag_1A", schema_1a, "validation/validation_bundle_index_1A"),
            "1B": ("validation_bundle_1B", "validation_passed_flag_1B", schema_1b, "validation/validation_bundle_index_1B"),
            "2A": ("validation_bundle_2A", "validation_passed_flag_2A", schema_2a, "validation/validation_bundle_index_2A"),
        }

        for segment_id, (bundle_id, flag_id, schema_pack, index_anchor) in gate_map.items():
            bundle_entry = find_dataset_entry(dictionary_6a, bundle_id).entry
            flag_entry = find_dataset_entry(dictionary_6a, flag_id).entry
            bundle_root = _resolve_dataset_path(bundle_entry, run_paths, config.external_roots, tokens)
            flag_path = _resolve_dataset_path(flag_entry, run_paths, config.external_roots, tokens)
            if not bundle_root.exists():
                _abort(
                    "6A.S0.UPSTREAM_HASHGATE_MISSING",
                    "V-03",
                    "validation_bundle_missing",
                    {"bundle_id": bundle_id, "path": str(bundle_root)},
                    manifest_fingerprint,
                )
            index_path = bundle_root / "index.json"
            try:
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
                flag_digest = _parse_pass_flag_any(flag_path)
            except (EngineFailure, InputResolutionError) as exc:
                _abort(
                    "6A.S0.UPSTREAM_HASHGATE_SCHEMA_INVALID",
                    "V-03",
                    "validation_bundle_invalid",
                    {"bundle_id": bundle_id, "detail": str(exc)},
                    manifest_fingerprint,
                )
            if bundle_digest != flag_digest:
                _abort(
                    "6A.S0.UPSTREAM_HASHGATE_DIGEST_MISMATCH",
                    "V-03",
                    "hashgate_mismatch",
                    {"bundle_id": bundle_id, "expected": bundle_digest, "actual": flag_digest},
                    manifest_fingerprint,
                )
            bundle_digests[bundle_id] = bundle_digest
            upstream_segments[segment_id] = {
                "status": "PASS",
                "bundle_path": _render_catalog_path(bundle_entry, tokens),
                "bundle_sha256": bundle_digest,
                "flag_path": _render_catalog_path(flag_entry, tokens),
            }
            logger.info(
                "S0: upstream_gate segment=%s status=PASS digest=%s law=index_files",
                segment_id,
                bundle_digest,
            )

        bundle_entry = find_dataset_entry(dictionary_6a, "validation_bundle_2B").entry
        flag_entry = find_dataset_entry(dictionary_6a, "validation_passed_flag_2B").entry
        index_path = _resolve_dataset_path(bundle_entry, run_paths, config.external_roots, tokens)
        flag_path = _resolve_dataset_path(flag_entry, run_paths, config.external_roots, tokens)
        if not index_path.exists():
            _abort(
                "6A.S0.UPSTREAM_HASHGATE_MISSING",
                "V-03",
                "validation_bundle_missing",
                {"bundle_id": "validation_bundle_2B", "path": str(index_path)},
                manifest_fingerprint,
            )
        try:
            index_payload = _load_json(index_path)
            schema = _schema_from_pack(schema_2b, "validation/validation_bundle_index_2B")
            _inline_external_refs(schema, schema_layer1, "schemas.layer1.yaml#")
            errors = list(Draft202012Validator(schema).iter_errors(index_payload))
            if errors:
                raise EngineFailure(
                    "F4",
                    "6A.S0.UPSTREAM_HASHGATE_SCHEMA_INVALID",
                    STATE,
                    MODULE_NAME,
                    {"detail": str(errors[0]), "path": str(index_path)},
                )
            if not isinstance(index_payload, list):
                raise EngineFailure(
                    "F4",
                    "6A.S0.UPSTREAM_HASHGATE_SCHEMA_INVALID",
                    STATE,
                    MODULE_NAME,
                    {"detail": "2B index.json is not a list", "path": str(index_path)},
                )
            _validate_index_entries(index_payload, index_path)
            bundle_digest, _ = _bundle_hash_from_index(run_paths.run_root, index_payload)
            flag_digest = _parse_pass_flag_any(flag_path)
        except (EngineFailure, InputResolutionError) as exc:
            _abort(
                "6A.S0.UPSTREAM_HASHGATE_SCHEMA_INVALID",
                "V-03",
                "validation_bundle_invalid",
                {"bundle_id": "validation_bundle_2B", "detail": str(exc)},
                manifest_fingerprint,
            )
        if bundle_digest != flag_digest:
            _abort(
                "6A.S0.UPSTREAM_HASHGATE_DIGEST_MISMATCH",
                "V-03",
                "hashgate_mismatch",
                {"bundle_id": "validation_bundle_2B", "expected": bundle_digest, "actual": flag_digest},
                manifest_fingerprint,
            )
        bundle_digests["validation_bundle_2B"] = bundle_digest
        upstream_segments["2B"] = {
            "status": "PASS",
            "bundle_path": _render_catalog_path(bundle_entry, tokens),
            "bundle_sha256": bundle_digest,
            "flag_path": _render_catalog_path(flag_entry, tokens),
        }
        logger.info(
            "S0: upstream_gate segment=2B status=PASS digest=%s law=index_paths",
            bundle_digest,
        )

        bundle_entry = find_dataset_entry(dictionary_6a, "validation_bundle_3A").entry
        flag_entry = find_dataset_entry(dictionary_6a, "validation_passed_flag_3A").entry
        bundle_root = _resolve_dataset_path(bundle_entry, run_paths, config.external_roots, tokens)
        flag_path = _resolve_dataset_path(flag_entry, run_paths, config.external_roots, tokens)
        if not bundle_root.exists():
            _abort(
                "6A.S0.UPSTREAM_HASHGATE_MISSING",
                "V-03",
                "validation_bundle_missing",
                {"bundle_id": "validation_bundle_3A", "path": str(bundle_root)},
                manifest_fingerprint,
            )
        index_path = bundle_root / "index.json"
        try:
            index_payload = _load_json(index_path)
            bundle_digest = _bundle_digest_from_members(
                index_payload, schema_layer1, logger, manifest_fingerprint, index_path
            )
            flag_digest = _parse_pass_flag_any(flag_path)
        except (EngineFailure, InputResolutionError) as exc:
            _abort(
                "6A.S0.UPSTREAM_HASHGATE_SCHEMA_INVALID",
                "V-03",
                "validation_bundle_invalid",
                {"bundle_id": "validation_bundle_3A", "detail": str(exc)},
                manifest_fingerprint,
            )
        if bundle_digest != flag_digest:
            _abort(
                "6A.S0.UPSTREAM_HASHGATE_DIGEST_MISMATCH",
                "V-03",
                "hashgate_mismatch",
                {"bundle_id": "validation_bundle_3A", "expected": bundle_digest, "actual": flag_digest},
                manifest_fingerprint,
            )
        bundle_digests["validation_bundle_3A"] = bundle_digest
        upstream_segments["3A"] = {
            "status": "PASS",
            "bundle_path": _render_catalog_path(bundle_entry, tokens),
            "bundle_sha256": bundle_digest,
            "flag_path": _render_catalog_path(flag_entry, tokens),
        }
        logger.info(
            "S0: upstream_gate segment=3A status=PASS digest=%s law=index_members",
            bundle_digest,
        )

        bundle_entry = find_dataset_entry(dictionary_6a, "validation_bundle_3B").entry
        flag_entry = find_dataset_entry(dictionary_6a, "validation_passed_flag_3B").entry
        bundle_root = _resolve_dataset_path(bundle_entry, run_paths, config.external_roots, tokens)
        flag_path = _resolve_dataset_path(flag_entry, run_paths, config.external_roots, tokens)
        if not bundle_root.exists():
            _abort(
                "6A.S0.UPSTREAM_HASHGATE_MISSING",
                "V-03",
                "validation_bundle_missing",
                {"bundle_id": "validation_bundle_3B", "path": str(bundle_root)},
                manifest_fingerprint,
            )
        index_path = bundle_root / "index.json"
        try:
            index_payload = _load_json(index_path)
            bundle_digest = _bundle_digest_from_member_files(
                bundle_root, index_payload, schema_layer1, logger, manifest_fingerprint, index_path
            )
            flag_digest = _parse_pass_flag_any(flag_path)
        except (EngineFailure, InputResolutionError) as exc:
            _abort(
                "6A.S0.UPSTREAM_HASHGATE_SCHEMA_INVALID",
                "V-03",
                "validation_bundle_invalid",
                {"bundle_id": "validation_bundle_3B", "detail": str(exc)},
                manifest_fingerprint,
            )
        if bundle_digest != flag_digest:
            _abort(
                "6A.S0.UPSTREAM_HASHGATE_DIGEST_MISMATCH",
                "V-03",
                "hashgate_mismatch",
                {"bundle_id": "validation_bundle_3B", "expected": bundle_digest, "actual": flag_digest},
                manifest_fingerprint,
            )
        bundle_digests["validation_bundle_3B"] = bundle_digest
        upstream_segments["3B"] = {
            "status": "PASS",
            "bundle_path": _render_catalog_path(bundle_entry, tokens),
            "bundle_sha256": bundle_digest,
            "flag_path": _render_catalog_path(flag_entry, tokens),
        }
        logger.info(
            "S0: upstream_gate segment=3B status=PASS digest=%s law=index_files",
            bundle_digest,
        )

        bundle_entry = find_dataset_entry(dictionary_6a, "validation_bundle_5A").entry
        flag_entry = find_dataset_entry(dictionary_6a, "validation_passed_flag_5A").entry
        bundle_root = _resolve_dataset_path(bundle_entry, run_paths, config.external_roots, tokens)
        flag_path = _resolve_dataset_path(flag_entry, run_paths, config.external_roots, tokens)
        if not bundle_root.exists():
            _abort(
                "6A.S0.UPSTREAM_HASHGATE_MISSING",
                "V-03",
                "validation_bundle_missing",
                {"bundle_id": "validation_bundle_5A", "path": str(bundle_root)},
                manifest_fingerprint,
            )
        index_path = bundle_root / "validation_bundle_index_5A.json"
        try:
            index_payload = _load_json(index_path)
            schema = _schema_from_pack(schema_layer2, "validation/validation_bundle_index_5A")
            _inline_external_refs(schema, schema_layer1, "schemas.layer1.yaml#")
            errors = list(Draft202012Validator(schema).iter_errors(index_payload))
            if errors:
                raise EngineFailure(
                    "F4",
                    "6A.S0.UPSTREAM_HASHGATE_SCHEMA_INVALID",
                    STATE,
                    MODULE_NAME,
                    {"detail": str(errors[0]), "path": str(index_path)},
                )
            entries = index_payload.get("entries")
            if not isinstance(entries, list):
                raise EngineFailure(
                    "F4",
                    "6A.S0.UPSTREAM_HASHGATE_SCHEMA_INVALID",
                    STATE,
                    MODULE_NAME,
                    {"detail": "validation_bundle_index_5A missing entries", "path": str(index_path)},
                )
            _validate_index_entries(entries, index_path)
            bundle_digest, _ = _bundle_hash(bundle_root, entries)
            flag_digest = _parse_pass_flag_any(flag_path)
        except (EngineFailure, InputResolutionError) as exc:
            _abort(
                "6A.S0.UPSTREAM_HASHGATE_SCHEMA_INVALID",
                "V-03",
                "validation_bundle_invalid",
                {"bundle_id": "validation_bundle_5A", "detail": str(exc)},
                manifest_fingerprint,
            )
        if bundle_digest != flag_digest:
            _abort(
                "6A.S0.UPSTREAM_HASHGATE_DIGEST_MISMATCH",
                "V-03",
                "hashgate_mismatch",
                {"bundle_id": "validation_bundle_5A", "expected": bundle_digest, "actual": flag_digest},
                manifest_fingerprint,
            )
        bundle_digests["validation_bundle_5A"] = bundle_digest
        upstream_segments["5A"] = {
            "status": "PASS",
            "bundle_path": _render_catalog_path(bundle_entry, tokens),
            "bundle_sha256": bundle_digest,
            "flag_path": _render_catalog_path(flag_entry, tokens),
        }
        logger.info(
            "S0: upstream_gate segment=5A status=PASS digest=%s law=index_entries",
            bundle_digest,
        )

        bundle_entry = find_dataset_entry(dictionary_6a, "validation_bundle_5B").entry
        flag_entry = find_dataset_entry(dictionary_6a, "validation_passed_flag_5B").entry
        bundle_root = _resolve_dataset_path(bundle_entry, run_paths, config.external_roots, tokens)
        flag_path = _resolve_dataset_path(flag_entry, run_paths, config.external_roots, tokens)
        if not bundle_root.exists():
            _abort(
                "6A.S0.UPSTREAM_HASHGATE_MISSING",
                "V-03",
                "validation_bundle_missing",
                {"bundle_id": "validation_bundle_5B", "path": str(bundle_root)},
                manifest_fingerprint,
            )
        index_path = bundle_root / "index.json"
        try:
            index_payload = _load_json(index_path)
            schema = _schema_from_pack(schema_layer2, "validation/validation_bundle_index_5B")
            _inline_external_refs(schema, schema_layer1, "schemas.layer1.yaml#")
            errors = list(Draft202012Validator(schema).iter_errors(index_payload))
            if errors:
                raise EngineFailure(
                    "F4",
                    "6A.S0.UPSTREAM_HASHGATE_SCHEMA_INVALID",
                    STATE,
                    MODULE_NAME,
                    {"detail": str(errors[0]), "path": str(index_path)},
                )
            entries = index_payload.get("entries")
            if not isinstance(entries, list):
                raise EngineFailure(
                    "F4",
                    "6A.S0.UPSTREAM_HASHGATE_SCHEMA_INVALID",
                    STATE,
                    MODULE_NAME,
                    {"detail": "validation_bundle_index_5B missing entries", "path": str(index_path)},
                )
            _validate_index_entries(entries, index_path)
            bundle_digest, _ = _bundle_hash(bundle_root, entries)
            flag_digest = _parse_pass_flag_any(flag_path)
        except (EngineFailure, InputResolutionError) as exc:
            _abort(
                "6A.S0.UPSTREAM_HASHGATE_SCHEMA_INVALID",
                "V-03",
                "validation_bundle_invalid",
                {"bundle_id": "validation_bundle_5B", "detail": str(exc)},
                manifest_fingerprint,
            )
        if bundle_digest != flag_digest:
            _abort(
                "6A.S0.UPSTREAM_HASHGATE_DIGEST_MISMATCH",
                "V-03",
                "hashgate_mismatch",
                {"bundle_id": "validation_bundle_5B", "expected": bundle_digest, "actual": flag_digest},
                manifest_fingerprint,
            )
        bundle_digests["validation_bundle_5B"] = bundle_digest
        upstream_segments["5B"] = {
            "status": "PASS",
            "bundle_path": _render_catalog_path(bundle_entry, tokens),
            "bundle_sha256": bundle_digest,
            "flag_path": _render_catalog_path(flag_entry, tokens),
        }
        logger.info(
            "S0: upstream_gate segment=5B status=PASS digest=%s law=index_sha",
            bundle_digest,
        )

        s0_entries = _s0_input_entries(dictionary_6a)
        if not s0_entries:
            _abort(
                "6A.S0.SEALED_INPUTS_EMPTY",
                "V-06",
                "sealed_inputs_empty",
                {"detail": "No dictionary entries list 6A.S0 in consumed_by."},
                manifest_fingerprint,
            )

        contract_schema_ref = "schemas.layer3.yaml#/$defs/contract_file"
        try:
            _validate_schema_ref(contract_schema_ref, schema_packs)
        except ContractError as exc:
            _abort(
                "6A.S0.L3_SCHEMA_MISSING_OR_INVALID",
                "V-04",
                "contract_schema_ref_invalid",
                {"schema_ref": contract_schema_ref, "detail": str(exc)},
                manifest_fingerprint,
            )
        contract_specs = [
            ("contracts.dataset_dictionary.layer3.6A", dict_6a_path),
            ("contracts.artefact_registry_6A", reg_6a_path),
            ("contracts.schemas.6A", schema_6a_path),
            ("contracts.schemas.layer3", schema_layer3_path),
        ]
        contracts_6a: dict[str, dict] = {}
        for logical_id, contract_path in contract_specs:
            try:
                digest_hex = sha256_file(contract_path)
            except (HashingError, OSError) as exc:
                _abort(
                    "6A.S0.L3_SCHEMA_MISSING_OR_INVALID",
                    "V-04",
                    "contract_digest_failed",
                    {"logical_id": logical_id, "path": str(contract_path), "detail": str(exc)},
                    manifest_fingerprint,
                )
            relative_path = _relative_path(contract_path, config.repo_root)
            contracts_6a[logical_id] = {
                "logical_id": logical_id,
                "path": relative_path,
                "sha256_hex": digest_hex,
                "schema_ref": contract_schema_ref,
                "role": "CONTRACT",
            }
            sealed_rows.append(
                {
                    "manifest_fingerprint": manifest_fingerprint,
                    "owner_layer": 3,
                    "owner_segment": SEGMENT,
                    "manifest_key": logical_id,
                    "path_template": relative_path,
                    "partition_keys": [],
                    "schema_ref": contract_schema_ref,
                    "role": "CONTRACT",
                    "status": "REQUIRED",
                    "read_scope": "METADATA_ONLY",
                    "sha256_hex": digest_hex,
                    "upstream_bundle_id": None,
                    "notes": "contract_file",
                }
            )

        optional_missing: list[str] = []
        seen_keys: set[tuple[int, str, str]] = set()

        for entry in s0_entries:
            dataset_id = str(entry.get("id") or "").strip()
            if not dataset_id:
                _abort(
                    "6A.S0.DICTIONARY_OR_REGISTRY_INCONSISTENT",
                    "V-04",
                    "dataset_id_missing",
                    {"entry": entry},
                    manifest_fingerprint,
                )
            try:
                reg_entry = find_artifact_entry(registry_6a, dataset_id).entry
            except ContractError as exc:
                _abort(
                    "6A.S0.SEALED_INPUTS_ARTIFACT_UNRESOLVED",
                    "V-06",
                    "registry_missing",
                    {"dataset_id": dataset_id, "detail": str(exc)},
                    manifest_fingerprint,
                )
            try:
                _validate_registry_alignment(entry, reg_entry)
            except ContractError as exc:
                _abort(
                    "6A.S0.DICTIONARY_OR_REGISTRY_INCONSISTENT",
                    "V-04",
                    "registry_alignment_failed",
                    {"dataset_id": dataset_id, "detail": str(exc)},
                    manifest_fingerprint,
                )
            try:
                schema_ref = _validate_schema_ref(entry.get("schema_ref"), schema_packs)
            except ContractError as exc:
                _abort(
                    "6A.S0.SCHEMA_REF_UNRESOLVED",
                    "V-04",
                    "schema_ref_invalid",
                    {"dataset_id": dataset_id, "detail": str(exc)},
                    manifest_fingerprint,
                )

            status_value = _normalize_status(entry.get("status"))
            owner_segment = str(entry.get("owner_segment") or entry.get("owner_subsegment") or SEGMENT)
            owner_layer = _owner_layer(entry, owner_segment)
            manifest_key = str(reg_entry.get("manifest_key") or dataset_id)
            catalog_path = str(entry.get("path") or "")
            partition_keys = list(entry.get("partitioning") or [])
            role = _role_for_dataset(dataset_id, owner_segment, schema_ref)
            read_scope = _read_scope_for_role(role)

            digest_hex = ""
            upstream_bundle_id: Optional[str] = None
            notes: Optional[str] = None

            if status_value == "IGNORED":
                digest_hex = _structural_digest(
                    {
                        "manifest_key": manifest_key,
                        "schema_ref": schema_ref,
                        "path_template": catalog_path,
                        "partition_keys": partition_keys,
                    }
                )
                notes = "ignored; structural_digest=path_template"
            elif dataset_id.startswith("validation_bundle_") or dataset_id.startswith("validation_passed_flag_"):
                bundle_id = dataset_id
                if dataset_id.startswith("validation_passed_flag_"):
                    bundle_id = dataset_id.replace("validation_passed_flag_", "validation_bundle_")
                digest_hex = bundle_digests.get(bundle_id, "")
                if not digest_hex:
                    _abort(
                        "6A.S0.SEALED_INPUTS_ARTIFACT_UNRESOLVED",
                        "V-06",
                        "bundle_digest_missing",
                        {"dataset_id": dataset_id, "bundle_id": bundle_id},
                        manifest_fingerprint,
                    )
                upstream_bundle_id = bundle_id
                notes = "bundle_digest=index_sha"
            elif schema_ref.startswith("schemas.6A.yaml#/prior/") or schema_ref.startswith(
                "schemas.6A.yaml#/taxonomy/"
            ) or schema_ref.startswith("schemas.6A.yaml#/policy/"):
                try:
                    resolved_path = _resolve_dataset_path(entry, run_paths, config.external_roots, tokens)
                except InputResolutionError as exc:
                    if status_value == "OPTIONAL":
                        optional_missing.append(dataset_id)
                        logger.info("S0: optional prior missing dataset_id=%s detail=%s", dataset_id, str(exc))
                        continue
                    _abort(
                        "6A.S0.PRIOR_PACK_MISSING",
                        "V-05",
                        "prior_pack_missing",
                        {"dataset_id": dataset_id, "detail": str(exc)},
                        manifest_fingerprint,
                    )
                if not _path_has_content(resolved_path):
                    if status_value == "OPTIONAL":
                        optional_missing.append(dataset_id)
                        logger.info("S0: optional prior missing dataset_id=%s path=%s", dataset_id, resolved_path)
                        continue
                    _abort(
                        "6A.S0.PRIOR_PACK_MISSING",
                        "V-05",
                        "prior_pack_missing",
                        {"dataset_id": dataset_id, "path": str(resolved_path)},
                        manifest_fingerprint,
                    )
                try:
                    payload = _load_yaml(resolved_path) if resolved_path.suffix in {".yaml", ".yml"} else _load_json(
                        resolved_path
                    )
                except (OSError, json.JSONDecodeError, yaml.YAMLError) as exc:
                    _abort(
                        "6A.S0.PRIOR_PACK_SCHEMA_INVALID",
                        "V-05",
                        "prior_pack_parse_failed",
                        {"dataset_id": dataset_id, "path": str(resolved_path), "detail": str(exc)},
                        manifest_fingerprint,
                    )
                anchor = schema_ref.split("#", 1)[1].strip("/")
                try:
                    _validate_payload(
                        payload,
                        schema_packs[schema_ref.split("#", 1)[0]],
                        schema_layer3,
                        anchor,
                        manifest_fingerprint,
                        {"dataset_id": dataset_id},
                    )
                except EngineFailure as exc:
                    _abort(
                        "6A.S0.PRIOR_PACK_SCHEMA_INVALID",
                        "V-05",
                        "prior_pack_schema_invalid",
                        {"dataset_id": dataset_id, "detail": str(exc)},
                        manifest_fingerprint,
                    )
                try:
                    digest_hex = sha256_file(resolved_path)
                except (HashingError, OSError) as exc:
                    _abort(
                        "6A.S0.IO_READ_FAILED",
                        "V-05",
                        "prior_pack_digest_failed",
                        {"dataset_id": dataset_id, "path": str(resolved_path), "detail": str(exc)},
                        manifest_fingerprint,
                    )
                expected_digest = reg_entry.get("digest")
                if isinstance(expected_digest, str) and expected_digest and not _is_placeholder(expected_digest):
                    if digest_hex != expected_digest:
                        _abort(
                            "6A.S0.PRIOR_PACK_DIGEST_MISMATCH",
                            "V-05",
                            "prior_pack_digest_mismatch",
                            {
                                "dataset_id": dataset_id,
                                "expected": expected_digest,
                                "actual": digest_hex,
                            },
                            manifest_fingerprint,
                        )
                notes = "content_digest=sha256"
            else:
                digest_hex = _structural_digest(
                    {
                        "manifest_key": manifest_key,
                        "schema_ref": schema_ref,
                        "path_template": catalog_path,
                        "partition_keys": partition_keys,
                    }
                )
                notes = "structural_digest=path_template"

            key = (owner_layer, owner_segment, manifest_key)
            if key in seen_keys:
                _abort(
                    "6A.S0.SEALED_INPUTS_ROW_CONFLICT",
                    "V-06",
                    "sealed_inputs_duplicate_key",
                    {"owner_layer": owner_layer, "owner_segment": owner_segment, "manifest_key": manifest_key},
                    manifest_fingerprint,
                )
            seen_keys.add(key)

            sealed_rows.append(
                {
                    "manifest_fingerprint": manifest_fingerprint,
                    "owner_layer": owner_layer,
                    "owner_segment": owner_segment,
                    "manifest_key": manifest_key,
                    "path_template": catalog_path,
                    "partition_keys": partition_keys,
                    "schema_ref": schema_ref,
                    "role": role,
                    "status": status_value,
                    "read_scope": read_scope,
                    "sha256_hex": digest_hex,
                    "upstream_bundle_id": upstream_bundle_id,
                    "notes": notes,
                }
            )

        if optional_missing:
            logger.info("S0: optional inputs missing (not sealed): %s", ", ".join(sorted(optional_missing)))

        sealed_rows_sorted = sorted(
            sealed_rows,
            key=lambda row: (
                row.get("owner_layer"),
                row.get("owner_segment"),
                row.get("manifest_key"),
                row.get("path_template"),
            ),
        )

        sealed_schema = _schema_from_pack(schema_layer3, "gate/6A/sealed_inputs_6A")
        if sealed_schema.get("type") == "array":
            schema_to_use = sealed_schema
        else:
            schema_to_use = {"type": "array", "items": sealed_schema}
        errors = list(Draft202012Validator(schema_to_use).iter_errors(sealed_rows_sorted))
        if errors:
            _abort(
                "6A.S0.INTERNAL_ERROR",
                "V-07",
                "sealed_inputs_schema_invalid",
                {"detail": str(errors[0])},
                manifest_fingerprint,
            )

        sealed_inputs_digest = _sealed_inputs_digest(sealed_rows_sorted)
        role_counts: dict[str, int] = {}
        status_counts: dict[str, int] = {"REQUIRED": 0, "OPTIONAL": 0, "IGNORED": 0}
        for row in sealed_rows_sorted:
            role_counts[row["role"]] = role_counts.get(row["role"], 0) + 1
            status_key = row.get("status")
            if status_key in status_counts:
                status_counts[status_key] += 1

        logger.info(
            "S0: sealed_inputs_digest=%s sealed_inputs_count_total=%d sealed_inputs_count_by_role=%s",
            sealed_inputs_digest,
            len(sealed_rows_sorted),
            role_counts,
        )
        logger.info("S0: sealed_inputs_status_counts=%s", status_counts)

        receipt_entry = find_dataset_entry(dictionary_6a, "s0_gate_receipt_6A").entry
        sealed_entry = find_dataset_entry(dictionary_6a, "sealed_inputs_6A").entry
        receipt_path = _resolve_dataset_path(receipt_entry, run_paths, config.external_roots, tokens)
        sealed_inputs_path = _resolve_dataset_path(sealed_entry, run_paths, config.external_roots, tokens)

        if f"manifest_fingerprint={manifest_fingerprint}" not in receipt_path.as_posix():
            _abort(
                "6A.S0.GATE_RECEIPT_CONFLICT",
                "V-08",
                "receipt_path_missing_manifest",
                {"path": str(receipt_path)},
                manifest_fingerprint,
            )
        if f"manifest_fingerprint={manifest_fingerprint}" not in sealed_inputs_path.as_posix():
            _abort(
                "6A.S0.SEALED_INPUTS_CONFLICT",
                "V-08",
                "sealed_inputs_path_missing_manifest",
                {"path": str(sealed_inputs_path)},
                manifest_fingerprint,
            )

        receipt_registry = find_artifact_entry(registry_6a, "s0_gate_receipt_6A").entry
        receipt_version = _normalize_semver(
            receipt_registry.get("semver") or schema_layer3.get("version") or "1.0.0"
        )

        receipt_payload = {
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": parameter_hash,
            "spec_version_6A": receipt_version,
            "upstream_segments": upstream_segments,
            "contracts_6A": contracts_6a,
            "sealed_inputs_digest_6A": sealed_inputs_digest,
        }

        receipt_schema = _schema_from_pack(schema_layer3, "gate/6A/s0_gate_receipt_6A")
        errors = list(Draft202012Validator(receipt_schema).iter_errors(receipt_payload))
        if errors:
            _abort(
                "6A.S0.INTERNAL_ERROR",
                "V-08",
                "receipt_schema_invalid",
                {"detail": str(errors[0])},
                manifest_fingerprint,
            )

        if sealed_inputs_path.exists() or receipt_path.exists():
            if not sealed_inputs_path.exists() or not receipt_path.exists():
                _abort(
                    "6A.S0.SEALED_INPUTS_CONFLICT",
                    "V-09",
                    "partial_outputs_exist",
                    {"sealed_inputs_path": str(sealed_inputs_path), "receipt_path": str(receipt_path)},
                    manifest_fingerprint,
                )
            existing_rows = _load_json(sealed_inputs_path)
            if not isinstance(existing_rows, list):
                _abort(
                    "6A.S0.SEALED_INPUTS_CONFLICT",
                    "V-09",
                    "sealed_inputs_existing_invalid",
                    {"path": str(sealed_inputs_path)},
                    manifest_fingerprint,
                )
            existing_sorted = sorted(
                existing_rows,
                key=lambda row: (
                    row.get("owner_layer"),
                    row.get("owner_segment"),
                    row.get("manifest_key"),
                    row.get("path_template"),
                ),
            )
            existing_digest = _sealed_inputs_digest(existing_sorted)
            if existing_digest != sealed_inputs_digest:
                _abort(
                    "6A.S0.SEALED_INPUTS_CONFLICT",
                    "V-09",
                    "sealed_inputs_digest_mismatch",
                    {"expected": sealed_inputs_digest, "actual": existing_digest},
                    manifest_fingerprint,
                )
            existing_receipt_payload = _load_json(receipt_path)
            if json.dumps(existing_receipt_payload, sort_keys=True, separators=(",", ":")) != json.dumps(
                receipt_payload, sort_keys=True, separators=(",", ":")
            ):
                _abort(
                    "6A.S0.GATE_RECEIPT_CONFLICT",
                    "V-09",
                    "receipt_payload_mismatch",
                    {"receipt_path": str(receipt_path)},
                    manifest_fingerprint,
                )
            existing_receipt_digest = existing_receipt_payload.get("sealed_inputs_digest_6A")
            if existing_receipt_digest != existing_digest:
                _abort(
                    "6A.S0.SEALED_INPUTS_DIGEST_MISMATCH",
                    "V-09",
                    "receipt_digest_mismatch",
                    {"expected": existing_digest, "actual": existing_receipt_digest},
                    manifest_fingerprint,
                )
            logger.info("S0: outputs already exist and are identical; skipping publish.")
            status = "PASS"
            return S0GateResult(
                run_id=run_id_value,
                parameter_hash=parameter_hash,
                manifest_fingerprint=manifest_fingerprint,
                receipt_path=receipt_path,
                sealed_inputs_path=sealed_inputs_path,
            )

        _atomic_publish_json(sealed_inputs_path, sealed_rows_sorted)
        _atomic_publish_json(receipt_path, receipt_payload)

        elapsed = time.monotonic() - started
        timer.info(f"S0: completed gate and sealed inputs (elapsed={elapsed:.2f}s)")

        status = "PASS"
        return S0GateResult(
            run_id=run_id_value,
            parameter_hash=parameter_hash,
            manifest_fingerprint=manifest_fingerprint,
            receipt_path=receipt_path,
            sealed_inputs_path=sealed_inputs_path,
        )
    except EngineFailure as exc:
        error_code = exc.failure_code
        error_detail = exc.detail
        raise
    except Exception as exc:
        error_code = "6A.S0.INTERNAL_ERROR"
        error_detail = {"detail": str(exc)}
        raise EngineFailure(
            "F9",
            error_code,
            STATE,
            MODULE_NAME,
            error_detail,
        ) from exc
    finally:
        elapsed = time.monotonic() - started
        logger.info(
            "S0: finished status=%s error_code=%s elapsed=%.2fs",
            status,
            error_code,
            elapsed,
        )
