"""Segment 5B.S4 arrival events (micro-time placement + routing)."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
import platform
import struct
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Optional

try:  # Faster JSON when available.
    import orjson

    def _json_dumps(payload: object) -> str:
        return orjson.dumps(payload, option=orjson.OPT_SORT_KEYS).decode("utf-8")

    _HAVE_ORJSON = True
except Exception:  # pragma: no cover - fallback

    def _json_dumps(payload: object) -> str:
        return json.dumps(payload, ensure_ascii=True, sort_keys=True)

    _HAVE_ORJSON = False

try:  # Optional parquet streaming
    import pyarrow as pa
    import pyarrow.parquet as pq

    _HAVE_PYARROW = True
except Exception:  # pragma: no cover - fallback
    pa = None
    pq = None
    _HAVE_PYARROW = False

import numpy as np
import polars as pl
from jsonschema import Draft202012Validator

from engine.contracts.jsonschema_adapter import normalize_nullable_schema
from engine.contracts.loader import find_dataset_entry, load_dataset_dictionary, load_schema_pack
from engine.contracts.source import ContractSource
from engine.core.config import EngineConfig
from engine.core.errors import ContractError, EngineFailure, InputResolutionError, SchemaValidationError
from engine.core.hashing import sha256_file
from engine.core.logging import add_file_handler, get_logger
from engine.core.paths import RunPaths
from engine.core.time import utc_now_rfc3339_micro
from engine.layers.l1.seg_1A.s1_hurdle.rng import add_u128, low64
from engine.layers.l2.seg_5B.s0_gate.runner import (
    _append_jsonl,
    _inline_external_refs,
    _load_json,
    _load_yaml,
    _resolve_dataset_path,
    _resolve_run_receipt,
    _schema_from_pack,
    _sealed_inputs_digest,
    _segment_state_runs_path,
)
from engine.layers.l2.seg_5B.s4_arrival_events.numba_kernel import NUMBA_AVAILABLE, expand_arrivals


MODULE_NAME = "5B.s4_arrival_events"
SEGMENT = "5B"
STATE = "S4"
MICROS_PER_DAY = 86_400_000_000
DEFAULT_PROGRESS_INTERVAL_SECONDS = 10.0


@dataclass(frozen=True)
class S4Result:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    output_paths: list[Path]
    run_report_path: Path


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
    def __init__(
        self,
        total: Optional[int],
        logger,
        label: str,
        min_interval_seconds: float = DEFAULT_PROGRESS_INTERVAL_SECONDS,
    ) -> None:
        self._total = int(total) if total is not None else None
        self._logger = logger
        self._label = label
        self._start = time.monotonic()
        self._last_log = self._start
        self._processed = 0
        self._min_interval = float(min_interval_seconds)

    def update(self, count: int) -> None:
        self._processed += int(count)
        now = time.monotonic()
        if now - self._last_log < self._min_interval and not (
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


def _env_flag(name: str, default: str = "0") -> bool:
    value = os.environ.get(name, default)
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_progress_interval_seconds(name: str, default: float = DEFAULT_PROGRESS_INTERVAL_SECONDS) -> float:
    raw = os.environ.get(name, f"{default}")
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} invalid: {raw}") from exc
    if not math.isfinite(value) or value < 0.1:
        raise ValueError(f"{name} invalid: {raw}")
    return value


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, str(default))
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} invalid: {raw}") from exc


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, f"{default}")
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} invalid: {raw}") from exc
    if not math.isfinite(value):
        raise ValueError(f"{name} invalid: {raw}")
    return value


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
    logger = get_logger("engine.layers.l2.seg_5B.s4_arrival_events.runner")
    _emit_validation(logger, manifest_fingerprint, validator_id, "fail", code, context)
    raise EngineFailure("F4", code, STATE, MODULE_NAME, context)


def _parse_utc_day_index(value: str) -> int:
    try:
        parsed = dt.date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Invalid utc_day: {value}") from exc
    epoch = dt.date(1970, 1, 1)
    return (parsed - epoch).days


def _rfc3339_to_us(value: str) -> int:
    value = value.strip()
    if value.endswith("Z"):
        value = value[:-1]
    parsed = dt.datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    epoch = dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)
    delta = parsed - epoch
    return int(delta.total_seconds() * 1_000_000)


def _uer_string(text: str) -> bytes:
    data = text.encode("utf-8")
    return struct.pack(">I", len(data)) + data


def _ser_u64_le(value: int) -> bytes:
    return struct.pack("<Q", int(value))


def _rng_prefix(
    domain_sep: str,
    family_id: str,
    manifest_fingerprint: str,
    parameter_hash: str,
    seed: int,
    scenario_id: str,
) -> bytes:
    return (
        _uer_string(domain_sep)
        + _uer_string(family_id)
        + _uer_string(manifest_fingerprint)
        + _uer_string(parameter_hash)
        + _ser_u64_le(seed)
        + _uer_string(scenario_id)
    )


def _derive_rng_seed(base_hasher: "hashlib._Hash", domain_key: str) -> tuple[int, int, int]:
    hasher = base_hasher.copy()
    hasher.update(_uer_string(domain_key))
    digest = hasher.digest()
    key = int.from_bytes(digest[0:8], "big", signed=False)
    counter_hi = int.from_bytes(digest[8:16], "big", signed=False)
    counter_lo = int.from_bytes(digest[16:24], "big", signed=False)
    return key, counter_hi, counter_lo


def _list_parquet_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    files = sorted(path for path in root.rglob("*.parquet") if path.is_file())
    if not files:
        raise InputResolutionError(f"No parquet files found under dataset path: {root}")
    return files


def _iter_parquet_batches(paths: Iterable[Path], columns: list[str], batch_size: int) -> Iterator[object]:
    for path in paths:
        if _HAVE_PYARROW:
            parquet = pq.ParquetFile(path)
            for batch in parquet.iter_batches(batch_size=batch_size, columns=columns):
                yield batch
        else:
            df = pl.read_parquet(path, columns=columns)
            yield df


def _count_parquet_rows(paths: Iterable[Path]) -> Optional[int]:
    if not paths:
        return None
    total = 0
    for path in paths:
        count_df = pl.scan_parquet(path).select(pl.len()).collect()
        total += int(count_df.item())
    return total


def _sum_parquet_counts(paths: Iterable[Path], column: str) -> Optional[int]:
    if not paths:
        return None
    total = 0
    for path in paths:
        count_df = pl.scan_parquet(path).select(pl.col(column).sum()).collect()
        value = count_df.item()
        if value is not None:
            total += int(value)
    return total


def _decode_alias_slice(blob: bytes, offset: int, length: int, endianness: str) -> tuple[np.ndarray, np.ndarray]:
    if offset < 0 or length <= 0 or offset + length > len(blob):
        raise ValueError("alias slice bounds invalid")
    view = memoryview(blob)[offset : offset + length]
    prefix = "<" if endianness == "little" else ">"
    header = struct.unpack_from(f"{prefix}IIII", view, 0)
    sites = int(header[0])
    prob_qbits = int(header[1])
    if sites <= 0:
        raise ValueError("alias slice empty")
    entry_count = sites * 2
    offset_bytes = 16
    values = struct.unpack_from(f"{prefix}{entry_count}I", view, offset_bytes)
    prob_q = np.array(values[0::2], dtype=np.uint64)
    alias = np.array(values[1::2], dtype=np.int64)
    q_scale = float(1 << prob_qbits)
    prob = prob_q.astype(np.float64) / q_scale
    return prob, alias


def _build_alias(weights: list[float]) -> tuple[list[float], list[int]]:
    if not weights:
        raise ValueError("empty weight vector")
    total = float(sum(weights))
    if not math.isfinite(total) or total <= 0.0:
        raise ValueError("invalid weight sum")
    if abs(total - 1.0) > 1e-6:
        weights = [value / total for value in weights]
    n = len(weights)
    scaled = [value * n for value in weights]
    small: list[int] = []
    large: list[int] = []
    for idx, value in enumerate(scaled):
        if value < 1.0:
            small.append(idx)
        else:
            large.append(idx)
    prob = [0.0] * n
    alias = [0] * n
    while small and large:
        s_idx = small.pop()
        l_idx = large.pop()
        prob[s_idx] = scaled[s_idx]
        alias[s_idx] = l_idx
        scaled[l_idx] = scaled[l_idx] - (1.0 - scaled[s_idx])
        if scaled[l_idx] < 1.0:
            small.append(l_idx)
        else:
            large.append(l_idx)
    for idx in small + large:
        prob[idx] = 1.0
        alias[idx] = idx
    return prob, alias


def _site_id_from_key(merchant_id: int, legal_country_iso: str, site_order: int) -> int:
    payload = f"{merchant_id}:{legal_country_iso}:{site_order}".encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    value = int(low64(digest))
    return value if value != 0 else 1


def _parse_tz_cache(cache_path: Path) -> tuple[list[str], np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    data = cache_path.read_bytes()
    if len(data) < 10:
        raise ValueError("tz cache too small")
    view = memoryview(data)
    if bytes(view[0:4]) != b"TZC1":
        raise ValueError("tz cache magic mismatch")
    pos = 4
    version = struct.unpack_from("<H", view, pos)[0]
    pos += 2
    if version != 1:
        raise ValueError("tz cache version mismatch")
    tzid_count = struct.unpack_from("<I", view, pos)[0]
    pos += 4
    tzid_list: list[str] = []
    index_start: list[int] = []
    index_count: list[int] = []
    transitions: list[int] = []
    offsets: list[int] = []
    for _ in range(int(tzid_count)):
        name_len = struct.unpack_from("<H", view, pos)[0]
        pos += 2
        tzid_bytes = bytes(view[pos : pos + name_len])
        pos += name_len
        tzid = tzid_bytes.decode("ascii")
        tzid_list.append(tzid)
        count = struct.unpack_from("<I", view, pos)[0]
        pos += 4
        index_start.append(len(transitions))
        index_count.append(int(count))
        for _ in range(int(count)):
            instant = struct.unpack_from("<q", view, pos)[0]
            pos += 8
            offset_minutes = struct.unpack_from("<i", view, pos)[0]
            pos += 4
            transitions.append(int(instant))
            offsets.append(int(offset_minutes))
    return (
        tzid_list,
        np.array(index_start, dtype=np.int64),
        np.array(index_count, dtype=np.int64),
        np.array(transitions, dtype=np.int64),
        np.array(offsets, dtype=np.int32),
    )


@dataclass(frozen=True)
class SiteAliasTables:
    table_offsets: np.ndarray
    table_lengths: np.ndarray
    prob: np.ndarray
    alias: np.ndarray
    site_ids: np.ndarray
    site_tzids: np.ndarray
    key_to_table: dict[tuple[int, int], int]


@dataclass(frozen=True)
class GroupAliasTables:
    table_offsets: np.ndarray
    table_lengths: np.ndarray
    prob: np.ndarray
    alias: np.ndarray
    tzids: np.ndarray
    key_to_table: dict[tuple[int, int], int]


@dataclass(frozen=True)
class EdgeAliasTables:
    table_offsets: np.ndarray
    table_lengths: np.ndarray
    prob: np.ndarray
    alias: np.ndarray
    edge_index: np.ndarray
    edge_weight: np.ndarray
    key_to_table: dict[int, int]


def _build_site_alias_tables(
    site_weights_df: pl.DataFrame,
    site_timezones_df: pl.DataFrame,
    tzid_to_idx: dict[str, int],
) -> SiteAliasTables:
    timezone_lookup: dict[tuple[int, str, int], str] = {}
    for row in site_timezones_df.iter_rows(named=True):
        merchant_id = int(row["merchant_id"])
        legal_country = str(row["legal_country_iso"])
        site_order = int(row["site_order"])
        tzid = str(row["tzid"])
        timezone_lookup[(merchant_id, legal_country, site_order)] = tzid

    rows_by_key: dict[tuple[int, int], list[tuple[int, int, float]]] = {}
    for row in site_weights_df.iter_rows(named=True):
        merchant_id = int(row["merchant_id"])
        legal_country = str(row["legal_country_iso"])
        site_order = int(row["site_order"])
        tzid = timezone_lookup.get((merchant_id, legal_country, site_order))
        if tzid is None:
            raise InputResolutionError(f"site_timezones missing tzid for merchant={merchant_id} site={site_order}")
        tzid_idx = tzid_to_idx.get(tzid)
        if tzid_idx is None:
            raise InputResolutionError(f"tzid missing from cache: {tzid}")
        site_id = _site_id_from_key(merchant_id, legal_country, site_order)
        p_weight = float(row["p_weight"])
        rows_by_key.setdefault((merchant_id, tzid_idx), []).append((site_id, tzid_idx, p_weight))

    key_to_table: dict[tuple[int, int], int] = {}
    table_offsets: list[int] = []
    table_lengths: list[int] = []
    prob_values: list[float] = []
    alias_values: list[int] = []
    site_ids: list[int] = []
    site_tzids: list[int] = []
    for key, rows in rows_by_key.items():
        weights = [row[2] for row in rows]
        prob, alias = _build_alias(weights)
        table_index = len(table_offsets)
        key_to_table[key] = table_index
        table_offsets.append(len(prob_values))
        table_lengths.append(len(weights))
        for idx, entry in enumerate(rows):
            site_ids.append(entry[0])
            site_tzids.append(entry[1])
            prob_values.append(prob[idx])
            alias_values.append(alias[idx])

    return SiteAliasTables(
        table_offsets=np.array(table_offsets, dtype=np.int64),
        table_lengths=np.array(table_lengths, dtype=np.int32),
        prob=np.array(prob_values, dtype=np.float64),
        alias=np.array(alias_values, dtype=np.int64),
        site_ids=np.array(site_ids, dtype=np.uint64),
        site_tzids=np.array(site_tzids, dtype=np.int32),
        key_to_table=key_to_table,
    )


def _build_group_alias_tables(
    group_df: pl.DataFrame,
    tzid_to_idx: dict[str, int],
) -> GroupAliasTables:
    key_to_rows: dict[tuple[int, int], list[tuple[int, float]]] = {}
    for row in group_df.iter_rows(named=True):
        merchant_id = int(row["merchant_id"])
        utc_day = str(row["utc_day"])
        tz_group_id = str(row["tz_group_id"])
        tzid_idx = tzid_to_idx.get(tz_group_id)
        if tzid_idx is None:
            raise InputResolutionError(f"tzid missing from cache: {tz_group_id}")
        p_group = float(row["p_group"])
        day_index = _parse_utc_day_index(utc_day)
        key_to_rows.setdefault((merchant_id, day_index), []).append((tzid_idx, p_group))

    key_to_table: dict[tuple[int, int], int] = {}
    table_offsets: list[int] = []
    table_lengths: list[int] = []
    prob_values: list[float] = []
    alias_values: list[int] = []
    tzids: list[int] = []
    for key, rows in key_to_rows.items():
        weights = [row[1] for row in rows]
        prob, alias = _build_alias(weights)
        table_index = len(table_offsets)
        key_to_table[key] = table_index
        table_offsets.append(len(prob_values))
        table_lengths.append(len(weights))
        for idx, entry in enumerate(rows):
            tzids.append(entry[0])
            prob_values.append(prob[idx])
            alias_values.append(alias[idx])

    return GroupAliasTables(
        table_offsets=np.array(table_offsets, dtype=np.int64),
        table_lengths=np.array(table_lengths, dtype=np.int32),
        prob=np.array(prob_values, dtype=np.float64),
        alias=np.array(alias_values, dtype=np.int64),
        tzids=np.array(tzids, dtype=np.int32),
        key_to_table=key_to_table,
    )


def _build_edge_alias_tables(
    edge_alias_index_df: pl.DataFrame,
    edge_catalogue_df: pl.DataFrame,
    blob_path: Path,
    endianness: str,
) -> tuple[EdgeAliasTables, np.ndarray, np.ndarray]:
    blob = blob_path.read_bytes()
    edge_catalogue_df = edge_catalogue_df.sort(["merchant_id", "edge_id"])
    edge_ids: list[int] = []
    edge_tzid_idx: list[int] = []
    edge_weights: list[float] = []
    edges_by_merchant: dict[int, list[int]] = {}
    for row in edge_catalogue_df.iter_rows(named=True):
        merchant_id = int(row["merchant_id"])
        edge_id = str(row["edge_id"])
        tzid_operational = int(row["tzid_operational_idx"])
        edge_weight = float(row.get("edge_weight") or 0.0)
        edge_index = len(edge_ids)
        edge_value = int(edge_id, 16)
        if edge_value == 0:
            raise InputResolutionError(f"edge_id cannot be 0 for merchant={merchant_id}")
        edge_ids.append(edge_value)
        edge_tzid_idx.append(tzid_operational)
        edge_weights.append(edge_weight)
        edges_by_merchant.setdefault(merchant_id, []).append(edge_index)

    key_to_table: dict[int, int] = {}
    table_offsets: list[int] = []
    table_lengths: list[int] = []
    prob_values: list[float] = []
    alias_values: list[int] = []
    edge_index_values: list[int] = []
    for row in edge_alias_index_df.iter_rows(named=True):
        if str(row.get("scope")) != "MERCHANT":
            continue
        merchant_id = int(row["merchant_id"])
        offset = int(row["blob_offset_bytes"])
        length = int(row["blob_length_bytes"])
        prob, alias = _decode_alias_slice(blob, offset, length, endianness)
        edge_indices = edges_by_merchant.get(merchant_id, [])
        if len(edge_indices) != len(prob):
            raise InputResolutionError(
                f"edge alias length mismatch for merchant {merchant_id}: {len(edge_indices)} vs {len(prob)}"
            )
        table_index = len(table_offsets)
        key_to_table[merchant_id] = table_index
        table_offsets.append(len(prob_values))
        table_lengths.append(len(prob))
        for idx, edge_idx in enumerate(edge_indices):
            edge_index_values.append(edge_idx)
            prob_values.append(float(prob[idx]))
            alias_values.append(int(alias[idx]))

    return (
        EdgeAliasTables(
            table_offsets=np.array(table_offsets, dtype=np.int64),
            table_lengths=np.array(table_lengths, dtype=np.int32),
            prob=np.array(prob_values, dtype=np.float64),
            alias=np.array(alias_values, dtype=np.int64),
            edge_index=np.array(edge_index_values, dtype=np.int32),
            edge_weight=np.array(edge_weights, dtype=np.float64),
            key_to_table=key_to_table,
        ),
        np.array(edge_ids, dtype=np.uint64),
        np.array(edge_tzid_idx, dtype=np.int32),
    )


def _build_non_top_edge_alias_tables(
    edge_alias_tables: EdgeAliasTables,
    edge_tzid_idx: np.ndarray,
    top_tzid_idx: set[int],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, dict[int, int]]:
    key_to_table: dict[int, int] = {}
    table_offsets: list[int] = []
    table_lengths: list[int] = []
    prob_values: list[float] = []
    alias_values: list[int] = []
    edge_index_values: list[int] = []

    for merchant_id, table_index in edge_alias_tables.key_to_table.items():
        offset = int(edge_alias_tables.table_offsets[table_index])
        length = int(edge_alias_tables.table_lengths[table_index])
        if length <= 0:
            continue
        non_top_edges: list[int] = []
        non_top_weights: list[float] = []
        for idx in range(length):
            edge_idx = int(edge_alias_tables.edge_index[offset + idx])
            tz_idx = int(edge_tzid_idx[edge_idx])
            if tz_idx in top_tzid_idx:
                continue
            weight = float(edge_alias_tables.edge_weight[edge_idx])
            if weight <= 0.0:
                continue
            non_top_edges.append(edge_idx)
            non_top_weights.append(weight)
        if not non_top_edges:
            continue
        prob, alias = _build_alias(non_top_weights)
        new_table_index = len(table_offsets)
        key_to_table[merchant_id] = new_table_index
        table_offsets.append(len(prob_values))
        table_lengths.append(len(non_top_edges))
        for idx, edge_idx in enumerate(non_top_edges):
            edge_index_values.append(edge_idx)
            prob_values.append(float(prob[idx]))
            alias_values.append(int(alias[idx]))

    return (
        np.array(table_offsets, dtype=np.int64),
        np.array(table_lengths, dtype=np.int32),
        np.array(prob_values, dtype=np.float64),
        np.array(alias_values, dtype=np.int64),
        np.array(edge_index_values, dtype=np.int32),
        key_to_table,
    )


def _split_by_arrival_count(counts: np.ndarray, max_arrivals: int) -> list[tuple[int, int]]:
    if counts.size == 0:
        return []
    prefix = np.zeros(counts.size + 1, dtype=np.int64)
    prefix[1:] = np.cumsum(counts.astype(np.int64))
    segments: list[tuple[int, int]] = []
    start = 0
    while start < counts.size:
        target = int(prefix[start] + max_arrivals)
        end = int(np.searchsorted(prefix, target, side="right") - 1)
        if end <= start:
            end = start + 1
        segments.append((start, end))
        start = end
    return segments


def _u128_gt(a_hi: int, a_lo: int, b_hi: int, b_lo: int) -> bool:
    if a_hi > b_hi:
        return True
    if a_hi == b_hi and a_lo > b_lo:
        return True
    return False


def _resolve_git_hash(repo_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return "unknown"
    return result.stdout.strip()


def _atomic_publish_file(tmp_path: Path, final_path: Path, logger, label: str) -> None:
    if final_path.exists():
        existing_hash = sha256_file(final_path).sha256_hex
        tmp_hash = sha256_file(tmp_path).sha256_hex
        if existing_hash != tmp_hash:
            raise EngineFailure(
                "F4",
                "5B.S4.IO_WRITE_CONFLICT",
                STATE,
                MODULE_NAME,
                {"detail": "output differs from existing", "path": str(final_path), "label": label},
            )
        tmp_path.unlink(missing_ok=True)
        try:
            tmp_path.parent.rmdir()
        except OSError:
            pass
        logger.info("S4: output already exists and is identical; skipping publish (%s).", label)
        return
    final_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path.replace(final_path)
    logger.info("S4: published %s (%s).", label, final_path)


def _atomic_publish_dir(tmp_root: Path, final_root: Path, logger, label: str) -> None:
    if final_root.exists():
        logger.info("S4: %s already exists at %s; skipping publish", label, final_root)
        return
    final_root.parent.mkdir(parents=True, exist_ok=True)
    tmp_root.replace(final_root)
    logger.info("S4: published %s (%s).", label, final_root)


def _ensure_rng_audit(audit_path: Path, payload: dict, logger) -> None:
    if audit_path.exists():
        with audit_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                record = json.loads(line)
                if (
                    record.get("run_id") == payload.get("run_id")
                    and record.get("seed") == payload.get("seed")
                    and record.get("parameter_hash") == payload.get("parameter_hash")
                    and record.get("manifest_fingerprint") == payload.get("manifest_fingerprint")
                ):
                    logger.info("S4: rng_audit_log already contains run_id=%s", payload.get("run_id"))
                    return
        with audit_path.open("a", encoding="utf-8") as handle:
            handle.write(_json_dumps(payload))
            handle.write("\n")
        logger.info("S4: appended rng_audit_log entry for run_id=%s", payload.get("run_id"))
        return
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(_json_dumps(payload) + "\n", encoding="utf-8")
    logger.info("S4: wrote rng_audit_log entry for run_id=%s", payload.get("run_id"))


def _write_trace_row(
    handle,
    run_id: str,
    seed: int,
    module: str,
    substream_label: str,
    before_hi: int,
    before_lo: int,
    after_hi: int,
    after_lo: int,
    draws_total: int,
    blocks_total: int,
    events_total: int,
) -> None:
    payload = {
        "ts_utc": utc_now_rfc3339_micro(),
        "run_id": run_id,
        "seed": seed,
        "module": module,
        "substream_label": substream_label,
        "rng_counter_before_lo": int(before_lo),
        "rng_counter_before_hi": int(before_hi),
        "rng_counter_after_lo": int(after_lo),
        "rng_counter_after_hi": int(after_hi),
        "draws_total": int(draws_total),
        "blocks_total": int(blocks_total),
        "events_total": int(events_total),
    }
    handle.write(_json_dumps(payload))
    handle.write("\n")

def _schema_for_payload(schema_pack: dict, schema_layer1: dict, schema_layer2: dict, anchor: str) -> dict:
    schema = _schema_from_pack(schema_pack, anchor)
    _inline_external_refs(schema, schema_layer1, "schemas.layer1.yaml#")
    _inline_external_refs(schema, schema_layer2, "schemas.layer2.yaml#")
    return schema


def _validate_payload(
    schema_pack: dict,
    schema_layer1: dict,
    schema_layer2: dict,
    anchor: str,
    payload: object,
    manifest_fingerprint: str,
    validator_id: str,
    error_code: str,
    label: str,
) -> None:
    schema = _schema_for_payload(schema_pack, schema_layer1, schema_layer2, anchor)
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    if errors:
        _abort(
            error_code,
            validator_id,
            "payload_schema_invalid",
            {"detail": str(errors[0]), "anchor": anchor, "label": label},
            manifest_fingerprint,
        )


def _resolve_sealed_row(
    sealed_by_id: dict[str, dict],
    artifact_id: str,
    manifest_fingerprint: str,
    read_scopes: set[str],
    required: bool,
    error_code: str,
) -> Optional[dict]:
    row = sealed_by_id.get(artifact_id)
    if not row or row.get("status") == "IGNORED":
        if required:
            _abort(
                error_code,
                "V-04",
                "required_input_missing",
                {"artifact_id": artifact_id},
                manifest_fingerprint,
            )
        return None
    if required and row.get("status") != "REQUIRED":
        _abort(
            error_code,
            "V-04",
            "required_input_unusable",
            {"artifact_id": artifact_id, "status": row.get("status")},
            manifest_fingerprint,
        )
    if row.get("read_scope") not in read_scopes:
        _abort(
            error_code,
            "V-04",
            "read_scope_invalid",
            {"artifact_id": artifact_id, "read_scope": row.get("read_scope")},
            manifest_fingerprint,
        )
    return row


def _format_rfc3339_us(values: np.ndarray) -> np.ndarray:
    values = values.astype(np.int64, copy=False)
    out = np.empty(values.shape, dtype=object)
    mask = values >= 0
    if mask.any():
        out[mask] = np.datetime_as_string(values[mask].astype("datetime64[us]"), unit="us", timezone="UTC")
    out[~mask] = None
    return out


def _format_local_wall_us(values: np.ndarray) -> np.ndarray:
    """Render local wall-clock timestamps without UTC marker semantics."""
    values = values.astype(np.int64, copy=False)
    out = np.empty(values.shape, dtype=object)
    mask = values >= 0
    if mask.any():
        out[mask] = np.datetime_as_string(values[mask].astype("datetime64[us]"), unit="us")
    out[~mask] = None
    return out


def _map_indices(values: np.ndarray, lookup: np.ndarray) -> np.ndarray:
    out = np.empty(values.shape, dtype=object)
    mask = values >= 0
    if mask.any():
        out[mask] = lookup[values[mask]]
    out[~mask] = None
    return out


def _schema_items(schema_pack: dict, schema_layer1: dict, schema_layer2: dict, anchor: str) -> dict:
    schema = _schema_for_payload(schema_pack, schema_layer1, schema_layer2, anchor)
    items = schema.get("items") or {}
    wrapped = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": schema.get("$id", ""),
        "$defs": schema.get("$defs", {}),
    }
    wrapped.update(items)
    return normalize_nullable_schema(wrapped)


def _validate_array_rows(
    rows: Iterable[dict],
    schema_pack: dict,
    schema_layer1: dict,
    schema_layer2: dict,
    anchor: str,
    manifest_fingerprint: str,
    label: str,
    total_rows: Optional[int] = None,
    limit: Optional[int] = None,
) -> None:
    items_schema = _schema_items(schema_pack, schema_layer1, schema_layer2, anchor)
    validator = Draft202012Validator(items_schema)
    checked = 0
    for row in rows:
        errors = list(validator.iter_errors(row))
        if errors:
            _abort(
                "5B.S4.SCHEMA_INVALID",
                "V-08",
                "output_schema_invalid",
                {"detail": str(errors[0]), "label": label, "row_index": checked},
                manifest_fingerprint,
            )
        checked += 1
        if limit is not None and checked >= limit:
            break
    if total_rows is not None:
        logger = get_logger("engine.layers.l2.seg_5B.s4_arrival_events.runner")
        logger.info("S4: validated rows=%d/%s for %s", checked, total_rows, label)


def _iter_jsonl_paths(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*.jsonl") if path.is_file())


def _iter_jsonl_rows(paths: Iterable[Path], label: str) -> Iterator[dict]:
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                payload = line.strip()
                if not payload:
                    continue
                try:
                    yield json.loads(payload)
                except json.JSONDecodeError as exc:
                    raise InputResolutionError(f"{label}: invalid jsonl {path}") from exc


def _trace_has_substream(trace_path: Path, module: str, substream_label: str) -> bool:
    with trace_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            payload = line.strip()
            if not payload:
                continue
            try:
                record = json.loads(payload)
            except json.JSONDecodeError:
                continue
            if record.get("module") == module and record.get("substream_label") == substream_label:
                return True
    return False


def _event_root_from_path(path: Path) -> Path:
    if "*" in path.name:
        return path.parent
    return path.parent


def _event_file_from_root(root: Path, index: int) -> Path:
    return root / f"part-{index:06d}.jsonl"


def run_s4(config: EngineConfig, run_id: Optional[str] = None) -> S4Result:
    logger = get_logger("engine.layers.l2.seg_5B.s4_arrival_events.runner")
    started_monotonic = time.monotonic()
    started_utc = utc_now_rfc3339_micro()
    timer = _StepTimer(logger)

    output_validate_full = _env_flag("ENGINE_5B_S4_VALIDATE_FULL")
    output_sample_rows_env = os.environ.get("ENGINE_5B_S4_VALIDATE_SAMPLE_ROWS", "2000")
    try:
        output_sample_rows = max(int(output_sample_rows_env), 0)
    except ValueError:
        output_sample_rows = 2000
    output_validation_mode = "full" if output_validate_full else "fast_sampled"
    progress_interval_seconds = _env_progress_interval_seconds("ENGINE_5B_S4_PROGRESS_INTERVAL_SEC")
    strict_ordering = _env_flag("ENGINE_5B_S4_STRICT_ORDERING")
    include_lambda = _env_flag("ENGINE_5B_S4_INCLUDE_LAMBDA")
    require_numba = _env_flag("ENGINE_5B_S4_REQUIRE_NUMBA", "1")
    enable_rng_events = _env_flag("ENGINE_5B_S4_RNG_EVENTS")
    validate_events_full = _env_flag("ENGINE_5B_S4_VALIDATE_EVENTS_FULL")
    validate_events_limit_env = os.environ.get("ENGINE_5B_S4_VALIDATE_EVENTS_LIMIT", "1000")
    try:
        validate_events_limit = max(int(validate_events_limit_env), 0)
    except ValueError:
        validate_events_limit = 1000
    event_buffer_env = os.environ.get("ENGINE_5B_S4_EVENT_BUFFER", "5000")
    try:
        event_buffer_size = max(int(event_buffer_env), 1)
    except ValueError:
        event_buffer_size = 5000
    batch_rows_env = os.environ.get("ENGINE_5B_S4_BATCH_ROWS", "200000")
    try:
        batch_rows = max(int(batch_rows_env), 1)
    except ValueError:
        batch_rows = 200000
    max_arrivals_env = os.environ.get("ENGINE_5B_S4_MAX_ARRIVALS_CHUNK", "250000")
    try:
        max_arrivals_chunk = max(int(max_arrivals_env), 1000)
    except ValueError:
        max_arrivals_chunk = 250000
    tz_temper_enabled_cfg = _env_flag("ENGINE_5B_S4_TZ_TEMPER_ENABLE")
    tz_temper_topk_cfg = max(_env_int("ENGINE_5B_S4_TZ_TEMPER_TOPK", 10), 1)
    tz_temper_redirect_p_cfg = _env_float("ENGINE_5B_S4_TZ_TEMPER_REDIRECT_P", 0.0)
    if tz_temper_redirect_p_cfg < 0.0 or tz_temper_redirect_p_cfg > 1.0:
        raise ValueError("ENGINE_5B_S4_TZ_TEMPER_REDIRECT_P must be in [0,1]")

    current_phase = "init"
    status = "FAIL"
    error_code: Optional[str] = None
    error_class: Optional[str] = None
    error_context: Optional[dict] = None
    first_failure_phase: Optional[str] = None

    run_paths: Optional[RunPaths] = None
    run_report_path: Optional[Path] = None
    parameter_hash: Optional[str] = None
    manifest_fingerprint: Optional[str] = None
    seed = 0
    scenario_set: list[str] = []

    dictionary_5b: dict = {}
    scenario_details: dict[str, dict[str, object]] = {}
    scenario_count_succeeded = 0

    total_rows_written = 0
    total_arrivals = 0
    total_virtual = 0
    total_bucket_rows = 0

    rng_draws_total = {"arrival_time_jitter": 0, "arrival_site_pick": 0, "arrival_edge_pick": 0}
    rng_blocks_total = {"arrival_time_jitter": 0, "arrival_site_pick": 0, "arrival_edge_pick": 0}
    rng_events_total = {"arrival_time_jitter": 0, "arrival_site_pick": 0, "arrival_edge_pick": 0}

    output_paths: list[Path] = []
    tz_temper_effective = False
    tz_temper_topk_names: list[str] = []
    tz_temper_eligible_merchants = 0

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
        seed = int(receipt.get("seed") or 0)

        run_paths = RunPaths(config.runs_root, run_id)
        run_log_path = run_paths.run_root / f"run_log_{run_id}.log"
        add_file_handler(run_log_path)
        logger.info("S4: run log initialized at %s", run_log_path)

        if require_numba and not NUMBA_AVAILABLE:
            raise EngineFailure(
                "F4",
                "5B.S4.NUMBA_REQUIRED",
                STATE,
                MODULE_NAME,
                {"detail": "numba not available"},
            )

        source = ContractSource(config.contracts_root, config.contracts_layout)
        dict_5b_path, dictionary_5b = load_dataset_dictionary(source, "5B")
        schema_5b_path, schema_5b = load_schema_pack(source, "5B", "5B")
        schema_layer2_path, schema_layer2 = load_schema_pack(source, "5A", "layer2")
        schema_layer1_path, schema_layer1 = load_schema_pack(source, "1A", "layer1")
        schema_2b_path, schema_2b = load_schema_pack(source, "2B", "2B")
        schema_3b_path, schema_3b = load_schema_pack(source, "3B", "3B")

        logger.info(
            "Contracts layout=%s root=%s dictionary=%s schemas=%s,%s,%s,%s,%s",
            config.contracts_layout,
            str(config.contracts_root),
            str(dict_5b_path),
            str(schema_5b_path),
            str(schema_layer2_path),
            str(schema_layer1_path),
            str(schema_2b_path),
            str(schema_3b_path),
        )

        logger.info(
            "S4: objective=expand bucket counts into arrival events (gate S0+S1+S3+policies; output arrival_events_5B + rng logs)"
        )
        logger.info(
            "S4: rng_event logging=%s (set ENGINE_5B_S4_RNG_EVENTS=1 to enable)",
            "on" if enable_rng_events else "off",
        )
        logger.info("S4: progress cadence interval=%.2fs", progress_interval_seconds)
        logger.info(
            "S4: tz concentration tempering config enabled=%s topk=%d redirect_p=%.4f",
            str(tz_temper_enabled_cfg).lower(),
            tz_temper_topk_cfg,
            tz_temper_redirect_p_cfg,
        )
        if include_lambda:
            logger.info("S4: lambda_realised inclusion enabled (may increase memory)")
        if not _HAVE_PYARROW:
            logger.warning("S4: pyarrow not available; batch reads will load full files")

        tokens = {
            "seed": str(seed),
            "parameter_hash": str(parameter_hash),
            "manifest_fingerprint": str(manifest_fingerprint),
            "run_id": str(run_id),
        }

        current_phase = "s0_gate"
        receipt_entry = find_dataset_entry(dictionary_5b, "s0_gate_receipt_5B").entry
        sealed_entry = find_dataset_entry(dictionary_5b, "sealed_inputs_5B").entry
        receipt_path = _resolve_dataset_path(receipt_entry, run_paths, config.external_roots, tokens)
        sealed_inputs_path = _resolve_dataset_path(sealed_entry, run_paths, config.external_roots, tokens)
        receipt_payload = _load_json(receipt_path)
        sealed_inputs = _load_json(sealed_inputs_path)

        _validate_payload(
            schema_5b,
            schema_layer1,
            schema_layer2,
            "validation/s0_gate_receipt_5B",
            receipt_payload,
            str(manifest_fingerprint),
            "V-03",
            "5B.S4.S0_GATE_INVALID",
            "s0_gate_receipt_5B",
        )
        _validate_payload(
            schema_5b,
            schema_layer1,
            schema_layer2,
            "validation/sealed_inputs_5B",
            sealed_inputs,
            str(manifest_fingerprint),
            "V-03",
            "5B.S4.S0_GATE_INVALID",
            "sealed_inputs_5B",
        )

        if receipt_payload.get("parameter_hash") != parameter_hash:
            _abort(
                "5B.S4.S0_GATE_INVALID",
                "V-03",
                "parameter_hash_mismatch",
                {"expected": parameter_hash, "actual": receipt_payload.get("parameter_hash")},
                manifest_fingerprint,
            )
        if receipt_payload.get("manifest_fingerprint") != manifest_fingerprint:
            _abort(
                "5B.S4.S0_GATE_INVALID",
                "V-03",
                "manifest_fingerprint_mismatch",
                {"expected": manifest_fingerprint, "actual": receipt_payload.get("manifest_fingerprint")},
                manifest_fingerprint,
            )

        scenario_set_payload = receipt_payload.get("scenario_set")
        if not isinstance(scenario_set_payload, list) or not scenario_set_payload:
            _abort(
                "5B.S4.S0_GATE_INVALID",
                "V-03",
                "scenario_set_missing",
                {"scenario_set": scenario_set_payload},
                manifest_fingerprint,
            )
        scenario_set = sorted({str(item) for item in scenario_set_payload if item})
        if not scenario_set:
            _abort(
                "5B.S4.S0_GATE_INVALID",
                "V-03",
                "scenario_set_empty",
                {"scenario_set": scenario_set_payload},
                manifest_fingerprint,
            )

        upstream = receipt_payload.get("upstream_segments") or {}
        for segment_id in ("1A", "1B", "2A", "2B", "3A", "3B", "5A"):
            status_value = None
            if isinstance(upstream, dict):
                status_value = (upstream.get(segment_id) or {}).get("status")
            if status_value != "PASS":
                _abort(
                    "5B.S4.UPSTREAM_NOT_PASS",
                    "V-03",
                    "upstream_not_pass",
                    {"segment_id": segment_id, "status": status_value},
                    manifest_fingerprint,
                )

        spec_version = str(receipt_payload.get("spec_version") or "")
        if not spec_version:
            _abort(
                "5B.S4.S0_GATE_INVALID",
                "V-03",
                "spec_version_missing",
                {"receipt_path": str(receipt_path)},
                manifest_fingerprint,
            )

        if not isinstance(sealed_inputs, list):
            _abort(
                "5B.S4.S0_GATE_INVALID",
                "V-03",
                "sealed_inputs_invalid",
                {"detail": "sealed_inputs_5B payload is not a list"},
                manifest_fingerprint,
            )
        sealed_sorted = sorted(
            sealed_inputs,
            key=lambda row: (row.get("owner_segment"), row.get("artifact_id"), row.get("role")),
        )
        sealed_by_id: dict[str, dict] = {}
        seen_keys: set[tuple[str, str]] = set()
        for row in sealed_sorted:
            key = (str(row.get("owner_segment") or ""), str(row.get("artifact_id") or ""))
            if key in seen_keys:
                _abort(
                    "5B.S4.S0_GATE_INVALID",
                    "V-03",
                    "sealed_inputs_duplicate_key",
                    {"owner_segment": key[0], "artifact_id": key[1]},
                    manifest_fingerprint,
                )
            seen_keys.add(key)
            if key[1]:
                sealed_by_id[key[1]] = row

        sealed_digest = _sealed_inputs_digest(sealed_sorted)
        if receipt_payload.get("sealed_inputs_digest") != sealed_digest:
            _abort(
                "5B.S4.S0_GATE_INVALID",
                "V-03",
                "sealed_inputs_digest_mismatch",
                {"expected": receipt_payload.get("sealed_inputs_digest"), "actual": sealed_digest},
                manifest_fingerprint,
            )

        read_scopes_any = {"ROW_LEVEL", "METADATA_ONLY"}
        _resolve_sealed_row(
            sealed_by_id,
            "arrival_time_placement_policy_5B",
            manifest_fingerprint,
            {"ROW_LEVEL"},
            True,
            "5B.S4.TIME_POLICY_INVALID",
        )
        _resolve_sealed_row(
            sealed_by_id,
            "arrival_routing_policy_5B",
            manifest_fingerprint,
            {"ROW_LEVEL"},
            True,
            "5B.S4.ROUTING_POLICY_INVALID",
        )
        _resolve_sealed_row(
            sealed_by_id,
            "arrival_rng_policy_5B",
            manifest_fingerprint,
            {"ROW_LEVEL"},
            True,
            "5B.S4.RNG_POLICY_INVALID",
        )
        _resolve_sealed_row(
            sealed_by_id,
            "route_rng_policy_v1",
            manifest_fingerprint,
            {"ROW_LEVEL"},
            True,
            "5B.S4.RNG_POLICY_INVALID",
        )
        _resolve_sealed_row(
            sealed_by_id,
            "alias_layout_policy_v1",
            manifest_fingerprint,
            {"ROW_LEVEL"},
            True,
            "5B.S4.RNG_POLICY_INVALID",
        )
        _resolve_sealed_row(
            sealed_by_id,
            "virtual_routing_policy_3B",
            manifest_fingerprint,
            read_scopes_any,
            True,
            "5B.S4.ROUTING_POLICY_INVALID",
        )

        for artifact_id in (
            "site_timezones",
            "s1_site_weights",
            "s2_alias_index",
            "s2_alias_blob",
            "s4_group_weights",
            "virtual_classification_3B",
            "edge_catalogue_3B",
            "edge_alias_index_3B",
            "edge_alias_blob_3B",
            "edge_universe_hash_3B",
        ):
            _resolve_sealed_row(
                sealed_by_id,
                artifact_id,
                manifest_fingerprint,
                read_scopes_any,
                True,
                "5B.S4.INPUTS_MISSING",
            )

        _resolve_sealed_row(
            sealed_by_id,
            "tz_timetable_cache",
            manifest_fingerprint,
            read_scopes_any,
            False,
            "5B.S4.INPUTS_MISSING",
        )
        _resolve_sealed_row(
            sealed_by_id,
            "virtual_settlement_3B",
            manifest_fingerprint,
            read_scopes_any,
            False,
            "5B.S4.INPUTS_MISSING",
        )

        current_phase = "config_load"
        time_policy_entry = find_dataset_entry(dictionary_5b, "arrival_time_placement_policy_5B").entry
        routing_policy_entry = find_dataset_entry(dictionary_5b, "arrival_routing_policy_5B").entry
        rng_policy_entry = find_dataset_entry(dictionary_5b, "arrival_rng_policy_5B").entry
        route_rng_entry = find_dataset_entry(dictionary_5b, "route_rng_policy_v1").entry
        alias_policy_entry = find_dataset_entry(dictionary_5b, "alias_layout_policy_v1").entry
        virtual_policy_entry = find_dataset_entry(dictionary_5b, "virtual_routing_policy_3B").entry

        time_policy = _load_yaml(_resolve_dataset_path(time_policy_entry, run_paths, config.external_roots, tokens))
        routing_policy = _load_yaml(
            _resolve_dataset_path(routing_policy_entry, run_paths, config.external_roots, tokens)
        )
        rng_policy = _load_yaml(_resolve_dataset_path(rng_policy_entry, run_paths, config.external_roots, tokens))
        route_rng_policy = _load_json(
            _resolve_dataset_path(route_rng_entry, run_paths, config.external_roots, tokens)
        )
        alias_layout_policy = _load_json(
            _resolve_dataset_path(alias_policy_entry, run_paths, config.external_roots, tokens)
        )
        virtual_routing_policy = _load_json(
            _resolve_dataset_path(virtual_policy_entry, run_paths, config.external_roots, tokens)
        )

        _validate_payload(
            schema_5b,
            schema_layer1,
            schema_layer2,
            "config/arrival_time_placement_policy_5B",
            time_policy,
            manifest_fingerprint,
            "V-05",
            "5B.S4.TIME_POLICY_INVALID",
            "arrival_time_placement_policy_5B",
        )
        _validate_payload(
            schema_5b,
            schema_layer1,
            schema_layer2,
            "config/arrival_routing_policy_5B",
            routing_policy,
            manifest_fingerprint,
            "V-05",
            "5B.S4.ROUTING_POLICY_INVALID",
            "arrival_routing_policy_5B",
        )
        _validate_payload(
            schema_5b,
            schema_layer1,
            schema_layer2,
            "config/arrival_rng_policy_5B",
            rng_policy,
            manifest_fingerprint,
            "V-05",
            "5B.S4.RNG_POLICY_INVALID",
            "arrival_rng_policy_5B",
        )
        _validate_payload(
            schema_2b,
            schema_layer1,
            schema_layer2,
            "policy/route_rng_policy_v1",
            route_rng_policy,
            manifest_fingerprint,
            "V-05",
            "5B.S4.RNG_POLICY_INVALID",
            "route_rng_policy_v1",
        )
        _validate_payload(
            schema_2b,
            schema_layer1,
            schema_layer2,
            "policy/alias_layout_policy_v1",
            alias_layout_policy,
            manifest_fingerprint,
            "V-05",
            "5B.S4.RNG_POLICY_INVALID",
            "alias_layout_policy_v1",
        )
        _validate_payload(
            schema_3b,
            schema_layer1,
            schema_layer2,
            "egress/virtual_routing_policy_3B",
            virtual_routing_policy,
            manifest_fingerprint,
            "V-05",
            "5B.S4.ROUTING_POLICY_INVALID",
            "virtual_routing_policy_3B",
        )

        guardrails = time_policy.get("guardrails") or {}
        max_arrivals_per_bucket = int(guardrails.get("max_arrivals_per_bucket") or 0)
        if max_arrivals_per_bucket <= 0:
            max_arrivals_per_bucket = 50_000

        p_virtual_hybrid = float((routing_policy.get("hybrid_policy") or {}).get("p_virtual_hybrid") or 0.0)

        rng_derivation = rng_policy.get("derivation") or {}
        domain_sep = str(rng_derivation.get("domain_sep") or "")
        if not domain_sep:
            _abort(
                "5B.S4.RNG_POLICY_INVALID",
                "V-05",
                "rng_domain_sep_missing",
                {},
                manifest_fingerprint,
            )
        families = {str(item.get("family_id")): item for item in (rng_policy.get("families") or [])}
        if "S4.arrival_time_jitter.v1" not in families:
            _abort(
                "5B.S4.RNG_POLICY_INVALID",
                "V-05",
                "rng_family_missing",
                {"family_id": "S4.arrival_time_jitter.v1"},
                manifest_fingerprint,
            )
        if "S4.arrival_site_pick.v1" not in families:
            _abort(
                "5B.S4.RNG_POLICY_INVALID",
                "V-05",
                "rng_family_missing",
                {"family_id": "S4.arrival_site_pick.v1"},
                manifest_fingerprint,
            )
        if "S4.arrival_edge_pick.v1" not in families:
            _abort(
                "5B.S4.RNG_POLICY_INVALID",
                "V-05",
                "rng_family_missing",
                {"family_id": "S4.arrival_edge_pick.v1"},
                manifest_fingerprint,
            )

        current_phase = "load_tz_cache"
        tz_cache_entry = find_dataset_entry(dictionary_5b, "tz_timetable_cache").entry
        tz_cache_root = _resolve_dataset_path(tz_cache_entry, run_paths, config.external_roots, tokens)
        tz_cache_files = list(tz_cache_root.rglob("*.bin")) if tz_cache_root.exists() else []
        if not tz_cache_files:
            raise InputResolutionError(f"tz_timetable_cache missing .bin under {tz_cache_root}")
        tz_cache_path = tz_cache_root / "tz_cache_v1.bin" if (tz_cache_root / "tz_cache_v1.bin").exists() else tz_cache_files[0]
        tzid_list, tz_index_start, tz_index_count, tz_transitions_utc, tz_offsets_minutes = _parse_tz_cache(
            tz_cache_path
        )
        tzid_to_idx = {tzid: idx for idx, tzid in enumerate(tzid_list)}
        tzid_lookup = np.array(tzid_list, dtype=object)
        logger.info("S4: tz cache loaded (tzids=%d, file=%s)", len(tzid_list), tz_cache_path)

        current_phase = "load_inputs"
        site_timezones_entry = find_dataset_entry(dictionary_5b, "site_timezones").entry
        site_weights_entry = find_dataset_entry(dictionary_5b, "s1_site_weights").entry
        group_weights_entry = find_dataset_entry(dictionary_5b, "s4_group_weights").entry
        edge_catalogue_entry = find_dataset_entry(dictionary_5b, "edge_catalogue_3B").entry
        edge_alias_index_entry = find_dataset_entry(dictionary_5b, "edge_alias_index_3B").entry
        edge_alias_blob_entry = find_dataset_entry(dictionary_5b, "edge_alias_blob_3B").entry
        edge_universe_entry = find_dataset_entry(dictionary_5b, "edge_universe_hash_3B").entry
        virtual_class_entry = find_dataset_entry(dictionary_5b, "virtual_classification_3B").entry

        site_timezones_path = _resolve_dataset_path(site_timezones_entry, run_paths, config.external_roots, tokens)
        site_weights_path = _resolve_dataset_path(site_weights_entry, run_paths, config.external_roots, tokens)
        group_weights_path = _resolve_dataset_path(group_weights_entry, run_paths, config.external_roots, tokens)
        edge_catalogue_path = _resolve_dataset_path(edge_catalogue_entry, run_paths, config.external_roots, tokens)
        edge_alias_index_path = _resolve_dataset_path(edge_alias_index_entry, run_paths, config.external_roots, tokens)
        edge_alias_blob_path = _resolve_dataset_path(edge_alias_blob_entry, run_paths, config.external_roots, tokens)
        edge_universe_path = _resolve_dataset_path(edge_universe_entry, run_paths, config.external_roots, tokens)
        virtual_class_path = _resolve_dataset_path(virtual_class_entry, run_paths, config.external_roots, tokens)

        virtual_settlement_entry = find_dataset_entry(dictionary_5b, "virtual_settlement_3B").entry
        virtual_settlement_path = _resolve_dataset_path(
            virtual_settlement_entry, run_paths, config.external_roots, tokens
        )
        virtual_settlement_exists = virtual_settlement_path.exists()

        site_timezones_df = pl.read_parquet(_list_parquet_files(site_timezones_path))
        site_weights_df = pl.read_parquet(_list_parquet_files(site_weights_path))
        group_weights_df = pl.read_parquet(_list_parquet_files(group_weights_path))
        edge_catalogue_df = pl.read_parquet(_list_parquet_files(edge_catalogue_path))
        edge_alias_index_df = pl.read_parquet(_list_parquet_files(edge_alias_index_path))
        virtual_class_df = pl.read_parquet(_list_parquet_files(virtual_class_path))

        edge_universe_payload = _load_json(edge_universe_path)
        _validate_payload(
            schema_3b,
            schema_layer1,
            schema_layer2,
            "validation/edge_universe_hash_3B",
            edge_universe_payload,
            manifest_fingerprint,
            "V-05",
            "5B.S4.INPUTS_MISSING",
            "edge_universe_hash_3B",
        )
        routing_universe_hash = str(edge_universe_payload.get("universe_hash") or "")

        virtual_settlement_df = None
        if virtual_settlement_exists:
            try:
                virtual_settlement_df = pl.read_parquet(_list_parquet_files(virtual_settlement_path))
            except Exception:
                virtual_settlement_df = None
        if virtual_settlement_df is None:
            logger.warning("S4: virtual_settlement_3B missing; settlement timezone will be null")

        current_phase = "build_alias_tables"
        site_alias_tables = _build_site_alias_tables(site_weights_df, site_timezones_df, tzid_to_idx)
        group_alias_tables = _build_group_alias_tables(group_weights_df, tzid_to_idx)

        alias_layout = alias_layout_policy
        endianness = str(alias_layout.get("endianness") or "little")
        edge_catalogue_df = edge_catalogue_df.with_columns(
            pl.col("tzid_operational").map_elements(
                lambda v: tzid_to_idx.get(str(v), -1), return_dtype=pl.Int32
            ).alias(
                "tzid_operational_idx"
            )
        )
        edge_alias_tables, edge_ids, edge_tzid_idx = _build_edge_alias_tables(
            edge_alias_index_df,
            edge_catalogue_df,
            edge_alias_blob_path,
            endianness,
        )

        current_phase = "merchant_index"
        counts_entry = find_dataset_entry(dictionary_5b, "s3_bucket_counts_5B").entry
        merchant_ids_set: set[int] = set()
        for scenario_id in scenario_set:
            counts_path = _resolve_dataset_path(
                counts_entry,
                run_paths,
                config.external_roots,
                {"seed": str(seed), "manifest_fingerprint": str(manifest_fingerprint), "scenario_id": str(scenario_id)},
            )
            merchant_df = (
                pl.scan_parquet(_list_parquet_files(counts_path))
                .select(pl.col("merchant_id").unique())
                .collect()
            )
            merchant_ids_set.update(int(mid) for mid in merchant_df.get_column("merchant_id").to_list())

        merchant_ids = sorted(merchant_ids_set)
        merchant_index = {merchant_id: idx for idx, merchant_id in enumerate(merchant_ids)}

        virtual_mode_map = {}
        for row in virtual_class_df.iter_rows(named=True):
            merchant_id = int(row["merchant_id"])
            mode = str(row.get("virtual_mode") or "")
            if mode == "NON_VIRTUAL":
                mode_value = 0
            elif mode == "HYBRID":
                mode_value = 1
            elif mode == "VIRTUAL_ONLY":
                mode_value = 2
            else:
                mode_value = 0
            virtual_mode_map[merchant_id] = mode_value

        settlement_map: dict[int, int] = {}
        if virtual_settlement_df is not None:
            for row in virtual_settlement_df.iter_rows(named=True):
                merchant_id = int(row["merchant_id"])
                tzid_settlement = str(row.get("tzid_settlement") or "")
                settlement_map[merchant_id] = tzid_to_idx.get(tzid_settlement, -1)

        merchant_virtual_mode = np.full(len(merchant_ids), 0, dtype=np.int32)
        merchant_settlement_tzid = np.full(len(merchant_ids), -1, dtype=np.int32)
        for merchant_id, idx in merchant_index.items():
            merchant_virtual_mode[idx] = int(virtual_mode_map.get(merchant_id, 0))
            merchant_settlement_tzid[idx] = int(settlement_map.get(merchant_id, -1))

        site_map_start = np.zeros(len(merchant_ids), dtype=np.int64)
        site_map_count = np.zeros(len(merchant_ids), dtype=np.int32)
        site_map_tzid: list[int] = []
        site_map_table: list[int] = []
        site_map_by_merchant: dict[int, list[tuple[int, int]]] = {}
        for (merchant_id, tzid_idx), table_idx in site_alias_tables.key_to_table.items():
            site_map_by_merchant.setdefault(merchant_id, []).append((tzid_idx, table_idx))
        for merchant_id, idx in merchant_index.items():
            rows = sorted(site_map_by_merchant.get(merchant_id, []), key=lambda item: item[0])
            site_map_start[idx] = len(site_map_tzid)
            site_map_count[idx] = len(rows)
            for tzid_idx, table_idx in rows:
                site_map_tzid.append(int(tzid_idx))
                site_map_table.append(int(table_idx))

        site_map_tzid_arr = np.array(site_map_tzid, dtype=np.int32)
        site_map_table_arr = np.array(site_map_table, dtype=np.int32)

        edge_table_index = np.full(len(merchant_ids), -1, dtype=np.int32)
        for merchant_id, table_idx in edge_alias_tables.key_to_table.items():
            idx = merchant_index.get(int(merchant_id))
            if idx is not None:
                edge_table_index[idx] = int(table_idx)

        edge_topk_mask = np.zeros(edge_tzid_idx.shape[0], dtype=np.bool_)
        merchant_non_top_table_index = np.full(len(merchant_ids), -1, dtype=np.int32)
        non_top_table_offsets = np.zeros(0, dtype=np.int64)
        non_top_table_lengths = np.zeros(0, dtype=np.int32)
        non_top_prob = np.zeros(0, dtype=np.float64)
        non_top_alias = np.zeros(0, dtype=np.int64)
        non_top_edge_index = np.zeros(0, dtype=np.int32)
        tz_temper_redirect_p = 0.0

        if tz_temper_enabled_cfg and tz_temper_redirect_p_cfg > 0.0:
            tz_weight_rows = (
                edge_catalogue_df.group_by("tzid_operational")
                .agg(pl.col("edge_weight").sum().alias("weight_sum"))
                .sort("weight_sum", descending=True)
                .iter_rows(named=True)
            )
            top_tzid_idx: set[int] = set()
            for row in tz_weight_rows:
                if len(top_tzid_idx) >= tz_temper_topk_cfg:
                    break
                tzid = str(row.get("tzid_operational") or "")
                tzid_idx = tzid_to_idx.get(tzid)
                if tzid_idx is None:
                    continue
                top_tzid_idx.add(int(tzid_idx))
                tz_temper_topk_names.append(tzid)

            if top_tzid_idx:
                edge_topk_mask = np.isin(
                    edge_tzid_idx.astype(np.int64),
                    np.array(sorted(top_tzid_idx), dtype=np.int64),
                )
                (
                    non_top_table_offsets,
                    non_top_table_lengths,
                    non_top_prob,
                    non_top_alias,
                    non_top_edge_index,
                    non_top_key_to_table,
                ) = _build_non_top_edge_alias_tables(edge_alias_tables, edge_tzid_idx, top_tzid_idx)
                for merchant_id, table_idx in non_top_key_to_table.items():
                    merchant_idx = merchant_index.get(int(merchant_id))
                    if merchant_idx is not None:
                        merchant_non_top_table_index[merchant_idx] = int(table_idx)
                tz_temper_eligible_merchants = int(np.count_nonzero(merchant_non_top_table_index >= 0))
                tz_temper_effective = tz_temper_eligible_merchants > 0 and bool(np.any(edge_topk_mask))
                if tz_temper_effective:
                    tz_temper_redirect_p = float(tz_temper_redirect_p_cfg)

        logger.info(
            "S4: tz tempering effective=%s topk_tzids=%d eligible_merchants=%d redirect_p=%.4f",
            str(tz_temper_effective).lower(),
            len(tz_temper_topk_names),
            tz_temper_eligible_merchants,
            tz_temper_redirect_p,
        )

        for merchant_id, idx in merchant_index.items():
            mode = int(merchant_virtual_mode[idx])
            if mode != 2 and site_map_count[idx] <= 0:
                _abort(
                    "5B.S4.INPUTS_MISSING",
                    "V-07",
                    "site_alias_missing",
                    {"merchant_id": merchant_id},
                    manifest_fingerprint,
                )
            if mode in (1, 2) and edge_table_index[idx] < 0:
                _abort(
                    "5B.S4.INPUTS_MISSING",
                    "V-07",
                    "edge_alias_missing",
                    {"merchant_id": merchant_id},
                    manifest_fingerprint,
                )

        current_phase = "rng_logs"
        event_entry = find_dataset_entry(dictionary_5b, "rng_event_arrival_time_jitter").entry
        event_path = _resolve_dataset_path(event_entry, run_paths, config.external_roots, tokens)
        event_root = _event_root_from_path(event_path)
        existing_events = _iter_jsonl_paths(event_root) if event_root.exists() else []
        event_enabled = enable_rng_events and not existing_events
        if not enable_rng_events:
            logger.info("S4: rng_event logging disabled; emitting rng_trace_log only")
        elif existing_events:
            logger.info("S4: rng_event logs already exist; skipping new emission")

        trace_entry = find_dataset_entry(dictionary_5b, "rng_trace_log").entry
        trace_path = _resolve_dataset_path(trace_entry, run_paths, config.external_roots, tokens)
        trace_mode = "create"
        if trace_path.exists():
            trace_mode = (
                "skip"
                if (
                    _trace_has_substream(trace_path, "5B.S4", "arrival_time_jitter")
                    and _trace_has_substream(trace_path, "5B.S4", "arrival_site_pick")
                    and _trace_has_substream(trace_path, "5B.S4", "arrival_edge_pick")
                )
                else "append"
            )
        if event_enabled and trace_mode == "skip":
            _abort(
                "5B.S4.RNG_ACCOUNTING_MISMATCH",
                "V-05",
                "rng_trace_without_events",
                {"detail": "trace already has substream but events are missing"},
                manifest_fingerprint,
            )

        trace_handle = None
        trace_tmp_path = None
        if trace_mode == "create":
            trace_tmp_path = run_paths.tmp_root / f"s4_trace_{uuid.uuid4().hex}.jsonl"
            trace_handle = trace_tmp_path.open("w", encoding="utf-8")
        elif trace_mode == "append":
            trace_handle = trace_path.open("a", encoding="utf-8")
        logger.info("S4: rng_trace_log mode=%s", trace_mode)

        audit_entry = find_dataset_entry(dictionary_5b, "rng_audit_log").entry
        audit_payload = {
            "ts_utc": utc_now_rfc3339_micro(),
            "run_id": str(run_id),
            "seed": int(seed),
            "manifest_fingerprint": str(manifest_fingerprint),
            "parameter_hash": str(parameter_hash),
            "algorithm": "philox2x64-10",
            "build_commit": _resolve_git_hash(config.repo_root),
            "code_digest": None,
            "hostname": platform.node(),
            "platform": platform.platform(),
            "notes": None,
        }
        audit_payload = {key: value for key, value in audit_payload.items() if value is not None}
        _validate_payload(
            schema_layer1,
            schema_layer1,
            schema_layer2,
            "rng/core/rng_audit_log/record",
            audit_payload,
            manifest_fingerprint,
            "V-05",
            "5B.S4.RNG_POLICY_INVALID",
            "rng_audit_log",
        )
        _ensure_rng_audit(
            _resolve_dataset_path(audit_entry, run_paths, config.external_roots, tokens),
            audit_payload,
            logger,
        )

        event_schema_time = None
        event_schema_site = None
        event_schema_edge = None
        validate_remaining_time = None
        validate_remaining_site = None
        validate_remaining_edge = None
        if event_enabled:
            event_schema_time = normalize_nullable_schema(_schema_from_pack(schema_layer1, "rng/events/arrival_time_jitter"))
            event_schema_site = normalize_nullable_schema(_schema_from_pack(schema_layer1, "rng/events/arrival_site_pick"))
            event_schema_edge = normalize_nullable_schema(_schema_from_pack(schema_layer1, "rng/events/arrival_edge_pick"))
            if not validate_events_full:
                validate_remaining_time = validate_events_limit
                validate_remaining_site = validate_events_limit
                validate_remaining_edge = validate_events_limit

        event_tmp_dir = None
        event_file_index = 0
        if event_enabled:
            event_tmp_dir = run_paths.tmp_root / f"s4_rng_events_{uuid.uuid4().hex}"
            event_tmp_dir.mkdir(parents=True, exist_ok=True)

        counts_entry = find_dataset_entry(dictionary_5b, "s3_bucket_counts_5B").entry

        for scenario_id in scenario_set:
            current_phase = f"scenario:{scenario_id}"
            logger.info(
                "S4: scenario=%s building time grid, routing tables, and streaming bucket counts", scenario_id
            )

            time_grid_entry = find_dataset_entry(dictionary_5b, "s1_time_grid_5B").entry
            time_grid_path = _resolve_dataset_path(
                time_grid_entry,
                run_paths,
                config.external_roots,
                {"manifest_fingerprint": str(manifest_fingerprint), "scenario_id": str(scenario_id)},
            )
            time_grid_df = pl.read_parquet(_list_parquet_files(time_grid_path))
            time_grid_df = time_grid_df.select(
                "bucket_index",
                "bucket_start_utc",
                "bucket_duration_seconds",
            )
            max_bucket = int(time_grid_df.get_column("bucket_index").max())
            bucket_start_us = np.full(max_bucket + 1, -1, dtype=np.int64)
            bucket_duration_us = np.full(max_bucket + 1, -1, dtype=np.int64)
            bucket_day_index = np.full(max_bucket + 1, -1, dtype=np.int64)
            for row in time_grid_df.iter_rows(named=True):
                bucket_idx = int(row["bucket_index"])
                start_us = _rfc3339_to_us(str(row["bucket_start_utc"]))
                duration_us = int(float(row["bucket_duration_seconds"]) * 1_000_000)
                bucket_start_us[bucket_idx] = start_us
                bucket_duration_us[bucket_idx] = duration_us
                day_index = _parse_utc_day_index(str(row["bucket_start_utc"])[:10])
                bucket_day_index[bucket_idx] = day_index

            counts_path = _resolve_dataset_path(
                counts_entry,
                run_paths,
                config.external_roots,
                {"seed": str(seed), "manifest_fingerprint": str(manifest_fingerprint), "scenario_id": str(scenario_id)},
            )
            counts_files = _list_parquet_files(counts_path)
            rows_total = _count_parquet_rows(counts_files)
            arrivals_total = _sum_parquet_counts(counts_files, "count_N")

            logger.info(
                "S4: processing counts (scenario_id=%s files=%d bucket_rows=%s arrivals_total=%s)",
                scenario_id,
                len(counts_files),
                rows_total,
                arrivals_total,
            )
            tracker_rows = _ProgressTracker(
                rows_total,
                logger,
                f"S4: bucket rows (scenario_id={scenario_id})",
                min_interval_seconds=progress_interval_seconds,
            )
            tracker_arrivals = _ProgressTracker(
                arrivals_total,
                logger,
                f"S4: arrivals emitted (scenario_id={scenario_id})",
                min_interval_seconds=progress_interval_seconds,
            )

            arrival_entry = find_dataset_entry(dictionary_5b, "arrival_events_5B").entry
            arrival_path = _resolve_dataset_path(
                arrival_entry,
                run_paths,
                config.external_roots,
                {"seed": str(seed), "manifest_fingerprint": str(manifest_fingerprint), "scenario_id": str(scenario_id)},
            )
            arrival_root = arrival_path.parent
            arrival_tmp_root = run_paths.tmp_root / f"s4_arrivals_{uuid.uuid4().hex}"
            arrival_tmp_root.mkdir(parents=True, exist_ok=True)
            part_index = 0

            sample_remaining = output_sample_rows
            scenario_rows = 0
            scenario_arrivals = 0
            scenario_virtual = 0
            missing_group_weights_total = 0
            missing_group_weights_logged = False
            rng_prefix_time = _rng_prefix(domain_sep, "S4.arrival_time_jitter.v1", str(manifest_fingerprint), str(parameter_hash), int(seed), str(scenario_id))
            rng_prefix_site = _rng_prefix(domain_sep, "S4.arrival_site_pick.v1", str(manifest_fingerprint), str(parameter_hash), int(seed), str(scenario_id))
            rng_prefix_edge = _rng_prefix(domain_sep, "S4.arrival_edge_pick.v1", str(manifest_fingerprint), str(parameter_hash), int(seed), str(scenario_id))
            base_hasher_time = hashlib.sha256(rng_prefix_time)
            base_hasher_site = hashlib.sha256(rng_prefix_site)
            base_hasher_edge = hashlib.sha256(rng_prefix_edge)
            domain_prefix_cache: dict[tuple[int, str], str] = {}

            merchant_seq: dict[int, int] = {}
            use_group_weights = bool((routing_policy.get("physical_router") or {}).get("use_group_weights"))

            def _write_part(frame: pl.DataFrame) -> None:
                nonlocal part_index
                if frame.is_empty():
                    return
                part_path = arrival_tmp_root / f"part-{part_index:06d}.parquet"
                part_index += 1
                if _HAVE_PYARROW:
                    table = frame.to_arrow()
                    pq.write_table(table, part_path, compression="zstd")
                else:
                    frame.write_parquet(part_path, compression="zstd")

            for batch in _iter_parquet_batches(
                counts_files,
                [
                    "scenario_id",
                    "merchant_id",
                    "zone_representation",
                    "channel_group",
                    "bucket_index",
                    "count_N",
                ],
                batch_rows,
            ):
                if _HAVE_PYARROW and hasattr(batch, "column"):
                    batch_df = pl.from_arrow(batch)
                else:
                    batch_df = batch
                if batch_df.is_empty():
                    continue

                tracker_rows.update(batch_df.height)

                if batch_df.filter(pl.col("scenario_id") != scenario_id).height:
                    _abort(
                        "5B.S4.DOMAIN_ALIGN_FAILED",
                        "V-08",
                        "scenario_id_mismatch",
                        {"scenario_id": scenario_id},
                        manifest_fingerprint,
                    )

                if "channel_group" not in batch_df.columns:
                    batch_df = batch_df.with_columns(pl.lit(None).alias("channel_group"))

                batch_df = batch_df.with_columns(
                    pl.col("merchant_id").cast(pl.UInt64),
                    pl.col("zone_representation").cast(pl.Utf8),
                    pl.col("channel_group").cast(pl.Utf8),
                    pl.col("bucket_index").cast(pl.Int64),
                    pl.col("count_N").cast(pl.Int64),
                )

                batch_df = batch_df.filter(pl.col("count_N") > 0)
                if batch_df.is_empty():
                    continue

                count_array = batch_df.get_column("count_N").to_numpy()
                if max_arrivals_per_bucket and int(count_array.max()) > max_arrivals_per_bucket:
                    _abort(
                        "5B.S4.TIME_POLICY_INVALID",
                        "V-06",
                        "count_exceeds_guardrail",
                        {"max_arrivals_per_bucket": max_arrivals_per_bucket},
                        manifest_fingerprint,
                    )

                merchant_array = batch_df.get_column("merchant_id").to_numpy()
                zone_values = batch_df.get_column("zone_representation").to_list()
                bucket_indices = batch_df.get_column("bucket_index").to_numpy()
                channel_values = batch_df.get_column("channel_group").to_list()

                row_seq_start = np.zeros(count_array.size, dtype=np.int64)
                for idx, merchant_id in enumerate(merchant_array):
                    merchant_id = int(merchant_id)
                    seq = merchant_seq.get(merchant_id, 0)
                    row_seq_start[idx] = seq
                    merchant_seq[merchant_id] = seq + int(count_array[idx])

                row_offsets = np.zeros(count_array.size, dtype=np.int64)
                row_offsets[1:] = np.cumsum(count_array[:-1].astype(np.int64))

                bucket_start_rows = bucket_start_us[bucket_indices]
                bucket_duration_rows = bucket_duration_us[bucket_indices]
                if (bucket_start_rows < 0).any() or (bucket_duration_rows < 0).any():
                    _abort(
                        "5B.S4.BUCKET_SET_INCONSISTENT",
                        "V-08",
                        "bucket_index_missing",
                        {"scenario_id": scenario_id},
                        manifest_fingerprint,
                    )

                day_indices = bucket_day_index[bucket_indices]
                group_table_index = np.full(count_array.size, -1, dtype=np.int32)
                for idx, merchant_id in enumerate(merchant_array):
                    day_index = int(day_indices[idx])
                    table_idx = group_alias_tables.key_to_table.get((int(merchant_id), day_index))
                    if table_idx is None:
                        group_table_index[idx] = -1
                    else:
                        group_table_index[idx] = int(table_idx)

                if use_group_weights:
                    missing_group_weights = int(np.count_nonzero(group_table_index < 0))
                    if missing_group_weights:
                        missing_group_weights_total += missing_group_weights
                        if not missing_group_weights_logged:
                            logger.warning(
                                "S4: group weights missing for %d bucket rows; falling back to zone_representation (scenario_id=%s output=arrival_events_5B)",
                                missing_group_weights,
                                scenario_id,
                            )
                            missing_group_weights_logged = True

                merchant_idx_array = np.array([merchant_index.get(int(mid), -1) for mid in merchant_array], dtype=np.int64)
                if (merchant_idx_array < 0).any():
                    _abort(
                        "5B.S4.DOMAIN_ALIGN_FAILED",
                        "V-08",
                        "merchant_missing",
                        {"scenario_id": scenario_id},
                        manifest_fingerprint,
                    )

                zone_rep_idx = np.array([tzid_to_idx.get(str(z), -1) for z in zone_values], dtype=np.int32)
                if (zone_rep_idx < 0).any():
                    _abort(
                        "5B.S4.DOMAIN_ALIGN_FAILED",
                        "V-08",
                        "tzid_missing",
                        {"scenario_id": scenario_id},
                        manifest_fingerprint,
                    )

                time_keys = np.zeros(count_array.size, dtype=np.uint64)
                time_ctr_hi = np.zeros(count_array.size, dtype=np.uint64)
                time_ctr_lo = np.zeros(count_array.size, dtype=np.uint64)
                site_keys = np.zeros(count_array.size, dtype=np.uint64)
                site_ctr_hi = np.zeros(count_array.size, dtype=np.uint64)
                site_ctr_lo = np.zeros(count_array.size, dtype=np.uint64)
                edge_keys = np.zeros(count_array.size, dtype=np.uint64)
                edge_ctr_hi = np.zeros(count_array.size, dtype=np.uint64)
                edge_ctr_lo = np.zeros(count_array.size, dtype=np.uint64)

                for idx, merchant_id in enumerate(merchant_array):
                    merchant_id = int(merchant_id)
                    zone_rep = str(zone_values[idx])
                    bucket_index = int(bucket_indices[idx])
                    cache_key = (merchant_id, zone_rep)
                    domain_prefix = domain_prefix_cache.get(cache_key)
                    if domain_prefix is None:
                        domain_prefix = f"merchant_id={merchant_id}|zone={zone_rep}|bucket_index="
                        domain_prefix_cache[cache_key] = domain_prefix
                    domain_key = f"{domain_prefix}{bucket_index}"
                    key, ctr_hi, ctr_lo = _derive_rng_seed(base_hasher_time, domain_key)
                    time_keys[idx] = np.uint64(key)
                    time_ctr_hi[idx] = np.uint64(ctr_hi)
                    time_ctr_lo[idx] = np.uint64(ctr_lo)
                    key, ctr_hi, ctr_lo = _derive_rng_seed(base_hasher_site, domain_key)
                    site_keys[idx] = np.uint64(key)
                    site_ctr_hi[idx] = np.uint64(ctr_hi)
                    site_ctr_lo[idx] = np.uint64(ctr_lo)
                    key, ctr_hi, ctr_lo = _derive_rng_seed(base_hasher_edge, domain_key)
                    edge_keys[idx] = np.uint64(key)
                    edge_ctr_hi[idx] = np.uint64(ctr_hi)
                    edge_ctr_lo[idx] = np.uint64(ctr_lo)

                lambda_realised_rows = np.zeros(count_array.size, dtype=np.float64)

                segments = _split_by_arrival_count(count_array, max_arrivals_chunk)
                for seg_start, seg_end in segments:
                    seg_slice = slice(seg_start, seg_end)
                    seg_counts = count_array[seg_slice]
                    seg_total = int(seg_counts.sum())
                    if seg_total <= 0:
                        continue

                    seg_offsets = row_offsets[seg_slice].copy()
                    seg_offsets -= seg_offsets[0]

                    out_ts_utc_us = np.zeros(seg_total, dtype=np.int64)
                    out_arrival_seq = np.zeros(seg_total, dtype=np.int64)
                    out_is_virtual = np.zeros(seg_total, dtype=np.bool_)
                    out_site_id = np.zeros(seg_total, dtype=np.uint64)
                    out_edge_index = np.zeros(seg_total, dtype=np.int32)
                    out_tzid_primary = np.zeros(seg_total, dtype=np.int32)
                    out_tzid_operational = np.zeros(seg_total, dtype=np.int32)
                    out_tzid_settlement = np.zeros(seg_total, dtype=np.int32)
                    out_ts_local_primary_us = np.zeros(seg_total, dtype=np.int64)
                    out_ts_local_operational_us = np.zeros(seg_total, dtype=np.int64)
                    out_ts_local_settlement_us = np.zeros(seg_total, dtype=np.int64)
                    out_merchant_id = np.zeros(seg_total, dtype=np.uint64)
                    out_bucket_index = np.zeros(seg_total, dtype=np.int64)
                    out_zone_rep_index = np.zeros(seg_total, dtype=np.int32)
                    out_lambda_realised = np.zeros(seg_total, dtype=np.float64)
                    row_virtual_counts = np.zeros(seg_counts.size, dtype=np.int64)
                    row_errors = np.zeros(seg_counts.size, dtype=np.int32)

                    expand_arrivals(
                        seg_offsets,
                        seg_counts,
                        bucket_start_rows[seg_slice],
                        bucket_duration_rows[seg_slice],
                        merchant_array[seg_slice],
                        merchant_idx_array[seg_slice],
                        zone_rep_idx[seg_slice],
                        bucket_indices[seg_slice],
                        row_seq_start[seg_slice],
                        time_keys[seg_slice],
                        time_ctr_hi[seg_slice],
                        time_ctr_lo[seg_slice],
                        site_keys[seg_slice],
                        site_ctr_hi[seg_slice],
                        site_ctr_lo[seg_slice],
                        edge_keys[seg_slice],
                        edge_ctr_hi[seg_slice],
                        edge_ctr_lo[seg_slice],
                        group_table_index[seg_slice],
                        group_alias_tables.table_offsets,
                        group_alias_tables.table_lengths,
                        group_alias_tables.prob,
                        group_alias_tables.alias,
                        group_alias_tables.tzids,
                        site_map_start,
                        site_map_count,
                        site_map_tzid_arr,
                        site_map_table_arr,
                        site_alias_tables.table_offsets,
                        site_alias_tables.table_lengths,
                        site_alias_tables.prob,
                        site_alias_tables.alias,
                        site_alias_tables.site_ids,
                        site_alias_tables.site_tzids,
                        edge_table_index,
                        edge_alias_tables.table_offsets,
                        edge_alias_tables.table_lengths,
                        edge_alias_tables.prob,
                        edge_alias_tables.alias,
                        edge_alias_tables.edge_index,
                        edge_tzid_idx,
                        edge_topk_mask,
                        merchant_non_top_table_index,
                        non_top_table_offsets,
                        non_top_table_lengths,
                        non_top_prob,
                        non_top_alias,
                        non_top_edge_index,
                        merchant_virtual_mode,
                        merchant_settlement_tzid,
                        tz_index_start,
                        tz_index_count,
                        tz_transitions_utc,
                        tz_offsets_minutes,
                        1 if tz_temper_effective else 0,
                        float(tz_temper_redirect_p),
                        float(p_virtual_hybrid),
                        out_ts_utc_us,
                        out_arrival_seq,
                        out_is_virtual,
                        out_site_id,
                        out_edge_index,
                        out_tzid_primary,
                        out_tzid_operational,
                        out_tzid_settlement,
                        out_ts_local_primary_us,
                        out_ts_local_operational_us,
                        out_ts_local_settlement_us,
                        out_merchant_id,
                        out_bucket_index,
                        out_zone_rep_index,
                        out_lambda_realised,
                        row_virtual_counts,
                        row_errors,
                        lambda_realised_rows[seg_slice],
                    )

                    if (row_errors > 0).any():
                        error_idx = int(np.flatnonzero(row_errors > 0)[0])
                        error_code_local = int(row_errors[error_idx])
                        reason = "site_alias_missing" if error_code_local == 1 else "edge_alias_missing"
                        _abort(
                            "5B.S4.ROUTING_POLICY_INVALID",
                            "V-06",
                            reason,
                            {"scenario_id": scenario_id, "row_index": error_idx},
                            manifest_fingerprint,
                        )

                    scenario_virtual += int(row_virtual_counts.sum())
                    tracker_arrivals.update(seg_total)

                    ts_utc = _format_rfc3339_us(out_ts_utc_us)
                    ts_local_primary = _format_local_wall_us(out_ts_local_primary_us)
                    if np.array_equal(out_ts_local_operational_us, out_ts_local_primary_us):
                        ts_local_operational = ts_local_primary
                    else:
                        ts_local_operational = _format_local_wall_us(out_ts_local_operational_us)
                    if np.array_equal(out_ts_local_settlement_us, out_ts_local_primary_us):
                        ts_local_settlement = ts_local_primary
                    elif np.array_equal(out_ts_local_settlement_us, out_ts_local_operational_us):
                        ts_local_settlement = ts_local_operational
                    else:
                        ts_local_settlement = _format_local_wall_us(out_ts_local_settlement_us)

                    tzid_primary = _map_indices(out_tzid_primary, tzid_lookup)
                    if np.array_equal(out_tzid_operational, out_tzid_primary):
                        tzid_operational = tzid_primary
                    else:
                        tzid_operational = _map_indices(out_tzid_operational, tzid_lookup)
                    if np.array_equal(out_tzid_settlement, out_tzid_primary):
                        tzid_settlement = tzid_primary
                    elif np.array_equal(out_tzid_settlement, out_tzid_operational):
                        tzid_settlement = tzid_operational
                    else:
                        tzid_settlement = _map_indices(out_tzid_settlement, tzid_lookup)
                    zone_rep = _map_indices(out_zone_rep_index, tzid_lookup)

                    edge_id_raw = np.zeros(out_edge_index.shape, dtype=np.uint64)
                    edge_mask = out_edge_index >= 0
                    if edge_mask.any():
                        edge_id_raw[edge_mask] = edge_ids[out_edge_index[edge_mask]]

                    site_id_raw = out_site_id

                    channel_repeat = np.repeat(
                        np.asarray(channel_values[seg_start:seg_end], dtype=object),
                        seg_counts.astype(np.int64, copy=False),
                    )

                    output_df = pl.DataFrame(
                        {
                            "manifest_fingerprint": str(manifest_fingerprint),
                            "parameter_hash": str(parameter_hash),
                            "seed": np.full(seg_total, int(seed), dtype=np.uint64),
                            "scenario_id": np.full(seg_total, str(scenario_id), dtype=object),
                            "merchant_id": out_merchant_id,
                            "zone_representation": zone_rep,
                            "channel_group": channel_repeat,
                            "bucket_index": out_bucket_index.astype(np.int64, copy=False),
                            "arrival_seq": out_arrival_seq.astype(np.int64, copy=False),
                            "ts_utc": ts_utc,
                            "tzid_primary": tzid_primary,
                            "ts_local_primary": ts_local_primary,
                            "tzid_settlement": tzid_settlement,
                            "ts_local_settlement": ts_local_settlement,
                            "tzid_operational": tzid_operational,
                            "ts_local_operational": ts_local_operational,
                            "site_id_raw": site_id_raw,
                            "edge_id_raw": edge_id_raw,
                            "routing_universe_hash": np.full(seg_total, routing_universe_hash, dtype=object),
                            "is_virtual": out_is_virtual,
                            "s4_spec_version": np.full(seg_total, spec_version, dtype=object),
                        }
                    )
                    output_df = output_df.with_columns(
                        pl.when(pl.col("site_id_raw") == 0)
                        .then(None)
                        .otherwise(pl.col("site_id_raw"))
                        .cast(pl.UInt64)
                        .alias("site_id"),
                        pl.when(pl.col("edge_id_raw") == 0)
                        .then(None)
                        .otherwise(pl.col("edge_id_raw"))
                        .cast(pl.UInt64)
                        .alias("edge_id"),
                    ).drop(["site_id_raw", "edge_id_raw"])

                    if include_lambda:
                        output_df = output_df.with_columns(
                            pl.Series("lambda_realised", out_lambda_realised)
                        )

                    if strict_ordering:
                        output_df = output_df.sort(["merchant_id", "ts_utc", "arrival_seq"])

                    if output_validate_full:
                        _validate_array_rows(
                            output_df.iter_rows(named=True),
                            schema_5b,
                            schema_layer1,
                            schema_layer2,
                            "egress/s4_arrival_events_5B",
                            manifest_fingerprint,
                            f"arrival_events_5B scenario_id={scenario_id}",
                            total_rows=output_df.height,
                        )
                    elif sample_remaining > 0:
                        sample_chunk = output_df.head(min(sample_remaining, output_df.height))
                        _validate_array_rows(
                            sample_chunk.iter_rows(named=True),
                            schema_5b,
                            schema_layer1,
                            schema_layer2,
                            "egress/s4_arrival_events_5B",
                            manifest_fingerprint,
                            f"arrival_events_5B scenario_id={scenario_id}",
                            total_rows=sample_chunk.height,
                            limit=sample_chunk.height,
                        )
                        sample_remaining -= sample_chunk.height

                    _write_part(output_df)

                    scenario_rows += output_df.height
                    scenario_arrivals += seg_total

                    rng_time_draws = int(seg_counts.sum())
                    rng_site_draws = int(seg_counts.sum() * 2)
                    rng_edge_draws = int(row_virtual_counts.sum())
                    rng_time_blocks = rng_time_draws
                    rng_site_blocks = int(seg_counts.sum())
                    rng_edge_blocks = rng_edge_draws

                    rng_draws_total["arrival_time_jitter"] += rng_time_draws
                    rng_blocks_total["arrival_time_jitter"] += rng_time_blocks
                    rng_events_total["arrival_time_jitter"] += int(seg_counts.size)

                    rng_draws_total["arrival_site_pick"] += rng_site_draws
                    rng_blocks_total["arrival_site_pick"] += rng_site_blocks
                    rng_events_total["arrival_site_pick"] += int(seg_counts.size)

                    rng_draws_total["arrival_edge_pick"] += rng_edge_draws
                    rng_blocks_total["arrival_edge_pick"] += rng_edge_blocks
                    rng_events_total["arrival_edge_pick"] += int(np.count_nonzero(row_virtual_counts))

                    if event_enabled and event_tmp_dir is not None:
                        event_path_time = _event_file_from_root(event_tmp_dir, event_file_index)
                        event_file_index += 1
                        event_path_site = _event_file_from_root(event_tmp_dir, event_file_index)
                        event_file_index += 1
                        event_path_edge = _event_file_from_root(event_tmp_dir, event_file_index)
                        event_file_index += 1

                        with event_path_time.open("w", encoding="utf-8") as handle:
                            buffer: list[str] = []
                            for row_idx, count_val in enumerate(seg_counts):
                                draws = int(count_val)
                                if draws <= 0:
                                    continue
                                before_hi = int(time_ctr_hi[seg_start + row_idx])
                                before_lo = int(time_ctr_lo[seg_start + row_idx])
                                after_hi, after_lo = add_u128(before_hi, before_lo, draws)
                                payload = {
                                    "ts_utc": utc_now_rfc3339_micro(),
                                    "run_id": str(run_id),
                                    "seed": int(seed),
                                    "parameter_hash": str(parameter_hash),
                                    "manifest_fingerprint": str(manifest_fingerprint),
                                    "module": "5B.S4",
                                    "substream_label": "arrival_time_jitter",
                                    "scenario_id": str(scenario_id),
                                    "bucket_index": int(bucket_indices[seg_start + row_idx]),
                                    "merchant_id": int(merchant_array[seg_start + row_idx]),
                                    "rng_counter_before_lo": before_lo,
                                    "rng_counter_before_hi": before_hi,
                                    "rng_counter_after_lo": int(after_lo),
                                    "rng_counter_after_hi": int(after_hi),
                                    "draws": str(draws),
                                    "blocks": int(draws),
                                }
                                if event_schema_time is not None and (
                                    validate_remaining_time is None or validate_remaining_time > 0
                                ):
                                    errors = list(Draft202012Validator(event_schema_time).iter_errors(payload))
                                    if errors:
                                        raise EngineFailure(
                                            "F4",
                                            "5B.S4.RNG_ACCOUNTING_MISMATCH",
                                            STATE,
                                            MODULE_NAME,
                                            {"detail": str(errors[0])},
                                        )
                                    if validate_remaining_time is not None:
                                        validate_remaining_time -= 1
                                buffer.append(_json_dumps(payload))
                                if len(buffer) >= event_buffer_size:
                                    handle.write("\n".join(buffer))
                                    handle.write("\n")
                                    buffer.clear()
                            if buffer:
                                handle.write("\n".join(buffer))
                                handle.write("\n")

                        with event_path_site.open("w", encoding="utf-8") as handle:
                            buffer = []
                            for row_idx, count_val in enumerate(seg_counts):
                                draws = int(count_val) * 2
                                if draws <= 0:
                                    continue
                                before_hi = int(site_ctr_hi[seg_start + row_idx])
                                before_lo = int(site_ctr_lo[seg_start + row_idx])
                                after_hi, after_lo = add_u128(before_hi, before_lo, int(count_val))
                                payload = {
                                    "ts_utc": utc_now_rfc3339_micro(),
                                    "run_id": str(run_id),
                                    "seed": int(seed),
                                    "parameter_hash": str(parameter_hash),
                                    "manifest_fingerprint": str(manifest_fingerprint),
                                    "module": "5B.S4",
                                    "substream_label": "arrival_site_pick",
                                    "scenario_id": str(scenario_id),
                                    "bucket_index": int(bucket_indices[seg_start + row_idx]),
                                    "merchant_id": int(merchant_array[seg_start + row_idx]),
                                    "rng_counter_before_lo": before_lo,
                                    "rng_counter_before_hi": before_hi,
                                    "rng_counter_after_lo": int(after_lo),
                                    "rng_counter_after_hi": int(after_hi),
                                    "draws": str(draws),
                                    "blocks": int(count_val),
                                }
                                if event_schema_site is not None and (
                                    validate_remaining_site is None or validate_remaining_site > 0
                                ):
                                    errors = list(Draft202012Validator(event_schema_site).iter_errors(payload))
                                    if errors:
                                        raise EngineFailure(
                                            "F4",
                                            "5B.S4.RNG_ACCOUNTING_MISMATCH",
                                            STATE,
                                            MODULE_NAME,
                                            {"detail": str(errors[0])},
                                        )
                                    if validate_remaining_site is not None:
                                        validate_remaining_site -= 1
                                buffer.append(_json_dumps(payload))
                                if len(buffer) >= event_buffer_size:
                                    handle.write("\n".join(buffer))
                                    handle.write("\n")
                                    buffer.clear()
                            if buffer:
                                handle.write("\n".join(buffer))
                                handle.write("\n")

                        with event_path_edge.open("w", encoding="utf-8") as handle:
                            buffer = []
                            for row_idx, virtual_count in enumerate(row_virtual_counts):
                                draws = int(virtual_count)
                                if draws <= 0:
                                    continue
                                before_hi = int(edge_ctr_hi[seg_start + row_idx])
                                before_lo = int(edge_ctr_lo[seg_start + row_idx])
                                after_hi, after_lo = add_u128(before_hi, before_lo, draws)
                                payload = {
                                    "ts_utc": utc_now_rfc3339_micro(),
                                    "run_id": str(run_id),
                                    "seed": int(seed),
                                    "parameter_hash": str(parameter_hash),
                                    "manifest_fingerprint": str(manifest_fingerprint),
                                    "module": "5B.S4",
                                    "substream_label": "arrival_edge_pick",
                                    "scenario_id": str(scenario_id),
                                    "bucket_index": int(bucket_indices[seg_start + row_idx]),
                                    "merchant_id": int(merchant_array[seg_start + row_idx]),
                                    "rng_counter_before_lo": before_lo,
                                    "rng_counter_before_hi": before_hi,
                                    "rng_counter_after_lo": int(after_lo),
                                    "rng_counter_after_hi": int(after_hi),
                                    "draws": str(draws),
                                    "blocks": int(draws),
                                }
                                if event_schema_edge is not None and (
                                    validate_remaining_edge is None or validate_remaining_edge > 0
                                ):
                                    errors = list(Draft202012Validator(event_schema_edge).iter_errors(payload))
                                    if errors:
                                        raise EngineFailure(
                                            "F4",
                                            "5B.S4.RNG_ACCOUNTING_MISMATCH",
                                            STATE,
                                            MODULE_NAME,
                                            {"detail": str(errors[0])},
                                        )
                                    if validate_remaining_edge is not None:
                                        validate_remaining_edge -= 1
                                buffer.append(_json_dumps(payload))
                                if len(buffer) >= event_buffer_size:
                                    handle.write("\n".join(buffer))
                                    handle.write("\n")
                                    buffer.clear()
                            if buffer:
                                handle.write("\n".join(buffer))
                                handle.write("\n")

                    if trace_handle is not None:
                        def _max_counter(before_hi_arr: np.ndarray, before_lo_arr: np.ndarray, increments: np.ndarray) -> Optional[tuple[int, int, int, int]]:
                            max_before_hi = 0
                            max_before_lo = 0
                            max_after_hi = 0
                            max_after_lo = 0
                            has_value = False
                            for idx in range(increments.size):
                                inc = int(increments[idx])
                                if inc <= 0:
                                    continue
                                before_hi = int(before_hi_arr[idx])
                                before_lo = int(before_lo_arr[idx])
                                after_hi, after_lo = add_u128(before_hi, before_lo, inc)
                                if not has_value or _u128_gt(int(after_hi), int(after_lo), max_after_hi, max_after_lo):
                                    max_before_hi = before_hi
                                    max_before_lo = before_lo
                                    max_after_hi = int(after_hi)
                                    max_after_lo = int(after_lo)
                                    has_value = True
                            if not has_value:
                                return None
                            return max_before_hi, max_before_lo, max_after_hi, max_after_lo

                        time_max = _max_counter(time_ctr_hi[seg_slice], time_ctr_lo[seg_slice], seg_counts)
                        site_max = _max_counter(site_ctr_hi[seg_slice], site_ctr_lo[seg_slice], seg_counts)
                        edge_max = _max_counter(edge_ctr_hi[seg_slice], edge_ctr_lo[seg_slice], row_virtual_counts)

                        if time_max is not None:
                            before_hi, before_lo, after_hi, after_lo = time_max
                            _write_trace_row(
                                trace_handle,
                                str(run_id),
                                int(seed),
                                "5B.S4",
                                "arrival_time_jitter",
                                before_hi,
                                before_lo,
                                after_hi,
                                after_lo,
                                rng_draws_total["arrival_time_jitter"],
                                rng_blocks_total["arrival_time_jitter"],
                                rng_events_total["arrival_time_jitter"],
                            )
                        if site_max is not None:
                            before_hi, before_lo, after_hi, after_lo = site_max
                            _write_trace_row(
                                trace_handle,
                                str(run_id),
                                int(seed),
                                "5B.S4",
                                "arrival_site_pick",
                                before_hi,
                                before_lo,
                                after_hi,
                                after_lo,
                                rng_draws_total["arrival_site_pick"],
                                rng_blocks_total["arrival_site_pick"],
                                rng_events_total["arrival_site_pick"],
                            )
                        if edge_max is not None:
                            before_hi, before_lo, after_hi, after_lo = edge_max
                            _write_trace_row(
                                trace_handle,
                                str(run_id),
                                int(seed),
                                "5B.S4",
                                "arrival_edge_pick",
                                before_hi,
                                before_lo,
                                after_hi,
                                after_lo,
                                rng_draws_total["arrival_edge_pick"],
                                rng_blocks_total["arrival_edge_pick"],
                                rng_events_total["arrival_edge_pick"],
                            )

            _atomic_publish_dir(arrival_tmp_root, arrival_root, logger, "arrival_events_5B")
            output_paths.append(arrival_root)

            scenario_details[str(scenario_id)] = {
                "arrival_rows": scenario_rows,
                "arrival_virtual": scenario_virtual,
                "bucket_rows": rows_total,
                "arrivals_total": arrivals_total,
                "missing_group_weights": missing_group_weights_total,
            }
            scenario_count_succeeded += 1
            total_rows_written += scenario_rows
            total_arrivals += scenario_arrivals
            total_virtual += scenario_virtual
            total_bucket_rows += int(rows_total or 0)

            timer.info("S4: scenario %s completed (arrivals=%d)", scenario_id, scenario_rows)

        if event_enabled and event_tmp_dir is not None:
            _atomic_publish_dir(event_tmp_dir, event_root, logger, "rng_event_arrival_time_jitter")
        if trace_handle is not None:
            trace_handle.close()
        if trace_mode == "create" and trace_tmp_path is not None:
            _atomic_publish_file(trace_tmp_path, trace_path, logger, "rng_trace_log")

        status = "PASS"
        timer.info("S4: completed arrival event expansion")
    except EngineFailure as exc:
        status = "FAIL"
        error_code = exc.failure_code
        error_class = exc.failure_class
        error_context = exc.detail
        if not first_failure_phase:
            first_failure_phase = current_phase
    except (ContractError, InputResolutionError, SchemaValidationError, ValueError) as exc:
        status = "FAIL"
        error_code = error_code or "5B.S4.IO_WRITE_FAILED"
        error_class = "F4"
        error_context = {"detail": str(exc), "phase": current_phase}
        if not first_failure_phase:
            first_failure_phase = current_phase
    except Exception as exc:  # pragma: no cover - unexpected error
        status = "FAIL"
        error_code = error_code or "5B.S4.IO_WRITE_FAILED"
        error_class = "F4"
        error_context = {"detail": str(exc), "phase": current_phase}
        if not first_failure_phase:
            first_failure_phase = current_phase
    finally:
        finished_utc = utc_now_rfc3339_micro()
        if run_id and parameter_hash and manifest_fingerprint and dictionary_5b and run_paths is not None:
            try:
                utc_day = started_utc[:10]
                run_report_path = _segment_state_runs_path(run_paths, dictionary_5b, utc_day)
                run_report_payload = {
                    "layer": "layer2",
                    "segment": SEGMENT,
                    "state": STATE,
                    "state_id": "5B.S4",
                    "parameter_hash": str(parameter_hash),
                    "manifest_fingerprint": str(manifest_fingerprint),
                    "seed": int(seed),
                    "run_id": str(run_id),
                    "scenario_set": list(scenario_set),
                    "status": status,
                    "error_code": error_code,
                    "started_at_utc": started_utc,
                    "finished_at_utc": finished_utc,
                    "durations": {"wall_ms": int((time.monotonic() - started_monotonic) * 1000)},
                    "validation_mode": output_validation_mode,
                    "scenario_count_requested": len(scenario_set),
                    "scenario_count_succeeded": scenario_count_succeeded,
                    "scenario_count_failed": len(scenario_set) - scenario_count_succeeded,
                    "total_rows_written": total_rows_written,
                    "total_arrivals": total_arrivals,
                    "total_virtual": total_virtual,
                    "total_bucket_rows": total_bucket_rows,
                    "rng_draws_total": rng_draws_total,
                    "rng_blocks_total": rng_blocks_total,
                    "rng_events_total": rng_events_total,
                    "tz_temper": {
                        "enabled_requested": bool(tz_temper_enabled_cfg),
                        "enabled_effective": bool(tz_temper_effective),
                        "topk_requested": int(tz_temper_topk_cfg),
                        "redirect_p_requested": float(tz_temper_redirect_p_cfg),
                        "redirect_p_effective": float(tz_temper_redirect_p),
                        "topk_tzids": list(tz_temper_topk_names),
                        "eligible_merchants": int(tz_temper_eligible_merchants),
                    },
                    "details": scenario_details,
                }
                if error_context:
                    run_report_payload["error_context"] = error_context
                    run_report_payload["first_failure_phase"] = first_failure_phase

                _append_jsonl(run_report_path, run_report_payload)
                logger.info("S4: run-report written %s", run_report_path)
            except Exception as exc:  # noqa: BLE001
                logger.warning("S4: failed to write segment_state_runs: %s", exc)

    if status != "PASS":
        raise EngineFailure(
            "F4",
            error_code or "5B.S4.IO_WRITE_FAILED",
            STATE,
            MODULE_NAME,
            error_context or {},
        )

    if run_report_path is None or run_paths is None:
        raise EngineFailure(
            "F4",
            "5B.S4.IO_WRITE_FAILED",
            STATE,
            MODULE_NAME,
            {"detail": "missing run_report_path or run_paths"},
        )

    return S4Result(
        run_id=str(run_id),
        parameter_hash=str(parameter_hash),
        manifest_fingerprint=str(manifest_fingerprint),
        output_paths=output_paths,
        run_report_path=run_report_path,
    )


__all__ = ["S4Result", "run_s4"]
