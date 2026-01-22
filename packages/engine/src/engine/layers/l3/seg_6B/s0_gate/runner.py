"""S0 gate-in runner for Segment 6B."""

from __future__ import annotations

import copy
import glob
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

from engine.contracts.jsonschema_adapter import normalize_nullable_schema
from engine.contracts.loader import (
    find_artifact_entry,
    find_dataset_entry,
    load_artefact_registry,
    load_dataset_dictionary,
    load_schema_pack,
)
from engine.contracts.source import ContractSource
from engine.core.config import EngineConfig
from engine.core.errors import ContractError, EngineFailure, HashingError, InputResolutionError
from engine.core.hashing import sha256_file
from engine.core.logging import add_file_handler, get_logger
from engine.core.paths import RunPaths, resolve_input_path
from engine.core.time import utc_now_rfc3339_micro


MODULE_NAME = "6B.s0_gate"
SEGMENT = "6B"
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


def _emit_event(logger, event_type: str, manifest_fingerprint: Optional[str], **fields: object) -> None:
    payload = {
        "event_type": event_type,
        "segment": SEGMENT,
        "state": STATE,
        "manifest_fingerprint": manifest_fingerprint or "unknown",
        "timestamp_utc": utc_now_rfc3339_micro(),
    }
    payload.update(fields)
    logger.info("%s %s", event_type, json.dumps(payload, ensure_ascii=True, sort_keys=True))


def _abort(code: str, message: str, context: dict, manifest_fingerprint: Optional[str]) -> None:
    logger = get_logger("engine.layers.l3.seg_6B.s0_gate.runner")
    _emit_event(logger, "6B.S0.FAIL", manifest_fingerprint, error_code=code, detail=message, context=context)
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


def _bundle_index_path(bundle_path: Path, segment_id: str) -> Path:
    if bundle_path.is_file():
        return bundle_path
    index_path = bundle_path / "index.json"
    if index_path.exists():
        return index_path
    return bundle_path / f"validation_bundle_index_{segment_id}.json"


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
    path_str = str(path)
    if "*" in path_str or "?" in path_str:
        return bool(glob.glob(path_str))
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
    if isinstance(owner_value, str) and owner_value.lower().startswith("layer"):
        try:
            return int(owner_value[-1])
        except ValueError:
            pass
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
    if dataset_id.startswith("sealed_inputs_"):
        return "UPSTREAM_SEALED_INPUTS"
    if schema_ref.startswith("schemas.6B.yaml#/policy/"):
        return "POLICY"
    if owner_segment and owner_segment != SEGMENT:
        return "UPSTREAM_EGRESS"
    return "DATASET"


def _read_scope_for_role(role: str) -> str:
    if role in {"UPSTREAM_GATE_BUNDLE", "UPSTREAM_GATE_FLAG", "CONTRACT", "UPSTREAM_SEALED_INPUTS"}:
        return "METADATA_ONLY"
    return "ROW_LEVEL"


def _assert_schema_defs_consistent(schema_layer3: dict, schema_6b: dict) -> None:
    defs_layer3 = schema_layer3.get("$defs") or {}
    defs_6b = schema_6b.get("$defs") or {}
    conflicts = []
    for key in sorted(set(defs_layer3) & set(defs_6b)):
        left = defs_layer3[key]
        right = defs_6b[key]
        if json.dumps(left, sort_keys=True) == json.dumps(right, sort_keys=True):
            continue
        ref_target = f"schemas.layer3.yaml#/$defs/{key}"
        if isinstance(left, dict) and left.get("$ref") == ref_target and len(left) == 1:
            continue
        if isinstance(right, dict) and right.get("$ref") == ref_target and len(right) == 1:
            continue
        conflicts.append(key)
    if conflicts:
        raise ContractError(f"Conflicting $defs between layer3 and 6B schemas: {conflicts}")


def _relative_path(path: Path, repo_root: Path) -> str:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


def _validate_payload(
    payload: object,
    schema_pack: dict,
    external_pack: Optional[dict],
    schema_anchor: str,
    error_code: str,
    manifest_fingerprint: str,
    context: dict,
    external_prefix: str,
) -> None:
    schema = _schema_from_pack(schema_pack, schema_anchor)
    if external_pack:
        _inline_external_refs(schema, external_pack, external_prefix)
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    if errors:
        raise EngineFailure(
            "F4",
            error_code,
            STATE,
            MODULE_NAME,
            {"detail": str(errors[0]), "context": context, "manifest_fingerprint": manifest_fingerprint},
        )


def _validate_registry_alignment(entry: dict, reg_entry: dict) -> str:
    entry_path = str(entry.get("path") or "").strip().rstrip("/")
    registry_path = str(reg_entry.get("path") or "").strip().rstrip("/")
    if entry_path and registry_path and entry_path != registry_path:
        raise ContractError(f"Registry path mismatch: {entry_path} != {registry_path}")
    entry_schema = str(entry.get("schema_ref") or "").strip()
    registry_schema = str(reg_entry.get("schema") or reg_entry.get("schema_ref") or "").strip()
    if registry_schema and entry_schema and registry_schema != entry_schema:
        raise ContractError(f"Registry schema mismatch: {entry_schema} != {registry_schema}")
    return entry_schema or registry_schema


def _atomic_publish_json(path: Path, payload: object, error_code: str) -> None:
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
            error_code,
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
            if "6B.S0" in consumed_by:
                entries.append(entry)
    return entries


def _index_upstream_rows(rows: list[dict]) -> dict[str, set]:
    by_artifact: set[str] = set()
    by_manifest: set[str] = set()
    by_path: set[tuple[str, str]] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        artifact_id = row.get("artifact_id")
        manifest_key = row.get("manifest_key")
        path_template = row.get("path_template")
        owner_segment = str(row.get("owner_segment") or "")
        if isinstance(artifact_id, str):
            by_artifact.add(artifact_id)
        if isinstance(manifest_key, str):
            by_manifest.add(manifest_key)
        if isinstance(path_template, str):
            by_path.add((owner_segment, path_template))
    return {"artifact_id": by_artifact, "manifest_key": by_manifest, "path_template": by_path}

def run_s0(config: EngineConfig, run_id: Optional[str] = None) -> S0GateResult:
    logger = get_logger("engine.layers.l3.seg_6B.s0_gate.runner")
    timer = _StepTimer(logger)
    started = time.monotonic()

    status = "FAIL"
    error_code: Optional[str] = None

    upstream_segments: dict[str, dict] = {}
    bundle_digests: dict[str, str] = {}
    sealed_rows: list[dict] = []
    sealed_inputs_digest: Optional[str] = None

    run_id_value = ""
    parameter_hash = ""
    manifest_fingerprint = ""
    seed: Optional[int] = None

    try:
        receipt_path, receipt = _resolve_run_receipt(config.runs_root, run_id)
        run_id_value = str(receipt.get("run_id") or "")
        if not run_id_value:
            _abort(
                "6B.S0.INTERNAL_ERROR",
                "run_receipt_missing_run_id",
                {"path": str(receipt_path)},
                None,
            )
        seed = receipt.get("seed")
        parameter_hash = str(receipt.get("parameter_hash") or "")
        manifest_fingerprint = str(receipt.get("manifest_fingerprint") or "")
        if seed is None or not parameter_hash or not manifest_fingerprint:
            _abort(
                "6B.S0.INTERNAL_ERROR",
                "run_receipt_missing_fields",
                {"seed": seed, "parameter_hash": parameter_hash, "manifest_fingerprint": manifest_fingerprint},
                manifest_fingerprint or None,
            )
        if not _HEX64_PATTERN.match(parameter_hash) or not _HEX64_PATTERN.match(manifest_fingerprint):
            _abort(
                "6B.S0.INTERNAL_ERROR",
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
            dict_6b_path, dictionary_6b = load_dataset_dictionary(source, "6B")
            reg_6b_path, registry_6b = load_artefact_registry(source, "6B")
            schema_6b_path, schema_6b = load_schema_pack(source, "6B", "6B")
            schema_layer3_path, schema_layer3 = load_schema_pack(source, "6B", "layer3")
            schema_6a_path, schema_6a = load_schema_pack(source, "6A", "6A")
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
                "6B.S0.CONTRACT_SET_INCOMPLETE",
                "contract_load_failed",
                {"detail": str(exc)},
                manifest_fingerprint,
            )

        logger.info(
            "Contracts layout=%s root=%s dictionary=%s registry=%s schemas=%s,%s",
            config.contracts_layout,
            str(config.contracts_root),
            str(dict_6b_path),
            str(reg_6b_path),
            str(schema_6b_path),
            str(schema_layer3_path),
        )

        _assert_schema_defs_consistent(schema_layer3, schema_6b)

        schema_packs = {
            "schemas.layer3.yaml": schema_layer3,
            "schemas.6B.yaml": schema_6b,
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

        _emit_event(
            logger,
            "6B.S0.START",
            manifest_fingerprint,
            objective="gate upstream 1A-3B,5A-5B,6A and seal 6B inputs",
            outputs=["s0_gate_receipt_6B", "sealed_inputs_6B"],
        )

        gate_map = [
            ("1A", "validation_bundle_1A", "validation_passed_flag_1A"),
            ("1B", "validation_bundle_1B", "validation_passed_flag_1B"),
            ("2A", "validation_bundle_2A", "validation_passed_flag_2A"),
            ("2B", "validation_bundle_2B", "validation_passed_flag_2B"),
            ("3A", "validation_bundle_3A", "validation_passed_flag_3A"),
            ("3B", "validation_bundle_3B", "validation_passed_flag_3B"),
            ("5A", "validation_bundle_5A", "validation_passed_flag_5A"),
            ("5B", "validation_bundle_5B", "validation_passed_flag_5B"),
            ("6A", "validation_bundle_6A", "validation_passed_flag_6A"),
        ]

        for segment_id, bundle_id, flag_id in gate_map:
            bundle_entry = find_dataset_entry(dictionary_6b, bundle_id).entry
            flag_entry = find_dataset_entry(dictionary_6b, flag_id).entry
            bundle_path = _resolve_dataset_path(bundle_entry, run_paths, config.external_roots, tokens)
            flag_path = _resolve_dataset_path(flag_entry, run_paths, config.external_roots, tokens)
            if not bundle_path.exists():
                _abort(
                    "6B.S0.UPSTREAM_HASHGATE_MISSING",
                    "validation_bundle_missing",
                    {"segment": segment_id, "bundle_id": bundle_id, "path": str(bundle_path)},
                    manifest_fingerprint,
                )
            if not flag_path.exists():
                _abort(
                    "6B.S0.UPSTREAM_HASHGATE_MISSING",
                    "validation_flag_missing",
                    {"segment": segment_id, "flag_id": flag_id, "path": str(flag_path)},
                    manifest_fingerprint,
                )
            index_path = _bundle_index_path(bundle_path, segment_id)
            if not index_path.exists():
                _abort(
                    "6B.S0.UPSTREAM_HASHGATE_INVALID",
                    "validation_index_missing",
                    {"segment": segment_id, "path": str(index_path)},
                    manifest_fingerprint,
                )
            try:
                bundle_digest = _parse_pass_flag_any(flag_path)
            except InputResolutionError as exc:
                _abort(
                    "6B.S0.UPSTREAM_HASHGATE_INVALID",
                    "validation_flag_invalid",
                    {"segment": segment_id, "path": str(flag_path), "detail": str(exc)},
                    manifest_fingerprint,
                )
            bundle_digests[bundle_id] = bundle_digest
            upstream_segments[segment_id] = {
                "status": "PASS",
                "bundle_path": _render_catalog_path(bundle_entry, tokens),
                "bundle_sha256": bundle_digest,
                "flag_path": _render_catalog_path(flag_entry, tokens),
            }
            _emit_event(
                logger,
                "6B.S0.UPSTREAM_CHECK",
                manifest_fingerprint,
                owner_segment=segment_id,
                status="PASS",
                bundle_id=bundle_id,
                digest_method="passed_flag",
            )

        sealed_inputs_sources: dict[str, tuple[dict, str, Optional[dict], str]] = {
            "sealed_inputs_5A": (schema_5a, "validation/sealed_inputs_5A", schema_layer1, "schemas.layer1.yaml#"),
            "sealed_inputs_5B": (schema_5b, "validation/sealed_inputs_5B", schema_layer1, "schemas.layer1.yaml#"),
            "sealed_inputs_6A": (schema_layer3, "gate/6A/sealed_inputs_6A", None, ""),
        }
        upstream_rows: dict[str, list[dict]] = {}

        for dataset_id, (schema_pack, anchor, external_pack, prefix) in sealed_inputs_sources.items():
            entry = find_dataset_entry(dictionary_6b, dataset_id).entry
            path = _resolve_dataset_path(entry, run_paths, config.external_roots, tokens)
            if not path.exists():
                _abort(
                    "6B.S0.UPSTREAM_SEALED_INPUTS_MISSING",
                    "sealed_inputs_missing",
                    {"dataset_id": dataset_id, "path": str(path)},
                    manifest_fingerprint,
                )
            payload = _load_json(path)
            if not isinstance(payload, list):
                _abort(
                    "6B.S0.UPSTREAM_SEALED_INPUTS_INVALID",
                    "sealed_inputs_invalid_shape",
                    {"dataset_id": dataset_id, "path": str(path)},
                    manifest_fingerprint,
                )
            try:
                schema = _schema_from_pack(schema_pack, anchor)
                if external_pack:
                    _inline_external_refs(schema, external_pack, prefix)
                if dataset_id == "sealed_inputs_6A" and schema.get("type") != "array":
                    schema = {"type": "array", "items": schema}
                errors = list(Draft202012Validator(schema).iter_errors(payload))
                if errors:
                    raise EngineFailure(
                        "F4",
                        "6B.S0.UPSTREAM_SEALED_INPUTS_INVALID",
                        STATE,
                        MODULE_NAME,
                        {"detail": str(errors[0]), "dataset_id": dataset_id},
                    )
            except EngineFailure as exc:
                _abort(
                    "6B.S0.UPSTREAM_SEALED_INPUTS_INVALID",
                    "sealed_inputs_schema_invalid",
                    {"dataset_id": dataset_id, "detail": str(exc)},
                    manifest_fingerprint,
                )
            upstream_rows[dataset_id] = payload

        upstream_index_5a = _index_upstream_rows(upstream_rows.get("sealed_inputs_5A", []))
        upstream_index_5b = _index_upstream_rows(upstream_rows.get("sealed_inputs_5B", []))
        upstream_index_6a = _index_upstream_rows(upstream_rows.get("sealed_inputs_6A", []))

        s0_entries = _s0_input_entries(dictionary_6b)
        if not s0_entries:
            _abort(
                "6B.S0.SEALED_INPUTS_SCHEMA_VIOLATION",
                "sealed_inputs_empty",
                {"detail": "No dictionary entries list 6B.S0 in consumed_by."},
                manifest_fingerprint,
            )

        contract_schema_ref = "schemas.layer3.yaml#/$defs/contract_file"
        try:
            _validate_schema_ref(contract_schema_ref, schema_packs)
        except ContractError as exc:
            _abort(
                "6B.S0.SCHEMA_ANCHOR_UNRESOLVED",
                "contract_schema_ref_invalid",
                {"schema_ref": contract_schema_ref, "detail": str(exc)},
                manifest_fingerprint,
            )
        contract_specs = [
            ("contracts.dataset_dictionary.layer3.6B", dict_6b_path),
            ("contracts.artefact_registry_6B", reg_6b_path),
            ("contracts.schemas.6B", schema_6b_path),
            ("contracts.schemas.layer3", schema_layer3_path),
        ]
        contracts_6b: dict[str, dict] = {}
        for logical_id, contract_path in contract_specs:
            try:
                digest_hex = sha256_file(contract_path).sha256_hex
            except (HashingError, OSError) as exc:
                _abort(
                    "6B.S0.CONTRACT_SET_INCOMPLETE",
                    "contract_digest_failed",
                    {"logical_id": logical_id, "path": str(contract_path), "detail": str(exc)},
                    manifest_fingerprint,
                )
            relative_path = _relative_path(contract_path, config.repo_root)
            contracts_6b[logical_id] = {
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
                    "6B.S0.CONTRACT_SET_INCOMPLETE",
                    "dataset_id_missing",
                    {"entry": entry},
                    manifest_fingerprint,
                )
            try:
                reg_entry = find_artifact_entry(registry_6b, dataset_id).entry
            except ContractError as exc:
                _abort(
                    "6B.S0.CONTRACT_SET_INCOMPLETE",
                    "registry_missing",
                    {"dataset_id": dataset_id, "detail": str(exc)},
                    manifest_fingerprint,
                )
            try:
                schema_ref = _validate_registry_alignment(entry, reg_entry)
            except ContractError as exc:
                _abort(
                    "6B.S0.CONTRACT_SET_INCOMPLETE",
                    "registry_alignment_failed",
                    {"dataset_id": dataset_id, "detail": str(exc)},
                    manifest_fingerprint,
                )
            try:
                schema_ref = _validate_schema_ref(schema_ref, schema_packs)
            except ContractError as exc:
                _abort(
                    "6B.S0.SCHEMA_ANCHOR_UNRESOLVED",
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
                        "6B.S0.UPSTREAM_HASHGATE_INVALID",
                        "bundle_digest_missing",
                        {"dataset_id": dataset_id, "bundle_id": bundle_id},
                        manifest_fingerprint,
                    )
                upstream_bundle_id = bundle_id
                notes = "bundle_digest=passed_flag"
            elif dataset_id in {"sealed_inputs_5A", "sealed_inputs_5B", "sealed_inputs_6A"}:
                try:
                    resolved_path = _resolve_dataset_path(entry, run_paths, config.external_roots, tokens)
                except InputResolutionError as exc:
                    _abort(
                        "6B.S0.UPSTREAM_SEALED_INPUTS_MISSING",
                        "sealed_inputs_missing",
                        {"dataset_id": dataset_id, "detail": str(exc)},
                        manifest_fingerprint,
                    )
                if not _path_has_content(resolved_path):
                    _abort(
                        "6B.S0.UPSTREAM_SEALED_INPUTS_MISSING",
                        "sealed_inputs_missing",
                        {"dataset_id": dataset_id, "path": str(resolved_path)},
                        manifest_fingerprint,
                    )
                try:
                    digest_hex = sha256_file(resolved_path).sha256_hex
                except (HashingError, OSError) as exc:
                    _abort(
                        "6B.S0.UPSTREAM_SEALED_INPUTS_INVALID",
                        "sealed_inputs_digest_failed",
                        {"dataset_id": dataset_id, "path": str(resolved_path), "detail": str(exc)},
                        manifest_fingerprint,
                    )
                notes = "content_digest=sha256"
            elif schema_ref.startswith("schemas.6B.yaml#/policy/"):
                try:
                    resolved_path = _resolve_dataset_path(entry, run_paths, config.external_roots, tokens)
                except InputResolutionError as exc:
                    _abort(
                        "6B.S0.CONFIG_VALIDATION_FAILED",
                        "config_missing",
                        {"dataset_id": dataset_id, "detail": str(exc)},
                        manifest_fingerprint,
                    )
                if not _path_has_content(resolved_path):
                    _abort(
                        "6B.S0.CONFIG_VALIDATION_FAILED",
                        "config_missing",
                        {"dataset_id": dataset_id, "path": str(resolved_path)},
                        manifest_fingerprint,
                    )
                try:
                    payload = _load_yaml(resolved_path) if resolved_path.suffix in {".yaml", ".yml"} else _load_json(
                        resolved_path
                    )
                except (OSError, json.JSONDecodeError, yaml.YAMLError) as exc:
                    _abort(
                        "6B.S0.CONFIG_VALIDATION_FAILED",
                        "config_parse_failed",
                        {"dataset_id": dataset_id, "path": str(resolved_path), "detail": str(exc)},
                        manifest_fingerprint,
                    )
                anchor = schema_ref.split("#", 1)[1].strip("/")
                try:
                    _validate_payload(
                        payload,
                        schema_6b,
                        schema_layer3,
                        anchor,
                        "6B.S0.CONFIG_VALIDATION_FAILED",
                        manifest_fingerprint,
                        {"dataset_id": dataset_id},
                        "schemas.layer3.yaml#",
                    )
                except EngineFailure as exc:
                    _abort(
                        "6B.S0.CONFIG_VALIDATION_FAILED",
                        "config_schema_invalid",
                        {"dataset_id": dataset_id, "detail": str(exc)},
                        manifest_fingerprint,
                    )
                try:
                    digest_hex = sha256_file(resolved_path).sha256_hex
                except (HashingError, OSError) as exc:
                    _abort(
                        "6B.S0.CONFIG_VALIDATION_FAILED",
                        "config_digest_failed",
                        {"dataset_id": dataset_id, "path": str(resolved_path), "detail": str(exc)},
                        manifest_fingerprint,
                    )
                expected_digest = reg_entry.get("digest")
                if isinstance(expected_digest, str) and expected_digest and not _is_placeholder(expected_digest):
                    if digest_hex != expected_digest:
                        _abort(
                            "6B.S0.CONFIG_VALIDATION_FAILED",
                            "config_digest_mismatch",
                            {"dataset_id": dataset_id, "expected": expected_digest, "actual": digest_hex},
                            manifest_fingerprint,
                        )
                notes = "content_digest=sha256"
            elif owner_segment != SEGMENT:
                upstream_index = None
                if owner_segment == "5A":
                    upstream_index = upstream_index_5a
                elif owner_segment == "5B":
                    upstream_index = upstream_index_5b
                elif owner_segment == "6A":
                    upstream_index = upstream_index_6a
                matches = False
                if upstream_index is not None:
                    matches = (
                        dataset_id in upstream_index["artifact_id"]
                        or manifest_key in upstream_index["manifest_key"]
                        or (owner_segment, catalog_path) in upstream_index["path_template"]
                    )
                if not matches:
                    try:
                        resolved_path = _resolve_dataset_path(
                            entry,
                            run_paths,
                            config.external_roots,
                            tokens,
                            allow_wildcards=True,
                        )
                    except InputResolutionError as exc:
                        if status_value == "OPTIONAL":
                            optional_missing.append(dataset_id)
                            logger.info(
                                "S0: optional upstream input missing dataset_id=%s owner_segment=%s detail=%s",
                                dataset_id,
                                owner_segment,
                                str(exc),
                            )
                            continue
                        _abort(
                            "6B.S0.SEALED_INPUTS_REQUIRED_ARTIFACT_MISSING",
                            "upstream_input_missing",
                            {"dataset_id": dataset_id, "owner_segment": owner_segment, "detail": str(exc)},
                            manifest_fingerprint,
                        )
                    if not _path_has_content(resolved_path):
                        if status_value == "OPTIONAL":
                            optional_missing.append(dataset_id)
                            logger.info(
                                "S0: optional upstream input missing dataset_id=%s owner_segment=%s path=%s",
                                dataset_id,
                                owner_segment,
                                resolved_path,
                            )
                            continue
                        _abort(
                            "6B.S0.SEALED_INPUTS_REQUIRED_ARTIFACT_MISSING",
                            "upstream_input_missing",
                            {"dataset_id": dataset_id, "owner_segment": owner_segment, "path": str(resolved_path)},
                            manifest_fingerprint,
                        )
                digest_hex = _structural_digest(
                    {
                        "manifest_key": manifest_key,
                        "schema_ref": schema_ref,
                        "path_template": catalog_path,
                        "partition_keys": partition_keys,
                    }
                )
                notes = "structural_digest=path_template"
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
                    "6B.S0.SEALED_INPUTS_SCHEMA_VIOLATION",
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

        sealed_schema = _schema_from_pack(schema_layer3, "gate/6B/sealed_inputs_6B")
        if sealed_schema.get("type") == "array":
            schema_to_use = sealed_schema
        else:
            schema_to_use = {"type": "array", "items": sealed_schema}
        errors = list(Draft202012Validator(schema_to_use).iter_errors(sealed_rows_sorted))
        if errors:
            _abort(
                "6B.S0.SEALED_INPUTS_SCHEMA_VIOLATION",
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

        _emit_event(
            logger,
            "6B.S0.SEALED_INPUTS_BUILT",
            manifest_fingerprint,
            sealed_inputs_count_total=len(sealed_rows_sorted),
            sealed_inputs_count_by_role=role_counts,
            sealed_inputs_status_counts=status_counts,
        )
        _emit_event(
            logger,
            "6B.S0.SEALED_INPUTS_DIGEST",
            manifest_fingerprint,
            sealed_inputs_digest=sealed_inputs_digest,
        )

        receipt_entry = find_dataset_entry(dictionary_6b, "s0_gate_receipt_6B").entry
        sealed_entry = find_dataset_entry(dictionary_6b, "sealed_inputs_6B").entry
        receipt_path = _resolve_dataset_path(receipt_entry, run_paths, config.external_roots, tokens)
        sealed_inputs_path = _resolve_dataset_path(sealed_entry, run_paths, config.external_roots, tokens)

        if f"manifest_fingerprint={manifest_fingerprint}" not in receipt_path.as_posix():
            _abort(
                "6B.S0.GATE_RECEIPT_SCHEMA_VIOLATION",
                "receipt_path_missing_manifest",
                {"path": str(receipt_path)},
                manifest_fingerprint,
            )
        if f"manifest_fingerprint={manifest_fingerprint}" not in sealed_inputs_path.as_posix():
            _abort(
                "6B.S0.SEALED_INPUTS_SCHEMA_VIOLATION",
                "sealed_inputs_path_missing_manifest",
                {"path": str(sealed_inputs_path)},
                manifest_fingerprint,
            )

        receipt_registry = find_artifact_entry(registry_6b, "s0_gate_receipt_6B").entry
        receipt_version = _normalize_semver(
            receipt_registry.get("semver") or schema_layer3.get("version") or "1.0.0"
        )

        receipt_payload = {
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": parameter_hash,
            "spec_version_6B": receipt_version,
            "upstream_segments": upstream_segments,
            "contracts_6B": contracts_6b,
            "sealed_inputs_digest_6B": sealed_inputs_digest,
        }

        receipt_schema = _schema_from_pack(schema_layer3, "gate/6B/s0_gate_receipt_6B")
        errors = list(Draft202012Validator(receipt_schema).iter_errors(receipt_payload))
        if errors:
            _abort(
                "6B.S0.GATE_RECEIPT_SCHEMA_VIOLATION",
                "receipt_schema_invalid",
                {"detail": str(errors[0])},
                manifest_fingerprint,
            )

        if sealed_inputs_path.exists() or receipt_path.exists():
            if not sealed_inputs_path.exists() or not receipt_path.exists():
                _abort(
                    "6B.S0.SEALED_INPUTS_DRIFT",
                    "partial_outputs_exist",
                    {"sealed_inputs_path": str(sealed_inputs_path), "receipt_path": str(receipt_path)},
                    manifest_fingerprint,
                )
            existing_rows = _load_json(sealed_inputs_path)
            if not isinstance(existing_rows, list):
                _abort(
                    "6B.S0.SEALED_INPUTS_DRIFT",
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
                    "6B.S0.SEALED_INPUTS_DRIFT",
                    "sealed_inputs_digest_mismatch",
                    {"expected": sealed_inputs_digest, "actual": existing_digest},
                    manifest_fingerprint,
                )
            existing_receipt_payload = _load_json(receipt_path)
            if json.dumps(existing_receipt_payload, sort_keys=True, separators=(",", ":")) != json.dumps(
                receipt_payload, sort_keys=True, separators=(",", ":")
            ):
                _abort(
                    "6B.S0.GATE_RECEIPT_IDEMPOTENCE_VIOLATION",
                    "receipt_payload_mismatch",
                    {"receipt_path": str(receipt_path)},
                    manifest_fingerprint,
                )
            existing_receipt_digest = existing_receipt_payload.get("sealed_inputs_digest_6B")
            if existing_receipt_digest != existing_digest:
                _abort(
                    "6B.S0.GATE_RECEIPT_IDEMPOTENCE_VIOLATION",
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

        _atomic_publish_json(sealed_inputs_path, sealed_rows_sorted, "6B.S0.SEALED_INPUTS_DIGEST_COMPUTE_FAILED")
        _atomic_publish_json(receipt_path, receipt_payload, "6B.S0.GATE_RECEIPT_WRITE_FAILED")
        _emit_event(
            logger,
            "6B.S0.GATE_RECEIPT_WRITE",
            manifest_fingerprint,
            receipt_path=str(receipt_path),
            sealed_inputs_path=str(sealed_inputs_path),
        )

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
        raise
    except Exception as exc:
        error_code = "6B.S0.INTERNAL_ERROR"
        raise EngineFailure(
            "F9",
            error_code,
            STATE,
            MODULE_NAME,
            {"detail": str(exc)},
        ) from exc
    finally:
        elapsed = time.monotonic() - started
        _emit_event(
            logger,
            "6B.S0.END",
            manifest_fingerprint or None,
            status=status,
            error_code=error_code,
            elapsed_sec=round(elapsed, 3),
        )
