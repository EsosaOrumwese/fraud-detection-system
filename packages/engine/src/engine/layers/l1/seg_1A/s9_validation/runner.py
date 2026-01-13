"""S9 validation runner for Segment 1A."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import polars as pl
import yaml
from jsonschema import Draft202012Validator

from engine.contracts.jsonschema_adapter import table_to_jsonschema, validate_dataframe
from engine.contracts.loader import (
    artifact_dependency_closure,
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
from engine.core.hashing import FileDigest, sha256_file
from engine.core.logging import add_file_handler, get_logger
from engine.core.paths import RunPaths
from engine.core.time import utc_now_ns, utc_now_rfc3339_micro
from engine.layers.l1.seg_1A.s0_foundations.hashing import (
    NamedDigest,
    NamedPath,
    compute_manifest_fingerprint,
    compute_parameter_hash,
)
from engine.layers.l1.seg_1A.s0_foundations.numeric_policy import run_numeric_self_tests


MODULE_NAME = "1A.s9_validation"
_DATE_VERSION_RE = re.compile(r"\d{4}-\d{2}-\d{2}")

DATASET_SEALED_INPUTS = "sealed_inputs_1A"
DATASET_OUTLET = "outlet_catalogue"
DATASET_CANDIDATE_SET = "s3_candidate_set"
DATASET_COUNTS = "s3_integerised_counts"
DATASET_SITE_SEQUENCE = "s3_site_sequence"
DATASET_MEMBERSHIP = "s6_membership"
DATASET_S6_RECEIPT = "s6_validation_receipt"
DATASET_ELIGIBILITY = "crossborder_eligibility_flags"
DATASET_TRACE = "rng_trace_log"
DATASET_AUDIT = "rng_audit_log"
DATASET_ANCHOR = "rng_event_anchor"
DATASET_HURDLE = "rng_event_hurdle_bernoulli"
DATASET_GAMMA = "rng_event_gamma_component"
DATASET_POISSON = "rng_event_poisson_component"
DATASET_NB_FINAL = "rng_event_nb_final"
DATASET_ZTP_REJECTION = "rng_event_ztp_rejection"
DATASET_ZTP_RETRY = "rng_event_ztp_retry_exhausted"
DATASET_ZTP_FINAL = "rng_event_ztp_final"
DATASET_GUMBEL = "rng_event_gumbel_key"
DATASET_DIRICHLET = "rng_event_dirichlet_gamma_vector"
DATASET_STREAM_JUMP = "rng_event_stream_jump"
DATASET_NORMAL = "rng_event_normal_box_muller"
DATASET_RESIDUAL = "rng_event_residual_rank"
DATASET_SEQUENCE_FINAL = "rng_event_sequence_finalize"
DATASET_SEQUENCE_OVERFLOW = "rng_event_site_sequence_overflow"
DATASET_VALIDATION_BUNDLE = "validation_bundle_1A"
DATASET_VALIDATION_INDEX = "validation_bundle_index_1A"
DATASET_VALIDATION_FLAG = "validation_passed_flag_1A"
DATASET_S3_INTEGERISATION_POLICY = "policy.s3.integerisation.yaml"

NONCONSUMING_FAMILIES = {
    "anchor",
    "nb_final",
    "ztp_rejection",
    "ztp_retry_exhausted",
    "ztp_final",
    "residual_rank",
    "sequence_finalize",
    "site_sequence_overflow",
}


@dataclass(frozen=True)
class S9RunResult:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    decision: str
    bundle_root: Path


@dataclass(frozen=True)
class S3IntegerisationPolicy:
    semver: str
    version: str
    emit_integerised_counts: bool
    emit_site_sequence: bool


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
    def __init__(self, seed: int, parameter_hash: str, manifest_fingerprint: str) -> None:
        self._seed = seed
        self._parameter_hash = parameter_hash
        self._manifest_fingerprint = manifest_fingerprint
        self.failures: list[dict] = []
        self.failures_by_code: dict[str, int] = defaultdict(int)
        self.failed_merchants: set[int] = set()

    def record(
        self,
        code: str,
        scope: str,
        reason: str,
        dataset_id: Optional[str] = None,
        anchor: Optional[str] = None,
        merchant_id: Optional[int] = None,
        country_iso: Optional[str] = None,
        attempt: Optional[int] = None,
        expected: Optional[object] = None,
        observed: Optional[object] = None,
    ) -> None:
        payload = {
            "s9.fail.code": code,
            "s9.fail.scope": scope,
            "s9.fail.reason": reason,
            "s9.run.seed": self._seed,
            "s9.run.parameter_hash": self._parameter_hash,
            "s9.run.manifest_fingerprint": self._manifest_fingerprint,
        }
        if dataset_id:
            payload["s9.fail.dataset_id"] = dataset_id
        if anchor:
            payload["s9.fail.anchor"] = anchor
        if merchant_id is not None:
            payload["s9.fail.merchant_id"] = int(merchant_id)
            if scope == "MERCHANT":
                self.failed_merchants.add(int(merchant_id))
        if country_iso:
            payload["s9.fail.country_iso"] = country_iso
        if attempt is not None:
            payload["s9.fail.attempt"] = int(attempt)
        if expected is not None:
            payload["s9.fail.expected"] = expected
        if observed is not None:
            payload["s9.fail.observed"] = observed
        self.failures.append(payload)
        self.failures_by_code[code] += 1


def _json_bytes(payload: object) -> bytes:
    return json.dumps(
        payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_json_bytes(payload))


def _write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True, sort_keys=True))
            handle.write("\n")

def _schema_from_pack(schema_pack: dict, path: str) -> dict:
    node: dict = schema_pack
    for part in path.strip("#/").split("/"):
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
    return schema


def _schema_section(schema_pack: dict, section: str) -> dict:
    node = schema_pack.get(section)
    if not isinstance(node, dict):
        raise ContractError(f"Schema section not found: {section}")
    subset = {"$id": schema_pack.get("$id", ""), "$defs": schema_pack.get("$defs", {})}
    subset.update(node)
    return subset


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


def _row_validator(schema_pack: dict, path: str) -> Draft202012Validator:
    pack, table_name = _table_pack(schema_pack, path)
    table_def = pack[table_name]
    if isinstance(table_def, dict) and "columns" in table_def:
        row_schema = table_to_jsonschema(pack, table_name)["items"]
    elif isinstance(table_def, dict) and "record" in table_def:
        record = table_def.get("record")
        if not isinstance(record, dict):
            raise ContractError(f"Invalid record schema for {path}")
        row_schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": pack.get("$id", ""),
            "$defs": pack.get("$defs", {}),
        }
        row_schema.update(record)
        row_schema = _apply_nullable_properties(row_schema)
    else:
        row_schema = _schema_from_pack(schema_pack, path)
    return Draft202012Validator(row_schema)


def _select_dataset_file(dataset_id: str, dataset_path: Path) -> Path:
    if dataset_path.is_file():
        return dataset_path
    if not dataset_path.exists():
        raise InputResolutionError(f"Dataset path does not exist: {dataset_path}")
    if not dataset_path.is_dir():
        raise InputResolutionError(f"Dataset path is not a file or dir: {dataset_path}")
    explicit = dataset_path / f"{dataset_id}.parquet"
    if explicit.exists():
        return explicit
    parquet_files = sorted(dataset_path.glob("*.parquet"))
    if len(parquet_files) == 1:
        return parquet_files[0]
    raise InputResolutionError(
        f"Unable to resolve dataset file in {dataset_path}; "
        f"expected {explicit.name} or a single parquet file."
    )


def _dataset_has_parquet(root: Path) -> bool:
    if not root.exists():
        return False
    if root.is_file() and root.suffix == ".parquet":
        return True
    if root.is_dir():
        return any(root.glob("*.parquet"))
    return False


def _iter_jsonl_files(paths: Iterable[Path]):
    for path in paths:
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                yield path, line_no, json.loads(line)


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise InputResolutionError(f"Missing JSON file: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        raise InputResolutionError(f"Missing YAML file: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _pick_latest_run_receipt(runs_root: Path) -> Path:
    candidates = sorted(
        runs_root.glob("*/run_receipt.json"),
        key=lambda path: path.stat().st_mtime,
    )
    if not candidates:
        raise InputResolutionError(f"No run_receipt.json found under {runs_root}")
    return candidates[-1]


def _resolve_run_receipt(runs_root: Path, run_id: Optional[str]) -> tuple[Path, dict]:
    if run_id:
        receipt_path = runs_root / run_id / "run_receipt.json"
        return receipt_path, _load_json(receipt_path)
    receipt_path = _pick_latest_run_receipt(runs_root)
    return receipt_path, _load_json(receipt_path)


def _load_sealed_inputs(path: Path) -> list[dict]:
    payload = _load_json(path)
    if not isinstance(payload, list):
        raise InputResolutionError("sealed_inputs_1A payload must be a list.")
    return payload


def _sealed_path(sealed_inputs: list[dict], asset_id: str) -> Path:
    for entry in sealed_inputs:
        if entry.get("asset_id") == asset_id:
            raw = entry.get("path")
            if not raw:
                raise InputResolutionError(f"sealed_inputs_1A missing path for {asset_id}")
            return Path(raw)
    raise InputResolutionError(f"sealed_inputs_1A missing asset_id {asset_id}")


def _resolve_run_path(run_paths: RunPaths, path_template: str, tokens: dict[str, str]) -> Path:
    path = path_template
    for key, value in tokens.items():
        path = path.replace(f"{{{key}}}", value)
    return run_paths.run_root / path


def _resolve_run_glob(run_paths: RunPaths, path_template: str, tokens: dict[str, str]) -> list[Path]:
    path = path_template
    for key, value in tokens.items():
        path = path.replace(f"{{{key}}}", value)
    if "*" in path:
        return sorted(run_paths.run_root.glob(path))
    return [run_paths.run_root / path]


def _resolve_event_path(run_paths: RunPaths, path_template: str, tokens: dict[str, str]) -> Path:
    path = path_template
    for key, value in tokens.items():
        path = path.replace(f"{{{key}}}", value)
    if "part-*.jsonl" in path:
        path = path.replace("part-*.jsonl", "part-00000.jsonl")
    elif "*" in path:
        raise InputResolutionError(f"Unhandled wildcard path template: {path_template}")
    return run_paths.run_root / path


def _resolve_event_dir(run_paths: RunPaths, path_template: str, tokens: dict[str, str]) -> Path:
    path = path_template
    for key, value in tokens.items():
        path = path.replace(f"{{{key}}}", value)
    if "part-*.jsonl" in path:
        return (run_paths.run_root / path).parent
    if "*" in path:
        raise InputResolutionError(f"Unhandled wildcard path template: {path_template}")
    return (run_paths.run_root / path).parent


def _event_has_rows(paths: Iterable[Path]) -> bool:
    for path in paths:
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    return True
    return False


def _resolve_registry_path(
    path_template: str, repo_root: Path, artifact_name: Optional[str] = None
) -> Path:
    has_version_token = "{version}" in path_template
    if "{" not in path_template:
        return repo_root / path_template
    pattern = path_template
    for token in (
        "{config_version}",
        "{policy_version}",
        "{iso8601_timestamp}",
        "{version}",
    ):
        if token in pattern:
            pattern = pattern.replace(token, "*")
    matches = sorted(repo_root.glob(pattern))
    matches = [path for path in matches if path.exists()]
    if not matches:
        raise InputResolutionError(
            f"No files match registry path template: {path_template}"
        )
    if has_version_token:
        dated = []
        for path in matches:
            version_label = path.name if path.is_dir() else path.parent.name
            if _DATE_VERSION_RE.fullmatch(version_label):
                dated.append((version_label, path))
        if dated:
            resolved = sorted(dated, key=lambda item: item[0])[-1][1]
        else:
            resolved = matches[-1]
    else:
        resolved = matches[-1]
    if resolved.is_dir():
        if artifact_name:
            for suffix in (".parquet", ".csv", ".json", ".yaml", ".yml", ".jsonl"):
                candidate = resolved / f"{artifact_name}{suffix}"
                if candidate.exists():
                    return candidate
        parquet_files = sorted(resolved.glob("*.parquet"))
        if len(parquet_files) == 1:
            return parquet_files[0]
        files = sorted([path for path in resolved.iterdir() if path.is_file()])
        if len(files) == 1:
            return files[0]
        raise InputResolutionError(
            f"Registry path template resolved to directory with multiple files: {resolved}"
        )
    return resolved


def find_registry_entry(registry: dict, name: str) -> dict:
    subsegments = registry.get("subsegments", [])
    for subsegment in subsegments:
        for artifact in subsegment.get("artifacts", []):
            if artifact.get("name") == name:
                return artifact
    raise ContractError(f"Registry entry not found: {name}")


def _resolve_param_files(registry: dict, repo_root: Path) -> tuple[list[NamedPath], dict[str, str]]:
    mapping = {
        "hurdle_coefficients.yaml": "hurdle_coefficients",
        "nb_dispersion_coefficients.yaml": "nb_dispersion_coefficients",
        "crossborder_hyperparams.yaml": "crossborder_hyperparams",
        "ccy_smoothing_params.yaml": "ccy_smoothing_params",
        "policy.s2.tile_weights.yaml": "policy.s2.tile_weights.yaml",
        "policy.s3.rule_ladder.yaml": "policy.s3.rule_ladder.yaml",
        "s6_selection_policy.yaml": "s6_selection_policy",
        "s7_integerisation_policy.yaml": "s7_integerisation_policy",
        "policy.s3.base_weight.yaml": "policy.s3.base_weight.yaml",
        "policy.s3.thresholds.yaml": "policy.s3.thresholds.yaml",
        "policy.s3.integerisation.yaml": "policy.s3.integerisation.yaml",
    }
    params: list[NamedPath] = []
    resolved_map: dict[str, str] = {}
    for canonical_name, artifact_name in mapping.items():
        try:
            entry = find_registry_entry(registry, artifact_name)
        except ContractError:
            if canonical_name.startswith("policy.s3."):
                continue
            raise
        path_template = entry.get("path")
        if not path_template:
            raise ContractError(f"Registry entry missing path for {artifact_name}")
        resolved_path = _resolve_registry_path(path_template, repo_root, artifact_name)
        if not resolved_path.exists():
            if canonical_name.startswith("policy.s3."):
                continue
            raise InputResolutionError(f"Missing parameter file: {resolved_path}")
        params.append(NamedPath(name=canonical_name, path=resolved_path))
        resolved_map[canonical_name] = artifact_name
    return params, resolved_map


def _git_hex_to_bytes(git_hex: str) -> bytes:
    git_hex = git_hex.strip().lower()
    raw = bytes.fromhex(git_hex)
    if len(raw) == 20:
        return b"\x00" * 12 + raw
    if len(raw) == 32:
        return raw
    raise InputResolutionError("Unexpected git hash length; expected SHA-1 or SHA-256.")


def _resolve_git_bytes(repo_root: Path) -> bytes:
    env_hash = os.environ.get("ENGINE_GIT_COMMIT")
    if env_hash:
        return _git_hex_to_bytes(env_hash)
    git_file = repo_root / "ci" / "manifests" / "git_commit_hash.txt"
    if git_file.exists():
        return _git_hex_to_bytes(git_file.read_text(encoding="utf-8").strip())
    try:
        output = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_root)
        return _git_hex_to_bytes(output.decode("utf-8").strip())
    except Exception as exc:
        raise InputResolutionError("Unable to resolve git commit hash.") from exc


def _load_audit_commit(path: Path) -> Optional[bytes]:
    if not path.exists():
        return None
    for _path, _line_no, payload in _iter_jsonl_files([path]):
        commit_hex = payload.get("build_commit")
        if commit_hex:
            try:
                return _git_hex_to_bytes(str(commit_hex))
            except Exception:
                return None
        break
    return None


def _apply_nullable_properties(schema: dict) -> dict:
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return schema
    rewritten = {}
    for name, prop in properties.items():
        if isinstance(prop, dict) and prop.get("nullable"):
            base = dict(prop)
            base.pop("nullable", None)
            if "$ref" in base:
                ref = base.pop("$ref")
                if base:
                    base_schema = {"allOf": [{"$ref": ref}, base]}
                else:
                    base_schema = {"$ref": ref}
            else:
                base_schema = base
            rewritten[name] = {"anyOf": [base_schema, {"type": "null"}]}
        else:
            rewritten[name] = prop
    schema["properties"] = rewritten
    return schema


def _load_s3_integerisation_policy(path: Path, schema_layer1: dict) -> S3IntegerisationPolicy:
    payload = _load_yaml(path)
    schema = _schema_from_pack(schema_layer1, "policy/s3_integerisation")
    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(payload))
    if errors:
        raise EngineFailure(
            "F4",
            "E_SCHEMA_INVALID",
            "S9",
            MODULE_NAME,
            {"detail": errors[0].message, "path": path.as_posix()},
        )
    return S3IntegerisationPolicy(
        semver=str(payload.get("semver")),
        version=str(payload.get("version")),
        emit_integerised_counts=bool(payload.get("emit_integerised_counts")),
        emit_site_sequence=bool(payload.get("emit_site_sequence")),
    )


def _segment_state_runs_path(run_paths: RunPaths, dictionary: dict, utc_day: str) -> Path:
    entry = find_dataset_entry(dictionary, "segment_state_runs").entry
    path_template = entry["path"]
    path = path_template.replace("{utc_day}", utc_day)
    return run_paths.run_root / path


def _require_pass_receipt(receipt_path: Path, passed_flag_path: Path, detail: str) -> None:
    if not receipt_path.exists() or not passed_flag_path.exists():
        raise EngineFailure(
            "F4",
            "E_PASS_GATE_MISSING",
            "S9",
            MODULE_NAME,
            {"detail": detail},
        )
    expected_hash = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
    flag_contents = passed_flag_path.read_text(encoding="ascii").strip()
    if flag_contents != f"sha256_hex = {expected_hash}":
        raise EngineFailure(
            "F4",
            "E_PASS_GATE_MISSING",
            "S9",
            MODULE_NAME,
            {"detail": f"{detail}_hash_mismatch"},
        )


def _u128(hi: int, lo: int) -> int:
    return (int(hi) << 64) + int(lo)


def _parse_draws(value: object) -> int:
    if value is None:
        return 0
    if isinstance(value, str):
        return int(value)
    return int(value)


def _trace_key(payload: dict) -> tuple[str, str, str]:
    return (
        str(payload.get("module", "")),
        str(payload.get("substream_label", "")),
        str(payload.get("run_id", "")),
    )


def _trace_score(payload: dict) -> tuple[int, str, int, int]:
    return (
        int(payload.get("events_total", 0)),
        str(payload.get("ts_utc", "")),
        int(payload.get("rng_counter_after_hi", 0)),
        int(payload.get("rng_counter_after_lo", 0)),
    )


def _bundle_hash(bundle_root: Path, index_entries: list[dict]) -> str:
    paths = sorted(entry["path"] for entry in index_entries if entry.get("path"))
    hasher = hashlib.sha256()
    for path in paths:
        hasher.update((bundle_root / path).read_bytes())
    return hasher.hexdigest()

def run_s9(
    config: EngineConfig, run_id: Optional[str] = None, validate_only: bool = False
) -> S9RunResult:
    logger = get_logger("engine.layers.l1.seg_1A.s9_validation.l2.runner")
    timer = _StepTimer(logger)

    source = ContractSource(
        layout=config.contracts_layout,
        root=config.contracts_root,
    )
    dictionary_path, dictionary = load_dataset_dictionary(source, "1A")
    registry_path, registry = load_artefact_registry(source, "1A")
    schema_layer1_path, schema_layer1 = load_schema_pack(source, "1A", "layer1")
    schema_1a_path, schema_1a = load_schema_pack(source, "1A", "1A")
    ingress_schema_path, ingress_schema = load_schema_pack(source, "1A", "ingress.layer1")
    timer.info(
        f"S9: contracts layout={config.contracts_layout} root={config.contracts_root}"
    )

    receipt_path, receipt = _resolve_run_receipt(config.runs_root, run_id)
    run_id = str(receipt.get("run_id"))
    seed = int(receipt.get("seed"))
    parameter_hash = str(receipt.get("parameter_hash"))
    manifest_fingerprint = str(receipt.get("manifest_fingerprint"))

    run_paths = RunPaths(config.runs_root, run_id)
    add_file_handler(run_paths.run_root / f"run_log_{run_id}.log")
    timer.info(f"S9: loaded run receipt {receipt_path}")

    tokens = {
        "seed": str(seed),
        "parameter_hash": parameter_hash,
        "manifest_fingerprint": manifest_fingerprint,
        "run_id": run_id,
    }

    tracker = _FailureTracker(seed, parameter_hash, manifest_fingerprint)
    checks = {
        "schema_pk_fk": True,
        "path_embed_equality": True,
        "rng_envelope": True,
        "rng_trace_coverage": True,
        "s1..s8_replay": True,
        "egress_writer_sort": True,
    }

    def mark_check_false(key: str) -> None:
        if key in checks:
            checks[key] = False

    def record_failure(
        code: str,
        scope: str,
        reason: str,
        dataset_id: Optional[str] = None,
        anchor: Optional[str] = None,
        merchant_id: Optional[int] = None,
        country_iso: Optional[str] = None,
        attempt: Optional[int] = None,
        expected: Optional[object] = None,
        observed: Optional[object] = None,
        check_key: Optional[str] = None,
    ) -> None:
        if check_key:
            mark_check_false(check_key)
        tracker.record(
            code,
            scope,
            reason,
            dataset_id=dataset_id,
            anchor=anchor,
            merchant_id=merchant_id,
            country_iso=country_iso,
            attempt=attempt,
            expected=expected,
            observed=observed,
        )

    # Sealed inputs and lineage recompute
    sealed_inputs = []
    opened_paths: dict[Path, FileDigest] = {}
    try:
        sealed_entry = find_dataset_entry(dictionary, DATASET_SEALED_INPUTS).entry
        sealed_path = _resolve_run_path(run_paths, sealed_entry["path"], tokens)
        sealed_inputs = _load_sealed_inputs(sealed_path)
        item_schema = _schema_from_pack(schema_1a, "validation/sealed_inputs_1A/items")
        item_validator = Draft202012Validator(item_schema)
        for entry in sealed_inputs:
            errors = list(item_validator.iter_errors(entry))
            if errors:
                record_failure(
                    "E_SCHEMA_INVALID",
                    "RUN",
                    errors[0].message,
                    dataset_id=DATASET_SEALED_INPUTS,
                    check_key="schema_pk_fk",
                )
                break
        for entry in sealed_inputs:
            asset_path = Path(entry.get("path", ""))
            if not asset_path.exists():
                record_failure(
                    "E_LINEAGE_SEAL_MISMATCH",
                    "RUN",
                    "sealed_input_missing",
                    dataset_id=DATASET_SEALED_INPUTS,
                    anchor=entry.get("asset_id"),
                    check_key="path_embed_equality",
                )
                continue
            digest = sha256_file(asset_path)
            opened_paths[asset_path] = digest
            if entry.get("sha256_hex") != digest.sha256_hex:
                record_failure(
                    "E_LINEAGE_SEAL_MISMATCH",
                    "RUN",
                    "sealed_input_digest_mismatch",
                    dataset_id=DATASET_SEALED_INPUTS,
                    anchor=entry.get("asset_id"),
                    check_key="path_embed_equality",
                    expected=entry.get("sha256_hex"),
                    observed=digest.sha256_hex,
                )
    except Exception as exc:
        record_failure(
            "E_LINEAGE_SEAL_MISMATCH",
            "RUN",
            str(exc),
            dataset_id=DATASET_SEALED_INPUTS,
            check_key="path_embed_equality",
        )

    # Parameter hash recompute
    param_digests: list[NamedDigest] = []
    parameter_hash_recomputed = parameter_hash
    try:
        param_files, _param_name_map = _resolve_param_files(registry, config.repo_root)
        parameter_hash_recomputed, parameter_hash_bytes, param_digests = compute_parameter_hash(
            param_files
        )
        if parameter_hash_recomputed != parameter_hash:
            record_failure(
                "E_LINEAGE_RECOMPUTE_MISMATCH",
                "RUN",
                "parameter_hash_mismatch",
                dataset_id="parameter_hash",
                check_key="path_embed_equality",
                expected=parameter_hash,
                observed=parameter_hash_recomputed,
            )
    except (ContractError, InputResolutionError, HashingError) as exc:
        record_failure(
            "E_LINEAGE_RECOMPUTE_MISMATCH",
            "RUN",
            str(exc),
            dataset_id="parameter_hash",
            check_key="path_embed_equality",
        )
        parameter_hash_bytes = b""

    # Numeric policy attestation (for manifest recompute)
    attestation_payload: dict = {}
    attestation_bytes = b""
    attestation_digest = FileDigest(path=Path("numeric_policy_attest.json"), size_bytes=0, mtime_ns=0, sha256_hex="")
    try:
        numeric_policy_entry = find_registry_entry(registry, "numeric_policy_profile")
        numeric_policy_path = _resolve_registry_path(
            numeric_policy_entry["path"], config.repo_root, "numeric_policy_profile"
        )
        math_profile_entry = find_registry_entry(registry, "math_profile_manifest")
        math_profile_path = _resolve_registry_path(
            math_profile_entry["path"], config.repo_root, "math_profile_manifest"
        )
        attestation_payload, _ = run_numeric_self_tests(
            numeric_policy_path, math_profile_path, "1A.s9_numeric_policy"
        )
        attestation_bytes = json.dumps(
            attestation_payload,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        attestation_digest_hex = hashlib.sha256(attestation_bytes).hexdigest()
        attestation_digest = FileDigest(
            path=Path("numeric_policy_attest.json"),
            size_bytes=len(attestation_bytes),
            mtime_ns=0,
            sha256_hex=attestation_digest_hex,
        )
    except Exception as exc:
        record_failure(
            "E_NUMERIC_POLICY_ATTEST",
            "RUN",
            str(exc),
            dataset_id="numeric_policy_attest",
            check_key="schema_pk_fk",
        )
        attestation_bytes = b""
        attestation_digest_hex = hashlib.sha256(attestation_bytes).hexdigest()
        attestation_digest = FileDigest(
            path=Path("numeric_policy_attest.json"),
            size_bytes=len(attestation_bytes),
            mtime_ns=0,
            sha256_hex=attestation_digest_hex,
        )

    # Add seed file to manifest inputs if it matches run seed
    seed_path = config.repo_root / "config" / "layer1" / "1A" / "rng" / "run_seed.yaml"
    if seed_path.exists():
        try:
            seed_payload = _load_yaml(seed_path)
            if int(seed_payload.get("seed")) == seed:
                opened_paths[seed_path] = sha256_file(seed_path)
        except Exception:
            pass

    opened_artifacts: list[NamedDigest] = []
    for path, digest in sorted(opened_paths.items(), key=lambda item: item[0].name):
        opened_artifacts.append(NamedDigest(name=path.name, digest=digest))
    opened_artifacts.append(
        NamedDigest(name="numeric_policy_attest.json", digest=attestation_digest)
    )

    audit_path_hint: Optional[Path] = None
    audit_commit_bytes: Optional[bytes] = None
    try:
        audit_entry = find_dataset_entry(dictionary, DATASET_AUDIT).entry
        audit_path_hint = _resolve_run_path(run_paths, audit_entry["path"], tokens)
        audit_commit_bytes = _load_audit_commit(audit_path_hint)
    except Exception:
        audit_commit_bytes = None

    manifest_fingerprint_recomputed = manifest_fingerprint
    try:
        git_bytes = audit_commit_bytes or _resolve_git_bytes(config.repo_root)
        manifest_fingerprint_recomputed, _ = compute_manifest_fingerprint(
            opened_artifacts, git_bytes, parameter_hash_bytes
        )
        if manifest_fingerprint_recomputed != manifest_fingerprint:
            record_failure(
                "E_LINEAGE_RECOMPUTE_MISMATCH",
                "RUN",
                "manifest_fingerprint_mismatch",
                dataset_id="manifest_fingerprint",
                check_key="path_embed_equality",
                expected=manifest_fingerprint,
                observed=manifest_fingerprint_recomputed,
            )
    except (InputResolutionError, HashingError) as exc:
        record_failure(
            "E_LINEAGE_RECOMPUTE_MISMATCH",
            "RUN",
            str(exc),
            dataset_id="manifest_fingerprint",
            check_key="path_embed_equality",
        )
        git_bytes = b""

    # ISO set
    iso_set: set[str] = set()
    try:
        iso_path = _sealed_path(sealed_inputs, "iso3166_canonical_2024")
        iso_df = pl.read_parquet(iso_path)
        iso_set = set(iso_df["country_iso"].to_list())
    except Exception as exc:
        record_failure(
            "E_SCHEMA_INVALID",
            "RUN",
            f"iso3166_load_failed: {exc}",
            dataset_id="iso3166_canonical_2024",
            check_key="schema_pk_fk",
        )

    # Policy: integerisation ownership
    policy_entry = find_registry_entry(registry, "policy.s3.integerisation.yaml")
    policy_path = _resolve_registry_path(
        policy_entry["path"], config.repo_root, "policy.s3.integerisation.yaml"
    )
    policy = _load_s3_integerisation_policy(policy_path, schema_layer1)
    counts_source = "s3_integerised_counts" if policy.emit_integerised_counts else "residual_rank"

    # Candidate set
    candidate_map: dict[int, dict[str, int]] = {}
    candidate_home: dict[int, str] = {}
    try:
        candidate_entry = find_dataset_entry(dictionary, DATASET_CANDIDATE_SET).entry
        candidate_root = _resolve_run_path(run_paths, candidate_entry["path"], tokens)
        candidate_file = _select_dataset_file(DATASET_CANDIDATE_SET, candidate_root)
        candidate_df = pl.read_parquet(candidate_file)
        candidate_pack, candidate_table = _table_pack(schema_1a, "s3/candidate_set")
        validate_dataframe(
            candidate_df.iter_rows(named=True),
            candidate_pack,
            candidate_table,
        )
        if candidate_df.filter(pl.col("parameter_hash") != parameter_hash).height > 0:
            record_failure(
                "E_PATH_EMBED_MISMATCH",
                "RUN",
                "candidate_set_parameter_hash",
                dataset_id=DATASET_CANDIDATE_SET,
                check_key="path_embed_equality",
            )
        candidate_df = candidate_df.sort(["merchant_id", "candidate_rank", "country_iso"])
        current_mid = None
        expected_rank = 0
        home_count = 0
        for row in candidate_df.iter_rows(named=True):
            mid = int(row["merchant_id"])
            if current_mid is None:
                current_mid = mid
            if mid != current_mid:
                if expected_rank == 0 or home_count != 1:
                    record_failure(
                        "E_ORDER_AUTHORITY_DRIFT",
                        "MERCHANT",
                        "candidate_rows_incomplete",
                        dataset_id=DATASET_CANDIDATE_SET,
                        merchant_id=current_mid,
                        check_key="s1..s8_replay",
                    )
                current_mid = mid
                expected_rank = 0
                home_count = 0
            rank = int(row["candidate_rank"])
            if rank != expected_rank:
                record_failure(
                    "E_ORDER_AUTHORITY_DRIFT",
                    "MERCHANT",
                    "candidate_rank_not_contiguous",
                    dataset_id=DATASET_CANDIDATE_SET,
                    merchant_id=mid,
                    check_key="s1..s8_replay",
                )
            expected_rank += 1
            country_iso = str(row["country_iso"])
            if iso_set and country_iso not in iso_set:
                record_failure(
                    "E_FK_ISO_INVALID",
                    "MERCHANT",
                    "candidate_set_iso_unknown",
                    dataset_id=DATASET_CANDIDATE_SET,
                    merchant_id=mid,
                    country_iso=country_iso,
                    check_key="schema_pk_fk",
                )
            candidate_map.setdefault(mid, {})[country_iso] = rank
            if bool(row["is_home"]):
                home_count += 1
                candidate_home[mid] = country_iso
        if current_mid is not None and (expected_rank == 0 or home_count != 1):
            record_failure(
                "E_ORDER_AUTHORITY_DRIFT",
                "MERCHANT",
                "candidate_rows_incomplete",
                dataset_id=DATASET_CANDIDATE_SET,
                merchant_id=current_mid,
                check_key="s1..s8_replay",
            )
        timer.info(f"S9: loaded candidate_set merchants={len(candidate_map)}")
    except Exception as exc:
        record_failure(
            "E_SCHEMA_INVALID",
            "RUN",
            str(exc),
            dataset_id=DATASET_CANDIDATE_SET,
            check_key="schema_pk_fk",
        )
        candidate_map = {}

    # Outlet catalogue scan
    counts_map: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    final_count_map: dict[int, dict[str, int]] = defaultdict(dict)
    site_orders: dict[int, dict[str, set[int]]] = defaultdict(lambda: defaultdict(set))
    egress_multi_flag: dict[int, bool] = {}
    egress_nb_draw: dict[int, int] = {}
    egress_files: list[Path] = []
    egress_has_rows = False
    outlet_root: Optional[Path] = None
    try:
        outlet_entry = find_dataset_entry(dictionary, DATASET_OUTLET).entry
        outlet_root = _resolve_run_path(run_paths, outlet_entry["path"], tokens)
        if outlet_root.is_file() and outlet_root.suffix == ".parquet":
            egress_files = [outlet_root]
        elif outlet_root.exists():
            egress_files = sorted(outlet_root.glob("*.parquet"))
        if not egress_files:
            record_failure(
                "E_SCHEMA_INVALID",
                "RUN",
                "outlet_catalogue_missing",
                dataset_id=DATASET_OUTLET,
                check_key="schema_pk_fk",
            )
        last_key = None
        outlet_pack, outlet_table = _table_pack(schema_1a, "egress/outlet_catalogue")
        for file_path in egress_files:
            df = pl.read_parquet(file_path)
            validate_dataframe(
                df.iter_rows(named=True),
                outlet_pack,
                outlet_table,
            )
            for row in df.iter_rows(named=True):
                egress_has_rows = True
                if row.get("manifest_fingerprint") != manifest_fingerprint:
                    record_failure(
                        "E_PATH_EMBED_MISMATCH",
                        "RUN",
                        "outlet_manifest_fingerprint",
                        dataset_id=DATASET_OUTLET,
                        check_key="path_embed_equality",
                    )
                if int(row.get("global_seed", seed)) != seed:
                    record_failure(
                        "E_PATH_EMBED_MISMATCH",
                        "RUN",
                        "outlet_seed_mismatch",
                        dataset_id=DATASET_OUTLET,
                        check_key="path_embed_equality",
                    )
                merchant_id = int(row["merchant_id"])
                legal_iso = str(row["legal_country_iso"])
                if iso_set and legal_iso not in iso_set:
                    record_failure(
                        "E_FK_ISO_INVALID",
                        "MERCHANT",
                        "outlet_legal_iso_unknown",
                        dataset_id=DATASET_OUTLET,
                        merchant_id=merchant_id,
                        country_iso=legal_iso,
                        check_key="schema_pk_fk",
                    )
                key = (merchant_id, legal_iso, int(row["site_order"]))
                if last_key is not None and key < last_key:
                    record_failure(
                        "E_EGRESS_WRITER_SORT",
                        "RUN",
                        "writer_sort_violation",
                        dataset_id=DATASET_OUTLET,
                        check_key="egress_writer_sort",
                        observed={"prev": last_key, "current": key},
                    )
                last_key = key
                multi_flag = bool(row.get("single_vs_multi_flag", False))
                if merchant_id not in egress_multi_flag:
                    egress_multi_flag[merchant_id] = multi_flag
                elif egress_multi_flag[merchant_id] != multi_flag:
                    record_failure(
                        "E_S1_GATING_VIOLATION",
                        "MERCHANT",
                        "egress_multi_flag_inconsistent",
                        dataset_id=DATASET_OUTLET,
                        merchant_id=merchant_id,
                        check_key="s1..s8_replay",
                    )
                nb_draw = int(row.get("raw_nb_outlet_draw", 0))
                if merchant_id not in egress_nb_draw:
                    egress_nb_draw[merchant_id] = nb_draw
                elif egress_nb_draw[merchant_id] != nb_draw:
                    record_failure(
                        "E_S2_COMPONENT_ORDER",
                        "MERCHANT",
                        "egress_nb_draw_inconsistent",
                        dataset_id=DATASET_OUTLET,
                        merchant_id=merchant_id,
                        check_key="s1..s8_replay",
                    )
                site_order = int(row["site_order"])
                site_id = row.get("site_id")
                if site_id and site_id != str(site_order).zfill(6):
                    record_failure(
                        "E_SITE_ID_OVERFLOW",
                        "MERCHANT",
                        "site_id_mismatch",
                        dataset_id=DATASET_OUTLET,
                        merchant_id=merchant_id,
                        country_iso=legal_iso,
                        check_key="s1..s8_replay",
                        expected=str(site_order).zfill(6),
                        observed=site_id,
                    )
                counts_map[merchant_id][legal_iso] += 1
                site_orders[merchant_id][legal_iso].add(site_order)
                if legal_iso in final_count_map[merchant_id]:
                    if final_count_map[merchant_id][legal_iso] != int(
                        row["final_country_outlet_count"]
                    ):
                        record_failure(
                            "E_S8_SEQUENCE_GAP",
                            "MERCHANT",
                            "final_country_outlet_count_mismatch",
                            dataset_id=DATASET_OUTLET,
                            merchant_id=merchant_id,
                            country_iso=legal_iso,
                            check_key="s1..s8_replay",
                        )
                else:
                    final_count_map[merchant_id][legal_iso] = int(
                        row["final_country_outlet_count"]
                    )
    except Exception as exc:
        record_failure(
            "E_SCHEMA_INVALID",
            "RUN",
            str(exc),
            dataset_id=DATASET_OUTLET,
            check_key="schema_pk_fk",
        )

    # Enforce site_order contiguity
    for merchant_id, countries in site_orders.items():
        for country_iso, orders in countries.items():
            expected = set(range(1, counts_map[merchant_id][country_iso] + 1))
            if orders != expected:
                record_failure(
                    "E_S8_SEQUENCE_GAP",
                    "MERCHANT",
                    "site_order_gap",
                    dataset_id=DATASET_OUTLET,
                    merchant_id=merchant_id,
                    country_iso=country_iso,
                    check_key="s1..s8_replay",
                    expected=sorted(expected),
                    observed=sorted(orders),
                )

    # Membership dataset
    membership_map: dict[int, set[str]] = defaultdict(set)
    membership_source = "gumbel_key"
    try:
        membership_entry = find_dataset_entry(dictionary, DATASET_MEMBERSHIP).entry
        membership_root = _resolve_run_path(run_paths, membership_entry["path"], tokens)
        if _dataset_has_parquet(membership_root):
            membership_source = "s6_membership"
            membership_file = _select_dataset_file(DATASET_MEMBERSHIP, membership_root)
            membership_df = pl.read_parquet(membership_file)
            membership_pack, membership_table = _table_pack(schema_1a, "alloc/membership")
            validate_dataframe(
                membership_df.iter_rows(named=True),
                membership_pack,
                membership_table,
            )
            for row in membership_df.iter_rows(named=True):
                if int(row.get("seed", seed)) != seed:
                    record_failure(
                        "E_PATH_EMBED_MISMATCH",
                        "RUN",
                        "membership_seed_mismatch",
                        dataset_id=DATASET_MEMBERSHIP,
                        check_key="path_embed_equality",
                    )
                if row.get("parameter_hash") != parameter_hash:
                    record_failure(
                        "E_PATH_EMBED_MISMATCH",
                        "RUN",
                        "membership_parameter_hash",
                        dataset_id=DATASET_MEMBERSHIP,
                        check_key="path_embed_equality",
                    )
                country_iso = str(row["country_iso"])
                merchant_id = int(row["merchant_id"])
                if iso_set and country_iso not in iso_set:
                    record_failure(
                        "E_FK_ISO_INVALID",
                        "MERCHANT",
                        "membership_iso_unknown",
                        dataset_id=DATASET_MEMBERSHIP,
                        merchant_id=merchant_id,
                        country_iso=country_iso,
                        check_key="schema_pk_fk",
                    )
                membership_map[merchant_id].add(country_iso)
    except ContractError:
        membership_source = "gumbel_key"
    except Exception as exc:
        record_failure(
            "E_SCHEMA_INVALID",
            "RUN",
            str(exc),
            dataset_id=DATASET_MEMBERSHIP,
            check_key="schema_pk_fk",
        )

    # S6 pass receipt gate if membership is used
    if membership_source == "s6_membership":
        try:
            s6_entry = find_dataset_entry(dictionary, DATASET_S6_RECEIPT).entry
            s6_root = _resolve_run_path(run_paths, s6_entry["path"], tokens)
            receipt_path = s6_root / "S6_VALIDATION.json"
            flag_path = s6_root / "_passed.flag"
            _require_pass_receipt(receipt_path, flag_path, "s6_pass_receipt")
        except EngineFailure as exc:
            record_failure(
                "E_PASS_GATE_MISSING",
                "RUN",
                str(exc),
                dataset_id=DATASET_S6_RECEIPT,
                check_key="s1..s8_replay",
            )

    # Crossborder eligibility flags (optional)
    eligibility_map: dict[int, bool] = {}
    eligibility_reason: dict[int, str] = {}
    try:
        eligibility_entry = find_dataset_entry(dictionary, DATASET_ELIGIBILITY).entry
        eligibility_root = _resolve_run_path(run_paths, eligibility_entry["path"], tokens)
        if _dataset_has_parquet(eligibility_root):
            eligibility_file = _select_dataset_file(DATASET_ELIGIBILITY, eligibility_root)
            eligibility_df = pl.read_parquet(eligibility_file)
            eligibility_pack, eligibility_table = _table_pack(
                schema_1a, "prep/crossborder_eligibility_flags"
            )
            validate_dataframe(
                eligibility_df.iter_rows(named=True),
                eligibility_pack,
                eligibility_table,
            )
            if eligibility_df.filter(pl.col("parameter_hash") != parameter_hash).height > 0:
                record_failure(
                    "E_PATH_EMBED_MISMATCH",
                    "RUN",
                    "eligibility_parameter_hash",
                    dataset_id=DATASET_ELIGIBILITY,
                    check_key="path_embed_equality",
                )
            for row in eligibility_df.iter_rows(named=True):
                merchant_id = int(row["merchant_id"])
                eligibility_map[merchant_id] = bool(row["is_eligible"])
                reason = row.get("reason")
                if reason is not None:
                    eligibility_reason[merchant_id] = str(reason)
            timer.info(
                f"S9: loaded crossborder_eligibility_flags merchants={len(eligibility_map)}"
            )
    except ContractError:
        pass
    except Exception as exc:
        record_failure(
            "E_SCHEMA_INVALID",
            "RUN",
            str(exc),
            dataset_id=DATASET_ELIGIBILITY,
            check_key="schema_pk_fk",
        )

    # S3 integerised counts (optional via policy)
    s3_counts_map: dict[int, dict[str, int]] = defaultdict(dict)
    s3_residual_rank: dict[int, dict[str, int]] = defaultdict(dict)
    s3_counts_present = False
    if policy.emit_integerised_counts:
        try:
            counts_entry = find_dataset_entry(dictionary, DATASET_COUNTS).entry
            counts_root = _resolve_run_path(run_paths, counts_entry["path"], tokens)
            counts_file = _select_dataset_file(DATASET_COUNTS, counts_root)
            counts_df = pl.read_parquet(counts_file)
            counts_pack, counts_table = _table_pack(schema_1a, "s3/integerised_counts")
            validate_dataframe(
                counts_df.iter_rows(named=True),
                counts_pack,
                counts_table,
            )
            if counts_df.filter(pl.col("parameter_hash") != parameter_hash).height > 0:
                record_failure(
                    "E_PATH_EMBED_MISMATCH",
                    "RUN",
                    "s3_counts_parameter_hash",
                    dataset_id=DATASET_COUNTS,
                    check_key="path_embed_equality",
                )
            for row in counts_df.iter_rows(named=True):
                merchant_id = int(row["merchant_id"])
                country_iso = str(row["country_iso"])
                if iso_set and country_iso not in iso_set:
                    record_failure(
                        "E_FK_ISO_INVALID",
                        "MERCHANT",
                        "s3_counts_iso_unknown",
                        dataset_id=DATASET_COUNTS,
                        merchant_id=merchant_id,
                        country_iso=country_iso,
                        check_key="schema_pk_fk",
                    )
                s3_counts_map[merchant_id][country_iso] = int(row["count"])
                s3_residual_rank[merchant_id][country_iso] = int(row["residual_rank"])
            s3_counts_present = True
            timer.info(f"S9: loaded s3_integerised_counts rows={counts_df.height}")
        except Exception as exc:
            record_failure(
                "E_SCHEMA_INVALID",
                "RUN",
                str(exc),
                dataset_id=DATASET_COUNTS,
                check_key="schema_pk_fk",
            )
    else:
        try:
            counts_entry = find_dataset_entry(dictionary, DATASET_COUNTS).entry
            counts_root = _resolve_run_path(run_paths, counts_entry["path"], tokens)
            if _dataset_has_parquet(counts_root):
                record_failure(
                    "E_S7_PARITY",
                    "RUN",
                    "s3_integerised_counts_unexpected",
                    dataset_id=DATASET_COUNTS,
                    check_key="s1..s8_replay",
                )
        except ContractError:
            pass

    # S3 site sequence (optional via policy)
    s3_sequence_present = False
    s3_sequence_counts: dict[int, dict[str, int]] = defaultdict(dict)
    if policy.emit_site_sequence:
        try:
            seq_entry = find_dataset_entry(dictionary, DATASET_SITE_SEQUENCE).entry
            seq_root = _resolve_run_path(run_paths, seq_entry["path"], tokens)
            seq_file = _select_dataset_file(DATASET_SITE_SEQUENCE, seq_root)
            seq_df = pl.read_parquet(seq_file)
            seq_pack, seq_table = _table_pack(schema_1a, "s3/site_sequence")
            validate_dataframe(
                seq_df.iter_rows(named=True),
                seq_pack,
                seq_table,
            )
            if seq_df.filter(pl.col("parameter_hash") != parameter_hash).height > 0:
                record_failure(
                    "E_PATH_EMBED_MISMATCH",
                    "RUN",
                    "s3_site_sequence_parameter_hash",
                    dataset_id=DATASET_SITE_SEQUENCE,
                    check_key="path_embed_equality",
                )
            seq_df = seq_df.sort(["merchant_id", "country_iso", "site_order"])
            current_mid = None
            current_iso = None
            expected_site = 1
            for row in seq_df.iter_rows(named=True):
                merchant_id = int(row["merchant_id"])
                country_iso = str(row["country_iso"])
                if iso_set and country_iso not in iso_set:
                    record_failure(
                        "E_FK_ISO_INVALID",
                        "MERCHANT",
                        "s3_site_sequence_iso_unknown",
                        dataset_id=DATASET_SITE_SEQUENCE,
                        merchant_id=merchant_id,
                        country_iso=country_iso,
                        check_key="schema_pk_fk",
                    )
                if current_mid != merchant_id or current_iso != country_iso:
                    current_mid = merchant_id
                    current_iso = country_iso
                    expected_site = 1
                site_order = int(row["site_order"])
                if site_order != expected_site:
                    record_failure(
                        "E_S8_SEQUENCE_GAP",
                        "MERCHANT",
                        "s3_site_sequence_gap",
                        dataset_id=DATASET_SITE_SEQUENCE,
                        merchant_id=merchant_id,
                        country_iso=country_iso,
                        check_key="s1..s8_replay",
                    )
                expected_site += 1
                site_id = row.get("site_id")
                if site_id and site_id != str(site_order).zfill(6):
                    record_failure(
                        "E_S8_SEQUENCE_GAP",
                        "MERCHANT",
                        "s3_site_sequence_site_id_mismatch",
                        dataset_id=DATASET_SITE_SEQUENCE,
                        merchant_id=merchant_id,
                        country_iso=country_iso,
                        check_key="s1..s8_replay",
                    )
                s3_sequence_counts[merchant_id][country_iso] = site_order
            s3_sequence_present = True
            timer.info(f"S9: loaded s3_site_sequence rows={seq_df.height}")
        except Exception as exc:
            record_failure(
                "E_SCHEMA_INVALID",
                "RUN",
                str(exc),
                dataset_id=DATASET_SITE_SEQUENCE,
                check_key="schema_pk_fk",
            )
    else:
        try:
            seq_entry = find_dataset_entry(dictionary, DATASET_SITE_SEQUENCE).entry
            seq_root = _resolve_run_path(run_paths, seq_entry["path"], tokens)
            if _dataset_has_parquet(seq_root):
                record_failure(
                    "E_S8_SEQUENCE_GAP",
                    "RUN",
                    "s3_site_sequence_unexpected",
                    dataset_id=DATASET_SITE_SEQUENCE,
                    check_key="s1..s8_replay",
                )
        except ContractError:
            pass

    # RNG event accounting
    family_stats: dict[str, dict] = {}
    trace_event_totals: dict[tuple[str, str, str], dict[str, int]] = {}
    run_ids_seen: set[str] = set()

    hurdle_events: dict[int, dict] = {}
    nb_final_events: dict[int, dict] = {}
    nb_gamma_counts: dict[int, int] = defaultdict(int)
    nb_poisson_counts: dict[int, int] = defaultdict(int)
    ztp_poisson_attempts: dict[int, set[int]] = defaultdict(set)
    ztp_rejection_attempts: dict[int, set[int]] = defaultdict(set)
    ztp_retry_attempts: dict[int, set[int]] = defaultdict(set)
    ztp_final_events: dict[int, dict] = {}
    gumbel_selected: dict[int, set[str]] = defaultdict(set)
    residual_events: dict[int, list[tuple[str, float, int]]] = defaultdict(list)
    residual_seen: set[tuple[int, str]] = set()
    sequence_finalize_events: dict[int, dict[str, dict]] = defaultdict(dict)
    overflow_events: dict[int, dict[str, dict]] = defaultdict(dict)

    family_label_map = {
        DATASET_ANCHOR: "anchor",
        DATASET_HURDLE: "hurdle_bernoulli",
        DATASET_GAMMA: "gamma_component",
        DATASET_POISSON: "poisson_component",
        DATASET_NB_FINAL: "nb_final",
        DATASET_ZTP_REJECTION: "ztp_rejection",
        DATASET_ZTP_RETRY: "ztp_retry_exhausted",
        DATASET_ZTP_FINAL: "ztp_final",
        DATASET_GUMBEL: "gumbel_key",
        DATASET_DIRICHLET: "dirichlet_gamma_vector",
        DATASET_STREAM_JUMP: "stream_jump",
        DATASET_NORMAL: "normal_box_muller",
        DATASET_RESIDUAL: "residual_rank",
        DATASET_SEQUENCE_FINAL: "sequence_finalize",
        DATASET_SEQUENCE_OVERFLOW: "site_sequence_overflow",
    }

    event_dataset_ids = list(family_label_map.keys())

    for dataset_id in event_dataset_ids:
        try:
            entry = find_dataset_entry(dictionary, dataset_id).entry
        except ContractError:
            continue
        schema_ref = entry.get("schema_ref", "")
        schema_pack = schema_layer1 if schema_ref.startswith("schemas.layer1.yaml#") else schema_1a
        schema_path = schema_ref.split("#", maxsplit=1)[-1].lstrip("/")
        validator = _row_validator(schema_pack, schema_path)
        event_dir = _resolve_event_dir(run_paths, entry["path"], tokens)
        if not event_dir.exists():
            continue
        event_files = sorted(event_dir.glob("*.jsonl"))
        if not event_files:
            continue

        for path, line_no, payload in _iter_jsonl_files(event_files):
            errors = list(validator.iter_errors(payload))
            if errors:
                record_failure(
                    "E_SCHEMA_INVALID",
                    "RUN",
                    f"{dataset_id}:{errors[0].message}",
                    dataset_id=dataset_id,
                    check_key="schema_pk_fk",
                )
            if int(payload.get("seed", seed)) != seed:
                record_failure(
                    "E_PATH_EMBED_MISMATCH",
                    "RUN",
                    "event_seed_mismatch",
                    dataset_id=dataset_id,
                    check_key="path_embed_equality",
                )
            if payload.get("parameter_hash") != parameter_hash:
                record_failure(
                    "E_PATH_EMBED_MISMATCH",
                    "RUN",
                    "event_parameter_hash_mismatch",
                    dataset_id=dataset_id,
                    check_key="path_embed_equality",
                )
            if payload.get("run_id") != run_id:
                record_failure(
                    "E_PATH_EMBED_MISMATCH",
                    "RUN",
                    "event_run_id_mismatch",
                    dataset_id=dataset_id,
                    check_key="path_embed_equality",
                )
            if payload.get("manifest_fingerprint") != manifest_fingerprint:
                record_failure(
                    "E_PATH_EMBED_MISMATCH",
                    "RUN",
                    "event_manifest_fingerprint_mismatch",
                    dataset_id=dataset_id,
                    check_key="path_embed_equality",
                )

            draws = _parse_draws(payload.get("draws"))
            blocks = int(payload.get("blocks", 0))
            before = _u128(payload.get("rng_counter_before_hi", 0), payload.get("rng_counter_before_lo", 0))
            after = _u128(payload.get("rng_counter_after_hi", 0), payload.get("rng_counter_after_lo", 0))
            if after - before != blocks:
                record_failure(
                    "E_RNG_COUNTER_MISMATCH",
                    "RUN",
                    "counter_delta_mismatch",
                    dataset_id=dataset_id,
                    check_key="rng_envelope",
                    expected=blocks,
                    observed=after - before,
                )

            family_label = family_label_map[dataset_id]
            context = payload.get("context")
            if dataset_id == DATASET_POISSON and context in ("nb", "ztp"):
                family_label = f"poisson_component_{context}"
            if dataset_id == DATASET_GAMMA and context in ("nb", "dirichlet"):
                family_label = f"gamma_component_{context}"

            module = str(payload.get("module", ""))
            substream = str(payload.get("substream_label", ""))
            trace_key = (module, substream, str(payload.get("run_id", "")))
            run_ids_seen.add(trace_key[2])

            stats = family_stats.setdefault(
                family_label,
                {
                    "module": module,
                    "substream_label": substream,
                    "run_id": trace_key[2],
                    "events_total": 0,
                    "draws_total": 0,
                    "blocks_total": 0,
                    "nonconsuming_events": 0,
                    "trace_key": trace_key,
                },
            )
            if stats.get("trace_key") != trace_key:
                record_failure(
                    "E_RNG_COUNTER_MISMATCH",
                    "RUN",
                    "trace_key_mismatch",
                    dataset_id=dataset_id,
                    check_key="rng_envelope",
                )
            stats["events_total"] += 1
            stats["draws_total"] += int(draws)
            stats["blocks_total"] += blocks
            if blocks == 0 and draws == 0:
                stats["nonconsuming_events"] += 1

            totals = trace_event_totals.setdefault(
                trace_key, {"events_total": 0, "draws_total": 0, "blocks_total": 0}
            )
            totals["events_total"] += 1
            totals["draws_total"] += int(draws)
            totals["blocks_total"] += blocks

            if family_label in NONCONSUMING_FAMILIES and (blocks != 0 or draws != 0):
                record_failure(
                    "E_NONCONSUMING_CHANGED_COUNTERS",
                    "RUN",
                    "nonconsuming_budget_violation",
                    dataset_id=dataset_id,
                    check_key="rng_envelope",
                )
            if family_label == "gumbel_key" and (blocks != 1 or draws != 1):
                record_failure(
                    "E_RNG_BUDGET_VIOLATION",
                    "RUN",
                    "gumbel_budget_violation",
                    dataset_id=dataset_id,
                    check_key="rng_envelope",
                )
            if family_label == "hurdle_bernoulli":
                deterministic = bool(payload.get("deterministic"))
                if deterministic and (blocks != 0 or draws != 0):
                    record_failure(
                        "E_NONCONSUMING_CHANGED_COUNTERS",
                        "RUN",
                        "hurdle_deterministic_budget",
                        dataset_id=dataset_id,
                        check_key="rng_envelope",
                    )
                if (not deterministic) and (blocks != 1 or draws != 1):
                    record_failure(
                        "E_RNG_BUDGET_VIOLATION",
                        "RUN",
                        "hurdle_stochastic_budget",
                        dataset_id=dataset_id,
                        check_key="rng_envelope",
                    )

            if dataset_id == DATASET_HURDLE:
                merchant_id = int(payload.get("merchant_id", 0))
                if merchant_id in hurdle_events:
                    record_failure(
                        "E_S1_CARDINALITY",
                        "MERCHANT",
                        "duplicate_hurdle_event",
                        dataset_id=dataset_id,
                        merchant_id=merchant_id,
                        check_key="s1..s8_replay",
                    )
                hurdle_events[merchant_id] = payload
            elif dataset_id == DATASET_NB_FINAL:
                merchant_id = int(payload.get("merchant_id", 0))
                if merchant_id in nb_final_events:
                    record_failure(
                        "E_FINALISER_CARDINALITY",
                        "MERCHANT",
                        "duplicate_nb_final",
                        dataset_id=dataset_id,
                        merchant_id=merchant_id,
                        check_key="s1..s8_replay",
                    )
                nb_final_events[merchant_id] = payload
            elif dataset_id == DATASET_GAMMA:
                merchant_id = int(payload.get("merchant_id", 0))
                if context == "nb":
                    nb_gamma_counts[merchant_id] += 1
            elif dataset_id == DATASET_POISSON:
                merchant_id = int(payload.get("merchant_id", 0))
                if context == "nb":
                    nb_poisson_counts[merchant_id] += 1
                elif context == "ztp":
                    attempt = int(payload.get("attempt", 0))
                    ztp_poisson_attempts[merchant_id].add(attempt)
            elif dataset_id == DATASET_ZTP_REJECTION:
                merchant_id = int(payload.get("merchant_id", 0))
                attempt = int(payload.get("attempt", 0))
                ztp_rejection_attempts[merchant_id].add(attempt)
            elif dataset_id == DATASET_ZTP_RETRY:
                merchant_id = int(payload.get("merchant_id", 0))
                attempts = int(payload.get("attempts", 0))
                ztp_retry_attempts[merchant_id].add(attempts)
            elif dataset_id == DATASET_ZTP_FINAL:
                merchant_id = int(payload.get("merchant_id", 0))
                if merchant_id in ztp_final_events:
                    record_failure(
                        "E_FINALISER_CARDINALITY",
                        "MERCHANT",
                        "duplicate_ztp_final",
                        dataset_id=dataset_id,
                        merchant_id=merchant_id,
                        check_key="s1..s8_replay",
                    )
                ztp_final_events[merchant_id] = payload
            elif dataset_id == DATASET_GUMBEL:
                merchant_id = int(payload.get("merchant_id", 0))
                country_iso = str(payload.get("country_iso", ""))
                if iso_set and country_iso not in iso_set:
                    record_failure(
                        "E_FK_ISO_INVALID",
                        "MERCHANT",
                        "gumbel_iso_unknown",
                        dataset_id=dataset_id,
                        merchant_id=merchant_id,
                        country_iso=country_iso,
                        check_key="schema_pk_fk",
                    )
                if payload.get("weight", 0) == 0 and payload.get("selected") is True:
                    record_failure(
                        "E_S6_ZERO_WEIGHT_SELECTED",
                        "MERCHANT",
                        "gumbel_zero_weight_selected",
                        dataset_id=dataset_id,
                        merchant_id=merchant_id,
                        country_iso=country_iso,
                        check_key="s1..s8_replay",
                    )
                if payload.get("selected") is True:
                    gumbel_selected[merchant_id].add(country_iso)
            elif dataset_id == DATASET_RESIDUAL:
                merchant_id = int(payload.get("merchant_id", 0))
                country_iso = str(payload.get("country_iso", ""))
                if iso_set and country_iso not in iso_set:
                    record_failure(
                        "E_FK_ISO_INVALID",
                        "MERCHANT",
                        "residual_iso_unknown",
                        dataset_id=dataset_id,
                        merchant_id=merchant_id,
                        country_iso=country_iso,
                        check_key="schema_pk_fk",
                    )
                key = (merchant_id, country_iso)
                if key in residual_seen:
                    record_failure(
                        "E_S7_PARITY",
                        "MERCHANT",
                        "duplicate_residual_rank",
                        dataset_id=dataset_id,
                        merchant_id=merchant_id,
                        country_iso=country_iso,
                        check_key="s1..s8_replay",
                    )
                residual_seen.add(key)
                residual = float(payload.get("residual", 0.0))
                residual_rank = int(payload.get("residual_rank", 0))
                residual_events[merchant_id].append((country_iso, residual, residual_rank))
            elif dataset_id == DATASET_SEQUENCE_FINAL:
                merchant_id = int(payload.get("merchant_id", 0))
                country_iso = str(payload.get("country_iso", payload.get("legal_country_iso", "")))
                if country_iso in sequence_finalize_events[merchant_id]:
                    record_failure(
                        "E_FINALISER_CARDINALITY",
                        "MERCHANT",
                        "duplicate_sequence_finalize",
                        dataset_id=dataset_id,
                        merchant_id=merchant_id,
                        country_iso=country_iso,
                        check_key="s1..s8_replay",
                    )
                sequence_finalize_events[merchant_id][country_iso] = payload
            elif dataset_id == DATASET_SEQUENCE_OVERFLOW:
                merchant_id = int(payload.get("merchant_id", 0))
                country_iso = str(payload.get("country_iso", ""))
                overflow_events[merchant_id][country_iso] = payload

    if run_id not in run_ids_seen and run_ids_seen:
        record_failure(
            "E_PATH_EMBED_MISMATCH",
            "RUN",
            "event_run_id_missing",
            check_key="path_embed_equality",
        )

    # RNG audit log
    audit_present = False
    try:
        if audit_path_hint is None:
            audit_entry = find_dataset_entry(dictionary, DATASET_AUDIT).entry
            audit_path = _resolve_run_path(run_paths, audit_entry["path"], tokens)
        else:
            audit_path = audit_path_hint
        if audit_path.exists():
            audit_validator = _row_validator(schema_layer1, "rng/core/rng_audit_log")
            for _path, _line_no, payload in _iter_jsonl_files([audit_path]):
                audit_present = True
                errors = list(audit_validator.iter_errors(payload))
                if errors:
                    record_failure(
                        "E_SCHEMA_INVALID",
                        "RUN",
                        errors[0].message,
                        dataset_id=DATASET_AUDIT,
                        check_key="schema_pk_fk",
                    )
                if int(payload.get("seed", seed)) != seed:
                    record_failure(
                        "E_PATH_EMBED_MISMATCH",
                        "RUN",
                        "audit_seed_mismatch",
                        dataset_id=DATASET_AUDIT,
                        check_key="path_embed_equality",
                    )
                if payload.get("parameter_hash") != parameter_hash:
                    record_failure(
                        "E_PATH_EMBED_MISMATCH",
                        "RUN",
                        "audit_parameter_hash_mismatch",
                        dataset_id=DATASET_AUDIT,
                        check_key="path_embed_equality",
                    )
                if payload.get("run_id") != run_id:
                    record_failure(
                        "E_PATH_EMBED_MISMATCH",
                        "RUN",
                        "audit_run_id_mismatch",
                        dataset_id=DATASET_AUDIT,
                        check_key="path_embed_equality",
                    )
                if payload.get("manifest_fingerprint") != manifest_fingerprint:
                    record_failure(
                        "E_PATH_EMBED_MISMATCH",
                        "RUN",
                        "audit_manifest_fingerprint_mismatch",
                        dataset_id=DATASET_AUDIT,
                        check_key="path_embed_equality",
                    )
        else:
            record_failure(
                "E_TRACE_COVERAGE_MISSING",
                "RUN",
                "audit_log_missing",
                dataset_id=DATASET_AUDIT,
                check_key="rng_trace_coverage",
            )
    except Exception as exc:
        record_failure(
            "E_SCHEMA_INVALID",
            "RUN",
            str(exc),
            dataset_id=DATASET_AUDIT,
            check_key="schema_pk_fk",
        )

    # RNG trace log
    trace_rows_total: dict[tuple[str, str, str], int] = defaultdict(int)
    trace_final: dict[tuple[str, str, str], dict] = {}
    try:
        trace_entry = find_dataset_entry(dictionary, DATASET_TRACE).entry
        trace_path = _resolve_run_path(run_paths, trace_entry["path"], tokens)
        if trace_path.exists():
            trace_validator = _row_validator(schema_layer1, "rng/core/rng_trace_log")
            for _path, _line_no, payload in _iter_jsonl_files([trace_path]):
                errors = list(trace_validator.iter_errors(payload))
                if errors:
                    record_failure(
                        "E_SCHEMA_INVALID",
                        "RUN",
                        errors[0].message,
                        dataset_id=DATASET_TRACE,
                        check_key="schema_pk_fk",
                    )
                if int(payload.get("seed", seed)) != seed:
                    record_failure(
                        "E_PATH_EMBED_MISMATCH",
                        "RUN",
                        "trace_seed_mismatch",
                        dataset_id=DATASET_TRACE,
                        check_key="path_embed_equality",
                    )
                if payload.get("run_id") != run_id:
                    record_failure(
                        "E_PATH_EMBED_MISMATCH",
                        "RUN",
                        "trace_run_id_mismatch",
                        dataset_id=DATASET_TRACE,
                        check_key="path_embed_equality",
                    )
                trace_key = _trace_key(payload)
                trace_rows_total[trace_key] += 1
                best = trace_final.get(trace_key)
                if best is None or _trace_score(payload) > _trace_score(best):
                    trace_final[trace_key] = payload
        else:
            record_failure(
                "E_TRACE_COVERAGE_MISSING",
                "RUN",
                "trace_log_missing",
                dataset_id=DATASET_TRACE,
                check_key="rng_trace_coverage",
            )
    except Exception as exc:
        record_failure(
            "E_SCHEMA_INVALID",
            "RUN",
            str(exc),
            dataset_id=DATASET_TRACE,
            check_key="schema_pk_fk",
        )

    # Membership parity checks
    if membership_source == "s6_membership":
        for merchant_id, selected in gumbel_selected.items():
            expected = membership_map.get(merchant_id, set())
            if expected != selected:
                record_failure(
                    "E_S6_MEMBERSHIP_MISMATCH",
                    "MERCHANT",
                    "membership_mismatch",
                    dataset_id=DATASET_MEMBERSHIP,
                    merchant_id=merchant_id,
                    check_key="s1..s8_replay",
                    expected=sorted(expected),
                    observed=sorted(selected),
                )
        for merchant_id, countries in membership_map.items():
            for country_iso in countries:
                if merchant_id not in candidate_map or country_iso not in candidate_map.get(merchant_id, {}):
                    record_failure(
                        "E_S6_MEMBERSHIP_MISMATCH",
                        "MERCHANT",
                        "membership_outside_candidate_set",
                        dataset_id=DATASET_MEMBERSHIP,
                        merchant_id=merchant_id,
                        country_iso=country_iso,
                        check_key="s1..s8_replay",
                    )
    else:
        membership_map = gumbel_selected

    # S7 policy (dirichlet lane expectation)
    dirichlet_enabled = False
    try:
        s7_policy_entry = find_registry_entry(registry, "s7_integerisation_policy")
        s7_policy_path = _resolve_registry_path(
            s7_policy_entry["path"], config.repo_root, "s7_integerisation_policy"
        )
        s7_policy = _load_yaml(s7_policy_path)
        dirichlet_enabled = bool(
            s7_policy.get("dirichlet_lane", {}).get("enabled", False)
        )
    except Exception:
        dirichlet_enabled = False

    if dirichlet_enabled and family_stats.get("dirichlet_gamma_vector", {}).get("events_total", 0) == 0:
        record_failure(
            "E_S7_PARITY",
            "RUN",
            "dirichlet_lane_enabled_missing_events",
            dataset_id=DATASET_DIRICHLET,
            check_key="s1..s8_replay",
        )

    merchants = sorted(candidate_map.keys())
    merchants_total = len(merchants)

    for merchant_id in merchants:
        home_iso = candidate_home.get(merchant_id)
        if not home_iso:
            record_failure(
                "E_S3_HOME_NOT_ZERO",
                "MERCHANT",
                "missing_home_candidate",
                dataset_id=DATASET_CANDIDATE_SET,
                merchant_id=merchant_id,
                check_key="s1..s8_replay",
            )
            home_iso = ""

        hurdle_payload = hurdle_events.get(merchant_id)
        is_multi = False
        if hurdle_payload is None:
            record_failure(
                "E_S1_CARDINALITY",
                "MERCHANT",
                "missing_hurdle_event",
                dataset_id=DATASET_HURDLE,
                merchant_id=merchant_id,
                check_key="s1..s8_replay",
            )
        else:
            is_multi = bool(hurdle_payload.get("is_multi"))

        if merchant_id in egress_multi_flag and hurdle_payload is not None:
            if egress_multi_flag[merchant_id] != is_multi:
                record_failure(
                    "E_S1_GATING_VIOLATION",
                    "MERCHANT",
                    "egress_multi_flag_mismatch",
                    dataset_id=DATASET_OUTLET,
                    merchant_id=merchant_id,
                    check_key="s1..s8_replay",
                    expected=is_multi,
                    observed=egress_multi_flag[merchant_id],
                )

        eligible = True
        if eligibility_map:
            eligible = eligibility_map.get(merchant_id, False)
        foreign_candidates = [
            country_iso
            for country_iso in candidate_map.get(merchant_id, {})
            if country_iso != home_iso
        ]

        nb_payload = nb_final_events.get(merchant_id)
        if is_multi:
            if nb_payload is None:
                record_failure(
                    "E_FINALISER_CARDINALITY",
                    "MERCHANT",
                    "missing_nb_final",
                    dataset_id=DATASET_NB_FINAL,
                    merchant_id=merchant_id,
                    check_key="s1..s8_replay",
                )
            else:
                n_outlets = int(nb_payload.get("n_outlets", 0))
                if n_outlets < 2:
                    record_failure(
                        "E_S2_N_LT_2",
                        "MERCHANT",
                        "nb_outlets_lt_2",
                        dataset_id=DATASET_NB_FINAL,
                        merchant_id=merchant_id,
                        check_key="s1..s8_replay",
                    )
                nb_rejections = int(nb_payload.get("nb_rejections", 0))
                if nb_gamma_counts[merchant_id] < 1 or nb_poisson_counts[merchant_id] < 1:
                    record_failure(
                        "E_S2_COMPONENT_ORDER",
                        "MERCHANT",
                        "nb_component_missing",
                        dataset_id=DATASET_NB_FINAL,
                        merchant_id=merchant_id,
                        check_key="s1..s8_replay",
                    )
                if nb_gamma_counts[merchant_id] and nb_gamma_counts[merchant_id] != nb_rejections + 1:
                    record_failure(
                        "E_S2_COMPONENT_ORDER",
                        "MERCHANT",
                        "nb_gamma_attempt_mismatch",
                        dataset_id=DATASET_GAMMA,
                        merchant_id=merchant_id,
                        check_key="s1..s8_replay",
                        expected=nb_rejections + 1,
                        observed=nb_gamma_counts[merchant_id],
                    )
                if nb_poisson_counts[merchant_id] and nb_poisson_counts[merchant_id] != nb_rejections + 1:
                    record_failure(
                        "E_S2_COMPONENT_ORDER",
                        "MERCHANT",
                        "nb_poisson_attempt_mismatch",
                        dataset_id=DATASET_POISSON,
                        merchant_id=merchant_id,
                        check_key="s1..s8_replay",
                        expected=nb_rejections + 1,
                        observed=nb_poisson_counts[merchant_id],
                    )
                if merchant_id in egress_nb_draw and egress_nb_draw[merchant_id] != n_outlets:
                    record_failure(
                        "E_S2_COMPONENT_ORDER",
                        "MERCHANT",
                        "egress_nb_draw_mismatch",
                        dataset_id=DATASET_OUTLET,
                        merchant_id=merchant_id,
                        check_key="s1..s8_replay",
                        expected=n_outlets,
                        observed=egress_nb_draw[merchant_id],
                    )
        else:
            if merchant_id in nb_final_events or nb_gamma_counts[merchant_id] or nb_poisson_counts[merchant_id]:
                record_failure(
                    "E_S1_GATING_VIOLATION",
                    "MERCHANT",
                    "nb_events_when_single",
                    dataset_id=DATASET_NB_FINAL,
                    merchant_id=merchant_id,
                    check_key="s1..s8_replay",
                )

        if (not is_multi) or (not eligible):
            if merchant_id in ztp_final_events:
                record_failure(
                    "E_S1_GATING_VIOLATION",
                    "MERCHANT",
                    "ztp_final_ineligible",
                    dataset_id=DATASET_ZTP_FINAL,
                    merchant_id=merchant_id,
                    check_key="s1..s8_replay",
                )
            if gumbel_selected.get(merchant_id):
                record_failure(
                    "E_S1_GATING_VIOLATION",
                    "MERCHANT",
                    "gumbel_ineligible",
                    dataset_id=DATASET_GUMBEL,
                    merchant_id=merchant_id,
                    check_key="s1..s8_replay",
                )
        else:
            if merchant_id not in ztp_final_events:
                record_failure(
                    "E_FINALISER_CARDINALITY",
                    "MERCHANT",
                    "missing_ztp_final",
                    dataset_id=DATASET_ZTP_FINAL,
                    merchant_id=merchant_id,
                    check_key="s1..s8_replay",
                )

        if merchant_id in ztp_final_events:
            payload = ztp_final_events[merchant_id]
            attempts_seen = 0
            if ztp_poisson_attempts[merchant_id]:
                attempts_seen = max(attempts_seen, max(ztp_poisson_attempts[merchant_id]))
            if ztp_rejection_attempts[merchant_id]:
                attempts_seen = max(attempts_seen, max(ztp_rejection_attempts[merchant_id]))
            if ztp_retry_attempts[merchant_id]:
                attempts_seen = max(attempts_seen, max(ztp_retry_attempts[merchant_id]))
            if attempts_seen:
                expected_attempts = set(range(1, attempts_seen + 1))
                if expected_attempts != ztp_poisson_attempts[merchant_id]:
                    record_failure(
                        "E_S4_SEQUENCE_INVALID",
                        "MERCHANT",
                        "ztp_attempt_gap",
                        dataset_id=DATASET_POISSON,
                        merchant_id=merchant_id,
                        check_key="s1..s8_replay",
                        expected=sorted(expected_attempts),
                        observed=sorted(ztp_poisson_attempts[merchant_id]),
                    )
            if int(payload.get("attempts", 0)) != attempts_seen:
                record_failure(
                    "E_S4_SEQUENCE_INVALID",
                    "MERCHANT",
                    "ztp_attempt_mismatch",
                    dataset_id=DATASET_ZTP_FINAL,
                    merchant_id=merchant_id,
                    check_key="s1..s8_replay",
                    expected=attempts_seen,
                    observed=int(payload.get("attempts", 0)),
                )

        in_scope = merchant_id in ztp_final_events
        if not in_scope:
            continue

        domain = set()
        if home_iso:
            domain.add(home_iso)
        domain.update(membership_map.get(merchant_id, set()))

        counts_source_map = s3_counts_map if s3_counts_present else counts_map
        counts_for_mid = counts_source_map.get(merchant_id, {})

        if domain:
            missing = domain - set(counts_for_mid)
            extra = set(counts_for_mid) - domain
            if missing and s3_counts_present:
                record_failure(
                    "E_S7_PARITY",
                    "MERCHANT",
                    "counts_missing_domain",
                    dataset_id=DATASET_COUNTS if s3_counts_present else DATASET_OUTLET,
                    merchant_id=merchant_id,
                    check_key="s1..s8_replay",
                    expected=sorted(domain),
                    observed=sorted(counts_for_mid),
                )
            if extra:
                record_failure(
                    "E_S7_PARITY",
                    "MERCHANT",
                    "counts_extra_domain",
                    dataset_id=DATASET_COUNTS if s3_counts_present else DATASET_OUTLET,
                    merchant_id=merchant_id,
                    check_key="s1..s8_replay",
                    expected=sorted(domain),
                    observed=sorted(counts_for_mid),
                )

        expected_n = None
        if nb_payload is not None:
            expected_n = int(nb_payload.get("n_outlets", 0))
        elif merchant_id in egress_nb_draw:
            expected_n = egress_nb_draw[merchant_id]

        if expected_n is not None:
            total_counts = sum(int(value) for value in counts_for_mid.values())
            if total_counts != expected_n:
                record_failure(
                    "E_SUM_MISMATCH",
                    "MERCHANT",
                    "sum_counts_mismatch",
                    dataset_id=DATASET_COUNTS if s3_counts_present else DATASET_OUTLET,
                    merchant_id=merchant_id,
                    check_key="s1..s8_replay",
                    expected=expected_n,
                    observed=total_counts,
                )

        residual_list = residual_events.get(merchant_id, [])
        if domain and len(residual_list) != len(domain):
            record_failure(
                "E_S7_PARITY",
                "MERCHANT",
                "residual_rank_missing",
                dataset_id=DATASET_RESIDUAL,
                merchant_id=merchant_id,
                check_key="s1..s8_replay",
                expected=len(domain),
                observed=len(residual_list),
            )
        residual_map = {iso: (resid, rank) for iso, resid, rank in residual_list}
        if domain and residual_map:
            ranks = sorted(item[1] for item in residual_map.values())
            expected_ranks = list(range(1, len(domain) + 1))
            if ranks != expected_ranks:
                record_failure(
                    "E_S7_PARITY",
                    "MERCHANT",
                    "residual_rank_not_contiguous",
                    dataset_id=DATASET_RESIDUAL,
                    merchant_id=merchant_id,
                    check_key="s1..s8_replay",
                )
            for country_iso in domain:
                if country_iso not in candidate_map.get(merchant_id, {}):
                    record_failure(
                        "E_S7_PARITY",
                        "MERCHANT",
                        "residual_iso_not_in_candidate",
                        dataset_id=DATASET_RESIDUAL,
                        merchant_id=merchant_id,
                        country_iso=country_iso,
                        check_key="s1..s8_replay",
                    )
            expected_order = sorted(
                domain,
                key=lambda iso: (
                    -residual_map.get(iso, (0.0, 0))[0],
                    iso,
                    candidate_map.get(merchant_id, {}).get(iso, 0),
                ),
            )
            for idx, country_iso in enumerate(expected_order, start=1):
                observed_rank = residual_map.get(country_iso, (0.0, 0))[1]
                if observed_rank != idx:
                    record_failure(
                        "E_S7_PARITY",
                        "MERCHANT",
                        "residual_rank_order_mismatch",
                        dataset_id=DATASET_RESIDUAL,
                        merchant_id=merchant_id,
                        country_iso=country_iso,
                        check_key="s1..s8_replay",
                        expected=idx,
                        observed=observed_rank,
                    )

        for country_iso, count in counts_for_mid.items():
            count = int(count)
            if count <= 0:
                continue
            if count > 999999:
                if country_iso not in overflow_events.get(merchant_id, {}):
                    record_failure(
                        "E_SITE_ID_OVERFLOW",
                        "MERCHANT",
                        "overflow_event_missing",
                        dataset_id=DATASET_SEQUENCE_OVERFLOW,
                        merchant_id=merchant_id,
                        country_iso=country_iso,
                        check_key="s1..s8_replay",
                    )
                if counts_map.get(merchant_id, {}).get(country_iso, 0) > 0:
                    record_failure(
                        "E_SITE_ID_OVERFLOW",
                        "MERCHANT",
                        "overflow_rows_present",
                        dataset_id=DATASET_OUTLET,
                        merchant_id=merchant_id,
                        country_iso=country_iso,
                        check_key="s1..s8_replay",
                    )
                continue

            if s3_counts_present and counts_map.get(merchant_id, {}).get(country_iso, 0) != count:
                record_failure(
                    "E_S7_PARITY",
                    "MERCHANT",
                    "egress_count_mismatch",
                    dataset_id=DATASET_OUTLET,
                    merchant_id=merchant_id,
                    country_iso=country_iso,
                    check_key="s1..s8_replay",
                    expected=count,
                    observed=counts_map.get(merchant_id, {}).get(country_iso, 0),
                )

            if country_iso not in site_orders.get(merchant_id, {}):
                record_failure(
                    "E_S8_SEQUENCE_GAP",
                    "MERCHANT",
                    "site_order_missing",
                    dataset_id=DATASET_OUTLET,
                    merchant_id=merchant_id,
                    country_iso=country_iso,
                    check_key="s1..s8_replay",
                )

            seq_event = sequence_finalize_events.get(merchant_id, {}).get(country_iso)
            if seq_event is None:
                record_failure(
                    "E_S8_SEQUENCE_GAP",
                    "MERCHANT",
                    "sequence_finalize_missing",
                    dataset_id=DATASET_SEQUENCE_FINAL,
                    merchant_id=merchant_id,
                    country_iso=country_iso,
                    check_key="s1..s8_replay",
                )
            else:
                if seq_event.get("start_sequence") != "000001":
                    record_failure(
                        "E_S8_SEQUENCE_GAP",
                        "MERCHANT",
                        "sequence_start_mismatch",
                        dataset_id=DATASET_SEQUENCE_FINAL,
                        merchant_id=merchant_id,
                        country_iso=country_iso,
                        check_key="s1..s8_replay",
                    )
                if seq_event.get("end_sequence") != str(count).zfill(6):
                    record_failure(
                        "E_S8_SEQUENCE_GAP",
                        "MERCHANT",
                        "sequence_end_mismatch",
                        dataset_id=DATASET_SEQUENCE_FINAL,
                        merchant_id=merchant_id,
                        country_iso=country_iso,
                        check_key="s1..s8_replay",
                        expected=str(count).zfill(6),
                        observed=seq_event.get("end_sequence"),
                    )
                if int(seq_event.get("site_count", count)) != count:
                    record_failure(
                        "E_S8_SEQUENCE_GAP",
                        "MERCHANT",
                        "sequence_count_mismatch",
                        dataset_id=DATASET_SEQUENCE_FINAL,
                        merchant_id=merchant_id,
                        country_iso=country_iso,
                        check_key="s1..s8_replay",
                        expected=count,
                        observed=seq_event.get("site_count"),
                    )

    for merchant_id in nb_final_events:
        if merchant_id not in candidate_map:
            record_failure(
                "E_ORDER_AUTHORITY_DRIFT",
                "MERCHANT",
                "nb_final_unknown_merchant",
                dataset_id=DATASET_NB_FINAL,
                merchant_id=merchant_id,
                check_key="s1..s8_replay",
            )
    for merchant_id in gumbel_selected:
        if merchant_id not in candidate_map:
            record_failure(
                "E_ORDER_AUTHORITY_DRIFT",
                "MERCHANT",
                "gumbel_unknown_merchant",
                dataset_id=DATASET_GUMBEL,
                merchant_id=merchant_id,
                check_key="s1..s8_replay",
            )
    for merchant_id in residual_events:
        if merchant_id not in candidate_map:
            record_failure(
                "E_ORDER_AUTHORITY_DRIFT",
                "MERCHANT",
                "residual_unknown_merchant",
                dataset_id=DATASET_RESIDUAL,
                merchant_id=merchant_id,
                check_key="s1..s8_replay",
            )

    if s3_sequence_present:
        for merchant_id, countries in s3_sequence_counts.items():
            for country_iso, site_order in countries.items():
                if s3_counts_present:
                    expected_count = s3_counts_map.get(merchant_id, {}).get(country_iso)
                else:
                    expected_count = counts_map.get(merchant_id, {}).get(country_iso)
                if expected_count is None:
                    record_failure(
                        "E_S8_SEQUENCE_GAP",
                        "MERCHANT",
                        "s3_site_sequence_orphan",
                        dataset_id=DATASET_SITE_SEQUENCE,
                        merchant_id=merchant_id,
                        country_iso=country_iso,
                        check_key="s1..s8_replay",
                    )
                    continue
                if int(site_order) != int(expected_count):
                    record_failure(
                        "E_S8_SEQUENCE_GAP",
                        "MERCHANT",
                        "s3_site_sequence_count_mismatch",
                        dataset_id=DATASET_SITE_SEQUENCE,
                        merchant_id=merchant_id,
                        country_iso=country_iso,
                        check_key="s1..s8_replay",
                        expected=expected_count,
                        observed=site_order,
                    )

    # RNG accounting summary
    family_keys = sorted(
        {
            "anchor",
            "hurdle_bernoulli",
            "gamma_component_nb",
            "gamma_component_dirichlet",
            "poisson_component_nb",
            "poisson_component_ztp",
            "nb_final",
            "ztp_rejection",
            "ztp_retry_exhausted",
            "ztp_final",
            "gumbel_key",
            "dirichlet_gamma_vector",
            "stream_jump",
            "normal_box_muller",
            "residual_rank",
            "sequence_finalize",
            "site_sequence_overflow",
        }
    )
    rng_accounting: dict[str, object] = {
        "runs": [
            {"seed": seed, "parameter_hash": parameter_hash, "run_id": rid}
            for rid in sorted(run_ids_seen or {run_id})
        ],
        "families": {},
    }
    trace_key_totals: dict[tuple[str, str, str], dict[str, int]] = defaultdict(
        lambda: {"events_total": 0, "draws_total": 0, "blocks_total": 0}
    )
    for stats in family_stats.values():
        if int(stats.get("events_total", 0)) <= 0:
            continue
        key = (
            str(stats.get("module", "")),
            str(stats.get("substream_label", "")),
            str(stats.get("run_id", run_id)),
        )
        totals = trace_key_totals[key]
        totals["events_total"] += int(stats.get("events_total", 0))
        totals["draws_total"] += int(stats.get("draws_total", 0))
        totals["blocks_total"] += int(stats.get("blocks_total", 0))
    trace_failures_seen: set[tuple[tuple[str, str, str], str]] = set()

    for family_label in family_keys:
        stats = family_stats.get(
            family_label,
            {
                "module": "",
                "substream_label": "",
                "run_id": run_id,
                "events_total": 0,
                "draws_total": 0,
                "blocks_total": 0,
                "nonconsuming_events": 0,
                "trace_key": ("", "", run_id),
            },
        )
        trace_key = None
        if stats.get("events_total", 0) > 0:
            trace_key = (
                str(stats.get("module", "")),
                str(stats.get("substream_label", "")),
                str(stats.get("run_id", "")),
            )
        expected_totals = trace_key_totals.get(
            trace_key, {"events_total": 0, "draws_total": 0, "blocks_total": 0}
        )
        trace_rows = trace_rows_total.get(trace_key, 0) if trace_key else 0
        trace_payload = trace_final.get(trace_key) if trace_key else None
        trace_totals = {
            "events_total": int(trace_payload.get("events_total", 0)) if trace_payload else 0,
            "draws_total_u128_dec": str(trace_payload.get("draws_total", 0))
            if trace_payload
            else "0",
            "blocks_total_u64": int(trace_payload.get("blocks_total", 0)) if trace_payload else 0,
        }
        coverage_ok = True
        if expected_totals["events_total"] != trace_rows:
            coverage_ok = False
            if trace_key and (trace_key, "trace_rows_mismatch") not in trace_failures_seen:
                trace_failures_seen.add((trace_key, "trace_rows_mismatch"))
                record_failure(
                    "E_TRACE_COVERAGE_MISSING",
                    "RUN",
                    "trace_rows_mismatch",
                    dataset_id=DATASET_TRACE,
                    check_key="rng_trace_coverage",
                    expected=expected_totals["events_total"],
                    observed=trace_rows,
                )
        if trace_payload is None and expected_totals["events_total"] > 0:
            coverage_ok = False
            if trace_key and (trace_key, "trace_missing") not in trace_failures_seen:
                trace_failures_seen.add((trace_key, "trace_missing"))
                record_failure(
                    "E_TRACE_COVERAGE_MISSING",
                    "RUN",
                    "trace_missing",
                    dataset_id=DATASET_TRACE,
                    check_key="rng_trace_coverage",
                )
        if trace_payload is not None:
            if int(trace_payload.get("events_total", 0)) != expected_totals["events_total"]:
                coverage_ok = False
                if trace_key and (trace_key, "trace_events_total_mismatch") not in trace_failures_seen:
                    trace_failures_seen.add((trace_key, "trace_events_total_mismatch"))
                    record_failure(
                        "E_TRACE_TOTALS_MISMATCH",
                        "RUN",
                        "trace_events_total_mismatch",
                        dataset_id=DATASET_TRACE,
                        check_key="rng_trace_coverage",
                        expected=expected_totals["events_total"],
                        observed=int(trace_payload.get("events_total", 0)),
                    )
            if int(trace_payload.get("blocks_total", 0)) != expected_totals["blocks_total"]:
                coverage_ok = False
                if trace_key and (trace_key, "trace_blocks_total_mismatch") not in trace_failures_seen:
                    trace_failures_seen.add((trace_key, "trace_blocks_total_mismatch"))
                    record_failure(
                        "E_TRACE_TOTALS_MISMATCH",
                        "RUN",
                        "trace_blocks_total_mismatch",
                        dataset_id=DATASET_TRACE,
                        check_key="rng_trace_coverage",
                        expected=expected_totals["blocks_total"],
                        observed=int(trace_payload.get("blocks_total", 0)),
                    )
            if int(trace_payload.get("draws_total", 0)) != expected_totals["draws_total"]:
                coverage_ok = False
                if trace_key and (trace_key, "trace_draws_total_mismatch") not in trace_failures_seen:
                    trace_failures_seen.add((trace_key, "trace_draws_total_mismatch"))
                    record_failure(
                        "E_TRACE_TOTALS_MISMATCH",
                        "RUN",
                        "trace_draws_total_mismatch",
                        dataset_id=DATASET_TRACE,
                        check_key="rng_trace_coverage",
                        expected=expected_totals["draws_total"],
                        observed=int(trace_payload.get("draws_total", 0)),
                    )

        rng_accounting["families"][family_label] = {
            "events_total": stats["events_total"],
            "draws_total_u128_dec": str(stats["draws_total"]),
            "blocks_total_u64": stats["blocks_total"],
            "nonconsuming_events": stats["nonconsuming_events"],
            "trace_rows_total": trace_rows,
            "trace_totals": trace_totals,
            "audit_present": audit_present,
            "coverage_ok": coverage_ok,
        }

    decision = "PASS" if not tracker.failures else "FAIL"
    summary_payload = {
        "run": {
            "seed": seed,
            "parameter_hash": parameter_hash,
            "manifest_fingerprint": manifest_fingerprint,
            "decision": decision,
        },
        "merchants_total": merchants_total,
        "merchants_failed": len(tracker.failed_merchants),
        "failures_by_code": dict(tracker.failures_by_code),
        "counts_source": counts_source,
        "membership_source": membership_source,
        "checks": checks,
    }

    if tracker.failures:
        summary_payload["failures"] = tracker.failures

    # Egress checksums
    egress_checksums = {
        "dataset_id": DATASET_OUTLET,
        "seed": seed,
        "manifest_fingerprint": manifest_fingerprint,
        "files": [],
        "composite_sha256_hex": "",
    }
    if outlet_root is None:
        record_failure(
            "E_SCHEMA_INVALID",
            "RUN",
            "outlet_root_missing",
            dataset_id=DATASET_OUTLET,
            check_key="schema_pk_fk",
        )
    else:
        file_lookup: dict[str, Path] = {}
        for file_path in sorted(egress_files, key=lambda path: path.name):
            digest = sha256_file(file_path)
            try:
                rel_path = file_path.relative_to(outlet_root).as_posix()
            except ValueError:
                rel_path = file_path.name
            egress_checksums["files"].append(
                {
                    "path": rel_path,
                    "sha256_hex": digest.sha256_hex,
                    "size_bytes": digest.size_bytes,
                }
            )
            file_lookup[rel_path] = file_path
        hasher = hashlib.sha256()
        for entry in sorted(egress_checksums["files"], key=lambda item: item["path"]):
            hasher.update(file_lookup[entry["path"]].read_bytes())
        egress_checksums["composite_sha256_hex"] = hasher.hexdigest()

    decision = "PASS" if not tracker.failures else "FAIL"
    summary_payload["run"]["decision"] = decision
    summary_payload["merchants_failed"] = len(tracker.failed_merchants)
    summary_payload["failures_by_code"] = dict(tracker.failures_by_code)
    if tracker.failures:
        summary_payload["failures"] = tracker.failures
    else:
        summary_payload.pop("failures", None)

    param_digest_entries = []
    for item in param_digests:
        param_digest_entries.append(
            {
                "filename": item.name,
                "size_bytes": item.digest.size_bytes,
                "sha256_hex": item.digest.sha256_hex,
                "mtime_ns": item.digest.mtime_ns,
            }
        )
    param_digest_entries.sort(key=lambda entry: entry["filename"])
    parameter_hash_resolved = {
        "parameter_hash": parameter_hash,
        "filenames_sorted": [entry["filename"] for entry in param_digest_entries],
        "artifact_count": len(param_digest_entries),
        "files": param_digest_entries,
    }

    fingerprint_artifacts = []
    for path, digest in opened_paths.items():
        fingerprint_artifacts.append(
            {
                "path": path.as_posix(),
                "sha256": digest.sha256_hex,
                "size_bytes": digest.size_bytes,
            }
        )
    fingerprint_artifacts.append(
        {
            "path": "numeric_policy_attest.json",
            "sha256": attestation_digest.sha256_hex,
            "size_bytes": attestation_digest.size_bytes,
        }
    )
    fingerprint_artifacts.sort(key=lambda entry: entry["path"])
    manifest_fingerprint_resolved = {
        "manifest_fingerprint": manifest_fingerprint,
        "artifact_count": len(opened_artifacts),
        "git_commit_hex": git_bytes.hex() if git_bytes else "",
        "parameter_hash": parameter_hash,
        "files": fingerprint_artifacts,
    }

    flags = attestation_payload.get("flags", {}) if attestation_payload else {}
    compiler_flags = {
        "fma": flags.get("fma") not in ("off", False, None),
        "ftz": flags.get("ftz_daz") not in ("off", False, None),
        "rounding": flags.get("rounding") or "RNE",
        "fast_math": False,
        "blas": "none",
    }
    manifest_payload = {
        "version": "1A.validation.v1",
        "manifest_fingerprint": manifest_fingerprint,
        "parameter_hash": parameter_hash,
        "git_commit_hex": git_bytes.hex() if git_bytes else "",
        "artifact_count": 0,
        "math_profile_id": attestation_payload.get("math_profile_id", "")
        if attestation_payload
        else "",
        "compiler_flags": compiler_flags,
        "created_utc_ns": utc_now_ns(),
    }

    index_entries = [
        {
            "artifact_id": "MANIFEST",
            "kind": "summary",
            "path": "MANIFEST.json",
            "mime": "application/json",
            "notes": None,
        },
        {
            "artifact_id": "parameter_hash_resolved",
            "kind": "table",
            "path": "parameter_hash_resolved.json",
            "mime": "application/json",
            "notes": None,
        },
        {
            "artifact_id": "manifest_fingerprint_resolved",
            "kind": "table",
            "path": "manifest_fingerprint_resolved.json",
            "mime": "application/json",
            "notes": None,
        },
        {
            "artifact_id": "rng_accounting",
            "kind": "table",
            "path": "rng_accounting.json",
            "mime": "application/json",
            "notes": None,
        },
        {
            "artifact_id": "s9_summary",
            "kind": "summary",
            "path": "s9_summary.json",
            "mime": "application/json",
            "notes": None,
        },
        {
            "artifact_id": "egress_checksums",
            "kind": "table",
            "path": "egress_checksums.json",
            "mime": "application/json",
            "notes": None,
        },
        {
            "artifact_id": "index",
            "kind": "table",
            "path": "index.json",
            "mime": "application/json",
            "notes": None,
        },
    ]
    manifest_payload["artifact_count"] = len(index_entries)

    index_schema_pack, index_table = _table_pack(
        schema_1a, "validation/validation_bundle_index_1A"
    )
    try:
        validate_dataframe(
            index_entries,
            index_schema_pack,
            index_table,
        )
    except SchemaValidationError as exc:
        record_failure(
            "E_SCHEMA_INVALID",
            "RUN",
            str(exc),
            dataset_id=DATASET_VALIDATION_INDEX,
            check_key="schema_pk_fk",
        )
    seen_artifacts: set[str] = set()
    for entry in index_entries:
        artifact_id = str(entry.get("artifact_id", ""))
        if artifact_id in seen_artifacts:
            record_failure(
                "E_SCHEMA_INVALID",
                "RUN",
                "duplicate_index_artifact_id",
                dataset_id=DATASET_VALIDATION_INDEX,
                check_key="schema_pk_fk",
            )
        seen_artifacts.add(artifact_id)

    if validate_only:
        return S9RunResult(
            run_id=run_id,
            parameter_hash=parameter_hash,
            manifest_fingerprint=manifest_fingerprint,
            decision=decision,
            bundle_root=Path(""),
        )

    bundle_entry = find_dataset_entry(dictionary, DATASET_VALIDATION_BUNDLE).entry
    bundle_root = _resolve_run_path(run_paths, bundle_entry["path"], tokens)
    tmp_root = bundle_root.parent / f"_tmp.{uuid.uuid4().hex}"
    if tmp_root.exists():
        shutil.rmtree(tmp_root)
    tmp_root.mkdir(parents=True, exist_ok=True)

    _write_json(tmp_root / "MANIFEST.json", manifest_payload)
    _write_json(tmp_root / "parameter_hash_resolved.json", parameter_hash_resolved)
    _write_json(tmp_root / "manifest_fingerprint_resolved.json", manifest_fingerprint_resolved)
    _write_json(tmp_root / "rng_accounting.json", rng_accounting)
    _write_json(tmp_root / "s9_summary.json", summary_payload)
    _write_json(tmp_root / "egress_checksums.json", egress_checksums)
    _write_json(tmp_root / "index.json", index_entries)

    if decision == "PASS":
        bundle_hash = _bundle_hash(tmp_root, index_entries)
        flag_payload = f"sha256_hex = {bundle_hash}"
        (tmp_root / "_passed.flag").write_text(flag_payload + "\n", encoding="ascii")

    if bundle_root.exists():
        shutil.rmtree(bundle_root)

    tmp_root.replace(bundle_root)
    timer.info(f"S9: bundle published decision={decision}")

    return S9RunResult(
        run_id=run_id,
        parameter_hash=parameter_hash,
        manifest_fingerprint=manifest_fingerprint,
        decision=decision,
        bundle_root=bundle_root,
    )

__all__ = ["S9RunResult", "run_s9"]
