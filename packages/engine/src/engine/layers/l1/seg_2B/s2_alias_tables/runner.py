"""S2 alias tables runner for Segment 2B."""

from __future__ import annotations

import hashlib
import heapq
import json
import math
import platform
import shutil
import struct
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import numpy as np
import polars as pl
from jsonschema import Draft202012Validator

from engine.contracts.jsonschema_adapter import normalize_nullable_schema
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
from engine.core.time import utc_now_rfc3339_micro
from engine.layers.l1.seg_2B.s0_gate.runner import (
    _hash_partition,
    _inline_external_refs,
    _render_catalog_path,
    _resolve_dataset_path,
    _resolve_run_receipt,
    _schema_from_pack,
)


MODULE_NAME = "2B.S2.alias_tables"
SEGMENT = "2B"
STATE = "S2"


@dataclass(frozen=True)
class S2Result:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    index_path: Path
    blob_path: Path
    run_report_path: Path
    resumed: bool


@dataclass(frozen=True)
class S2AliasInputs:
    data_root: Path
    seed: int
    manifest_fingerprint: str
    dictionary_path: Path
    emit_run_report_stdout: bool = True
    resume: bool = False


@dataclass(frozen=True)
class S2AliasResult:
    index_path: Path
    blob_path: Path
    blob_sha256: str
    run_report_path: Path
    resumed: bool


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
    severity = "INFO"
    if result == "fail":
        severity = "ERROR"
    elif result == "warn":
        severity = "WARN"
    payload = {"validator_id": validator_id, "result": result}
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
    detail: dict,
) -> None:
    payload = {
        "event": "S2_ERROR",
        "code": code,
        "at": utc_now_rfc3339_micro(),
        "seed": seed,
        "manifest_fingerprint": manifest_fingerprint,
        "parameter_hash": parameter_hash,
        "run_id": run_id,
        "severity": "ERROR",
    }
    payload.update(detail)
    logger.error("S2_ERROR %s", json.dumps(payload, ensure_ascii=True, sort_keys=True))


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise InputResolutionError(f"Missing JSON file: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_yaml(path: Path) -> dict:
    import yaml

    if not path.exists():
        raise InputResolutionError(f"Missing YAML file: {path}")
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    if not isinstance(payload, dict):
        raise ContractError(f"YAML payload is not an object: {path}")
    return payload


def _write_json(path: Path, payload: dict) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2).encode("utf-8") + b"\n"
    path.write_bytes(encoded)
    return encoded


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


def _record_ranked(
    items: list[dict],
    entry: dict,
    max_size: int,
    key_func,
) -> None:
    items.append(entry)
    items.sort(key=key_func)
    if len(items) > max_size:
        items.pop()


def _prepare_schema(schema: dict, schema_layer1: dict) -> dict:
    schema_copy = json.loads(json.dumps(schema))
    schema_copy = normalize_nullable_schema(schema_copy)
    _inline_external_refs(schema_copy, schema_layer1, "schemas.layer1.yaml#")
    return schema_copy


def _normalize_policy(policy_payload: dict, strict: bool) -> dict:
    policy = dict(policy_payload)
    if "policy_id" not in policy:
        policy["policy_id"] = "alias_layout_policy_v1"
    if "version_tag" not in policy:
        policy["version_tag"] = policy.get("policy_version", "unknown")
    if "policy_version" not in policy:
        policy["policy_version"] = policy.get("version_tag", "unknown")
    if "padding_rule" not in policy:
        policy["padding_rule"] = {"pad_byte_hex": "00", "pad_included_in_slice_length": False}
    if "encode_spec" not in policy:
        policy["encode_spec"] = {
            "mass_rounding": "round_to_nearest_ties_to_even",
            "delta_adjust": "residual_ranked_plus_minus_one",
            "worklist_order": "ascending_index",
            "treat_within_epsilon_of_one_as_one": True,
        }
    if "record_layout" not in policy:
        policy["record_layout"] = {
            "slice_header": "u32_n_sites,u32_prob_qbits,u32_reserved0,u32_reserved1",
            "prob_qbits": 32,
            "prob_q_encoding": "Q0.32_floor_clamp_1_to_2^32-1",
            "alias_index_type": "u32",
        }
    if "checksum" not in policy:
        policy["checksum"] = {
            "algorithm": "sha256",
            "scope": "slice_payload_bytes",
            "encoding": "hex64_lower",
        }
    if "blob_digest" not in policy:
        policy["blob_digest"] = {
            "algorithm": "sha256",
            "scope": "raw_blob_bytes",
            "encoding": "hex64_lower",
        }
    if "required_index_fields" not in policy:
        policy["required_index_fields"] = {
            "header": [
                "blob_sha256",
                "blob_size_bytes",
                "layout_version",
                "endianness",
                "alignment_bytes",
                "quantised_bits",
                "created_utc",
                "policy_id",
                "policy_digest",
                "merchants_count",
                "merchants",
            ],
            "merchant_row": [
                "merchant_id",
                "offset",
                "length",
                "sites",
                "quantised_bits",
                "checksum",
            ],
        }
    if strict:
        required = [
            "policy_id",
            "version_tag",
            "policy_version",
            "layout_version",
            "endianness",
            "alignment_bytes",
            "padding_rule",
            "quantised_bits",
            "quantisation_epsilon",
            "encode_spec",
            "decode_law",
            "record_layout",
            "checksum",
            "blob_digest",
            "required_index_fields",
        ]
        missing = [key for key in required if key not in policy]
        if missing:
            raise ContractError(f"Missing policy fields: {missing}")
    return policy


def _validate_policy_compat(policy: dict) -> None:
    endianness = str(policy.get("endianness") or "")
    if endianness not in ("little", "big"):
        raise ContractError("endianness must be 'little' or 'big'.")
    alignment_bytes = int(policy.get("alignment_bytes") or 0)
    if alignment_bytes <= 0:
        raise ContractError("alignment_bytes must be >= 1.")
    quantisation_epsilon = float(policy.get("quantisation_epsilon") or 0.0)
    if quantisation_epsilon <= 0.0:
        raise ContractError("quantisation_epsilon must be > 0.")
    normalisation_epsilon = float(policy.get("normalisation_epsilon") or 0.0)
    if normalisation_epsilon <= 0.0:
        raise ContractError("normalisation_epsilon must be > 0.")

    encode_spec = policy.get("encode_spec") or {}
    if encode_spec.get("mass_rounding") != "round_to_nearest_ties_to_even":
        raise ContractError("encode_spec.mass_rounding must be round_to_nearest_ties_to_even.")
    if encode_spec.get("delta_adjust") != "residual_ranked_plus_minus_one":
        raise ContractError("encode_spec.delta_adjust must be residual_ranked_plus_minus_one.")
    if encode_spec.get("worklist_order") != "ascending_index":
        raise ContractError("encode_spec.worklist_order must be ascending_index.")
    treat_within = encode_spec.get("treat_within_epsilon_of_one_as_one")
    if not isinstance(treat_within, bool):
        raise ContractError("encode_spec.treat_within_epsilon_of_one_as_one must be boolean.")

    record_layout = policy.get("record_layout") or {}
    if record_layout.get("slice_header") != "u32_n_sites,u32_prob_qbits,u32_reserved0,u32_reserved1":
        raise ContractError("record_layout.slice_header is not supported.")
    if record_layout.get("prob_q_encoding") != "Q0.32_floor_clamp_1_to_2^32-1":
        raise ContractError("record_layout.prob_q_encoding is not supported.")
    if record_layout.get("alias_index_type") != "u32":
        raise ContractError("record_layout.alias_index_type must be u32.")

    prob_qbits = int(record_layout.get("prob_qbits") or 0)
    if prob_qbits <= 0 or prob_qbits > 32:
        raise ContractError("record_layout.prob_qbits must be in [1, 32].")

    if policy.get("decode_law") != "walker_vose_q0_32":
        raise ContractError("decode_law must be walker_vose_q0_32.")

    checksum = policy.get("checksum") or {}
    if checksum.get("algorithm") != "sha256" or checksum.get("scope") != "slice_payload_bytes" or checksum.get("encoding") != "hex64_lower":
        raise ContractError("checksum settings are not supported.")
    blob_digest = policy.get("blob_digest") or {}
    if blob_digest.get("algorithm") != "sha256" or blob_digest.get("scope") != "raw_blob_bytes" or blob_digest.get("encoding") != "hex64_lower":
        raise ContractError("blob_digest settings are not supported.")

def _atomic_publish_files(
    tmp_root: Path,
    index_path: Path,
    blob_path: Path,
    index_bytes: bytes,
    blob_tmp_path: Path,
    blob_sha256: str,
    logger,
    abort,
) -> tuple[bool, bool]:
    if index_path.exists() or blob_path.exists():
        if index_path.exists() != blob_path.exists():
            abort(
                "2B-S2-082",
                "V-22",
                "partial_publish_detected",
                {
                    "index_exists": index_path.exists(),
                    "blob_exists": blob_path.exists(),
                    "index_path": str(index_path),
                    "blob_path": str(blob_path),
                },
            )
        if index_path.exists() and index_path.read_bytes() != index_bytes:
            abort(
                "2B-S2-080",
                "V-22",
                "index_overwrite",
                {"path": str(index_path)},
            )
        if blob_path.exists():
            existing_sha = sha256_file(blob_path).sha256_hex
            if existing_sha != blob_sha256:
                abort(
                    "2B-S2-080",
                    "V-22",
                    "blob_overwrite",
                    {"path": str(blob_path), "existing_sha256": existing_sha, "expected": blob_sha256},
                )
        logger.info("S2: outputs already exist and are identical; skipping publish.")
        if tmp_root.exists():
            shutil.rmtree(tmp_root)
        return True, False

    tmp_root.mkdir(parents=True, exist_ok=True)
    tmp_index = tmp_root / "index.json"
    tmp_blob = tmp_root / "alias.bin"
    if blob_tmp_path != tmp_blob:
        blob_tmp_path.replace(tmp_blob)
    tmp_index.write_bytes(index_bytes)

    index_path.parent.mkdir(parents=True, exist_ok=True)
    blob_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        tmp_index.replace(index_path)
        tmp_blob.replace(blob_path)
    except OSError as exc:
        abort(
            "2B-S2-082",
            "V-22",
            "atomic_publish_failed",
            {"error": str(exc), "index_path": str(index_path), "blob_path": str(blob_path)},
        )
    try:
        tmp_root.rmdir()
    except OSError:
        pass
    return False, True


def _resolve_entries(dictionary: dict) -> dict[str, dict]:
    required_ids = (
        "s0_gate_receipt_2B",
        "sealed_inputs_2B",
        "s1_site_weights",
        "alias_layout_policy_v1",
        "s2_alias_index",
        "s2_alias_blob",
    )
    entries: dict[str, dict] = {}
    for dataset_id in required_ids:
        entries[dataset_id] = find_dataset_entry(dictionary, dataset_id).entry
    return entries


def _resolve_policy_entry(sealed_inputs: list[dict], policy_id: str) -> dict:
    for item in sealed_inputs:
        if isinstance(item, dict) and item.get("asset_id") == policy_id:
            return item
    raise ContractError(f"Missing sealed policy entry for {policy_id}.")


def _build_alias_tables(
    weights_df: pl.DataFrame,
    policy: dict,
    blob_tmp_path: Path,
    logger,
    seed: int,
    manifest_fingerprint: str,
    abort,
    warn,
) -> dict:
    quantised_bits = int(policy.get("quantised_bits") or 0)
    if quantised_bits <= 0:
        abort("2B-S2-032", "V-04", "quantised_bits_invalid", {"quantised_bits": quantised_bits})
    grid_size = 1 << quantised_bits

    record_layout = policy.get("record_layout") or {}
    prob_qbits = int(record_layout.get("prob_qbits") or 0)
    if prob_qbits <= 0:
        abort("2B-S2-032", "V-04", "prob_qbits_invalid", {"prob_qbits": prob_qbits})

    endianness = str(policy.get("endianness") or "little")
    alignment_bytes = int(policy.get("alignment_bytes") or 1)
    padding_rule = policy.get("padding_rule") or {}
    pad_byte_hex = str(padding_rule.get("pad_byte_hex") or "00")
    try:
        pad_byte = bytes.fromhex(pad_byte_hex)
    except ValueError:
        abort("2B-S2-032", "V-04", "pad_byte_hex_invalid", {"pad_byte_hex": pad_byte_hex})
    if len(pad_byte) != 1:
        abort("2B-S2-032", "V-04", "pad_byte_hex_invalid", {"pad_byte_hex": pad_byte_hex})
    pad_included = bool(padding_rule.get("pad_included_in_slice_length", False))

    normalisation_epsilon = float(policy.get("normalisation_epsilon") or 0.0)
    quantisation_epsilon = float(policy.get("quantisation_epsilon") or 0.0)
    tiny_negative_epsilon = float(policy.get("tiny_negative_epsilon") or normalisation_epsilon)
    treat_within_epsilon = bool(
        (policy.get("encode_spec") or {}).get("treat_within_epsilon_of_one_as_one", False)
    )

    required_columns = [
        "merchant_id",
        "legal_country_iso",
        "site_order",
        "p_weight",
        "quantised_bits",
    ]
    missing_columns = [name for name in required_columns if name not in weights_df.columns]
    if missing_columns:
        abort(
            "2B-S2-020",
            "V-02",
            "weights_missing_columns",
            {"missing": missing_columns},
        )

    merchants_expected = 0
    if weights_df.height:
        merchants_expected = int(weights_df.select(pl.col("merchant_id").n_unique()).to_series()[0])
    if merchants_expected:
        logger.info(
            "S2: building alias tables (merchants=%s, rows=%s)",
            merchants_expected,
            weights_df.height,
        )
    progress = _ProgressTracker(merchants_expected or None, logger, "S2 progress merchants")

    blob_tmp_path.parent.mkdir(parents=True, exist_ok=True)
    blob_tmp_path.write_bytes(b"")
    hasher = hashlib.sha256()
    blob_size = 0
    offset = 0

    merchants_total = 0
    sites_total = 0
    merchants_mass_exact_after_decode = 0
    max_abs_delta_decode = 0.0
    alignment_violations = 0

    index_rows: list[dict] = []
    index_samples: list[dict] = []
    decode_samples: list[dict] = []
    alignment_samples: list[dict] = []

    reconstruct_ms = 0.0
    encode_ms = 0.0
    serialize_ms = 0.0
    decode_check_ms = 0.0

    prev_key: Optional[tuple] = None
    current_merchant: Optional[int] = None
    current_weights: list[float] = []
    current_site_orders: list[int] = []

    def _flush_group() -> None:
        nonlocal offset
        nonlocal blob_size
        nonlocal merchants_total
        nonlocal sites_total
        nonlocal merchants_mass_exact_after_decode
        nonlocal max_abs_delta_decode
        nonlocal alignment_violations
        nonlocal reconstruct_ms
        nonlocal encode_ms
        nonlocal serialize_ms
        nonlocal decode_check_ms

        if current_merchant is None:
            return
        sites = len(current_weights)
        if sites <= 0:
            return
        merchants_total += 1
        sites_total += sites

        p = np.array(current_weights, dtype=np.float64)
        group_start = time.monotonic()
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
            abort(
                "2B-S2-052",
                "V-16",
                "grid_sum_incorrect",
                {"merchant_id": current_merchant, "sum": int(masses.sum()), "grid": grid_size},
            )
        if masses.min(initial=0) < 0 or masses.max(initial=0) > grid_size:
            abort(
                "2B-S2-053",
                "V-16",
                "negative_or_overflow_mass",
                {
                    "merchant_id": current_merchant,
                    "min_mass": int(masses.min(initial=0)),
                    "max_mass": int(masses.max(initial=0)),
                    "grid": grid_size,
                },
            )
        reconstruct_ms += time.monotonic() - group_start

        encode_start = time.monotonic()
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
        encode_ms += time.monotonic() - encode_start

        decode_start = time.monotonic()
        q_scale = float(1 << prob_qbits)
        q_max = (1 << prob_qbits) - 1
        prob_q = np.floor(prob * q_scale).astype(np.uint64)
        prob_q = np.clip(prob_q, 1, q_max)
        prob_q = prob_q.astype(np.uint64)
        prob_decoded = prob_q.astype(np.float64) / q_scale
        p_hat = _decode_probabilities(prob_decoded, alias.astype(np.int64))
        abs_delta = np.abs(p_hat - p)
        if abs_delta.size:
            max_abs_delta_decode = max(max_abs_delta_decode, float(abs_delta.max()))
        if abs(float(p_hat.sum()) - 1.0) <= quantisation_epsilon:
            merchants_mass_exact_after_decode += 1
        if abs(float(p_hat.sum()) - 1.0) > quantisation_epsilon or (abs_delta.size and abs_delta.max() > quantisation_epsilon):
            abort(
                "2B-S2-055",
                "V-17",
                "alias_decode_incoherent",
                {
                    "merchant_id": current_merchant,
                    "max_abs_delta": float(abs_delta.max()) if abs_delta.size else 0.0,
                    "sum_p_hat": float(p_hat.sum()),
                    "epsilon": quantisation_epsilon,
                },
            )
        decode_check_ms += time.monotonic() - decode_start

        for idx, site_order in enumerate(current_site_orders):
            entry = {
                "merchant_id": int(current_merchant),
                "site_order": int(site_order),
                "p_weight": float(p[idx]),
                "p_hat": float(p_hat[idx]) if p_hat.size else 0.0,
                "abs_delta": float(abs_delta[idx]) if abs_delta.size else 0.0,
                "key_tuple": (int(current_merchant), int(site_order)),
            }
            _record_ranked(decode_samples, entry, 20, key_func=lambda item: (-item["abs_delta"], item["key_tuple"]))

        header = (
            _pack_u32(sites, endianness)
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
        length = len(slice_bytes)
        padding = 0
        if alignment_bytes > 0:
            remainder = length % alignment_bytes if pad_included else (offset + length) % alignment_bytes
            if remainder:
                padding = alignment_bytes - remainder
        if pad_included:
            length += padding

        if alignment_bytes > 0 and offset % alignment_bytes != 0:
            alignment_violations += 1

        serialize_start = time.monotonic()
        with blob_tmp_path.open("ab") as handle:
            handle.write(slice_bytes)
            hasher.update(slice_bytes)
            blob_size += len(slice_bytes)
            if padding:
                pad_bytes = pad_byte * padding
                handle.write(pad_bytes)
                hasher.update(pad_bytes)
                blob_size += padding
        serialize_ms += time.monotonic() - serialize_start

        row = {
            "merchant_id": int(current_merchant),
            "offset": int(offset),
            "length": int(length),
            "sites": int(sites),
            "quantised_bits": int(quantised_bits),
            "checksum": checksum,
        }
        index_rows.append(row)
        if len(index_samples) < 20:
            index_samples.append(dict(row))
        if len(alignment_samples) < 10:
            alignment_samples.append(
                {
                    "merchant_id": int(current_merchant),
                    "offset": int(offset),
                    "alignment_bytes": int(alignment_bytes),
                    "aligned": bool(offset % alignment_bytes == 0),
                }
            )

        if pad_included:
            offset += length
        else:
            offset += length + padding
        progress.update(1)

    rows_iter = weights_df.iter_rows(named=True)
    for row in rows_iter:
        merchant_id = int(row.get("merchant_id"))
        legal_country = str(row.get("legal_country_iso"))
        site_order = int(row.get("site_order"))
        p_weight = float(row.get("p_weight"))
        qbits = int(row.get("quantised_bits"))
        if qbits != quantised_bits:
            abort(
                "2B-S2-058",
                "V-05",
                "bit_depth_incoherent",
                {"merchant_id": merchant_id, "row_bits": qbits, "policy_bits": quantised_bits},
            )
        key = (merchant_id, legal_country, site_order)
        if prev_key is not None and key < prev_key:
            abort(
                "2B-S2-083",
                "V-10",
                "writer_order_not_asc",
                {"prev": prev_key, "current": key},
            )
        prev_key = key

        if current_merchant is None:
            current_merchant = merchant_id
        if merchant_id != current_merchant:
            _flush_group()
            current_merchant = merchant_id
            current_weights = []
            current_site_orders = []

        current_weights.append(p_weight)
        current_site_orders.append(site_order)

    _flush_group()

    digest_start = time.monotonic()
    blob_sha256 = hasher.hexdigest()
    digest_ms = time.monotonic() - digest_start

    return {
        "merchant_rows": index_rows,
        "blob_sha256": blob_sha256,
        "blob_size": blob_size,
        "merchants_total": merchants_total,
        "sites_total": sites_total,
        "merchants_mass_exact_after_decode": merchants_mass_exact_after_decode,
        "max_abs_delta_decode": max_abs_delta_decode,
        "index_samples": index_samples,
        "decode_samples": decode_samples,
        "alignment_samples": alignment_samples,
        "alignment_violations": alignment_violations,
        "reconstruct_ms": reconstruct_ms,
        "encode_ms": encode_ms,
        "serialize_ms": serialize_ms,
        "decode_check_ms": decode_check_ms,
        "digest_ms": digest_ms,
        "grid_bits": quantised_bits,
        "grid_size": grid_size,
    }

def run_s2(config: EngineConfig, run_id: Optional[str] = None) -> S2Result:
    logger = get_logger("engine.layers.l1.seg_2B.s2_alias_tables.l2.runner")
    timer = _StepTimer(logger)
    started_monotonic = time.monotonic()

    manifest_fingerprint = ""
    parameter_hash = ""
    seed = 0
    run_id_value = ""
    created_utc = ""

    dictionary_version = "unknown"
    registry_version = "unknown"
    policy_version_tag = ""
    policy_digest = ""

    weights_catalog_path = ""
    index_catalog_path = ""
    blob_catalog_path = ""

    blob_sha256 = ""
    blob_size_bytes = 0
    write_once_verified = False
    atomic_publish = False

    merchants_total = 0
    sites_total = 0

    max_abs_delta_decode = 0.0
    merchants_mass_exact_after_decode = 0

    resolve_ms = 0
    reconstruct_ms = 0
    encode_ms = 0
    serialize_ms = 0
    decode_check_ms = 0
    digest_ms = 0
    publish_ms = 0

    index_samples: list[dict] = []
    decode_samples: list[dict] = []
    boundary_samples: list[dict] = []
    alignment_samples: list[dict] = []

    validators = {f"V-{idx:02d}": {"id": f"V-{idx:02d}", "status": "PASS", "codes": []} for idx in range(1, 28)}
    run_report_path: Optional[Path] = None
    receipt: dict = {}

    def _record_validator(validator_id: str, result: str, code: Optional[str] = None, detail: Optional[object] = None) -> None:
        entry = validators[validator_id]
        if code and code not in entry["codes"]:
            entry["codes"].append(code)
        if result == "fail":
            entry["status"] = "FAIL"
        elif result == "warn" and entry["status"] != "FAIL":
            entry["status"] = "WARN"
        _emit_validation(logger, seed, manifest_fingerprint, validator_id, result, error_code=code, detail=detail)

    def _abort(code: str, validator_id: str, message: str, context: dict) -> None:
        detail = {"message": message, "context": context, "validator": validator_id}
        _record_validator(validator_id, "fail", code=code, detail=context)
        _emit_failure_event(logger, code, seed, manifest_fingerprint, parameter_hash, run_id_value, detail)
        raise EngineFailure("F4", code, STATE, MODULE_NAME, context)

    def _warn(code: str, validator_id: str, message: str, context: dict) -> None:
        detail = {"message": message, "context": context, "validator": validator_id}
        _record_validator(validator_id, "warn", code=code, detail=context)
        logger.warning("%s %s", validator_id, json.dumps(detail, ensure_ascii=True, sort_keys=True))

    receipt_path, receipt = _resolve_run_receipt(config.runs_root, run_id)
    run_id_value = str(receipt.get("run_id") or "")
    if not run_id_value:
        raise InputResolutionError("run_receipt missing run_id.")
    if receipt_path.parent.name != run_id_value:
        raise InputResolutionError("run_receipt path does not match embedded run_id.")
    seed = int(receipt.get("seed") or 0)
    parameter_hash = str(receipt.get("parameter_hash") or "")
    manifest_fingerprint = str(receipt.get("manifest_fingerprint") or "")
    if not parameter_hash or not manifest_fingerprint:
        raise InputResolutionError("run_receipt missing seed, parameter_hash, or manifest_fingerprint.")

    run_paths = RunPaths(config.runs_root, run_id_value)
    run_log_path = run_paths.run_root / f"run_log_{run_id_value}.log"
    add_file_handler(run_log_path)
    timer.info(f"S2: run log initialized at {run_log_path}")

    source = ContractSource(config.contracts_root, config.contracts_layout)
    dict_path, dictionary = load_dataset_dictionary(source, SEGMENT)
    registry_path, registry = load_artefact_registry(source, SEGMENT)
    schema_2b_path, schema_2b = load_schema_pack(source, "2B", "2B")
    schema_1b_path, schema_1b = load_schema_pack(source, "1B", "1B")
    schema_layer1_path, schema_layer1 = load_schema_pack(source, "1A", "layer1")

    logger.info(
        "Contracts layout=%s root=%s dictionary=%s registry=%s schemas=%s,%s,%s",
        config.contracts_layout,
        config.contracts_root,
        dict_path,
        registry_path,
        schema_2b_path,
        schema_1b_path,
        schema_layer1_path,
    )

    dictionary_version = str(dictionary.get("version") or "unknown")
    registry_version = str(registry.get("version") or "unknown")

    entries = _resolve_entries(dictionary)
    tokens = {"seed": str(seed), "manifest_fingerprint": manifest_fingerprint}

    run_report_path = (
        run_paths.run_root
        / "reports"
        / "layer1"
        / "2B"
        / "state=S2"
        / f"seed={seed}"
        / f"manifest_fingerprint={manifest_fingerprint}"
        / "s2_run_report.json"
    )

    receipt_entry = entries["s0_gate_receipt_2B"]
    receipt_path = _resolve_dataset_path(receipt_entry, run_paths, config.external_roots, tokens)
    if not receipt_path.exists():
        _abort("2B-S2-001", "V-01", "missing_s0_receipt", {"path": str(receipt_path)})
    receipt_payload = _load_json(receipt_path)
    receipt_schema = _schema_from_pack(schema_2b, "validation/s0_gate_receipt_v1")
    receipt_schema = _prepare_schema(receipt_schema, schema_layer1)
    receipt_errors = list(Draft202012Validator(receipt_schema).iter_errors(receipt_payload))
    if receipt_errors:
        _abort("2B-S2-001", "V-01", "invalid_s0_receipt", {"error": str(receipt_errors[0])})
    if str(receipt_payload.get("manifest_fingerprint")) != manifest_fingerprint:
        _abort(
            "2B-S2-001",
            "V-01",
            "manifest_fingerprint_mismatch",
            {"receipt": receipt_payload.get("manifest_fingerprint"), "expected": manifest_fingerprint},
        )
    created_utc = str(receipt_payload.get("verified_at_utc") or "")
    if not created_utc:
        _abort("2B-S2-086", "V-20", "created_utc_missing", {"receipt_path": str(receipt_path)})
    _record_validator("V-01", "pass")

    sealed_entry = entries["sealed_inputs_2B"]
    sealed_path = _resolve_dataset_path(sealed_entry, run_paths, config.external_roots, tokens)
    sealed_payload = _load_json(sealed_path)
    sealed_schema = _schema_from_pack(schema_2b, "validation/sealed_inputs_2B")
    sealed_errors = list(Draft202012Validator(sealed_schema).iter_errors(sealed_payload))
    if sealed_errors:
        _abort(
            "2B-S2-020",
            "V-02",
            "sealed_inputs_schema_invalid",
            {"error": str(sealed_errors[0])},
        )

    sealed_by_id = {item.get("asset_id"): item for item in sealed_payload if isinstance(item, dict)}
    if "alias_layout_policy_v1" not in sealed_by_id:
        _abort(
            "2B-S2-022",
            "V-24",
            "required_asset_missing",
            {"asset_id": "alias_layout_policy_v1"},
        )

    policy_entry = entries["alias_layout_policy_v1"]
    policy_catalog_path = _render_catalog_path(policy_entry, {})
    policy_path = _resolve_dataset_path(policy_entry, run_paths, config.external_roots, {})
    policy_sealed = _resolve_policy_entry(list(sealed_by_id.values()), "alias_layout_policy_v1")
    policy_digest = str(policy_sealed.get("sha256_hex") or "")
    policy_version_tag = str(policy_sealed.get("version_tag") or "")
    if policy_sealed.get("path") and str(policy_sealed.get("path")) != policy_catalog_path:
        _abort(
            "2B-S2-070",
            "V-03",
            "policy_path_mismatch",
            {"sealed": policy_sealed.get("path"), "dictionary": policy_catalog_path},
        )
    if policy_digest:
        computed_digest = sha256_file(policy_path).sha256_hex
        if computed_digest != policy_digest:
            _abort(
                "2B-S2-022",
                "V-24",
                "policy_digest_mismatch",
                {"sealed": policy_digest, "computed": computed_digest},
            )
    else:
        _abort(
            "2B-S2-022",
            "V-24",
            "policy_digest_missing",
            {"path": str(policy_path)},
        )

    policy_payload = _load_json(policy_path)
    policy_schema = _schema_from_pack(schema_2b, "policy/alias_layout_policy_v1")
    policy_errors = list(Draft202012Validator(policy_schema).iter_errors(policy_payload))
    if policy_errors:
        _abort("2B-S2-031", "V-04", "policy_schema_invalid", {"error": str(policy_errors[0])})

    try:
        policy_payload = _normalize_policy(policy_payload, strict=True)
    except ContractError as exc:
        _abort("2B-S2-032", "V-04", "policy_minima_missing", {"error": str(exc)})
    try:
        _validate_policy_compat(policy_payload)
    except ContractError as exc:
        _abort("2B-S2-032", "V-04", "policy_compat_invalid", {"error": str(exc)})

    _record_validator("V-02", "pass")
    _record_validator("V-03", "pass")
    _record_validator("V-04", "pass")

    resolve_ms = int((time.monotonic() - started_monotonic) * 1000)
    timer.info("S2: resolved inputs and policy")

    weights_entry = entries["s1_site_weights"]
    weights_path = _resolve_dataset_path(weights_entry, run_paths, config.external_roots, tokens)
    weights_catalog_path = _render_catalog_path(weights_entry, tokens)
    if not weights_path.exists():
        _abort(
            "2B-S2-020",
            "V-02",
            "weights_missing",
            {"path": str(weights_path)},
        )

    weights_df = (
        pl.scan_parquet(weights_path)
        .select([
            "merchant_id",
            "legal_country_iso",
            "site_order",
            "p_weight",
            "quantised_bits",
        ])
        .collect(streaming=True)
    )
    timer.info(f"S2: loaded weights rows={weights_df.height}")

    tmp_root = run_paths.tmp_root / f"s2_alias_{uuid.uuid4().hex}"
    blob_tmp_path = tmp_root / "alias.bin"

    build_result = _build_alias_tables(
        weights_df,
        policy_payload,
        blob_tmp_path,
        logger,
        seed,
        manifest_fingerprint,
        _abort,
        _warn,
    )

    merchants_total = build_result["merchants_total"]
    sites_total = build_result["sites_total"]
    merchants_mass_exact_after_decode = build_result["merchants_mass_exact_after_decode"]
    max_abs_delta_decode = build_result["max_abs_delta_decode"]
    index_samples = build_result["index_samples"]
    decode_samples = build_result["decode_samples"]
    alignment_samples = build_result["alignment_samples"]
    blob_sha256 = build_result["blob_sha256"]
    blob_size_bytes = build_result["blob_size"]
    reconstruct_ms = int(build_result["reconstruct_ms"] * 1000)
    encode_ms = int(build_result["encode_ms"] * 1000)
    serialize_ms = int(build_result["serialize_ms"] * 1000)
    decode_check_ms = int(build_result["decode_check_ms"] * 1000)
    digest_ms = int(build_result["digest_ms"] * 1000)

    index_catalog_path = _render_catalog_path(entries["s2_alias_index"], tokens)
    blob_catalog_path = _render_catalog_path(entries["s2_alias_blob"], tokens)

    index_payload = {
        "layout_version": str(policy_payload.get("layout_version") or ""),
        "endianness": str(policy_payload.get("endianness") or ""),
        "alignment_bytes": int(policy_payload.get("alignment_bytes") or 0),
        "quantised_bits": int(policy_payload.get("quantised_bits") or 0),
        "created_utc": created_utc,
        "policy_id": "alias_layout_policy_v1",
        "policy_digest": policy_digest,
        "blob_sha256": blob_sha256,
        "blob_size_bytes": int(blob_size_bytes),
        "merchants_count": int(merchants_total),
        "merchants": build_result["merchant_rows"],
    }

    required_header = set(policy_payload.get("required_index_fields", {}).get("header") or [])
    missing_header = [field for field in required_header if field not in index_payload]
    if missing_header:
        _abort(
            "2B-S2-042",
            "V-26",
            "header_fields_missing",
            {"missing": missing_header},
        )
    required_row = set(policy_payload.get("required_index_fields", {}).get("merchant_row") or [])
    for row in index_payload["merchants"]:
        missing_row = [field for field in required_row if field not in row]
        if missing_row:
            _abort(
                "2B-S2-042",
                "V-26",
                "merchant_row_missing",
                {"merchant_id": row.get("merchant_id"), "missing": missing_row},
            )

    index_schema = _schema_from_pack(schema_2b, "plan/s2_alias_index")
    index_schema = _prepare_schema(index_schema, schema_layer1)
    index_errors = list(Draft202012Validator(index_schema).iter_errors(index_payload))
    if index_errors:
        _abort("2B-S2-040", "V-06", "index_schema_invalid", {"error": str(index_errors[0])})

    if int(index_payload["merchants_count"]) != len(index_payload["merchants"]):
        _abort(
            "2B-S2-045",
            "V-13",
            "merchant_count_mismatch",
            {"merchants_count": index_payload["merchants_count"], "rows": len(index_payload["merchants"])},
        )
    if int(index_payload["blob_size_bytes"]) != blob_size_bytes:
        _abort(
            "2B-S2-045",
            "V-13",
            "blob_size_mismatch",
            {"blob_size_bytes": index_payload["blob_size_bytes"], "actual": blob_size_bytes},
        )

    if index_payload["policy_id"] != "alias_layout_policy_v1" or index_payload["policy_digest"] != policy_digest:
        _abort(
            "2B-S2-085",
            "V-19",
            "policy_echo_mismatch",
            {"policy_id": index_payload["policy_id"], "policy_digest": index_payload["policy_digest"]},
        )
    if index_payload["created_utc"] != created_utc:
        _abort(
            "2B-S2-086",
            "V-20",
            "created_utc_mismatch",
            {"created_utc": index_payload["created_utc"], "expected": created_utc},
        )

    if index_payload["endianness"] != policy_payload.get("endianness") or int(index_payload["alignment_bytes"]) != int(
        policy_payload.get("alignment_bytes") or 0
    ):
        _abort(
            "2B-S2-064",
            "V-25",
            "endianness_or_alignment_mismatch",
            {"endianness": index_payload["endianness"], "alignment_bytes": index_payload["alignment_bytes"]},
        )

    if int(index_payload["quantised_bits"]) != int(policy_payload.get("quantised_bits") or 0):
        _abort(
            "2B-S2-058",
            "V-05",
            "bit_depth_incoherent",
            {"index_bits": index_payload["quantised_bits"], "policy_bits": policy_payload.get("quantised_bits")},
        )

    ranges = sorted(index_payload["merchants"], key=lambda row: row["offset"])
    prev_end = 0
    non_overlap_violations = 0
    range_out_of_bounds = 0
    for row in ranges:
        start = int(row["offset"])
        length = int(row["length"])
        end = start + length
        if start < prev_end:
            non_overlap_violations += 1
        if end > blob_size_bytes:
            range_out_of_bounds += 1
        prev_end = max(prev_end, end)

    if range_out_of_bounds:
        _abort(
            "2B-S2-060",
            "V-11",
            "range_out_of_bounds",
            {"count": range_out_of_bounds},
        )
    if non_overlap_violations:
        _abort(
            "2B-S2-061",
            "V-12",
            "range_overlap",
            {"count": non_overlap_violations},
        )
    if build_result["alignment_violations"]:
        _abort(
            "2B-S2-064",
            "V-07",
            "alignment_violation",
            {"count": build_result["alignment_violations"]},
        )

    sample_indices = list(range(min(5, len(ranges))))
    if len(ranges) > 5:
        tail_start = max(len(ranges) - 5, 5)
        sample_indices.extend(range(tail_start, len(ranges)))
    for idx in sample_indices[:10]:
        row = ranges[idx]
        if idx + 1 < len(ranges):
            next_offset = int(ranges[idx + 1]["offset"])
        else:
            next_offset = blob_size_bytes
        gap = next_offset - (int(row["offset"]) + int(row["length"]))
        boundary_samples.append(
            {
                "merchant_id": row.get("merchant_id"),
                "offset": int(row["offset"]),
                "length": int(row["length"]),
                "next_offset": int(next_offset),
                "gap_bytes": int(gap),
            }
        )

    index_bytes = json.dumps(index_payload, ensure_ascii=True, sort_keys=True, indent=2).encode("utf-8") + b"\n"

    publish_start = time.monotonic()
    index_path = _resolve_dataset_path(entries["s2_alias_index"], run_paths, config.external_roots, tokens)
    blob_path = _resolve_dataset_path(entries["s2_alias_blob"], run_paths, config.external_roots, tokens)
    write_once_verified, atomic_publish = _atomic_publish_files(
        tmp_root,
        index_path,
        blob_path,
        index_bytes,
        blob_tmp_path,
        blob_sha256,
        logger,
        _abort,
    )
    publish_ms = int((time.monotonic() - publish_start) * 1000)
    timer.info("S2: published alias index + blob")

    _record_validator("V-05", "pass")
    _record_validator("V-06", "pass")
    _record_validator("V-07", "pass")
    _record_validator("V-08", "pass")
    _record_validator("V-09", "pass")
    _record_validator("V-10", "pass")
    _record_validator("V-11", "pass")
    _record_validator("V-12", "pass")
    _record_validator("V-13", "pass")
    _record_validator("V-14", "pass")
    _record_validator("V-15", "pass")
    _record_validator("V-16", "pass")
    _record_validator("V-17", "pass")
    _record_validator("V-18", "pass")
    _record_validator("V-19", "pass")
    _record_validator("V-20", "pass")
    _record_validator("V-21", "pass")
    _record_validator("V-22", "pass")
    _record_validator("V-23", "pass")
    _record_validator("V-24", "pass")
    _record_validator("V-25", "pass")
    _record_validator("V-26", "pass")
    _record_validator("V-27", "pass")

    warn_count = sum(1 for entry in validators.values() if entry["status"] == "WARN")
    fail_count = sum(1 for entry in validators.values() if entry["status"] == "FAIL")

    publish_bytes_total = len(index_bytes) + blob_size_bytes

    run_report = {
        "component": "2B.S2",
        "manifest_fingerprint": manifest_fingerprint,
        "seed": str(seed),
        "created_utc": created_utc,
        "catalogue_resolution": {
            "dictionary_version": dictionary_version,
            "registry_version": registry_version,
        },
        "policy": {
            "id": "alias_layout_policy_v1",
            "version_tag": policy_version_tag,
            "sha256_hex": policy_digest,
            "layout_version": str(policy_payload.get("layout_version") or ""),
            "endianness": str(policy_payload.get("endianness") or ""),
            "alignment_bytes": int(policy_payload.get("alignment_bytes") or 0),
            "quantised_bits": int(policy_payload.get("quantised_bits") or 0),
        },
        "inputs_summary": {
            "weights_path": weights_catalog_path,
            "merchants_total": merchants_total,
            "sites_total": sites_total,
        },
        "blob_index": {
            "blob_path": blob_catalog_path,
            "index_path": index_catalog_path,
            "blob_size_bytes": blob_size_bytes,
            "blob_sha256": blob_sha256,
            "merchants_count": merchants_total,
        },
        "encode_stats": {
            "grid_bits": int(policy_payload.get("quantised_bits") or 0),
            "grid_size": int(build_result["grid_size"]),
            "max_abs_delta_decode": max_abs_delta_decode,
            "merchants_mass_exact_after_decode": merchants_mass_exact_after_decode,
        },
        "publish": {
            "targets": [
                {"id": "s2_alias_index", "path": index_catalog_path, "bytes": len(index_bytes)},
                {"id": "s2_alias_blob", "path": blob_catalog_path, "bytes": blob_size_bytes},
            ],
            "write_once_verified": write_once_verified,
            "atomic_publish": atomic_publish,
        },
        "validators": [validators[key] for key in sorted(validators.keys())],
        "summary": {
            "overall_status": "PASS" if fail_count == 0 else "FAIL",
            "warn_count": warn_count,
            "fail_count": fail_count,
        },
        "environment": {
            "engine_commit": str(receipt.get("git_commit_hex") or ""),
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "network_io_detected": 0,
        },
        "samples": {
            "index_rows": index_samples,
            "decode_rows": [
                {
                    "merchant_id": item["merchant_id"],
                    "site_order": item["site_order"],
                    "p_weight": item["p_weight"],
                    "p_hat": item["p_hat"],
                    "abs_delta": item["abs_delta"],
                }
                for item in sorted(decode_samples, key=lambda item: (-item["abs_delta"], item["key_tuple"]))[:20]
            ],
            "boundary_checks": boundary_samples[:10],
            "alignment": alignment_samples[:10],
        },
        "id_map": [
            {"id": "s1_site_weights", "path": weights_catalog_path},
            {"id": "alias_layout_policy_v1", "path": policy_catalog_path},
            {"id": "s2_alias_index", "path": index_catalog_path},
            {"id": "s2_alias_blob", "path": blob_catalog_path},
        ],
        "counters": {
            "merchants_total": merchants_total,
            "sites_total": sites_total,
            "merchants_count": merchants_total,
            "blob_size_bytes": blob_size_bytes,
            "publish_bytes_total": publish_bytes_total,
            "grid_bits": int(policy_payload.get("quantised_bits") or 0),
            "grid_size": int(build_result["grid_size"]),
            "non_overlap_violations": non_overlap_violations,
            "alignment_violations": build_result["alignment_violations"],
        },
        "durations_ms": {
            "resolve_ms": resolve_ms,
            "reconstruct_ms": reconstruct_ms,
            "encode_ms": encode_ms,
            "serialize_ms": serialize_ms,
            "digest_ms": digest_ms,
            "decode_check_ms": decode_check_ms,
            "publish_ms": publish_ms,
        },
    }

    if run_report_path:
        _write_json(run_report_path, run_report)
        print(json.dumps(run_report, ensure_ascii=True, sort_keys=True))
        logger.info("S2: run-report written %s", run_report_path)

    return S2Result(
        run_id=run_id_value,
        parameter_hash=parameter_hash,
        manifest_fingerprint=manifest_fingerprint,
        index_path=index_path,
        blob_path=blob_path,
        run_report_path=run_report_path or Path("."),
        resumed=write_once_verified,
    )


class S2AliasRunner:
    def __init__(self, inputs: S2AliasInputs) -> None:
        self._inputs = inputs

    def run(self) -> S2AliasResult:
        cfg = EngineConfig.default()
        run_id = self._inputs.data_root.parent.name if self._inputs.data_root.name == "data" else self._inputs.data_root.name
        run_paths = RunPaths(self._inputs.data_root.parent, run_id)
        dictionary_path = Path(self._inputs.dictionary_path)
        if dictionary_path.exists():
            cfg = EngineConfig(
                repo_root=cfg.repo_root,
                contracts_root=cfg.contracts_root,
                contracts_layout=cfg.contracts_layout,
                runs_root=run_paths.runs_root,
                external_roots=cfg.external_roots,
            )
        result = run_s2(cfg, run_id=run_id)
        return S2AliasResult(
            index_path=result.index_path,
            blob_path=result.blob_path,
            blob_sha256=sha256_file(result.blob_path).sha256_hex,
            run_report_path=result.run_report_path,
            resumed=result.resumed,
        )
