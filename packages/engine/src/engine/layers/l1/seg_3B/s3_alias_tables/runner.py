"""S3 alias tables and edge universe hash for Segment 3B."""

from __future__ import annotations

import hashlib
import heapq
import json
import struct
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import polars as pl
from jsonschema import Draft202012Validator

from engine.contracts.jsonschema_adapter import normalize_nullable_schema, validate_dataframe
from engine.contracts.loader import find_dataset_entry, load_artefact_registry, load_dataset_dictionary, load_schema_pack
from engine.contracts.source import ContractSource
from engine.core.config import EngineConfig
from engine.core.errors import ContractError, EngineFailure, HashingError, InputResolutionError, SchemaValidationError
from engine.core.hashing import sha256_file
from engine.core.logging import add_file_handler, get_logger
from engine.core.paths import RunPaths
from engine.core.time import utc_now_rfc3339_micro
from engine.layers.l1.seg_3B.s0_gate.runner import (
    _hash_partition,
    _inline_external_refs,
    _load_json,
    _render_catalog_path,
    _resolve_dataset_path,
    _resolve_run_receipt,
    _schema_from_pack,
    _table_pack,
)


MODULE_NAME = "3B.S3.alias_tables"
SEGMENT = "3B"
STATE = "S3"


@dataclass(frozen=True)
class S3Result:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    blob_path: Path
    index_path: Path
    universe_hash_path: Path
    gamma_log_path: Path
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
    elif result == "pass":
        severity = "INFO"
    else:
        severity = "DEBUG"
    payload = {"validator_id": validator_id, "result": result}
    if error_code:
        payload["error_code"] = error_code
    if detail is not None:
        payload["detail"] = detail
    _emit_event(logger, "VALIDATION", manifest_fingerprint, severity, **payload)


def _abort(code: str, validator_id: str, message: str, context: dict, manifest_fingerprint: Optional[str]) -> None:
    logger = get_logger("engine.layers.l1.seg_3B.s3_alias_tables.l2.runner")
    _emit_validation(logger, manifest_fingerprint, validator_id, "fail", code, context)
    raise EngineFailure("F4", code, STATE, MODULE_NAME, context)


def _warn(message: str, context: dict, manifest_fingerprint: Optional[str]) -> None:
    logger = get_logger("engine.layers.l1.seg_3B.s3_alias_tables.l2.runner")
    _emit_validation(logger, manifest_fingerprint, "W-01", "warn", None, {"message": message, **context})


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _schema_for_payload(schema_pack: dict, schema_layer1: dict, anchor: str) -> dict:
    schema = _schema_from_pack(schema_pack, anchor)
    _inline_external_refs(schema, schema_layer1, "schemas.layer1.yaml#")
    return normalize_nullable_schema(schema)


def _validate_payload(schema_pack: dict, schema_layer1: dict, anchor: str, payload: object) -> None:
    schema = _schema_for_payload(schema_pack, schema_layer1, anchor)
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    if errors:
        raise SchemaValidationError(str(errors[0]), [])


def _resolve_parquet_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    if not root.exists():
        raise InputResolutionError(f"Missing parquet directory: {root}")
    paths = sorted(root.rglob("*.parquet"))
    if not paths:
        raise InputResolutionError(f"No parquet files found under {root}")
    return paths


def _atomic_publish_file(tmp_path: Path, final_path: Path, logger, label: str) -> None:
    if final_path.exists():
        tmp_hash = sha256_file(tmp_path).sha256_hex
        final_hash = sha256_file(final_path).sha256_hex
        if tmp_hash != final_hash:
            raise EngineFailure(
                "F4",
                "E3B_S3_OUTPUT_INCONSISTENT_REWRITE",
                STATE,
                MODULE_NAME,
                {"detail": "non-identical output exists", "path": str(final_path), "label": label},
            )
        tmp_path.unlink()
        logger.info("S3: %s already exists and is identical; skipping publish.", label)
        return
    final_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path.replace(final_path)


def _hash_dataset(path: Path) -> str:
    if path.is_dir():
        digest, _ = _hash_partition(path)
        return digest
    return sha256_file(path).sha256_hex


def _pack_u32(value: int, endianness: str) -> bytes:
    fmt = "<I" if endianness == "little" else ">I"
    return struct.pack(fmt, value & 0xFFFFFFFF)


def _decode_probabilities(prob: np.ndarray, alias: np.ndarray) -> np.ndarray:
    count = prob.size
    if count == 0:
        return np.array([], dtype=np.float64)
    p_hat = prob / float(count)
    residual = (1.0 - prob) / float(count)
    for idx in range(count):
        target = int(alias[idx])
        p_hat[target] += residual[idx]
    return p_hat


def _normalise_weights(
    weights: list[float],
    normalisation_epsilon: float,
    tiny_negative_epsilon: float,
    manifest_fingerprint: str,
    merchant_id: int,
) -> tuple[np.ndarray, bool]:
    values = np.array(weights, dtype=np.float64)
    if values.size == 0:
        _abort(
            "E3B_S3_WEIGHT_VECTOR_INVALID",
            "V-10",
            "empty_weight_vector",
            {"merchant_id": merchant_id},
            manifest_fingerprint,
        )
    if not np.isfinite(values).all():
        _warn("non_finite_weights", {"merchant_id": merchant_id}, manifest_fingerprint)
        return np.full(values.size, 1.0 / float(values.size), dtype=np.float64), True
    if (values < -tiny_negative_epsilon).any():
        _warn("negative_weights", {"merchant_id": merchant_id}, manifest_fingerprint)
        return np.full(values.size, 1.0 / float(values.size), dtype=np.float64), True
    values = np.where(values < 0.0, 0.0, values)
    total = float(values.sum())
    if total <= normalisation_epsilon:
        _warn("weights_sum_too_small", {"merchant_id": merchant_id, "sum": total}, manifest_fingerprint)
        return np.full(values.size, 1.0 / float(values.size), dtype=np.float64), True
    if abs(total - 1.0) > normalisation_epsilon:
        values = values / total
    return values, False


def _build_alias_slice(
    weights: list[float],
    merchant_id: int,
    policy: dict,
    manifest_fingerprint: str,
) -> tuple[bytes, str, int, float, bool]:
    quantised_bits = int(policy["quantised_bits"])
    grid_size = 1 << quantised_bits
    prob_qbits = int(policy["prob_qbits"])
    endianness = policy["endianness"]
    alignment_bytes = int(policy["alignment_bytes"])
    normalisation_epsilon = float(policy["normalisation_epsilon"])
    quantisation_epsilon = float(policy["quantisation_epsilon"])
    tiny_negative_epsilon = float(policy["tiny_negative_epsilon"])
    treat_within_epsilon = bool(policy["treat_within_epsilon"])

    p, fallback_used = _normalise_weights(
        weights,
        normalisation_epsilon,
        tiny_negative_epsilon,
        manifest_fingerprint,
        merchant_id,
    )

    if treat_within_epsilon and p.size > 0:
        max_idx = int(np.argmax(p))
        if p[max_idx] >= 1.0 - normalisation_epsilon:
            masses = np.zeros(p.size, dtype=np.int64)
            masses[max_idx] = grid_size
        else:
            masses = np.rint(p * grid_size).astype(np.int64)
    else:
        masses = np.rint(p * grid_size).astype(np.int64)

    residual = (p * grid_size) - masses.astype(np.float64)
    diff = int(grid_size - int(masses.sum()))
    if diff != 0:
        if diff > 0:
            order = np.lexsort((np.arange(masses.size), -residual))
            for idx in order[:diff]:
                masses[idx] += 1
        else:
            order = np.lexsort((np.arange(masses.size), residual))
            for idx in order[: abs(diff)]:
                masses[idx] -= 1
    if masses.sum() != grid_size:
        _abort(
            "E3B_S3_QUANTISATION_FAILED",
            "V-11",
            "grid_sum_incorrect",
            {"merchant_id": merchant_id, "sum": int(masses.sum()), "grid": grid_size},
            manifest_fingerprint,
        )
    if masses.min(initial=0) < 0 or masses.max(initial=0) > grid_size:
        _abort(
            "E3B_S3_QUANTISATION_FAILED",
            "V-11",
            "negative_or_overflow_mass",
            {"merchant_id": merchant_id, "grid": grid_size},
            manifest_fingerprint,
        )

    prob = np.zeros(masses.size, dtype=np.float64)
    alias = np.zeros(masses.size, dtype=np.int64)
    if masses.size == 1:
        prob[0] = 1.0
        alias[0] = 0
    else:
        scaled = (masses.astype(np.float64) / grid_size) * masses.size
        small = [
            idx for idx, value in enumerate(scaled) if value < 1.0 - tiny_negative_epsilon
        ]
        large = [
            idx for idx, value in enumerate(scaled) if value >= 1.0 - tiny_negative_epsilon
        ]
        heapq.heapify(small)
        heapq.heapify(large)
        while small and large:
            s_idx = heapq.heappop(small)
            l_idx = heapq.heappop(large)
            prob[s_idx] = scaled[s_idx]
            alias[s_idx] = l_idx
            scaled[l_idx] = scaled[l_idx] - (1.0 - prob[s_idx])
            if scaled[l_idx] < 1.0 - tiny_negative_epsilon:
                heapq.heappush(small, l_idx)
            else:
                heapq.heappush(large, l_idx)
        while small:
            idx = heapq.heappop(small)
            prob[idx] = 1.0
            alias[idx] = idx
        while large:
            idx = heapq.heappop(large)
            prob[idx] = 1.0
            alias[idx] = idx

    q_scale = float(1 << prob_qbits)
    q_max = (1 << prob_qbits) - 1
    prob_q = np.floor(prob * q_scale).astype(np.uint64)
    prob_q = np.clip(prob_q, 1, q_max)
    prob_decoded = prob_q.astype(np.float64) / q_scale
    p_hat = _decode_probabilities(prob_decoded, alias.astype(np.int64))
    abs_delta = np.abs(p_hat - p)
    max_abs_delta = float(abs_delta.max()) if abs_delta.size else 0.0
    if abs(float(p_hat.sum()) - 1.0) > quantisation_epsilon or (
        abs_delta.size and abs_delta.max() > quantisation_epsilon
    ):
        _abort(
            "E3B_S3_ALIAS_CONSTRUCTION_FAILED",
            "V-12",
            "alias_decode_incoherent",
            {
                "merchant_id": merchant_id,
                "max_abs_delta": max_abs_delta,
                "sum_p_hat": float(p_hat.sum()),
                "epsilon": quantisation_epsilon,
            },
            manifest_fingerprint,
        )

    header = (
        _pack_u32(int(masses.size), endianness)
        + _pack_u32(prob_qbits, endianness)
        + _pack_u32(0, endianness)
        + _pack_u32(0, endianness)
    )
    payload_parts = []
    for idx in range(prob_q.size):
        payload_parts.append(_pack_u32(int(prob_q[idx]), endianness))
        payload_parts.append(_pack_u32(int(alias[idx]), endianness))
    payload = b"".join(payload_parts)
    slice_bytes = header + payload
    checksum = hashlib.sha256(slice_bytes).hexdigest()
    if alignment_bytes <= 0:
        _abort(
            "E3B_S3_ALIAS_LAYOUT_POLICY_INVALID",
            "V-09",
            "alignment_bytes_invalid",
            {"alignment_bytes": alignment_bytes},
            manifest_fingerprint,
        )
    return slice_bytes, checksum, int(masses.size), max_abs_delta, fallback_used


def run_s3(config: EngineConfig, run_id: Optional[str] = None) -> S3Result:
    logger = get_logger("engine.layers.l1.seg_3B.s3_alias_tables.l2.runner")
    timer = _StepTimer(logger)
    started_monotonic = time.monotonic()
    started_utc = utc_now_rfc3339_micro()

    status = "FAIL"
    error_code: Optional[str] = None
    error_class: Optional[str] = None
    error_context: Optional[dict] = None
    first_failure_phase: Optional[str] = None

    seed: Optional[int] = None
    manifest_fingerprint: Optional[str] = None
    parameter_hash: Optional[str] = None
    blob_path: Optional[Path] = None
    index_path: Optional[Path] = None
    universe_hash_path: Optional[Path] = None
    gamma_log_path: Optional[Path] = None
    run_report_path: Optional[Path] = None

    counts = {
        "merchants_total": 0,
        "edges_total": 0,
        "fallback_uniform_total": 0,
        "merchants_mass_exact_after_decode": 0,
    }
    max_abs_delta_decode = 0.0

    current_phase = "init"

    try:
        current_phase = "run_receipt"
        receipt_path, receipt = _resolve_run_receipt(config.runs_root, run_id)
        run_id = receipt.get("run_id")
        if not run_id:
            raise InputResolutionError("run_receipt missing run_id.")
        if receipt_path.parent.name != run_id:
            raise InputResolutionError("run_receipt path does not match embedded run_id.")
        parameter_hash = receipt.get("parameter_hash")
        manifest_fingerprint = receipt.get("manifest_fingerprint")
        if manifest_fingerprint is None or parameter_hash is None:
            raise InputResolutionError("run_receipt missing manifest_fingerprint or parameter_hash.")
        seed = int(receipt.get("seed"))

        run_paths = RunPaths(config.runs_root, run_id)
        run_log_path = run_paths.run_root / f"run_log_{run_id}.log"
        add_file_handler(run_log_path)
        logger.info("S3: run log initialized at %s", run_log_path)

        source = ContractSource(config.contracts_root, config.contracts_layout)
        dict_3b_path, dictionary_3b = load_dataset_dictionary(source, "3B")
        reg_3b_path, registry_3b = load_artefact_registry(source, "3B")
        schema_3b_path, schema_3b = load_schema_pack(source, "3B", "3B")
        schema_2b_path, schema_2b = load_schema_pack(source, "2B", "2B")
        schema_1a_path, schema_1a = load_schema_pack(source, "1A", "1A")
        schema_layer1_path, schema_layer1 = load_schema_pack(source, "1A", "layer1")

        logger.info(
            "Contracts layout=%s root=%s dictionary=%s registry=%s schemas=%s",
            config.contracts_layout,
            config.contracts_root,
            dict_3b_path,
            reg_3b_path,
            ",".join(
                [
                    str(schema_3b_path),
                    str(schema_2b_path),
                    str(schema_1a_path),
                    str(schema_layer1_path),
                ]
            ),
        )

        tokens = {
            "seed": str(seed),
            "manifest_fingerprint": str(manifest_fingerprint),
            "parameter_hash": str(parameter_hash),
            "run_id": str(run_id),
        }

        logger.info(
            "S3: objective=build edge alias blob/index and universe hash; gated inputs "
            "(s0_gate_receipt_3B, sealed_inputs_3B, virtual_classification_3B, "
            "virtual_settlement_3B, edge_catalogue_3B, edge_catalogue_index_3B, "
            "alias_layout_policy_v1, cdn_country_weights, mcc_channel_rules, "
            "route_rng_policy_v1) -> outputs (edge_alias_blob_3B, edge_alias_index_3B, "
            "edge_universe_hash_3B, gamma_draw_log_3B)"
        )

        current_phase = "s0_gate"
        receipt_entry = find_dataset_entry(dictionary_3b, "s0_gate_receipt_3B").entry
        receipt_path = _resolve_dataset_path(receipt_entry, run_paths, config.external_roots, tokens)
        receipt_payload = _load_json(receipt_path)
        try:
            _validate_payload(schema_3b, schema_layer1, "validation/s0_gate_receipt_3B", receipt_payload)
        except SchemaValidationError as exc:
            _abort(
                "E3B_S3_001_S0_GATE_MISSING_OR_INVALID",
                "V-01",
                "s0_gate_receipt_invalid",
                {"detail": str(exc), "path": str(receipt_path)},
                manifest_fingerprint,
            )
        if receipt_payload.get("manifest_fingerprint") != manifest_fingerprint:
            _abort(
                "E3B_S3_001_S0_GATE_MISSING_OR_INVALID",
                "V-01",
                "s0_gate_manifest_mismatch",
                {"expected": manifest_fingerprint, "actual": receipt_payload.get("manifest_fingerprint")},
                manifest_fingerprint,
            )
        if receipt_payload.get("seed") not in (None, seed) or receipt_payload.get("parameter_hash") not in (
            None,
            parameter_hash,
        ):
            _abort(
                "E3B_S3_001_S0_GATE_MISSING_OR_INVALID",
                "V-01",
                "s0_gate_identity_mismatch",
                {
                    "seed": receipt_payload.get("seed"),
                    "parameter_hash": receipt_payload.get("parameter_hash"),
                },
                manifest_fingerprint,
            )
        for segment_id in ("segment_1A", "segment_1B", "segment_2A", "segment_3A"):
            status_value = receipt_payload.get("upstream_gates", {}).get(segment_id, {}).get("status")
            if status_value != "PASS":
                _abort(
                    "E3B_S3_002_UPSTREAM_GATE_NOT_PASS",
                    "V-02",
                    "upstream_gate_not_pass",
                    {"segment": segment_id, "status": status_value},
                    manifest_fingerprint,
                )

        current_phase = "sealed_inputs"
        sealed_entry = find_dataset_entry(dictionary_3b, "sealed_inputs_3B").entry
        sealed_path = _resolve_dataset_path(sealed_entry, run_paths, config.external_roots, tokens)
        sealed_payload = _load_json(sealed_path)
        if not isinstance(sealed_payload, list):
            _abort(
                "E3B_S3_001_S0_GATE_MISSING_OR_INVALID",
                "V-03",
                "sealed_inputs_not_list",
                {"path": str(sealed_path)},
                manifest_fingerprint,
            )
        sealed_schema = _schema_for_payload(schema_3b, schema_layer1, "validation/sealed_inputs_3B")
        validator = Draft202012Validator(sealed_schema)
        sealed_rows: list[dict] = []
        for row in sealed_payload:
            if not isinstance(row, dict):
                _abort(
                    "E3B_S3_001_S0_GATE_MISSING_OR_INVALID",
                    "V-03",
                    "sealed_input_not_object",
                    {"row": str(row)[:200]},
                    manifest_fingerprint,
                )
            errors = list(validator.iter_errors(row))
            if errors:
                _abort(
                    "E3B_S3_001_S0_GATE_MISSING_OR_INVALID",
                    "V-03",
                    "sealed_input_schema_invalid",
                    {"error": errors[0].message},
                    manifest_fingerprint,
                )
            if row.get("manifest_fingerprint") != str(manifest_fingerprint):
                _abort(
                    "E3B_S3_001_S0_GATE_MISSING_OR_INVALID",
                    "V-03",
                    "sealed_manifest_mismatch",
                    {"expected": str(manifest_fingerprint), "actual": row.get("manifest_fingerprint")},
                    manifest_fingerprint,
                )
            sealed_rows.append(row)

        sealed_by_id: dict[str, dict] = {}
        for row in sealed_rows:
            logical_id = str(row.get("logical_id") or "")
            if not logical_id:
                _abort(
                    "E3B_S3_001_S0_GATE_MISSING_OR_INVALID",
                    "V-03",
                    "sealed_logical_id_missing",
                    {"row": row},
                    manifest_fingerprint,
                )
            if logical_id in sealed_by_id:
                _abort(
                    "E3B_S3_001_S0_GATE_MISSING_OR_INVALID",
                    "V-03",
                    "sealed_logical_id_duplicate",
                    {"logical_id": logical_id},
                    manifest_fingerprint,
                )
            sealed_by_id[logical_id] = row

        required_ids = [
            "alias_layout_policy_v1",
            "cdn_country_weights",
            "mcc_channel_rules",
            "route_rng_policy_v1",
        ]

        def _verify_sealed_asset(logical_id: str) -> tuple[dict, Path, str, str]:
            if logical_id not in sealed_by_id:
                _abort(
                    "E3B_S3_003_REQUIRED_INPUT_NOT_SEALED",
                    "V-04",
                    "sealed_input_missing",
                    {"logical_id": logical_id},
                    manifest_fingerprint,
                )
            sealed_row = sealed_by_id[logical_id]
            entry = find_dataset_entry(dictionary_3b, logical_id).entry
            expected_path = _render_catalog_path(entry, tokens).rstrip("/")
            sealed_path_value = str(sealed_row.get("path") or "").rstrip("/")
            if expected_path != sealed_path_value:
                _abort(
                    "E3B_S3_004_SEALED_INPUT_MISMATCH",
                    "V-04",
                    "sealed_path_mismatch",
                    {"logical_id": logical_id, "expected": expected_path, "actual": sealed_path_value},
                    manifest_fingerprint,
                )
            asset_path = _resolve_dataset_path(entry, run_paths, config.external_roots, tokens)
            if not asset_path.exists():
                _abort(
                    "E3B_S3_003_REQUIRED_INPUT_NOT_SEALED",
                    "V-04",
                    "input_missing",
                    {"logical_id": logical_id, "path": str(asset_path)},
                    manifest_fingerprint,
                )
            computed_digest = _hash_dataset(asset_path)
            sealed_digest = str(sealed_row.get("sha256_hex") or "")
            if computed_digest != sealed_digest:
                _abort(
                    "E3B_S3_005_SEALED_INPUT_DIGEST_MISMATCH",
                    "V-04",
                    "sealed_digest_mismatch",
                    {
                        "logical_id": logical_id,
                        "path": str(asset_path),
                        "sealed_sha256_hex": sealed_digest,
                        "computed_sha256_hex": computed_digest,
                    },
                    manifest_fingerprint,
                )
            return sealed_row, asset_path, expected_path, computed_digest

        verified_assets: dict[str, tuple[dict, Path, str, str]] = {}
        for logical_id in required_ids:
            verified_assets[logical_id] = _verify_sealed_asset(logical_id)

        timer.info("S3: verified required sealed inputs and digests")

        digest_map = receipt_payload.get("digests") or {}
        cdn_weights_digest = verified_assets["cdn_country_weights"][3]
        virtual_rules_digest = verified_assets["mcc_channel_rules"][3]
        if digest_map.get("cdn_weights_digest") and digest_map.get("cdn_weights_digest") != cdn_weights_digest:
            _abort(
                "E3B_S3_005_SEALED_INPUT_DIGEST_MISMATCH",
                "V-05",
                "cdn_weights_digest_mismatch",
                {
                    "logical_id": "cdn_country_weights",
                    "sealed_digest": cdn_weights_digest,
                    "receipt_digest": digest_map.get("cdn_weights_digest"),
                },
                manifest_fingerprint,
            )
        if digest_map.get("virtual_rules_digest") and digest_map.get("virtual_rules_digest") != virtual_rules_digest:
            _abort(
                "E3B_S3_005_SEALED_INPUT_DIGEST_MISMATCH",
                "V-05",
                "virtual_rules_digest_mismatch",
                {
                    "logical_id": "mcc_channel_rules",
                    "sealed_digest": virtual_rules_digest,
                    "receipt_digest": digest_map.get("virtual_rules_digest"),
                },
                manifest_fingerprint,
            )
        current_phase = "s1_outputs"
        class_entry = find_dataset_entry(dictionary_3b, "virtual_classification_3B").entry
        settle_entry = find_dataset_entry(dictionary_3b, "virtual_settlement_3B").entry
        class_path = _resolve_dataset_path(class_entry, run_paths, config.external_roots, tokens)
        settle_path = _resolve_dataset_path(settle_entry, run_paths, config.external_roots, tokens)

        class_files = _resolve_parquet_files(class_path)
        settle_files = _resolve_parquet_files(settle_path)
        class_df = pl.read_parquet(class_files)
        settle_df = pl.read_parquet(settle_files)

        class_pack, class_table = _table_pack(schema_3b, "plan/virtual_classification_3B")
        settle_pack, settle_table = _table_pack(schema_3b, "plan/virtual_settlement_3B")
        _inline_external_refs(class_pack, schema_layer1, "schemas.layer1.yaml#")
        _inline_external_refs(settle_pack, schema_layer1, "schemas.layer1.yaml#")
        try:
            validate_dataframe(class_df.iter_rows(named=True), class_pack, class_table)
        except SchemaValidationError as exc:
            _abort(
                "E3B_S3_006_S1_INPUT_INVALID",
                "V-06",
                "classification_schema_invalid",
                {"error": str(exc), "path": str(class_path)},
                manifest_fingerprint,
            )
        try:
            validate_dataframe(settle_df.iter_rows(named=True), settle_pack, settle_table)
        except SchemaValidationError as exc:
            _abort(
                "E3B_S3_006_S1_INPUT_INVALID",
                "V-06",
                "settlement_schema_invalid",
                {"error": str(exc), "path": str(settle_path)},
                manifest_fingerprint,
            )

        virtual_ids = set(
            int(row["merchant_id"]) for row in class_df.iter_rows(named=True) if row.get("is_virtual")
        )
        settlement_ids = set(int(row["merchant_id"]) for row in settle_df.iter_rows(named=True))
        missing_settlement = sorted(virtual_ids - settlement_ids)
        extra_settlement = sorted(settlement_ids - virtual_ids)
        if missing_settlement or extra_settlement:
            _abort(
                "E3B_S3_006_S1_INPUT_INVALID",
                "V-07",
                "classification_settlement_mismatch",
                {
                    "missing_settlement": missing_settlement[:10],
                    "extra_settlement": extra_settlement[:10],
                    "missing_count": len(missing_settlement),
                    "extra_count": len(extra_settlement),
                },
                manifest_fingerprint,
            )
        timer.info(
            f"S3: validated S1 inputs (virtual_merchants={len(virtual_ids)}, "
            f"settlement_rows={settle_df.height})"
        )

        current_phase = "s2_outputs"
        edge_entry = find_dataset_entry(dictionary_3b, "edge_catalogue_3B").entry
        edge_index_entry = find_dataset_entry(dictionary_3b, "edge_catalogue_index_3B").entry
        edge_catalogue_root = _resolve_dataset_path(edge_entry, run_paths, config.external_roots, tokens)
        edge_index_path = _resolve_dataset_path(edge_index_entry, run_paths, config.external_roots, tokens)

        edge_files = _resolve_parquet_files(edge_catalogue_root)
        index_df = pl.read_parquet(edge_index_path)

        index_pack, index_table = _table_pack(schema_3b, "plan/edge_catalogue_index_3B")
        _inline_external_refs(index_pack, schema_layer1, "schemas.layer1.yaml#")
        try:
            validate_dataframe(index_df.iter_rows(named=True), index_pack, index_table)
        except SchemaValidationError as exc:
            _abort(
                "E3B_S3_007_S2_INPUT_INVALID",
                "V-08",
                "edge_index_schema_invalid",
                {"error": str(exc), "path": str(edge_index_path)},
                manifest_fingerprint,
            )

        expected_counts: dict[int, int] = {}
        global_edges_total: Optional[int] = None
        edge_catalogue_digest_global = None
        for row in index_df.iter_rows(named=True):
            scope = row.get("scope")
            if scope == "MERCHANT":
                merchant_id = row.get("merchant_id")
                edge_count = row.get("edge_count_total")
                if merchant_id is None or edge_count is None:
                    _abort(
                        "E3B_S3_007_S2_INPUT_INVALID",
                        "V-08",
                        "edge_index_missing_fields",
                        {"row": row},
                        manifest_fingerprint,
                    )
                merchant_id = int(merchant_id)
                if merchant_id in expected_counts:
                    _abort(
                        "E3B_S3_007_S2_INPUT_INVALID",
                        "V-08",
                        "edge_index_duplicate_merchant",
                        {"merchant_id": merchant_id},
                        manifest_fingerprint,
                    )
                expected_counts[merchant_id] = int(edge_count)
            elif scope == "GLOBAL":
                global_edges_total = row.get("edge_count_total_all_merchants")
                edge_catalogue_digest_global = row.get("edge_catalogue_digest_global")

        if global_edges_total is None:
            _abort(
                "E3B_S3_007_S2_INPUT_INVALID",
                "V-08",
                "edge_index_missing_global",
                {"path": str(edge_index_path)},
                manifest_fingerprint,
            )
        if edge_catalogue_digest_global is None:
            _warn(
                "edge_catalogue_digest_global_missing",
                {"path": str(edge_index_path)},
                manifest_fingerprint,
            )

        edge_catalogue_index_digest = _hash_dataset(edge_index_path)
        timer.info(
            f"S3: loaded S2 edge index (merchants={len(expected_counts)}, "
            f"edges_total={global_edges_total}, index_digest={edge_catalogue_index_digest})"
        )

        current_phase = "alias_policy"
        policy_path = verified_assets["alias_layout_policy_v1"][1]
        policy_payload = _load_json(policy_path)
        try:
            _validate_payload(schema_2b, schema_layer1, "policy/alias_layout_policy_v1", policy_payload)
        except SchemaValidationError as exc:
            _abort(
                "E3B_S3_ALIAS_LAYOUT_POLICY_INVALID",
                "V-09",
                "alias_policy_schema_invalid",
                {"error": str(exc), "path": str(policy_path)},
                manifest_fingerprint,
            )

        record_layout = policy_payload.get("record_layout") or {}
        if record_layout.get("alias_index_type") != "u32":
            _abort(
                "E3B_S3_ALIAS_LAYOUT_POLICY_INVALID",
                "V-09",
                "alias_index_type_invalid",
                {"alias_index_type": record_layout.get("alias_index_type")},
                manifest_fingerprint,
            )

        pad_byte_hex = str((policy_payload.get("padding_rule") or {}).get("pad_byte_hex") or "00")
        try:
            pad_byte = bytes.fromhex(pad_byte_hex)
        except ValueError:
            _abort(
                "E3B_S3_ALIAS_LAYOUT_POLICY_INVALID",
                "V-09",
                "pad_byte_hex_invalid",
                {"pad_byte_hex": pad_byte_hex},
                manifest_fingerprint,
            )
        if len(pad_byte) != 1:
            _abort(
                "E3B_S3_ALIAS_LAYOUT_POLICY_INVALID",
                "V-09",
                "pad_byte_hex_invalid",
                {"pad_byte_hex": pad_byte_hex},
                manifest_fingerprint,
            )

        policy = {
            "policy_id": str(policy_payload.get("policy_id") or "alias_layout_policy_v1"),
            "policy_version": str(policy_payload.get("policy_version") or policy_payload.get("version_tag") or ""),
            "layout_version": str(policy_payload.get("layout_version") or ""),
            "endianness": str(policy_payload.get("endianness") or "little"),
            "alignment_bytes": int(policy_payload.get("alignment_bytes") or 1),
            "quantised_bits": int(policy_payload.get("quantised_bits") or 0),
            "prob_qbits": int(record_layout.get("prob_qbits") or 0),
            "pad_byte": pad_byte,
            "pad_included": bool((policy_payload.get("padding_rule") or {}).get("pad_included_in_slice_length", False)),
            "normalisation_epsilon": float(policy_payload.get("normalisation_epsilon") or 0.0),
            "quantisation_epsilon": float(policy_payload.get("quantisation_epsilon") or 0.0),
            "tiny_negative_epsilon": float(
                policy_payload.get("tiny_negative_epsilon") or policy_payload.get("normalisation_epsilon") or 0.0
            ),
            "treat_within_epsilon": bool(
                (policy_payload.get("encode_spec") or {}).get("treat_within_epsilon_of_one_as_one", False)
            ),
        }
        if policy["quantised_bits"] <= 0 or policy["prob_qbits"] <= 0:
            _abort(
                "E3B_S3_ALIAS_LAYOUT_POLICY_INVALID",
                "V-09",
                "policy_bits_invalid",
                {"quantised_bits": policy["quantised_bits"], "prob_qbits": policy["prob_qbits"]},
                manifest_fingerprint,
            )

        timer.info(
            f"S3: parsed alias policy (layout={policy['layout_version']}, "
            f"qbits={policy['quantised_bits']}, prob_qbits={policy['prob_qbits']})"
        )

        current_phase = "alias_build"
        expected_merchants = len(expected_counts)
        progress = _ProgressTracker(
            expected_merchants if expected_merchants > 0 else None,
            logger,
            "S3 alias build merchants (edge_catalogue_3B -> alias blob/index)",
        )

        tmp_root = run_paths.tmp_root / f"s3_alias_{uuid.uuid4().hex}"
        tmp_root.mkdir(parents=True, exist_ok=True)
        blob_tmp_path = tmp_root / "edge_alias_blob_3B.bin"

        index_rows: list[dict] = []
        current_merchant: Optional[int] = None
        current_weights: list[float] = []
        prev_key: Optional[tuple[int, str]] = None
        processed_merchants: set[int] = set()

        blob_hasher = hashlib.sha256()
        blob_size = 0
        offset = 0

        def _flush_merchant() -> None:
            nonlocal current_merchant, current_weights, offset, blob_size, max_abs_delta_decode
            if current_merchant is None:
                return
            expected = expected_counts.get(current_merchant)
            if expected is None:
                _abort(
                    "E3B_S3_007_S2_INPUT_INVALID",
                    "V-08",
                    "edge_index_missing_merchant",
                    {"merchant_id": current_merchant},
                    manifest_fingerprint,
                )
            if expected != len(current_weights):
                _abort(
                    "E3B_S3_010_ALIAS_INDEX_INVALID",
                    "V-13",
                    "edge_count_mismatch",
                    {
                        "merchant_id": current_merchant,
                        "expected": expected,
                        "actual": len(current_weights),
                    },
                    manifest_fingerprint,
                )
            slice_bytes, checksum, alias_len, abs_delta, fallback_used = _build_alias_slice(
                current_weights,
                current_merchant,
                policy,
                str(manifest_fingerprint),
            )
            if fallback_used:
                counts["fallback_uniform_total"] += 1
            max_abs_delta_decode = max(max_abs_delta_decode, abs_delta)
            if abs_delta <= float(policy["quantisation_epsilon"]):
                counts["merchants_mass_exact_after_decode"] += 1
            alignment_bytes = int(policy["alignment_bytes"])
            pad_included = bool(policy["pad_included"])
            pad_byte = policy["pad_byte"]
            if offset % alignment_bytes != 0:
                _abort(
                    "E3B_S3_ALIAS_CONSTRUCTION_FAILED",
                    "V-12",
                    "alignment_violation",
                    {"merchant_id": current_merchant, "offset": offset},
                    manifest_fingerprint,
                )
            slice_length = len(slice_bytes)
            padding = 0
            remainder = slice_length % alignment_bytes if pad_included else (offset + slice_length) % alignment_bytes
            if remainder:
                padding = alignment_bytes - remainder
            length_for_index = slice_length + padding if pad_included else slice_length
            with blob_tmp_path.open("ab") as handle:
                handle.write(slice_bytes)
                if padding:
                    handle.write(pad_byte * padding)
            blob_hasher.update(slice_bytes)
            if padding:
                blob_hasher.update(pad_byte * padding)
            blob_size += slice_length + padding
            index_rows.append(
                {
                    "scope": "MERCHANT",
                    "seed": int(seed),
                    "manifest_fingerprint": str(manifest_fingerprint),
                    "merchant_id": int(current_merchant),
                    "blob_offset_bytes": int(offset),
                    "blob_length_bytes": int(length_for_index),
                    "edge_count_total": int(expected),
                    "alias_table_length": int(alias_len),
                    "merchant_alias_checksum": checksum,
                    "alias_layout_version": policy["layout_version"],
                    "universe_hash": None,
                    "blob_sha256_hex": None,
                    "notes": None,
                }
            )
            counts["edges_total"] += int(expected)
            counts["merchants_total"] += 1
            processed_merchants.add(int(current_merchant))
            offset += slice_length + padding
            current_merchant = None
            current_weights = []
            progress.update(1)

        for edge_file in edge_files:
            edge_df = pl.read_parquet(edge_file, columns=["merchant_id", "edge_id", "edge_weight"])
            for row in edge_df.iter_rows(named=True):
                merchant_id = int(row["merchant_id"])
                edge_id = str(row["edge_id"])
                edge_weight = float(row["edge_weight"])
                if merchant_id not in virtual_ids:
                    _abort(
                        "E3B_S3_006_S1_INPUT_INVALID",
                        "V-07",
                        "edge_for_non_virtual_merchant",
                        {"merchant_id": merchant_id},
                        manifest_fingerprint,
                    )
                key = (merchant_id, edge_id)
                if prev_key is not None and key < prev_key:
                    _abort(
                        "E3B_S3_008_EDGE_ORDER_INVALID",
                        "V-14",
                        "edge_order_not_asc",
                        {"prev": prev_key, "current": key},
                        manifest_fingerprint,
                    )
                prev_key = key
                if current_merchant is None:
                    current_merchant = merchant_id
                if merchant_id != current_merchant:
                    _flush_merchant()
                    current_merchant = merchant_id
                current_weights.append(edge_weight)

        _flush_merchant()

        missing_merchants = [
            merchant_id
            for merchant_id, count in expected_counts.items()
            if count > 0 and merchant_id not in processed_merchants
        ]
        if missing_merchants:
            _abort(
                "E3B_S3_010_ALIAS_INDEX_INVALID",
                "V-13",
                "missing_merchants",
                {"count": len(missing_merchants), "sample": missing_merchants[:10]},
                manifest_fingerprint,
            )
        if global_edges_total is not None and counts["edges_total"] != int(global_edges_total):
            _abort(
                "E3B_S3_010_ALIAS_INDEX_INVALID",
                "V-13",
                "global_edge_count_mismatch",
                {"expected": int(global_edges_total), "actual": counts["edges_total"]},
                manifest_fingerprint,
            )

        blob_sha256 = blob_hasher.hexdigest()
        blob_size_bytes = blob_size

        logger.info(
            "S3: alias blob built (merchants=%s, edges=%s, bytes=%s)",
            counts["merchants_total"],
            counts["edges_total"],
            blob_size_bytes,
        )

        index_rows.sort(key=lambda row: row["merchant_id"])
        index_rows.append(
            {
                "scope": "GLOBAL",
                "seed": int(seed),
                "manifest_fingerprint": str(manifest_fingerprint),
                "merchant_id": None,
                "blob_offset_bytes": None,
                "blob_length_bytes": int(blob_size_bytes),
                "edge_count_total": int(counts["edges_total"]),
                "alias_table_length": None,
                "merchant_alias_checksum": None,
                "alias_layout_version": policy["layout_version"],
                "universe_hash": None,
                "blob_sha256_hex": blob_sha256,
                "notes": None,
            }
        )

        index_schema = {
            "scope": pl.Utf8,
            "seed": pl.UInt64,
            "manifest_fingerprint": pl.Utf8,
            "merchant_id": pl.UInt64,
            "blob_offset_bytes": pl.Int64,
            "blob_length_bytes": pl.Int64,
            "edge_count_total": pl.Int64,
            "alias_table_length": pl.Int64,
            "merchant_alias_checksum": pl.Utf8,
            "alias_layout_version": pl.Utf8,
            "universe_hash": pl.Utf8,
            "blob_sha256_hex": pl.Utf8,
            "notes": pl.Utf8,
        }

        index_df = pl.DataFrame(index_rows, schema=index_schema)
        alias_index_pack, alias_index_table = _table_pack(schema_3b, "plan/edge_alias_index_3B")
        _inline_external_refs(alias_index_pack, schema_layer1, "schemas.layer1.yaml#")
        try:
            validate_dataframe(index_df.iter_rows(named=True), alias_index_pack, alias_index_table)
        except SchemaValidationError as exc:
            _abort(
                "E3B_S3_010_ALIAS_INDEX_INVALID",
                "V-13",
                "alias_index_schema_invalid",
                {"error": str(exc)},
                manifest_fingerprint,
            )

        index_tmp_path = tmp_root / "edge_alias_index_3B.parquet"
        index_df.write_parquet(index_tmp_path, compression="zstd")

        edge_alias_index_digest = sha256_file(index_tmp_path).sha256_hex
        components = [
            ("cdn_weights", cdn_weights_digest),
            ("edge_alias_index", edge_alias_index_digest),
            ("edge_catalogue_index", edge_catalogue_index_digest),
            ("virtual_rules", virtual_rules_digest),
        ]
        components.sort(key=lambda item: item[0])
        digest_bytes = b"".join(bytes.fromhex(item[1]) for item in components)
        universe_hash = hashlib.sha256(digest_bytes).hexdigest()

        logger.info(
            "S3: universe hash computed (components=%s, universe_hash=%s)",
            [name for name, _ in components],
            universe_hash,
        )

        _warn(
            "universe_hash_not_echoed_in_alias_index",
            {"reason": "avoid digest circularity", "universe_hash": universe_hash},
            manifest_fingerprint,
        )

        universe_payload = {
            "manifest_fingerprint": str(manifest_fingerprint),
            "parameter_hash": str(parameter_hash),
            "cdn_weights_digest": cdn_weights_digest,
            "edge_catalogue_index_digest": edge_catalogue_index_digest,
            "edge_alias_index_digest": edge_alias_index_digest,
            "virtual_rules_digest": virtual_rules_digest,
            "universe_hash": universe_hash,
            "created_at_utc": utc_now_rfc3339_micro(),
        }
        try:
            _validate_payload(schema_3b, schema_layer1, "validation/edge_universe_hash_3B", universe_payload)
        except SchemaValidationError as exc:
            _abort(
                "E3B_S3_012_UNIVERSE_HASH_INVALID",
                "V-15",
                "edge_universe_hash_schema_invalid",
                {"error": str(exc)},
                manifest_fingerprint,
            )

        universe_tmp_path = tmp_root / "edge_universe_hash_3B.json"
        _write_json(universe_tmp_path, universe_payload)

        gamma_tmp_path = tmp_root / "gamma_draw_log_3B.jsonl"
        gamma_tmp_path.write_text("", encoding="utf-8")

        blob_entry = find_dataset_entry(dictionary_3b, "edge_alias_blob_3B").entry
        index_entry = find_dataset_entry(dictionary_3b, "edge_alias_index_3B").entry
        hash_entry = find_dataset_entry(dictionary_3b, "edge_universe_hash_3B").entry
        gamma_entry = find_dataset_entry(dictionary_3b, "gamma_draw_log_3B").entry

        blob_path = _resolve_dataset_path(blob_entry, run_paths, config.external_roots, tokens)
        index_path = _resolve_dataset_path(index_entry, run_paths, config.external_roots, tokens)
        universe_hash_path = _resolve_dataset_path(hash_entry, run_paths, config.external_roots, tokens)
        gamma_log_path = _resolve_dataset_path(gamma_entry, run_paths, config.external_roots, tokens)

        _atomic_publish_file(blob_tmp_path, blob_path, logger, "edge_alias_blob_3B")
        _atomic_publish_file(index_tmp_path, index_path, logger, "edge_alias_index_3B")
        _atomic_publish_file(universe_tmp_path, universe_hash_path, logger, "edge_universe_hash_3B")
        _atomic_publish_file(gamma_tmp_path, gamma_log_path, logger, "gamma_draw_log_3B")

        status = "PASS"
        timer.info("S3: outputs published (blob/index/universe hash/gamma guardrail)")

    except EngineFailure as exc:
        status = "FAIL"
        error_code = exc.error_code
        error_class = exc.error_class
        error_context = exc.context
        if not first_failure_phase:
            first_failure_phase = current_phase
    except (ContractError, HashingError, InputResolutionError, SchemaValidationError, ValueError) as exc:
        if not error_code:
            error_code = "E3B_S3_019_INFRASTRUCTURE_IO_ERROR"
        error_class = "F4"
        error_context = {"detail": str(exc), "phase": current_phase}
        if not first_failure_phase:
            first_failure_phase = current_phase
    except Exception as exc:  # noqa: BLE001
        if not error_code:
            error_code = "E3B_S3_019_INFRASTRUCTURE_IO_ERROR"
        error_class = "F4"
        error_context = {"detail": str(exc), "phase": current_phase}
        if not first_failure_phase:
            first_failure_phase = current_phase
    finally:
        finished_utc = utc_now_rfc3339_micro()
        if run_id and parameter_hash and manifest_fingerprint:
            try:
                run_report_entry = find_dataset_entry(dictionary_3b, "s3_run_report_3B").entry
                run_report_path = _resolve_dataset_path(run_report_entry, run_paths, config.external_roots, tokens)
                run_report = {
                    "layer": "layer1",
                    "segment": SEGMENT,
                    "state": STATE,
                    "parameter_hash": str(parameter_hash),
                    "manifest_fingerprint": str(manifest_fingerprint),
                    "run_id": str(run_id),
                    "status": status,
                    "seed": int(seed) if seed is not None else 0,
                    "started_at_utc": started_utc,
                    "finished_at_utc": finished_utc,
                    "durations": {"wall_ms": int((time.monotonic() - started_monotonic) * 1000)},
                    "policy": {
                        "alias_layout_policy_id": "alias_layout_policy_v1",
                        "alias_layout_policy_version": policy.get("policy_version") if "policy" in locals() else "",
                        "cdn_weights_digest": cdn_weights_digest if "cdn_weights_digest" in locals() else "",
                        "virtual_rules_digest": virtual_rules_digest if "virtual_rules_digest" in locals() else "",
                        "edge_catalogue_index_digest": edge_catalogue_index_digest
                        if "edge_catalogue_index_digest" in locals()
                        else "",
                        "edge_alias_index_digest": edge_alias_index_digest if "edge_alias_index_digest" in locals() else "",
                    },
                    "counts": counts,
                    "decode": {"max_abs_delta": max_abs_delta_decode},
                    "error_code": error_code,
                    "error_class": error_class,
                    "error_context": error_context,
                    "first_failure_phase": first_failure_phase,
                    "output": {
                        "edge_alias_blob_path": _render_catalog_path(
                            find_dataset_entry(dictionary_3b, "edge_alias_blob_3B").entry, tokens
                        ),
                        "edge_alias_index_path": _render_catalog_path(
                            find_dataset_entry(dictionary_3b, "edge_alias_index_3B").entry, tokens
                        ),
                        "edge_universe_hash_path": _render_catalog_path(
                            find_dataset_entry(dictionary_3b, "edge_universe_hash_3B").entry, tokens
                        ),
                        "gamma_draw_log_path": _render_catalog_path(
                            find_dataset_entry(dictionary_3b, "gamma_draw_log_3B").entry, tokens
                        ),
                        "format": "binary/parquet/json/jsonl",
                    },
                }
                _write_json(run_report_path, run_report)
                logger.info("S3: run-report written %s", run_report_path)
            except Exception as exc:  # noqa: BLE001
                logger.warning("S3: failed to write run-report: %s", exc)

    if status != "PASS":
        raise EngineFailure(
            "F4",
            error_code or "E3B_S3_019_INFRASTRUCTURE_IO_ERROR",
            STATE,
            MODULE_NAME,
            error_context or {},
        )

    if (
        blob_path is None
        or index_path is None
        or universe_hash_path is None
        or gamma_log_path is None
        or run_report_path is None
    ):
        raise EngineFailure(
            "F4",
            "E3B_S3_019_INFRASTRUCTURE_IO_ERROR",
            STATE,
            MODULE_NAME,
            {"detail": "missing output paths"},
        )

    return S3Result(
        run_id=str(run_id),
        parameter_hash=str(parameter_hash),
        manifest_fingerprint=str(manifest_fingerprint),
        blob_path=blob_path,
        index_path=index_path,
        universe_hash_path=universe_hash_path,
        gamma_log_path=gamma_log_path,
        run_report_path=run_report_path,
    )
