"""S0 gate-in runner for Segment 5B."""

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


MODULE_NAME = "5B.s0_gate"
SEGMENT = "5B"
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
    logger = get_logger("engine.layers.l2.seg_5B.s0_gate.runner")
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
    schema_5b: dict,
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
    if schema_ref.startswith("schemas.5B.yaml#"):
        _schema_anchor_exists(schema_5b, schema_ref)
    elif schema_ref.startswith("schemas.5A.yaml#"):
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


def _parse_pass_flag(path: Path) -> str:
    if not path.exists():
        raise InputResolutionError(f"Missing PASS flag: {path}")
    content = path.read_text(encoding="utf-8").strip()
    line = content.splitlines()[0] if content else ""
    match = _FLAG_PATTERN.match(line)
    if not match:
        raise InputResolutionError(f"Invalid _passed.flag format: {path}")
    return match.group(1)


def _parse_pass_flag_json(path: Path) -> str:
    if not path.exists():
        raise InputResolutionError(f"Missing PASS flag: {path}")
    payload = _load_json(path)
    if not isinstance(payload, dict):
        raise InputResolutionError(f"Invalid JSON _passed.flag: {path}")
    digest = payload.get("bundle_digest_sha256")
    if not isinstance(digest, str) or not _HEX64_PATTERN.match(digest):
        raise InputResolutionError(f"Missing bundle_digest_sha256 in _passed.flag: {path}")
    return digest

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
    hasher = hashlib.sha256()
    total_bytes = 0
    for path in paths:
        file_path = bundle_root / path
        if not file_path.exists():
            raise EngineFailure(
                "F4",
                "5B.S0.UPSTREAM_GATE_MISSING",
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
                "5B.S0.UPSTREAM_GATE_MISSING",
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


def _sha256_concat_hex(values: list[str]) -> str:
    hasher = hashlib.sha256()
    for value in values:
        hasher.update(value.encode("utf-8"))
    return hasher.hexdigest()


def _validate_index_entries(index_entries: list[dict], index_path: Path) -> list[str]:
    paths = []
    for entry in index_entries:
        path = entry.get("path")
        if not isinstance(path, str) or not path:
            raise EngineFailure(
                "F4",
                "5B.S0.UPSTREAM_GATE_MISMATCH",
                STATE,
                MODULE_NAME,
                {"detail": "index entry missing path", "path": str(index_path)},
            )
        try:
            path.encode("ascii")
        except UnicodeEncodeError as exc:
            raise EngineFailure(
                "F4",
                "5B.S0.UPSTREAM_GATE_MISMATCH",
                STATE,
                MODULE_NAME,
                {"detail": f"non-ascii path: {path}", "path": str(index_path)},
            ) from exc
        if "\\" in path or path.startswith(("/", "\\")) or ".." in Path(path).parts or ":" in path:
            raise EngineFailure(
                "F4",
                "5B.S0.UPSTREAM_GATE_MISMATCH",
                STATE,
                MODULE_NAME,
                {"detail": f"invalid index path: {path}", "path": str(index_path)},
            )
        paths.append(path)
    if len(set(paths)) != len(paths):
        raise EngineFailure(
            "F4",
            "5B.S0.UPSTREAM_GATE_MISMATCH",
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
                "5B.S0.UPSTREAM_GATE_MISMATCH",
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
                "5B.S0.UPSTREAM_GATE_MISMATCH",
                STATE,
                MODULE_NAME,
                {"detail": str(errors[0]), "path": str(index_path)},
            )
        entries = list(payload.get("files", []))
    else:
        raise EngineFailure(
            "F4",
            "5B.S0.UPSTREAM_GATE_MISMATCH",
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
            "5B.S0.UPSTREAM_GATE_MISMATCH",
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
            "5B.S0.UPSTREAM_GATE_MISMATCH",
            STATE,
            MODULE_NAME,
            {"detail": str(errors[0]), "path": str(index_path)},
        )
    members = index_payload.get("members")
    if not isinstance(members, list) or not members:
        raise EngineFailure(
            "F4",
            "5B.S0.UPSTREAM_GATE_MISMATCH",
            STATE,
            MODULE_NAME,
            {"detail": "bundle index missing members", "path": str(index_path)},
        )
    for member in members:
        sha256_hex = member.get("sha256_hex") if isinstance(member, dict) else None
        if not isinstance(sha256_hex, str) or not _HEX64_PATTERN.match(sha256_hex):
            raise EngineFailure(
                "F4",
                "5B.S0.UPSTREAM_GATE_MISMATCH",
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
            "5B.S0.UPSTREAM_GATE_MISMATCH",
            STATE,
            MODULE_NAME,
            {"detail": str(errors[0]), "path": str(index_path)},
        )
    members = index_payload.get("members")
    if not isinstance(members, list) or not members:
        raise EngineFailure(
            "F4",
            "5B.S0.UPSTREAM_GATE_MISMATCH",
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


def _resolve_partitioned_paths(
    entry: dict,
    run_paths: RunPaths,
    external_roots: Iterable[Path],
    tokens: dict[str, str],
    scenario_ids: list[str],
) -> list[tuple[Optional[str], Path]]:
    path_template = str(entry.get("path") or "")
    if "{scenario_id}" in path_template:
        if not scenario_ids:
            raise InputResolutionError("Scenario set missing for scenario-partitioned dataset.")
        resolved = []
        for scenario_id in scenario_ids:
            local_tokens = dict(tokens)
            local_tokens["scenario_id"] = scenario_id
            resolved.append((scenario_id, _resolve_dataset_path(entry, run_paths, external_roots, local_tokens)))
        return resolved
    return [(None, _resolve_dataset_path(entry, run_paths, external_roots, tokens))]


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


def _hash_path_content(path: Path, logger, label: str) -> tuple[str, int]:
    if "*" in str(path) or "?" in str(path):
        matched = sorted(path.parent.glob(path.name))
        if not matched:
            raise HashingError(f"No files matched {path}")
        total_bytes = sum(p.stat().st_size for p in matched if p.is_file())
        tracker = _ProgressTracker(total_bytes, logger, label)
        hasher = hashlib.sha256()
        processed = 0
        for file_path in matched:
            if not file_path.is_file():
                continue
            with file_path.open("rb") as handle:
                while True:
                    chunk = handle.read(1024 * 1024)
                    if not chunk:
                        break
                    processed += len(chunk)
                    hasher.update(chunk)
                    tracker.update(len(chunk))
        return hasher.hexdigest(), processed
    if path.is_dir():
        return _hash_partition(path, logger, label)
    digest = sha256_file(path)
    return digest.sha256_hex, digest.size_bytes


def _owner_layer(owner_segment: str) -> str:
    if owner_segment in {"1A", "1B", "2A", "2B", "3A", "3B", "4A", "4B"}:
        return "layer1"
    if owner_segment in {"5A", "5B"}:
        return "layer2"
    if owner_segment in {"6A", "6B"}:
        return "layer3"
    return "engine"


def _role_for_dataset(dataset_id: str) -> str:
    if dataset_id.startswith("validation_bundle_"):
        return "validation_bundle"
    if dataset_id.startswith("validation_passed_flag_"):
        return "validation_flag"
    if dataset_id in {
        "route_rng_policy_v1",
        "alias_layout_policy_v1",
        "time_grid_policy_5B",
        "grouping_policy_5B",
        "arrival_lgcp_config_5B",
        "arrival_count_config_5B",
        "arrival_rng_policy_5B",
        "arrival_time_placement_policy_5B",
        "arrival_routing_policy_5B",
        "bundle_layout_policy_5B",
        "validation_policy_5B",
    }:
        return "policy"
    return "dataset"


def _read_scope_for_dataset(dataset_id: str) -> str:
    if dataset_id.startswith("validation_bundle_") or dataset_id.startswith("validation_passed_flag_"):
        return "METADATA_ONLY"
    if dataset_id in {
        "route_rng_policy_v1",
        "alias_layout_policy_v1",
        "time_grid_policy_5B",
        "grouping_policy_5B",
        "arrival_lgcp_config_5B",
        "arrival_count_config_5B",
        "arrival_rng_policy_5B",
        "arrival_time_placement_policy_5B",
        "arrival_routing_policy_5B",
        "bundle_layout_policy_5B",
        "validation_policy_5B",
        "scenario_manifest_5A",
    }:
        return "ROW_LEVEL"
    return "METADATA_ONLY"


def _structural_digest(payload: dict) -> str:
    hasher = hashlib.sha256()
    hasher.update(json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    return hasher.hexdigest()


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
        "status",
        "read_scope",
        "notes",
        "owner_team",
        "source_manifest",
    )
    hasher = hashlib.sha256()
    for row in rows:
        payload = {field: row.get(field) for field in ordered_fields}
        hasher.update(
            json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=False).encode("utf-8")
        )
    return hasher.hexdigest()


def _segment_state_runs_path(run_paths: RunPaths, dictionary: dict, utc_day: str) -> Path:
    entry = find_dataset_entry(dictionary, "segment_state_runs").entry
    path_template = entry["path"]
    path = path_template.replace("{utc_day}", utc_day)
    return run_paths.run_root / path


def _append_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True, sort_keys=True))
        handle.write("\n")


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
            "5B.S0.IO_WRITE_FAILED",
            STATE,
            MODULE_NAME,
            {"detail": "atomic publish failed", "path": str(path), "error": str(exc)},
        ) from exc
    try:
        tmp_dir.rmdir()
    except OSError:
        pass


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
        _abort(
            "5B.S0.SEALED_INPUTS_SCHEMA_INVALID",
            "V-08",
            "payload_schema_invalid",
            {"detail": str(errors[0]), "context": context},
            manifest_fingerprint,
        )


def _spec_version_for_segment(
    registry: dict,
    schema_pack: dict,
    bundle_id: str,
) -> str:
    try:
        reg_entry = find_artifact_entry(registry, bundle_id).entry
    except ContractError:
        reg_entry = {}
    semver = reg_entry.get("semver")
    if semver and not _is_placeholder(str(semver)):
        return str(semver)
    if schema_pack.get("version"):
        return str(schema_pack.get("version"))
    return "unknown"

def run_s0(config: EngineConfig, run_id: Optional[str] = None) -> S0GateResult:
    logger = get_logger("engine.layers.l2.seg_5B.s0_gate.runner")
    timer = _StepTimer(logger)
    started = time.monotonic()
    started_utc = utc_now_rfc3339_micro()

    status = "FAIL"
    error_code: Optional[str] = None
    error_detail: Optional[dict] = None

    upstream_segments: dict[str, dict] = {}
    bundle_digests: dict[str, str] = {}
    sealed_rows_sorted: list[dict] = []
    sealed_inputs_digest: Optional[str] = None
    scenario_set: list[str] = []

    run_report_path: Optional[Path] = None

    run_id_value = ""
    parameter_hash = ""
    manifest_fingerprint = ""
    seed: Optional[int] = None

    dictionary_5b: Optional[dict] = None
    registry_5b: Optional[dict] = None
    schema_5b: Optional[dict] = None
    schema_5a: Optional[dict] = None
    schema_layer2: Optional[dict] = None
    schema_ingress_layer2: Optional[dict] = None
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
                "5B.S0.RUN_IDENTITY_INVALID",
                "V-01",
                "run_receipt_missing_run_id",
                {"path": str(receipt_path)},
                None,
            )
        if receipt_path.parent.name != run_id_value:
            _abort(
                "5B.S0.RUN_IDENTITY_INVALID",
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
                "5B.S0.RUN_IDENTITY_INVALID",
                "V-01",
                "run_receipt_missing_fields",
                {"seed": seed, "parameter_hash": parameter_hash, "manifest_fingerprint": manifest_fingerprint},
                manifest_fingerprint or None,
            )
        if not _HEX64_PATTERN.match(parameter_hash) or not _HEX64_PATTERN.match(manifest_fingerprint):
            _abort(
                "5B.S0.RUN_IDENTITY_INVALID",
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
            dict_5b_path, dictionary_5b = load_dataset_dictionary(source, "5B")
            dict_5a_path, dictionary_5a = load_dataset_dictionary(source, "5A")
            dict_3b_path, dictionary_3b = load_dataset_dictionary(source, "3B")
            dict_3a_path, dictionary_3a = load_dataset_dictionary(source, "3A")
            dict_2b_path, dictionary_2b = load_dataset_dictionary(source, "2B")
            dict_2a_path, dictionary_2a = load_dataset_dictionary(source, "2A")
            dict_1b_path, dictionary_1b = load_dataset_dictionary(source, "1B")
            dict_1a_path, dictionary_1a = load_dataset_dictionary(source, "1A")
            reg_5b_path, registry_5b = load_artefact_registry(source, "5B")
            schema_5b_path, schema_5b = load_schema_pack(source, "5B", "5B")
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
                "5B.S0.CATALOGUE_INCOMPLETE",
                "V-02",
                "contract_load_failed",
                {"detail": str(exc)},
                manifest_fingerprint,
            )

        logger.info(
            "Contracts layout=%s root=%s dictionary=%s registry=%s schemas=%s,%s,%s",
            config.contracts_layout,
            str(config.contracts_root),
            str(dict_5b_path),
            str(reg_5b_path),
            str(schema_5b_path),
            str(schema_layer2_path),
            str(schema_layer1_path),
        )

        logger.info(
            "S0: objective=gate 1A-3B + 5A and seal inputs (L1 egress + 5A surfaces + 5B policies) -> outputs (s0_gate_receipt_5B, sealed_inputs_5B)"
        )

        tokens = {
            "seed": str(seed),
            "parameter_hash": parameter_hash,
            "manifest_fingerprint": manifest_fingerprint,
            "run_id": run_id_value,
        }

        gate_map = {
            "1A": (
                "validation_bundle_1A",
                "validation_passed_flag_1A",
                schema_1a,
                "validation/validation_bundle_index_1A",
            ),
            "1B": (
                "validation_bundle_1B",
                "validation_passed_flag_1B",
                schema_1b,
                "validation/validation_bundle_index_1B",
            ),
            "2A": (
                "validation_bundle_2A",
                "validation_passed_flag_2A",
                schema_2a,
                "validation/validation_bundle_index_2A",
            ),
        }

        for segment_id, (bundle_id, flag_id, schema_pack, index_anchor) in gate_map.items():
            bundle_entry = find_dataset_entry(dictionary_5b, bundle_id).entry
            flag_entry = find_dataset_entry(dictionary_5b, flag_id).entry
            bundle_root = _resolve_dataset_path(bundle_entry, run_paths, config.external_roots, tokens)
            flag_path = _resolve_dataset_path(flag_entry, run_paths, config.external_roots, tokens)
            spec_version = _spec_version_for_segment(registry_5b, schema_pack, bundle_id)
            if not bundle_root.exists():
                upstream_segments[segment_id] = {
                    "status": "MISSING",
                    "bundle_path": _render_catalog_path(bundle_entry, tokens),
                    "flag_path": _render_catalog_path(flag_entry, tokens),
                    "spec_version": spec_version,
                }
                _abort(
                    "5B.S0.UPSTREAM_GATE_MISSING",
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
                flag_digest = _parse_pass_flag(flag_path)
            except (EngineFailure, InputResolutionError) as exc:
                upstream_segments[segment_id] = {
                    "status": "FAIL",
                    "bundle_path": _render_catalog_path(bundle_entry, tokens),
                    "flag_path": _render_catalog_path(flag_entry, tokens),
                    "spec_version": spec_version,
                }
                _abort(
                    "5B.S0.UPSTREAM_GATE_MISMATCH",
                    "V-03",
                    "validation_bundle_invalid",
                    {"bundle_id": bundle_id, "detail": str(exc)},
                    manifest_fingerprint,
                )
            if bundle_digest != flag_digest:
                upstream_segments[segment_id] = {
                    "status": "FAIL",
                    "bundle_path": _render_catalog_path(bundle_entry, tokens),
                    "flag_path": _render_catalog_path(flag_entry, tokens),
                    "spec_version": spec_version,
                    "bundle_digest": bundle_digest,
                }
                _abort(
                    "5B.S0.UPSTREAM_GATE_MISMATCH",
                    "V-03",
                    "hashgate_mismatch",
                    {"bundle_id": bundle_id, "expected": bundle_digest, "actual": flag_digest},
                    manifest_fingerprint,
                )
            bundle_digests[bundle_id] = bundle_digest
            upstream_segments[segment_id] = {
                "status": "PASS",
                "bundle_path": _render_catalog_path(bundle_entry, tokens),
                "flag_path": _render_catalog_path(flag_entry, tokens),
                "spec_version": spec_version,
                "bundle_digest": bundle_digest,
            }
            logger.info(
                "S0: segment_%s gate verified (bundle=%s, digest=%s, law=index_files)",
                segment_id,
                bundle_root.as_posix(),
                bundle_digest,
            )

        bundle_entry = find_dataset_entry(dictionary_5b, "validation_bundle_2B").entry
        flag_entry = find_dataset_entry(dictionary_5b, "validation_passed_flag_2B").entry
        index_path = _resolve_dataset_path(bundle_entry, run_paths, config.external_roots, tokens)
        flag_path = _resolve_dataset_path(flag_entry, run_paths, config.external_roots, tokens)
        spec_version = _spec_version_for_segment(registry_5b, schema_2b, "validation_bundle_2B")
        if not index_path.exists():
            upstream_segments["2B"] = {
                "status": "MISSING",
                "bundle_path": _render_catalog_path(bundle_entry, tokens),
                "flag_path": _render_catalog_path(flag_entry, tokens),
                "spec_version": spec_version,
            }
            _abort(
                "5B.S0.UPSTREAM_GATE_MISSING",
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
                    "5B.S0.UPSTREAM_GATE_MISMATCH",
                    STATE,
                    MODULE_NAME,
                    {"detail": str(errors[0]), "path": str(index_path)},
                )
            if not isinstance(index_payload, list):
                raise EngineFailure(
                    "F4",
                    "5B.S0.UPSTREAM_GATE_MISMATCH",
                    STATE,
                    MODULE_NAME,
                    {"detail": "2B index.json is not a list", "path": str(index_path)},
                )
            _validate_index_entries(index_payload, index_path)
            bundle_digest, _ = _bundle_hash_from_index(run_paths.run_root, index_payload)
            flag_digest = _parse_pass_flag(flag_path)
        except (EngineFailure, InputResolutionError) as exc:
            upstream_segments["2B"] = {
                "status": "FAIL",
                "bundle_path": _render_catalog_path(bundle_entry, tokens),
                "flag_path": _render_catalog_path(flag_entry, tokens),
                "spec_version": spec_version,
            }
            _abort(
                "5B.S0.UPSTREAM_GATE_MISMATCH",
                "V-03",
                "validation_bundle_invalid",
                {"bundle_id": "validation_bundle_2B", "detail": str(exc)},
                manifest_fingerprint,
            )
        if bundle_digest != flag_digest:
            upstream_segments["2B"] = {
                "status": "FAIL",
                "bundle_path": _render_catalog_path(bundle_entry, tokens),
                "flag_path": _render_catalog_path(flag_entry, tokens),
                "spec_version": spec_version,
                "bundle_digest": bundle_digest,
            }
            _abort(
                "5B.S0.UPSTREAM_GATE_MISMATCH",
                "V-03",
                "hashgate_mismatch",
                {"bundle_id": "validation_bundle_2B", "expected": bundle_digest, "actual": flag_digest},
                manifest_fingerprint,
            )
        bundle_digests["validation_bundle_2B"] = bundle_digest
        upstream_segments["2B"] = {
            "status": "PASS",
            "bundle_path": _render_catalog_path(bundle_entry, tokens),
            "flag_path": _render_catalog_path(flag_entry, tokens),
            "spec_version": spec_version,
            "bundle_digest": bundle_digest,
        }
        logger.info(
            "S0: segment_2B gate verified (bundle=%s, digest=%s, law=index_paths)",
            index_path.as_posix(),
            bundle_digest,
        )

        bundle_entry = find_dataset_entry(dictionary_5b, "validation_bundle_3A").entry
        flag_entry = find_dataset_entry(dictionary_5b, "validation_passed_flag_3A").entry
        bundle_root = _resolve_dataset_path(bundle_entry, run_paths, config.external_roots, tokens)
        flag_path = _resolve_dataset_path(flag_entry, run_paths, config.external_roots, tokens)
        spec_version = _spec_version_for_segment(registry_5b, schema_3a, "validation_bundle_3A")
        if not bundle_root.exists():
            upstream_segments["3A"] = {
                "status": "MISSING",
                "bundle_path": _render_catalog_path(bundle_entry, tokens),
                "flag_path": _render_catalog_path(flag_entry, tokens),
                "spec_version": spec_version,
            }
            _abort(
                "5B.S0.UPSTREAM_GATE_MISSING",
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
            flag_digest = _parse_pass_flag(flag_path)
        except (EngineFailure, InputResolutionError) as exc:
            upstream_segments["3A"] = {
                "status": "FAIL",
                "bundle_path": _render_catalog_path(bundle_entry, tokens),
                "flag_path": _render_catalog_path(flag_entry, tokens),
                "spec_version": spec_version,
            }
            _abort(
                "5B.S0.UPSTREAM_GATE_MISMATCH",
                "V-03",
                "validation_bundle_invalid",
                {"bundle_id": "validation_bundle_3A", "detail": str(exc)},
                manifest_fingerprint,
            )
        if bundle_digest != flag_digest:
            upstream_segments["3A"] = {
                "status": "FAIL",
                "bundle_path": _render_catalog_path(bundle_entry, tokens),
                "flag_path": _render_catalog_path(flag_entry, tokens),
                "spec_version": spec_version,
                "bundle_digest": bundle_digest,
            }
            _abort(
                "5B.S0.UPSTREAM_GATE_MISMATCH",
                "V-03",
                "hashgate_mismatch",
                {"bundle_id": "validation_bundle_3A", "expected": bundle_digest, "actual": flag_digest},
                manifest_fingerprint,
            )
        bundle_digests["validation_bundle_3A"] = bundle_digest
        upstream_segments["3A"] = {
            "status": "PASS",
            "bundle_path": _render_catalog_path(bundle_entry, tokens),
            "flag_path": _render_catalog_path(flag_entry, tokens),
            "spec_version": spec_version,
            "bundle_digest": bundle_digest,
        }
        logger.info(
            "S0: segment_3A gate verified (bundle=%s, digest=%s, law=index_only)",
            bundle_root.as_posix(),
            bundle_digest,
        )

        bundle_entry = find_dataset_entry(dictionary_5b, "validation_bundle_3B").entry
        flag_entry = find_dataset_entry(dictionary_5b, "validation_passed_flag_3B").entry
        bundle_root = _resolve_dataset_path(bundle_entry, run_paths, config.external_roots, tokens)
        flag_path = _resolve_dataset_path(flag_entry, run_paths, config.external_roots, tokens)
        spec_version = _spec_version_for_segment(registry_5b, schema_3b, "validation_bundle_3B")
        if not bundle_root.exists():
            upstream_segments["3B"] = {
                "status": "MISSING",
                "bundle_path": _render_catalog_path(bundle_entry, tokens),
                "flag_path": _render_catalog_path(flag_entry, tokens),
                "spec_version": spec_version,
            }
            _abort(
                "5B.S0.UPSTREAM_GATE_MISSING",
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
            flag_digest = _parse_pass_flag(flag_path)
        except (EngineFailure, InputResolutionError) as exc:
            upstream_segments["3B"] = {
                "status": "FAIL",
                "bundle_path": _render_catalog_path(bundle_entry, tokens),
                "flag_path": _render_catalog_path(flag_entry, tokens),
                "spec_version": spec_version,
            }
            _abort(
                "5B.S0.UPSTREAM_GATE_MISMATCH",
                "V-03",
                "validation_bundle_invalid",
                {"bundle_id": "validation_bundle_3B", "detail": str(exc)},
                manifest_fingerprint,
            )
        if bundle_digest != flag_digest:
            upstream_segments["3B"] = {
                "status": "FAIL",
                "bundle_path": _render_catalog_path(bundle_entry, tokens),
                "flag_path": _render_catalog_path(flag_entry, tokens),
                "spec_version": spec_version,
                "bundle_digest": bundle_digest,
            }
            _abort(
                "5B.S0.UPSTREAM_GATE_MISMATCH",
                "V-03",
                "hashgate_mismatch",
                {"bundle_id": "validation_bundle_3B", "expected": bundle_digest, "actual": flag_digest},
                manifest_fingerprint,
            )
        bundle_digests["validation_bundle_3B"] = bundle_digest
        upstream_segments["3B"] = {
            "status": "PASS",
            "bundle_path": _render_catalog_path(bundle_entry, tokens),
            "flag_path": _render_catalog_path(flag_entry, tokens),
            "spec_version": spec_version,
            "bundle_digest": bundle_digest,
        }
        logger.info(
            "S0: segment_3B gate verified (bundle=%s, digest=%s, law=index_files)",
            bundle_root.as_posix(),
            bundle_digest,
        )

        bundle_entry = find_dataset_entry(dictionary_5b, "validation_bundle_5A").entry
        flag_entry = find_dataset_entry(dictionary_5b, "validation_passed_flag_5A").entry
        bundle_root = _resolve_dataset_path(bundle_entry, run_paths, config.external_roots, tokens)
        flag_path = _resolve_dataset_path(flag_entry, run_paths, config.external_roots, tokens)
        spec_version = _spec_version_for_segment(registry_5b, schema_5a, "validation_bundle_5A")
        if not bundle_root.exists():
            upstream_segments["5A"] = {
                "status": "MISSING",
                "bundle_path": _render_catalog_path(bundle_entry, tokens),
                "flag_path": _render_catalog_path(flag_entry, tokens),
                "spec_version": spec_version,
            }
            _abort(
                "5B.S0.UPSTREAM_GATE_MISSING",
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
                    "5B.S0.UPSTREAM_GATE_MISMATCH",
                    STATE,
                    MODULE_NAME,
                    {"detail": str(errors[0]), "path": str(index_path)},
                )
            entries = index_payload.get("entries")
            if not isinstance(entries, list):
                raise EngineFailure(
                    "F4",
                    "5B.S0.UPSTREAM_GATE_MISMATCH",
                    STATE,
                    MODULE_NAME,
                    {"detail": "validation_bundle_index_5A missing entries", "path": str(index_path)},
                )
            _validate_index_entries(entries, index_path)
            bundle_digest, _ = _bundle_hash(bundle_root, entries)
            flag_digest = _parse_pass_flag_json(flag_path)
        except (EngineFailure, InputResolutionError) as exc:
            upstream_segments["5A"] = {
                "status": "FAIL",
                "bundle_path": _render_catalog_path(bundle_entry, tokens),
                "flag_path": _render_catalog_path(flag_entry, tokens),
                "spec_version": spec_version,
            }
            _abort(
                "5B.S0.UPSTREAM_GATE_MISMATCH",
                "V-03",
                "validation_bundle_invalid",
                {"bundle_id": "validation_bundle_5A", "detail": str(exc)},
                manifest_fingerprint,
            )
        if bundle_digest != flag_digest:
            upstream_segments["5A"] = {
                "status": "FAIL",
                "bundle_path": _render_catalog_path(bundle_entry, tokens),
                "flag_path": _render_catalog_path(flag_entry, tokens),
                "spec_version": spec_version,
                "bundle_digest": bundle_digest,
            }
            _abort(
                "5B.S0.UPSTREAM_GATE_MISMATCH",
                "V-03",
                "hashgate_mismatch",
                {"bundle_id": "validation_bundle_5A", "expected": bundle_digest, "actual": flag_digest},
                manifest_fingerprint,
            )
        bundle_digests["validation_bundle_5A"] = bundle_digest
        upstream_segments["5A"] = {
            "status": "PASS",
            "bundle_path": _render_catalog_path(bundle_entry, tokens),
            "flag_path": _render_catalog_path(flag_entry, tokens),
            "spec_version": spec_version,
            "bundle_digest": bundle_digest,
        }
        logger.info(
            "S0: segment_5A gate verified (bundle=%s, digest=%s, law=index_entries)",
            bundle_root.as_posix(),
            bundle_digest,
        )

        logger.info(
            "S0: upstream_segments=%s",
            json.dumps(upstream_segments, ensure_ascii=True, sort_keys=True),
        )

        scenario_entry = find_dataset_entry(dictionary_5b, "scenario_manifest_5A").entry
        scenario_manifest_path = _resolve_dataset_path(scenario_entry, run_paths, config.external_roots, tokens)
        if not scenario_manifest_path.exists():
            _abort(
                "5B.S0.SEALED_INPUTS_INCOMPLETE",
                "V-04",
                "scenario_manifest_missing",
                {"dataset_id": "scenario_manifest_5A", "path": str(scenario_manifest_path)},
                manifest_fingerprint,
            )
        scenario_manifest_df = pl.read_parquet(scenario_manifest_path)
        scenario_rows = scenario_manifest_df.to_dicts()
        scenario_schema = _schema_from_pack(schema_5a, "validation/scenario_manifest_5A")
        _inline_external_refs(scenario_schema, schema_layer1, "schemas.layer1.yaml#")
        _inline_external_refs(scenario_schema, schema_layer2, "schemas.layer2.yaml#")
        _inline_external_refs(scenario_schema, schema_ingress_layer2, "schemas.ingress.layer2.yaml#")
        errors = list(Draft202012Validator(scenario_schema).iter_errors(scenario_rows))
        if errors:
            _abort(
                "5B.S0.SEALED_INPUTS_SCHEMA_INVALID",
                "V-04",
                "scenario_manifest_schema_invalid",
                {"detail": str(errors[0]), "path": str(scenario_manifest_path)},
                manifest_fingerprint,
            )
        if "scenario_id" not in scenario_manifest_df.columns:
            _abort(
                "5B.S0.SEALED_INPUTS_INCOMPLETE",
                "V-04",
                "scenario_manifest_missing_ids",
                {"dataset_id": "scenario_manifest_5A", "path": str(scenario_manifest_path)},
                manifest_fingerprint,
            )
        scenario_set = sorted({str(value) for value in scenario_manifest_df["scenario_id"].to_list()})
        if not scenario_set:
            _abort(
                "5B.S0.SEALED_INPUTS_INCOMPLETE",
                "V-04",
                "scenario_manifest_empty",
                {"dataset_id": "scenario_manifest_5A", "path": str(scenario_manifest_path)},
                manifest_fingerprint,
            )
        if len(scenario_set) <= 10:
            logger.info("S0: scenario_set resolved (count=%d ids=%s)", len(scenario_set), scenario_set)
        else:
            logger.info(
                "S0: scenario_set resolved (count=%d sample=%s)",
                len(scenario_set),
                scenario_set[:10],
            )

        scenario_manifest_digest = sha256_file(scenario_manifest_path).sha256_hex

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
            "validation_bundle_5A",
            "validation_passed_flag_5A",
            "site_locations",
            "site_timezones",
            "s1_site_weights",
            "s2_alias_blob",
            "s2_alias_index",
            "s3_day_effects",
            "s4_group_weights",
            "zone_alloc",
            "zone_alloc_universe_hash",
            "virtual_classification_3B",
            "edge_catalogue_3B",
            "edge_catalogue_index_3B",
            "edge_alias_blob_3B",
            "edge_alias_index_3B",
            "edge_universe_hash_3B",
            "virtual_routing_policy_3B",
            "virtual_validation_contract_3B",
            "route_rng_policy_v1",
            "alias_layout_policy_v1",
            "scenario_manifest_5A",
            "merchant_zone_profile_5A",
            "shape_grid_definition_5A",
            "class_zone_shape_5A",
            "merchant_zone_baseline_local_5A",
            "merchant_zone_scenario_local_5A",
            "time_grid_policy_5B",
            "grouping_policy_5B",
            "arrival_lgcp_config_5B",
            "arrival_count_config_5B",
            "arrival_rng_policy_5B",
            "arrival_time_placement_policy_5B",
            "arrival_routing_policy_5B",
            "validation_policy_5B",
        ]
        optional_ids = [
            "tz_timetable_cache",
            "virtual_settlement_3B",
            "merchant_zone_overlay_factors_5A",
            "merchant_zone_scenario_utc_5A",
            "bundle_layout_policy_5B",
        ]
        scenario_partitioned_ids = {
            "shape_grid_definition_5A",
            "class_zone_shape_5A",
            "merchant_zone_baseline_local_5A",
            "merchant_zone_overlay_factors_5A",
            "merchant_zone_scenario_local_5A",
            "merchant_zone_scenario_utc_5A",
        }

        policy_ids = {
            "route_rng_policy_v1",
            "alias_layout_policy_v1",
            "time_grid_policy_5B",
            "grouping_policy_5B",
            "arrival_lgcp_config_5B",
            "arrival_count_config_5B",
            "arrival_rng_policy_5B",
            "arrival_time_placement_policy_5B",
            "arrival_routing_policy_5B",
            "bundle_layout_policy_5B",
            "validation_policy_5B",
        }
        content_hash_ids = {
            "scenario_manifest_5A",
            "zone_alloc_universe_hash",
            "edge_universe_hash_3B",
            "virtual_routing_policy_3B",
            "virtual_validation_contract_3B",
            "tz_timetable_cache",
        }

        sealed_rows: list[dict] = []
        sealed_optional_missing: list[str] = []
        seen_keys: set[tuple[str, str]] = set()

        for dataset_id in required_ids + optional_ids:
            try:
                entry = find_dataset_entry(dictionary_5b, dataset_id).entry
            except ContractError as exc:
                _abort(
                    "5B.S0.CATALOGUE_INCOMPLETE",
                    "V-05",
                    "dataset_missing",
                    {"dataset_id": dataset_id, "detail": str(exc)},
                    manifest_fingerprint,
                )
            try:
                reg_entry = find_artifact_entry(registry_5b, dataset_id).entry
            except ContractError as exc:
                _abort(
                    "5B.S0.CATALOGUE_INCOMPLETE",
                    "V-05",
                    "registry_missing",
                    {"dataset_id": dataset_id, "detail": str(exc)},
                    manifest_fingerprint,
                )

            try:
                schema_ref = _validate_schema_ref(
                    entry.get("schema_ref"),
                    schema_5b,
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
                    "5B.S0.CATALOGUE_INCOMPLETE",
                    "V-05",
                    "schema_ref_invalid",
                    {"dataset_id": dataset_id, "detail": str(exc)},
                    manifest_fingerprint,
                )

            status_value = "REQUIRED" if dataset_id in required_ids else "OPTIONAL"
            owner_segment = str(entry.get("owner_subsegment") or SEGMENT)
            manifest_key = str(reg_entry.get("manifest_key") or "")
            catalog_path = entry.get("path") or ""
            partition_keys = list(entry.get("partitioning") or [])
            owner_team = ""
            owner_entry = reg_entry.get("owner")
            if isinstance(owner_entry, dict):
                owner_team = str(owner_entry.get("team") or owner_entry.get("owner_team") or "")

            try:
                resolved_pairs = _resolve_partitioned_paths(
                    entry, run_paths, config.external_roots, tokens, scenario_set
                )
            except InputResolutionError as exc:
                if status_value == "OPTIONAL":
                    sealed_optional_missing.append(dataset_id)
                    logger.info(
                        "S0: optional input missing (dataset_id=%s detail=%s)",
                        dataset_id,
                        str(exc),
                    )
                    continue
                _abort(
                    "5B.S0.SEALED_INPUTS_INCOMPLETE",
                    "V-06",
                    "sealed_input_missing",
                    {"dataset_id": dataset_id, "detail": str(exc)},
                    manifest_fingerprint,
                )
            missing_partitions: list[str] = []
            for scenario_id, resolved_path in resolved_pairs:
                if not _path_has_content(resolved_path):
                    missing_partitions.append(scenario_id or resolved_path.as_posix())

            if missing_partitions:
                if status_value == "OPTIONAL":
                    sealed_optional_missing.append(dataset_id)
                    logger.info(
                        "S0: optional input missing (dataset_id=%s missing_partitions=%s)",
                        dataset_id,
                        missing_partitions,
                    )
                    continue
                _abort(
                    "5B.S0.SEALED_INPUTS_INCOMPLETE",
                    "V-06",
                    "sealed_input_missing",
                    {"dataset_id": dataset_id, "missing": missing_partitions},
                    manifest_fingerprint,
                )

            if dataset_id.startswith("validation_bundle_"):
                digest_hex = bundle_digests.get(dataset_id)
                if not digest_hex:
                    _abort(
                        "5B.S0.SEALED_INPUTS_INCOMPLETE",
                        "V-06",
                        "bundle_digest_missing",
                        {"dataset_id": dataset_id},
                        manifest_fingerprint,
                    )
            elif dataset_id.startswith("validation_passed_flag_"):
                bundle_id = dataset_id.replace("validation_passed_flag", "validation_bundle")
                digest_hex = bundle_digests.get(bundle_id)
                if not digest_hex:
                    _abort(
                        "5B.S0.SEALED_INPUTS_INCOMPLETE",
                        "V-06",
                        "bundle_digest_missing",
                        {"dataset_id": dataset_id},
                        manifest_fingerprint,
                    )
            elif dataset_id in policy_ids:
                resolved_path = resolved_pairs[0][1]
                if not resolved_path.exists():
                    if status_value == "OPTIONAL":
                        sealed_optional_missing.append(dataset_id)
                        continue
                    _abort(
                        "5B.S0.SEALED_INPUTS_INCOMPLETE",
                        "V-06",
                        "policy_missing",
                        {"dataset_id": dataset_id, "path": str(resolved_path)},
                        manifest_fingerprint,
                    )
                payload = (
                    _load_yaml(resolved_path)
                    if resolved_path.suffix.lower() in {".yaml", ".yml"}
                    else _load_json(resolved_path)
                )
                policy_version = _policy_version_from_payload(payload)
                version_decl = entry.get("version")
                if _is_placeholder(version_decl):
                    if policy_version is None:
                        _abort(
                            "5B.S0.SEALED_INPUTS_INCOMPLETE",
                            "V-06",
                            "policy_version_missing",
                            {"dataset_id": dataset_id, "path": str(resolved_path)},
                            manifest_fingerprint,
                        )
                else:
                    expected_version = str(version_decl).replace("{parameter_hash}", parameter_hash)
                    if policy_version and not _policy_version_matches(expected_version, policy_version):
                        _abort(
                            "5B.S0.SEALED_INPUTS_INCOMPLETE",
                            "V-06",
                            "policy_version_mismatch",
                            {
                                "dataset_id": dataset_id,
                                "expected": expected_version,
                                "actual": policy_version,
                            },
                            manifest_fingerprint,
                        )
                    if policy_version and expected_version != policy_version:
                        logger.info(
                            "S0: policy version accepted by semver prefix (dataset_id=%s expected=%s actual=%s)",
                            dataset_id,
                            expected_version,
                            policy_version,
                        )

                if schema_ref.startswith("schemas.5B.yaml#"):
                    anchor = schema_ref.split("#", 1)[1].strip("/")
                    _validate_payload(
                        schema_5b,
                        schema_layer1,
                        schema_layer2,
                        schema_ingress_layer2,
                        anchor,
                        payload,
                        manifest_fingerprint,
                        {"dataset_id": dataset_id},
                    )
                elif schema_ref.startswith("schemas.5A.yaml#"):
                    anchor = schema_ref.split("#", 1)[1].strip("/")
                    _validate_payload(
                        schema_5a,
                        schema_layer1,
                        schema_layer2,
                        schema_ingress_layer2,
                        anchor,
                        payload,
                        manifest_fingerprint,
                        {"dataset_id": dataset_id},
                    )
                elif schema_ref.startswith("schemas.2B.yaml#"):
                    anchor = schema_ref.split("#", 1)[1].strip("/")
                    _validate_payload(
                        schema_2b,
                        schema_layer1,
                        schema_layer2,
                        schema_ingress_layer2,
                        anchor,
                        payload,
                        manifest_fingerprint,
                        {"dataset_id": dataset_id},
                    )
                else:
                    anchor = schema_ref.split("#", 1)[1].strip("/")
                    _validate_payload(
                        schema_layer2,
                        schema_layer1,
                        schema_layer2,
                        schema_ingress_layer2,
                        anchor,
                        payload,
                        manifest_fingerprint,
                        {"dataset_id": dataset_id},
                    )
                digest_hex, _ = _hash_path_content(resolved_path, logger, f"S0: hash {dataset_id} bytes")
            elif dataset_id in content_hash_ids:
                if dataset_id == "scenario_manifest_5A":
                    digest_hex = scenario_manifest_digest
                else:
                    resolved_path = resolved_pairs[0][1]
                    digest_hex, _ = _hash_path_content(resolved_path, logger, f"S0: hash {dataset_id} bytes")
            else:
                digest_payload = {
                    "artifact_id": dataset_id,
                    "manifest_key": manifest_key,
                    "schema_ref": schema_ref,
                    "path_template": catalog_path,
                    "partition_keys": partition_keys,
                }
                digest_hex = _structural_digest(digest_payload)

            notes = ""
            if dataset_id in scenario_partitioned_ids:
                notes = f"structural_digest=path_template;scenario_ids={','.join(scenario_set)}"
            elif dataset_id not in policy_ids and dataset_id not in content_hash_ids and not dataset_id.startswith("validation_"):
                notes = "structural_digest=path_template"

            key = (owner_segment, dataset_id)
            if key in seen_keys:
                _abort(
                    "5B.S0.SEALED_INPUTS_DUPLICATE_KEY",
                    "V-07",
                    "sealed_inputs_duplicate_key",
                    {"owner_segment": owner_segment, "dataset_id": dataset_id},
                    manifest_fingerprint,
                )
            seen_keys.add(key)

            sealed_rows.append(
                {
                    "manifest_fingerprint": manifest_fingerprint,
                    "parameter_hash": parameter_hash,
                    "owner_layer": _owner_layer(owner_segment),
                    "owner_segment": owner_segment,
                    "artifact_id": dataset_id,
                    "manifest_key": manifest_key,
                    "role": _role_for_dataset(dataset_id),
                    "schema_ref": schema_ref,
                    "path_template": catalog_path,
                    "partition_keys": partition_keys,
                    "sha256_hex": digest_hex,
                    "status": status_value,
                    "read_scope": _read_scope_for_dataset(dataset_id),
                    "notes": notes,
                    "owner_team": owner_team,
                }
            )

        if sealed_optional_missing:
            logger.info("S0: optional inputs missing (not sealed): %s", ", ".join(sealed_optional_missing))

        sealed_rows_sorted = sorted(
            sealed_rows,
            key=lambda row: (row.get("owner_segment"), row.get("artifact_id"), row.get("role")),
        )

        sealed_schema = _schema_from_pack(schema_5b, "validation/sealed_inputs_5B")
        _inline_external_refs(sealed_schema, schema_layer1, "schemas.layer1.yaml#")
        _inline_external_refs(sealed_schema, schema_layer2, "schemas.layer2.yaml#")
        errors = list(Draft202012Validator(sealed_schema).iter_errors(sealed_rows_sorted))
        if errors:
            _abort(
                "5B.S0.SEALED_INPUTS_SCHEMA_INVALID",
                "V-08",
                "sealed_inputs_schema_invalid",
                {"error": str(errors[0])},
                manifest_fingerprint,
            )

        sealed_inputs_digest = _sealed_inputs_digest(sealed_rows_sorted)
        role_counts: dict[str, int] = {}
        status_counts: dict[str, int] = {"REQUIRED": 0, "OPTIONAL": 0, "INTERNAL": 0, "IGNORED": 0}
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

        receipt_entry = find_dataset_entry(dictionary_5b, "s0_gate_receipt_5B").entry
        sealed_entry = find_dataset_entry(dictionary_5b, "sealed_inputs_5B").entry
        receipt_path = _resolve_dataset_path(receipt_entry, run_paths, config.external_roots, tokens)
        sealed_inputs_path = _resolve_dataset_path(sealed_entry, run_paths, config.external_roots, tokens)

        if f"manifest_fingerprint={manifest_fingerprint}" not in sealed_inputs_path.as_posix():
            _abort(
                "5B.S0.IO_WRITE_CONFLICT",
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

        receipt_registry = find_artifact_entry(registry_5b, "s0_gate_receipt_5B").entry
        receipt_version = _normalize_semver(receipt_registry.get("semver") or schema_5b.get("version") or "1.0.0")

        receipt_payload = {
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": parameter_hash,
            "seed": seed,
            "run_id": run_id_value,
            "created_utc": created_utc,
            "upstream_segments": upstream_segments,
            "scenario_set": scenario_set,
            "sealed_inputs_digest": sealed_inputs_digest,
            "sealed_inputs_row_count": len(sealed_rows_sorted),
            "spec_version": receipt_version,
        }

        receipt_schema = _schema_from_pack(schema_5b, "validation/s0_gate_receipt_5B")
        _inline_external_refs(receipt_schema, schema_layer1, "schemas.layer1.yaml#")
        _inline_external_refs(receipt_schema, schema_layer2, "schemas.layer2.yaml#")
        errors = list(Draft202012Validator(receipt_schema).iter_errors(receipt_payload))
        if errors:
            _abort(
                "5B.S0.GATE_RECEIPT_SCHEMA_INVALID",
                "V-10",
                "receipt_schema_invalid",
                {"error": str(errors[0])},
                manifest_fingerprint,
            )

        if sealed_inputs_path.exists() or receipt_path.exists():
            if not sealed_inputs_path.exists() or not receipt_path.exists():
                _abort(
                    "5B.S0.IO_WRITE_CONFLICT",
                    "V-11",
                    "partial_outputs_exist",
                    {"sealed_inputs_path": str(sealed_inputs_path), "receipt_path": str(receipt_path)},
                    manifest_fingerprint,
                )
            existing_rows = _load_json(sealed_inputs_path)
            if not isinstance(existing_rows, list):
                _abort(
                    "5B.S0.IO_WRITE_CONFLICT",
                    "V-11",
                    "sealed_inputs_existing_invalid",
                    {"path": str(sealed_inputs_path)},
                    manifest_fingerprint,
                )
            existing_sorted = sorted(
                existing_rows,
                key=lambda row: (row.get("owner_segment"), row.get("artifact_id"), row.get("role")),
            )
            existing_digest = _sealed_inputs_digest(existing_sorted)
            if existing_digest != sealed_inputs_digest:
                _abort(
                    "5B.S0.IO_WRITE_CONFLICT",
                    "V-11",
                    "sealed_inputs_digest_mismatch",
                    {"expected": sealed_inputs_digest, "actual": existing_digest},
                    manifest_fingerprint,
                )
            existing_receipt_payload = _load_json(receipt_path)
            if json.dumps(existing_receipt_payload, sort_keys=True, separators=(",", ":")) != json.dumps(
                receipt_payload, sort_keys=True, separators=(",", ":")
            ):
                _abort(
                    "5B.S0.GATE_RECEIPT_DIGEST_MISMATCH",
                    "V-11",
                    "receipt_payload_mismatch",
                    {"receipt_path": str(receipt_path)},
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
    finally:
        if dictionary_5b and run_id_value and parameter_hash and manifest_fingerprint:
            utc_day = started_utc[:10]
            run_report_path = _segment_state_runs_path(RunPaths(config.runs_root, run_id_value), dictionary_5b, utc_day)
            upstream_total = 7
            upstream_pass = sum(1 for item in upstream_segments.values() if item.get("status") == "PASS")
            upstream_fail = sum(1 for item in upstream_segments.values() if item.get("status") == "FAIL")
            upstream_missing = sum(1 for item in upstream_segments.values() if item.get("status") == "MISSING")
            if upstream_pass + upstream_fail + upstream_missing < upstream_total:
                missing_segments = {"1A", "1B", "2A", "2B", "3A", "3B", "5A"} - set(upstream_segments.keys())
                for segment_id in sorted(missing_segments):
                    upstream_segments[segment_id] = {"status": "MISSING"}
                upstream_missing = sum(1 for item in upstream_segments.values() if item.get("status") == "MISSING")

            status_counts = {"REQUIRED": 0, "OPTIONAL": 0, "INTERNAL": 0, "IGNORED": 0}
            role_counts = {"dataset": 0, "config": 0, "validation": 0}
            for row in sealed_rows_sorted:
                status_key = row.get("status")
                if status_key in status_counts:
                    status_counts[status_key] += 1
                role_value = str(row.get("role") or "")
                if role_value.startswith("validation"):
                    role_counts["validation"] += 1
                elif role_value in {"policy", "config"}:
                    role_counts["config"] += 1
                else:
                    role_counts["dataset"] += 1

            run_report_payload = {
                "layer": "layer2",
                "segment": SEGMENT,
                "state": STATE,
                "state_id": "5B.S0",
                "parameter_hash": parameter_hash,
                "manifest_fingerprint": manifest_fingerprint,
                "seed": seed,
                "run_id": run_id_value,
                "scenario_set": scenario_set,
                "status": status,
                "error_code": error_code,
                "started_at_utc": started_utc,
                "finished_at_utc": utc_now_rfc3339_micro(),
                "upstream_total": upstream_total,
                "upstream_pass_count": upstream_pass,
                "upstream_fail_count": upstream_fail,
                "upstream_missing_count": upstream_missing,
                "sealed_inputs_row_count_total": len(sealed_rows_sorted),
                "sealed_inputs_row_count_required": status_counts["REQUIRED"],
                "sealed_inputs_row_count_optional": status_counts["OPTIONAL"],
                "sealed_inputs_row_count_internal": status_counts["INTERNAL"],
                "sealed_inputs_row_count_ignored": status_counts["IGNORED"],
                "sealed_inputs_count_dataset": role_counts["dataset"],
                "sealed_inputs_count_config": role_counts["config"],
                "sealed_inputs_count_validation": role_counts["validation"],
                "sealed_inputs_digest": sealed_inputs_digest,
                "upstream_segments": upstream_segments,
            }
            if error_detail:
                run_report_payload["error_detail"] = error_detail

            try:
                _append_jsonl(run_report_path, run_report_payload)
            except Exception as exc:
                logger.warning("S0: failed to write segment_state_runs: %s", exc)
