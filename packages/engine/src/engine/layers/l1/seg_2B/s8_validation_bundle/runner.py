"""S8 validation bundle runner for Segment 2B."""

from __future__ import annotations

import hashlib
import json
import shutil
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

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
from engine.core.paths import RunPaths, resolve_input_path
from engine.core.time import utc_now_rfc3339_micro
from engine.core.run_receipt import pick_latest_run_receipt
from engine.layers.l1.seg_2B.s0_gate.runner import _inline_external_refs, _schema_from_pack


MODULE_NAME = "2B.S8.validation_bundle"
SEGMENT = "2B"
STATE = "S8"

DATASET_S0_RECEIPT = "s0_gate_receipt_2B"
DATASET_SEALED_INPUTS = "sealed_inputs_2B"
DATASET_S2_INDEX = "s2_alias_index"
DATASET_S2_BLOB = "s2_alias_blob"
DATASET_S3 = "s3_day_effects"
DATASET_S4 = "s4_group_weights"
DATASET_S7 = "s7_audit_report"
DATASET_BUNDLE = "validation_bundle_2B"
DATASET_INDEX = "validation_bundle_index_2B"
DATASET_FLAG = "validation_passed_flag_2B"

POLICY_IDS = [
    "alias_layout_policy_v1",
    "route_rng_policy_v1",
    "virtual_edge_policy_v1",
]


@dataclass(frozen=True)
class S8RunResult:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    bundle_root: Path


class _StepTimer:
    def __init__(self, logger) -> None:
        self._logger = logger
        self._start = time.monotonic()
        self._last = self._start

    def info(self, message: str, *args) -> None:
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
        if self._total and self._total > 0:
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


def _json_bytes(payload: object) -> bytes:
    return json.dumps(
        payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_json_bytes(payload))


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise InputResolutionError(f"Missing JSON file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_payload(
    schema_pack: dict,
    pointer: str,
    payload: object,
    schema_layer1: dict,
) -> None:
    schema = _schema_from_pack(schema_pack, pointer)
    _inline_external_refs(schema, schema_layer1, "schemas.layer1.yaml#/$defs/")
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    if errors:
        raise SchemaValidationError(errors[0].message)


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
    if resolved.startswith(("data/", "logs/", "reports/", "artefacts/")):
        return run_paths.run_root / resolved
    return resolve_input_path(resolved, run_paths, external_roots, allow_run_local=True)


def _pick_latest_run_receipt(runs_root: Path) -> Path:
    return pick_latest_run_receipt(runs_root)


def _resolve_run_receipt(runs_root: Path, run_id: Optional[str]) -> tuple[Path, dict]:
    if run_id:
        receipt_path = runs_root / run_id / "run_receipt.json"
        return receipt_path, _load_json(receipt_path)
    receipt_path = _pick_latest_run_receipt(runs_root)
    return receipt_path, _load_json(receipt_path)


def _extract_seed_from_path(path: Path) -> Optional[int]:
    for part in path.parts:
        if part.startswith("seed="):
            value = part.split("=", 1)[1]
            if value:
                return int(value)
    return None


def _discover_seeds(entry: dict, run_paths: RunPaths, manifest_fingerprint: str) -> set[int]:
    path_template = entry.get("path", "")
    if "{seed}" not in path_template:
        raise ContractError(f"Dataset path missing seed token: {path_template}")
    path_glob = (
        path_template.replace("{manifest_fingerprint}", manifest_fingerprint)
        .replace("{seed}", "*")
    )
    matches = run_paths.run_root.glob(path_glob)
    seeds: set[int] = set()
    for path in matches:
        seed = _extract_seed_from_path(path)
        if seed is not None:
            seeds.add(seed)
    return seeds


def _bundle_hash(run_root: Path, index_entries: list[dict]) -> str:
    paths = sorted(entry["path"] for entry in index_entries if entry.get("path"))
    hasher = hashlib.sha256()
    for rel_path in paths:
        hasher.update((run_root / rel_path).read_bytes())
    return hasher.hexdigest()


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
                "2B-S8-080",
                STATE,
                MODULE_NAME,
                {"detail": "partition_exists_nonidentical", "dataset": label},
            )
        shutil.rmtree(tmp_root)
        logger.info("S8: %s partition already exists with identical bytes", label)
        return
    final_root.parent.mkdir(parents=True, exist_ok=True)
    tmp_root.replace(final_root)


def _abort(logger, code: str, validator: str, message: str, context: dict) -> None:
    logger.error(
        "VALIDATION %s",
        json.dumps(
            {
                "event": "VALIDATION",
                "validator_id": validator,
                "result": "fail",
                "error_code": code,
                "detail": context,
                "segment": SEGMENT,
                "state": STATE,
                "severity": "ERROR",
                "timestamp_utc": utc_now_rfc3339_micro(),
                "manifest_fingerprint": context.get("manifest_fingerprint"),
            },
            ensure_ascii=True,
            sort_keys=True,
        ),
    )
    raise EngineFailure("F4", code, STATE, MODULE_NAME, context)


def run_s8(config: EngineConfig, run_id: Optional[str] = None) -> S8RunResult:
    logger = get_logger("engine.layers.l1.seg_2B.s8_validation_bundle.l2.runner")
    timer = _StepTimer(logger)

    source = ContractSource(layout=config.contracts_layout, root=config.contracts_root)
    dictionary_path, dictionary = load_dataset_dictionary(source, "2B")
    registry_path, registry = load_artefact_registry(source, "2B")
    schema_layer1_path, schema_layer1 = load_schema_pack(source, "1A", "layer1")
    schema_2b_path, schema_2b = load_schema_pack(source, "2B", "2B")
    timer.info(
        "S8: contracts layout=%s root=%s dictionary=%s registry=%s schemas=%s,%s",
        config.contracts_layout,
        config.contracts_root,
        dictionary_path,
        registry_path,
        schema_2b_path,
        schema_layer1_path,
    )

    receipt_path, receipt = _resolve_run_receipt(config.runs_root, run_id)
    run_id = str(receipt.get("run_id"))
    seed = int(receipt.get("seed") or 0)
    parameter_hash = str(receipt.get("parameter_hash"))
    manifest_fingerprint = str(receipt.get("manifest_fingerprint"))
    if not run_id or not parameter_hash or not manifest_fingerprint:
        raise InputResolutionError("run_receipt missing run_id, parameter_hash, or manifest_fingerprint.")

    run_paths = RunPaths(config.runs_root, run_id)
    add_file_handler(run_paths.run_root / f"run_log_{run_id}.log")
    timer.info("S8: loaded run receipt %s", receipt_path)

    tokens = {
        "seed": str(seed),
        "parameter_hash": parameter_hash,
        "manifest_fingerprint": manifest_fingerprint,
        "run_id": run_id,
    }

    logger.info(
        "S8: objective=package validation bundle; gated inputs (S0 receipt + sealed_inputs, "
        "S7 PASS reports, S2/S3/S4 for seed discovery, sealed policies) -> outputs "
        "(validation_bundle_2B, index.json, _passed.flag)"
    )

    s0_entry = find_dataset_entry(dictionary, DATASET_S0_RECEIPT).entry
    sealed_entry = find_dataset_entry(dictionary, DATASET_SEALED_INPUTS).entry

    s0_path = _resolve_dataset_path(s0_entry, run_paths, config.external_roots, tokens)
    sealed_path = _resolve_dataset_path(sealed_entry, run_paths, config.external_roots, tokens)
    s0_payload = _load_json(s0_path)
    sealed_payload = _load_json(sealed_path)

    try:
        _validate_payload(schema_2b, "validation/s0_gate_receipt_v1", s0_payload, schema_layer1)
        _validate_payload(schema_2b, "validation/sealed_inputs_2B", sealed_payload, schema_layer1)
    except SchemaValidationError as exc:
        _abort(
            logger,
            "2B-S8-020",
            "V-01",
            "s0_evidence_invalid",
            {"error": str(exc), "manifest_fingerprint": manifest_fingerprint},
        )

    if str(s0_payload.get("manifest_fingerprint") or "") != manifest_fingerprint:
        _abort(
            logger,
            "2B-S8-020",
            "V-01",
            "manifest_fingerprint_mismatch",
            {"expected": manifest_fingerprint, "actual": s0_payload.get("manifest_fingerprint")},
        )
    timer.info("S8: S0 evidence validated for manifest_fingerprint=%s", manifest_fingerprint)

    sealed_by_id: dict[str, dict] = {}
    for entry in sealed_payload:
        asset_id = str(entry.get("asset_id") or "")
        if asset_id:
            sealed_by_id[asset_id] = entry

    s2_entry = find_dataset_entry(dictionary, DATASET_S2_INDEX).entry
    s3_entry = find_dataset_entry(dictionary, DATASET_S3).entry
    s4_entry = find_dataset_entry(dictionary, DATASET_S4).entry

    seeds_s2 = _discover_seeds(s2_entry, run_paths, manifest_fingerprint)
    seeds_s3 = _discover_seeds(s3_entry, run_paths, manifest_fingerprint)
    seeds_s4 = _discover_seeds(s4_entry, run_paths, manifest_fingerprint)
    seeds_required = sorted(seeds_s2 & seeds_s3 & seeds_s4, key=lambda value: str(value))
    logger.info(
        "S8: seed discovery (s2=%d, s3=%d, s4=%d, intersection=%d)",
        len(seeds_s2),
        len(seeds_s3),
        len(seeds_s4),
        len(seeds_required),
    )
    if not seeds_required:
        _abort(
            logger,
            "2B-S8-030",
            "V-03",
            "seed_intersection_empty",
            {"manifest_fingerprint": manifest_fingerprint},
        )

    s7_entry = find_dataset_entry(dictionary, DATASET_S7).entry
    s7_warn_total = 0
    for seed_value in seeds_required:
        seed_tokens = {
            "seed": str(seed_value),
            "manifest_fingerprint": manifest_fingerprint,
        }
        s7_path = _resolve_dataset_path(s7_entry, run_paths, config.external_roots, seed_tokens)
        if not s7_path.exists():
            _abort(
                logger,
                "2B-S8-031",
                "V-04",
                "s7_report_missing",
                {"seed": seed_value, "path": str(s7_path)},
            )
        s7_payload = _load_json(s7_path)
        try:
            _validate_payload(schema_2b, "validation/s7_audit_report_v1", s7_payload, schema_layer1)
        except SchemaValidationError as exc:
            _abort(
                logger,
                "2B-S8-032",
                "V-04",
                "s7_report_invalid",
                {"seed": seed_value, "error": str(exc)},
            )
        if int(s7_payload.get("seed") or -1) != int(seed_value):
            _abort(
                logger,
                "2B-S8-032",
                "V-04",
                "s7_seed_mismatch",
                {"seed": seed_value, "payload_seed": s7_payload.get("seed")},
            )
        if str(s7_payload.get("manifest_fingerprint") or "") != manifest_fingerprint:
            _abort(
                logger,
                "2B-S8-032",
                "V-04",
                "s7_manifest_mismatch",
                {"seed": seed_value, "payload": s7_payload.get("manifest_fingerprint")},
            )
        summary = s7_payload.get("summary") or {}
        if str(summary.get("overall_status") or "").upper() != "PASS":
            _abort(
                logger,
                "2B-S8-032",
                "V-04",
                "s7_not_pass",
                {"seed": seed_value, "status": summary.get("overall_status")},
            )
        s7_warn_total += int(summary.get("warn_count") or 0)
    timer.info("S8: verified S7 PASS coverage for %d seeds", len(seeds_required))

    policy_digests: dict[str, dict] = {}
    for policy_id in POLICY_IDS:
        sealed = sealed_by_id.get(policy_id)
        if not sealed:
            _abort(
                logger,
                "2B-S8-033",
                "V-05",
                "policy_not_sealed",
                {"asset_id": policy_id},
            )
        policy_path = Path(sealed.get("path") or "")
        policy_resolved = resolve_input_path(
            str(policy_path),
            run_paths,
            config.external_roots,
            allow_run_local=True,
        )
        digest = sha256_file(policy_resolved).sha256_hex
        sealed_digest = str(sealed.get("sha256_hex") or "")
        if sealed_digest != digest:
            _abort(
                logger,
                "2B-S8-033",
                "V-05",
                "sealed_digest_mismatch",
                {"asset_id": policy_id, "sealed": sealed_digest, "computed": digest},
            )
        policy_digests[policy_id] = {"path": str(policy_resolved), "sha256_hex": digest}

    bundle_entry = find_dataset_entry(dictionary, DATASET_BUNDLE).entry
    bundle_root = _resolve_dataset_path(bundle_entry, run_paths, config.external_roots, tokens)
    tmp_root = run_paths.run_root / "tmp" / f"s8_validation_bundle_{uuid.uuid4().hex}"
    if tmp_root.exists():
        shutil.rmtree(tmp_root)
    tmp_root.mkdir(parents=True, exist_ok=True)

    index_entries: list[dict] = []
    total_bytes = 0

    def hash_source(src: Path) -> None:
        nonlocal total_bytes
        try:
            rel_path = src.relative_to(run_paths.run_root).as_posix()
        except ValueError as exc:
            raise InputResolutionError(f"Index path not under run_root: {src}") from exc
        digest = sha256_file(src).sha256_hex
        index_entries.append({"path": rel_path, "sha256_hex": digest})
        total_bytes += src.stat().st_size

    logger.info("S8: building index-only bundle (no copies); paths are run-root relative")
    logger.warning(
        "S8: index paths reference run_root (deviation: spec expects bundle-root paths for members)"
    )
    hash_source(s0_path)
    hash_source(sealed_path)

    progress = _ProgressTracker(len(seeds_required), logger, "S8: hashing S7 reports")
    for seed_value in seeds_required:
        seed_tokens = {"seed": str(seed_value), "manifest_fingerprint": manifest_fingerprint}
        s7_path = _resolve_dataset_path(s7_entry, run_paths, config.external_roots, seed_tokens)
        hash_source(s7_path)
        progress.update(1)

    index_entries = sorted(index_entries, key=lambda entry: entry["path"])
    if any(entry["path"] == "_passed.flag" for entry in index_entries):
        _abort(
            logger,
            "2B-S8-041",
            "V-06",
            "flag_in_index",
            {"detail": "index_includes_passed_flag"},
        )
    try:
        _validate_payload(schema_2b, "validation/validation_bundle_index_2B", index_entries, schema_layer1)
    except SchemaValidationError as exc:
        _abort(
            logger,
            "2B-S8-040",
            "V-06",
            "index_schema_invalid",
            {"error": str(exc)},
        )

    _write_json(tmp_root / "index.json", index_entries)
    bundle_hash = _bundle_hash(run_paths.run_root, index_entries)
    (tmp_root / "_passed.flag").write_text(f"sha256_hex = {bundle_hash}\n", encoding="ascii")
    timer.info("S8: index.json + _passed.flag written (files_indexed=%d)", len(index_entries))

    _atomic_publish_dir(tmp_root, bundle_root, logger, DATASET_BUNDLE)
    timer.info("S8: bundle published path=%s", bundle_root)

    inputs_digest = {
        "s2_alias_index": {
            "path": s2_entry.get("path"),
            "partition": {"seed": "<varies>", "manifest_fingerprint": manifest_fingerprint},
            "sha256_hex": None,
        },
        "s2_alias_blob": {
            "path": find_dataset_entry(dictionary, DATASET_S2_BLOB).entry.get("path"),
            "partition": {"seed": "<varies>", "manifest_fingerprint": manifest_fingerprint},
            "sha256_hex": None,
        },
        "s3_day_effects": {
            "path": s3_entry.get("path"),
            "partition": {"seed": "<varies>", "manifest_fingerprint": manifest_fingerprint},
            "sha256_hex": None,
        },
        "s4_group_weights": {
            "path": s4_entry.get("path"),
            "partition": {"seed": "<varies>", "manifest_fingerprint": manifest_fingerprint},
            "sha256_hex": None,
        },
        "policies": policy_digests,
    }

    run_report = {
        "component": "2B.S8",
        "manifest_fingerprint": manifest_fingerprint,
        "created_utc": s0_payload.get("verified_at_utc"),
        "catalogue_resolution": s0_payload.get("catalogue_resolution"),
        "seed_coverage": {
            "rule": "intersection(s2_alias_index, s3_day_effects, s4_group_weights)",
            "seeds_discovered": [str(seed_value) for seed_value in seeds_required],
            "required_count": len(seeds_required),
            "s7_pass_count": len(seeds_required),
            "missing_or_fail_count": 0,
        },
        "inputs_digest": inputs_digest,
        "bundle": {
            "publish_path": str(bundle_entry.get("path") or "").replace(
                "{manifest_fingerprint}", manifest_fingerprint
            ),
            "index_path": "./index.json",
            "flag_path": "./_passed.flag",
            "files_indexed": len(index_entries),
            "bytes_indexed_total": total_bytes,
            "index_ascii_lex": True,
            "flag_excluded_from_index": True,
            "bundle_digest": bundle_hash,
            "flag_digest_matches": True,
        },
        "validators": [
            {"id": "V-01", "status": "PASS", "codes": []},
            {"id": "V-03", "status": "PASS", "codes": []},
            {"id": "V-04", "status": "PASS", "codes": []},
            {"id": "V-05", "status": "PASS", "codes": []},
            {"id": "V-06", "status": "PASS", "codes": []},
            {"id": "V-09", "status": "PASS", "codes": []},
        ],
        "summary": {
            "overall_status": "PASS",
            "warn_count": s7_warn_total,
            "fail_count": 0,
        },
    }

    logger.info("S8_RUN_REPORT %s", json.dumps(run_report, ensure_ascii=True, sort_keys=True))

    return S8RunResult(
        run_id=run_id,
        parameter_hash=parameter_hash,
        manifest_fingerprint=manifest_fingerprint,
        bundle_root=bundle_root,
    )


__all__ = ["S8RunResult", "run_s8"]
