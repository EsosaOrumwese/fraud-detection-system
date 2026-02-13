"""S4 allocation plan runner for Segment 1B."""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

import numpy as np
import polars as pl
import psutil
import yaml
from jsonschema import Draft202012Validator

try:  # Optional fast row-group scanning.
    import pyarrow.compute as pc
    import pyarrow.parquet as pq

    _HAVE_PYARROW = True
except Exception:  # pragma: no cover - fallback when pyarrow missing.
    pc = None
    pq = None
    _HAVE_PYARROW = False

from engine.contracts.loader import find_dataset_entry, load_dataset_dictionary, load_schema_pack
from engine.contracts.source import ContractSource
from engine.core.config import EngineConfig
from engine.core.errors import EngineFailure, InputResolutionError, SchemaValidationError
from engine.core.logging import add_file_handler, get_logger
from engine.core.paths import RunPaths, resolve_input_path
from engine.core.time import utc_now_rfc3339_micro
from engine.core.run_receipt import pick_latest_run_receipt


MODULE_NAME = "1B.s4_alloc_plan"
BATCH_SIZE = 1_000_000
CACHE_COUNTRIES_MAX = 8


@dataclass(frozen=True)
class S4Result:
    run_id: str
    parameter_hash: str
    manifest_fingerprint: str
    alloc_plan_path: Path
    run_report_path: Path


@dataclass(frozen=True)
class S4AllocPolicy:
    policy_version: str
    enabled: bool
    country_share_soft_guard: float
    country_share_hard_guard: float
    reroute_enabled: bool
    reroute_mode: str
    max_moves_per_pair: int
    residual_enabled: bool
    min_active_tile_fraction: float
    max_steps_per_pair: int
    diversify_enabled: bool
    diversify_apply_n_sites_max: int
    diversify_candidate_window_fraction: float
    diversify_candidate_window_min: int
    deterministic_seed_namespace: str


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


def _close_parquet_reader(pfile) -> None:
    reader = getattr(pfile, "reader", None)
    if reader and hasattr(reader, "close"):
        reader.close()


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise InputResolutionError(f"Missing JSON file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        raise InputResolutionError(f"Missing YAML file: {path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise InputResolutionError(f"YAML payload must be an object: {path}")
    return payload


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True), encoding="utf-8")


def _pick_latest_run_receipt(runs_root: Path) -> Path:
    return pick_latest_run_receipt(runs_root)


def _resolve_run_receipt(runs_root: Path, run_id: Optional[str]) -> tuple[Path, dict]:
    if run_id:
        receipt_path = runs_root / run_id / "run_receipt.json"
        return receipt_path, _load_json(receipt_path)
    receipt_path = _pick_latest_run_receipt(runs_root)
    return receipt_path, _load_json(receipt_path)


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


def _schema_from_pack(schema_pack: dict, path: str) -> dict:
    node: dict = schema_pack
    for part in path.strip("#/").split("/"):
        node = node[part]
    schema: dict = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": schema_pack.get("$id", ""),
        "$defs": schema_pack.get("$defs", {}),
    }
    schema.update(node)
    return schema


def _item_schema(item: dict) -> dict:
    if "$ref" in item:
        return {"$ref": item["$ref"]}
    item_type = item.get("type")
    if item_type == "object":
        schema = {
            "type": "object",
            "properties": item.get("properties", {}),
        }
        if item.get("required"):
            schema["required"] = item["required"]
        if "additionalProperties" in item:
            schema["additionalProperties"] = item["additionalProperties"]
        return schema
    if item_type in ("string", "integer", "number", "boolean"):
        schema: dict = {"type": item_type}
        for key in (
            "pattern",
            "minimum",
            "maximum",
            "exclusiveMinimum",
            "exclusiveMaximum",
            "enum",
            "minLength",
            "maxLength",
        ):
            if key in item:
                schema[key] = item[key]
        return schema
    raise InputResolutionError(f"Unsupported array item type '{item_type}' for receipt schema.")


def _column_schema(column: dict) -> dict:
    if "$ref" in column:
        schema: dict = {"$ref": column["$ref"]}
    else:
        col_type = column.get("type")
        if col_type == "array":
            items = column.get("items") or {}
            schema = {"type": "array", "items": _item_schema(items)}
        elif col_type in ("string", "integer", "number", "boolean"):
            schema = {"type": col_type}
        else:
            raise InputResolutionError(f"Unsupported column type '{col_type}' for receipt schema.")
    if column.get("nullable"):
        schema = {"anyOf": [schema, {"type": "null"}]}
    return schema


def _table_row_schema(schema_pack: dict, path: str) -> dict:
    node: dict = schema_pack
    for part in path.strip("#/").split("/"):
        node = node[part]
    columns = node.get("columns") or []
    properties = {}
    required = []
    for column in columns:
        name = column.get("name")
        if not name:
            raise InputResolutionError(f"Column missing name in {path}.")
        properties[name] = _column_schema(column)
        required.append(name)
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": schema_pack.get("$id", ""),
        "$defs": schema_pack.get("$defs", {}),
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def _validate_payload(schema_pack: dict, path: str, payload: dict) -> None:
    schema = _schema_from_pack(schema_pack, path)
    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(payload))
    if errors:
        detail = errors[0].message if errors else "schema validation failed"
        raise SchemaValidationError(detail, [{"message": detail}])


def _parse_s4_policy(policy_payload: dict) -> S4AllocPolicy:
    reroute = policy_payload.get("reroute") or {}
    residual = policy_payload.get("residual_redistribution") or {}
    diversify = policy_payload.get("support_diversification") or {}
    return S4AllocPolicy(
        policy_version=str(policy_payload.get("policy_version") or "unknown"),
        enabled=bool(policy_payload.get("enabled", False)),
        country_share_soft_guard=float(policy_payload.get("country_share_soft_guard", 1.0)),
        country_share_hard_guard=float(policy_payload.get("country_share_hard_guard", 1.0)),
        reroute_enabled=bool(reroute.get("enabled", False)),
        reroute_mode=str(reroute.get("mode") or "next_eligible"),
        max_moves_per_pair=int(reroute.get("max_moves_per_pair", 0)),
        residual_enabled=bool(residual.get("enabled", False)),
        min_active_tile_fraction=float(residual.get("min_active_tile_fraction", 0.0)),
        max_steps_per_pair=int(residual.get("max_steps_per_pair", 0)),
        diversify_enabled=bool(diversify.get("enabled", False)),
        diversify_apply_n_sites_max=int(diversify.get("apply_n_sites_max", 0)),
        diversify_candidate_window_fraction=float(diversify.get("candidate_window_fraction", 0.0)),
        diversify_candidate_window_min=int(diversify.get("candidate_window_min", 0)),
        deterministic_seed_namespace=str(
            policy_payload.get("deterministic_seed_namespace") or "1B.S4.ANTI_COLLAPSE"
        ),
    )


def _summary_stats(values: list[float]) -> dict[str, float]:
    if not values:
        return {"p50": 0.0, "p90": 0.0, "p99": 0.0, "mean": 0.0}
    arr = np.array(values, dtype=np.float64)
    return {
        "p50": float(np.quantile(arr, 0.50)),
        "p90": float(np.quantile(arr, 0.90)),
        "p99": float(np.quantile(arr, 0.99)),
        "mean": float(arr.mean()),
    }


def _hhi_from_counts(counts: np.ndarray) -> float:
    total = int(np.sum(counts))
    if total <= 0:
        return 0.0
    shares = counts.astype(np.float64) / float(total)
    return float(np.sum(shares * shares))


def _top1_share_from_counts(counts: np.ndarray) -> float:
    total = int(np.sum(counts))
    if total <= 0:
        return 0.0
    return float(np.max(counts) / float(total))


def _apply_anticollapse_controls(
    counts_in: np.ndarray,
    weight_fp: np.ndarray,
    tile_ids: np.ndarray,
    n_sites: int,
    policy: S4AllocPolicy,
) -> tuple[np.ndarray, dict[str, Any]]:
    counts = counts_in.astype(np.int64, copy=True)
    pair_total = int(n_sites)
    pre_top1 = _top1_share_from_counts(counts)
    pre_hhi = _hhi_from_counts(counts)
    pre_active = int(np.count_nonzero(counts))
    moves_soft = 0
    moves_residual = 0

    if (
        policy.enabled
        and pair_total > 1
        and counts.size > 1
        and policy.country_share_soft_guard < 1.0
        and policy.reroute_enabled
        and policy.max_moves_per_pair > 0
    ):
        max_soft = max(1, int(np.ceil(policy.country_share_soft_guard * pair_total)))
        max_hard = max(max_soft, int(np.ceil(policy.country_share_hard_guard * pair_total)))
        weight_i64 = weight_fp.astype(np.int64, copy=False)
        rank = np.lexsort((tile_ids, -weight_i64))
        rank_pos = np.empty(rank.size, dtype=np.int64)
        rank_pos[rank] = np.arange(rank.size, dtype=np.int64)

        while moves_soft < policy.max_moves_per_pair:
            donors = np.flatnonzero(counts > max_soft)
            if donors.size == 0:
                break
            donor = donors[
                np.lexsort(
                    (
                        tile_ids[donors],
                        -weight_i64[donors],
                        -counts[donors],
                    )
                )[0]
            ]
            donor_rank = int(rank_pos[donor])
            moved = False
            for step in range(1, rank.size + 1):
                receiver = int(rank[(donor_rank + step) % rank.size])
                if receiver == donor:
                    continue
                if counts[receiver] + 1 > max_hard:
                    continue
                counts[donor] -= 1
                counts[receiver] += 1
                moves_soft += 1
                moved = True
                break
            if not moved:
                break

    if (
        policy.enabled
        and pair_total > 1
        and counts.size > 1
        and policy.residual_enabled
        and policy.min_active_tile_fraction > 0.0
        and policy.max_steps_per_pair > 0
    ):
        max_active_possible = int(min(pair_total, counts.size))
        target_active = int(
            min(
                max_active_possible,
                max(
                    1,
                    np.ceil(policy.min_active_tile_fraction * max_active_possible),
                ),
            )
        )
        max_hard = max(1, int(np.ceil(policy.country_share_hard_guard * pair_total)))
        weight_i64 = weight_fp.astype(np.int64, copy=False)
        for _ in range(policy.max_steps_per_pair):
            active_now = int(np.count_nonzero(counts))
            if active_now >= target_active:
                break
            donor_candidates = np.flatnonzero(counts > 1)
            receiver_candidates = np.flatnonzero(counts == 0)
            if donor_candidates.size == 0 or receiver_candidates.size == 0:
                break
            donor = donor_candidates[
                np.lexsort(
                    (
                        tile_ids[donor_candidates],
                        -weight_i64[donor_candidates],
                        -counts[donor_candidates],
                    )
                )[0]
            ]
            receiver = receiver_candidates[
                np.lexsort((tile_ids[receiver_candidates], -weight_i64[receiver_candidates]))[0]
            ]
            if counts[receiver] + 1 > max_hard:
                break
            counts[donor] -= 1
            counts[receiver] += 1
            moves_residual += 1

    post_top1 = _top1_share_from_counts(counts)
    post_hhi = _hhi_from_counts(counts)
    post_active = int(np.count_nonzero(counts))
    diagnostics = {
        "pair_top1_pre": float(pre_top1),
        "pair_top1_post": float(post_top1),
        "pair_hhi_pre": float(pre_hhi),
        "pair_hhi_post": float(post_hhi),
        "pair_active_tiles_pre": int(pre_active),
        "pair_active_tiles_post": int(post_active),
        "moves_soft": int(moves_soft),
        "moves_residual": int(moves_residual),
    }
    return counts, diagnostics


def _rotation_offset(namespace: str, merchant_id: int, legal_country_iso: str, modulo: int) -> int:
    if modulo <= 1:
        return 0
    material = f"{namespace}|{merchant_id}|{legal_country_iso}".encode("utf-8")
    digest = hashlib.sha256(material).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False) % modulo


def _select_shortfall_bump_indices(
    *,
    tile_ids: np.ndarray,
    residues_i64: np.ndarray,
    shortfall: int,
    n_sites: int,
    merchant_id: int,
    legal_country_iso: str,
    policy: S4AllocPolicy,
) -> tuple[np.ndarray, bool]:
    base_order = np.lexsort((tile_ids, -residues_i64))
    if shortfall <= 0:
        return base_order[:0], False
    if (
        not policy.enabled
        or not policy.diversify_enabled
        or policy.diversify_apply_n_sites_max <= 0
        or n_sites > policy.diversify_apply_n_sites_max
    ):
        return base_order[:shortfall], False

    window_min = max(shortfall, policy.diversify_candidate_window_min)
    window_frac = int(np.ceil(policy.diversify_candidate_window_fraction * float(base_order.size)))
    window = max(window_min, window_frac)
    window = min(window, int(base_order.size))
    if window <= shortfall:
        return base_order[:shortfall], False

    candidates = base_order[:window]
    offset = _rotation_offset(
        policy.deterministic_seed_namespace,
        merchant_id,
        legal_country_iso,
        window,
    )
    if offset == 0:
        return candidates[:shortfall], True
    rotated = np.concatenate((candidates[offset:], candidates[:offset]))
    return rotated[:shortfall], True


def _emit_failure_event(
    logger,
    code: str,
    seed: int,
    manifest_fingerprint: str,
    parameter_hash: str,
    detail: dict,
) -> None:
    payload = {
        "event": "S4_ERROR",
        "code": code,
        "at": utc_now_rfc3339_micro(),
        "seed": seed,
        "manifest_fingerprint": manifest_fingerprint,
        "parameter_hash": parameter_hash,
    }
    payload.update(detail)
    logger.error("S4_ERROR %s", json.dumps(payload, ensure_ascii=True, sort_keys=True))


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


def _atomic_publish_dir(
    tmp_root: Path,
    final_root: Path,
    logger,
    label: str,
) -> None:
    if final_root.exists():
        tmp_hash, _ = _hash_partition(tmp_root)
        final_hash, _ = _hash_partition(final_root)
        if tmp_hash != final_hash:
            raise EngineFailure(
                "F4",
                "E_IMMUTABLE_PARTITION_EXISTS_NONIDENTICAL",
                "S4",
                MODULE_NAME,
                {"detail": "partition_exists_nonidentical", "dataset": label},
            )
        logger.info("S4: %s partition already exists with identical bytes", label)
        return
    final_root.parent.mkdir(parents=True, exist_ok=True)
    tmp_root.replace(final_root)


def _select_open_files_counter(proc: psutil.Process) -> tuple[Callable[[], int], str]:
    def _open_files() -> int:
        return len(proc.open_files())

    try:
        _open_files()
        return _open_files, "open_files"
    except Exception:
        if hasattr(proc, "num_handles"):
            return proc.num_handles, "handles"
        if hasattr(proc, "num_fds"):
            return proc.num_fds, "fds"
        return lambda: 0, "unknown"


def _entry_version(entry: dict) -> Optional[str]:
    version = entry.get("version")
    if not version or not isinstance(version, str):
        return None
    if "{" in version:
        return None
    return version


def _list_parquet_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    if not root.exists():
        raise InputResolutionError(f"Dataset path does not exist: {root}")
    files = sorted([path for path in root.rglob("*.parquet") if path.is_file()])
    if files:
        return files
    raise InputResolutionError(f"No parquet files found under dataset path: {root}")


def _tile_index_files(tile_index_root: Path, country_iso: str) -> list[Path]:
    country_root = tile_index_root / f"country={country_iso}"
    if country_root.exists():
        return _list_parquet_files(country_root)
    return []


def _tile_weight_files(tile_weights_root: Path, country_iso: str) -> list[Path]:
    if tile_weights_root.is_file():
        return [tile_weights_root]
    direct = tile_weights_root / f"part-{country_iso}.parquet"
    if direct.exists():
        return [direct]
    country_root = tile_weights_root / f"country={country_iso}"
    if country_root.exists():
        return _list_parquet_files(country_root)
    matches = [
        path
        for path in tile_weights_root.rglob("*.parquet")
        if f"part-{country_iso}" in path.name or f"country={country_iso}" in path.as_posix()
    ]
    return sorted(matches)


def _load_tile_index_country(
    tile_index_root: Path,
    country_iso: str,
) -> tuple[np.ndarray, int]:
    files = _tile_index_files(tile_index_root, country_iso)
    if not files:
        return np.array([], dtype=np.uint64), 0
    bytes_total = sum(path.stat().st_size for path in files)
    arrays = []
    if _HAVE_PYARROW:
        for path in files:
            pf = pq.ParquetFile(path)
            try:
                for rg in range(pf.num_row_groups):
                    table = pf.read_row_group(rg, columns=["tile_id"])
                    arrays.append(table.column("tile_id").to_numpy(zero_copy_only=False))
            finally:
                _close_parquet_reader(pf)
    else:
        for path in files:
            df = pl.read_parquet(path, columns=["tile_id"])
            arrays.append(df.get_column("tile_id").to_numpy())
    if not arrays:
        return np.array([], dtype=np.uint64), bytes_total
    return np.concatenate(arrays).astype(np.uint64, copy=False), bytes_total


def _load_tile_weights_country(
    tile_weights_root: Path,
    country_iso: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, int]:
    files = _tile_weight_files(tile_weights_root, country_iso)
    if not files:
        return (
            np.array([], dtype=np.uint64),
            np.array([], dtype=np.int64),
            np.array([], dtype=np.int64),
            0,
        )
    bytes_total = sum(path.stat().st_size for path in files)
    tile_ids = []
    weight_fp = []
    dp_values = []
    if _HAVE_PYARROW:
        for path in files:
            pf = pq.ParquetFile(path)
            try:
                for rg in range(pf.num_row_groups):
                    table = pf.read_row_group(rg, columns=["country_iso", "tile_id", "weight_fp", "dp"])
                    if "country_iso" in table.column_names:
                        countries = table.column("country_iso")
                        bad_country = pc.any(
                            pc.or_(
                                pc.is_null(countries),
                                pc.not_equal(countries, country_iso),
                            )
                        ).as_py()
                        if bad_country:
                            raise InputResolutionError(
                                f"tile_weights row country mismatch for {country_iso} in {path}"
                            )
                    tile_ids.append(table.column("tile_id").to_numpy(zero_copy_only=False))
                    weight_fp.append(table.column("weight_fp").to_numpy(zero_copy_only=False))
                    dp_values.append(table.column("dp").to_numpy(zero_copy_only=False))
            finally:
                _close_parquet_reader(pf)
    else:
        for path in files:
            df = pl.read_parquet(path, columns=["country_iso", "tile_id", "weight_fp", "dp"])
            if "country_iso" in df.columns:
                mismatched = df.filter(pl.col("country_iso") != country_iso)
                if mismatched.height > 0:
                    raise InputResolutionError(
                        f"tile_weights row country mismatch for {country_iso} in {path}"
                    )
            tile_ids.append(df.get_column("tile_id").to_numpy())
            weight_fp.append(df.get_column("weight_fp").to_numpy())
            dp_values.append(df.get_column("dp").to_numpy())
    if not tile_ids:
        return (
            np.array([], dtype=np.uint64),
            np.array([], dtype=np.int64),
            np.array([], dtype=np.int64),
            bytes_total,
        )
    tile_ids_arr = np.concatenate(tile_ids).astype(np.uint64, copy=False)
    weight_fp_arr = np.concatenate(weight_fp).astype(np.int64, copy=False)
    dp_arr = np.concatenate(dp_values).astype(np.int64, copy=False)
    return tile_ids_arr, weight_fp_arr, dp_arr, bytes_total


def _write_batch(
    batch_rows: list[tuple[int, str, int, int]],
    batch_index: int,
    output_root: Path,
    logger,
) -> None:
    if not batch_rows:
        return
    part_path = output_root / f"part-{batch_index:05d}.parquet"
    merchant_ids, country_isos, tile_ids, n_sites_tile = zip(*batch_rows)
    data = {
        "merchant_id": np.array(merchant_ids, dtype=np.uint64),
        "legal_country_iso": np.array(country_isos, dtype=object),
        "tile_id": np.array(tile_ids, dtype=np.uint64),
        "n_sites_tile": np.array(n_sites_tile, dtype=np.int64),
    }
    if _HAVE_PYARROW:
        import pyarrow as pa

        table = pa.Table.from_pydict(data)
        pq.write_table(table, part_path, compression="zstd", row_group_size=200000)
    else:
        df = pl.DataFrame(data)
        df.write_parquet(part_path, compression="zstd", row_group_size=200000)
    logger.info("S4: wrote %d rows to %s", len(batch_rows), part_path)


def run_s4(config: EngineConfig, run_id: Optional[str] = None) -> S4Result:
    logger = get_logger("engine.layers.l1.seg_1B.s4_alloc_plan.l2.runner")
    timer = _StepTimer(logger)

    receipt_path, receipt = _resolve_run_receipt(config.runs_root, run_id)
    run_id = receipt.get("run_id")
    if not run_id:
        raise InputResolutionError("run_receipt missing run_id.")
    if receipt_path.parent.name != run_id:
        raise InputResolutionError("run_receipt path does not match embedded run_id.")
    seed = int(receipt.get("seed"))
    parameter_hash = receipt.get("parameter_hash")
    manifest_fingerprint = receipt.get("manifest_fingerprint")
    if not parameter_hash or not manifest_fingerprint:
        raise InputResolutionError("run_receipt missing parameter_hash or manifest_fingerprint.")

    run_paths = RunPaths(config.runs_root, run_id)
    run_log_path = run_paths.run_root / f"run_log_{run_id}.log"
    add_file_handler(run_log_path)

    source = ContractSource(config.contracts_root, config.contracts_layout)
    dict_path, dictionary = load_dataset_dictionary(source, "1B")
    schema_1b_path, schema_1b = load_schema_pack(source, "1B", "1B")
    logger.info(
        "Contracts layout=%s root=%s dictionary=%s schemas=%s",
        config.contracts_layout,
        config.contracts_root,
        dict_path,
        schema_1b_path,
    )

    tokens = {
        "seed": str(seed),
        "parameter_hash": str(parameter_hash),
        "manifest_fingerprint": str(manifest_fingerprint),
        "run_id": str(run_id),
    }
    external_roots = config.external_roots or (config.repo_root,)

    receipt_entry = find_dataset_entry(dictionary, "s0_gate_receipt_1B").entry
    s3_entry = find_dataset_entry(dictionary, "s3_requirements").entry
    policy_entry = find_dataset_entry(dictionary, "s4_alloc_plan_policy").entry
    tile_weights_entry = find_dataset_entry(dictionary, "tile_weights").entry
    tile_index_entry = find_dataset_entry(dictionary, "tile_index").entry
    iso_entry = find_dataset_entry(dictionary, "iso3166_canonical_2024").entry
    alloc_plan_entry = find_dataset_entry(dictionary, "s4_alloc_plan").entry
    run_report_entry = find_dataset_entry(dictionary, "s4_run_report").entry

    receipt_path = _resolve_dataset_path(receipt_entry, run_paths, external_roots, tokens)
    if not receipt_path.exists():
        _emit_failure_event(
            logger,
            "E301_NO_PASS_FLAG",
            seed,
            manifest_fingerprint,
            str(parameter_hash),
            {"detail": "s0_gate_receipt_missing", "path": str(receipt_path)},
        )
        raise EngineFailure(
            "F4",
            "E301_NO_PASS_FLAG",
            "S4",
            MODULE_NAME,
            {"path": str(receipt_path)},
        )

    receipt_payload = _load_json(receipt_path)
    try:
        receipt_schema = _table_row_schema(schema_1b, "validation/s0_gate_receipt")
        validator = Draft202012Validator(receipt_schema)
        errors = list(validator.iter_errors(receipt_payload))
        if errors:
            raise SchemaValidationError(errors[0].message, [{"message": errors[0].message}])
    except SchemaValidationError as exc:
        _emit_failure_event(
            logger,
            "E_RECEIPT_SCHEMA_INVALID",
            seed,
            manifest_fingerprint,
            str(parameter_hash),
            {"detail": str(exc)},
        )
        raise EngineFailure(
            "F4",
            "E_RECEIPT_SCHEMA_INVALID",
            "S4",
            MODULE_NAME,
            {"detail": str(exc)},
        ) from exc

    if receipt_payload.get("manifest_fingerprint") != manifest_fingerprint:
        _emit_failure_event(
            logger,
            "E406_TOKEN_MISMATCH",
            seed,
            manifest_fingerprint,
            str(parameter_hash),
            {"detail": "receipt_manifest_fingerprint_mismatch"},
        )
        raise EngineFailure(
            "F4",
            "E406_TOKEN_MISMATCH",
            "S4",
            MODULE_NAME,
            {"detail": "receipt_manifest_fingerprint_mismatch"},
        )

    sealed_inputs = receipt_payload.get("sealed_inputs") or []
    sealed_ids = {entry.get("id") for entry in sealed_inputs if isinstance(entry, dict)}
    required_sealed = {"s3_requirements", "tile_weights", "tile_index", "iso3166_canonical_2024"}
    missing_sealed = sorted(required_sealed - sealed_ids)
    if missing_sealed:
        _emit_failure_event(
            logger,
            "E409_DISALLOWED_READ",
            seed,
            manifest_fingerprint,
            str(parameter_hash),
            {"detail": "sealed_inputs_missing", "missing": missing_sealed},
        )
        raise EngineFailure(
            "F4",
            "E409_DISALLOWED_READ",
            "S4",
            MODULE_NAME,
            {"detail": "sealed_inputs_missing", "missing": missing_sealed},
        )
    logger.info(
        "S4: gate receipt verified; sealed_inputs=%d (authorizes S3 requirements + tile assets)",
        len(sealed_inputs),
    )

    s3_root = _resolve_dataset_path(s3_entry, run_paths, external_roots, tokens)
    tile_weights_root = _resolve_dataset_path(
        tile_weights_entry,
        run_paths,
        external_roots,
        {"parameter_hash": str(parameter_hash)},
    )
    tile_index_root = _resolve_dataset_path(
        tile_index_entry,
        run_paths,
        external_roots,
        {"parameter_hash": str(parameter_hash)},
    )
    iso_path = _resolve_dataset_path(iso_entry, run_paths, external_roots, {})
    alloc_plan_root = _resolve_dataset_path(alloc_plan_entry, run_paths, external_roots, tokens)
    run_report_path = _resolve_dataset_path(run_report_entry, run_paths, external_roots, tokens)
    policy_path = _resolve_dataset_path(policy_entry, run_paths, external_roots, {})

    policy_payload = _load_yaml(policy_path)
    _validate_payload(schema_1b, "#/policy/s4_alloc_plan_policy", policy_payload)
    s4_policy = _parse_s4_policy(policy_payload)
    logger.info(
        "S4: loaded anti-collapse policy enabled=%s soft_guard=%.4f hard_guard=%.4f reroute=%s residual=%s diversify=%s path=%s",
        s4_policy.enabled,
        s4_policy.country_share_soft_guard,
        s4_policy.country_share_hard_guard,
        s4_policy.reroute_enabled,
        s4_policy.residual_enabled,
        s4_policy.diversify_enabled,
        policy_path,
    )

    if not s3_root.exists():
        _emit_failure_event(
            logger,
            "E401_NO_S3_REQUIREMENTS",
            seed,
            manifest_fingerprint,
            str(parameter_hash),
            {"detail": "s3_requirements_missing", "path": str(s3_root)},
        )
        raise EngineFailure(
            "F4",
            "E401_NO_S3_REQUIREMENTS",
            "S4",
            MODULE_NAME,
            {"path": str(s3_root)},
        )

    logger.info("S4: allocation inputs resolved (s3_requirements + tile_weights + tile_index)")

    iso_df = pl.read_parquet(iso_path, columns=["country_iso"])
    iso_set = set(iso_df.get_column("country_iso").to_list())
    logger.info("S4: ISO domain loaded (count=%d) for country validation", len(iso_set))
    ingress_versions = {"iso3166": _entry_version(iso_entry) or ""}

    s3_files = _list_parquet_files(s3_root)
    bytes_read_s3_total = sum(path.stat().st_size for path in s3_files)
    logger.info(
        "S4: s3_requirements files=%d bytes=%d (merchant-country requirements)",
        len(s3_files),
        bytes_read_s3_total,
    )
    logger.info("S4: read mode=%s", "pyarrow" if _HAVE_PYARROW else "polars")

    total_pairs: Optional[int] = None
    if _HAVE_PYARROW:
        total_pairs = 0
        for path in s3_files:
            pf = pq.ParquetFile(path)
            try:
                total_pairs += pf.metadata.num_rows
            finally:
                _close_parquet_reader(pf)
        logger.info("S4: s3_requirements rows=%d (merchant-country pairs)", total_pairs)

    tracker = _ProgressTracker(
        total_pairs,
        logger,
        "S4 allocation progress pairs_processed (merchant-country requirements)",
    )

    run_paths.tmp_root.mkdir(parents=True, exist_ok=True)
    alloc_plan_tmp = run_paths.tmp_root / f"s4_alloc_plan_{uuid.uuid4().hex}"
    alloc_plan_tmp.mkdir(parents=True, exist_ok=True)

    wall_start = time.monotonic()
    cpu_start = time.process_time()
    proc = psutil.Process()
    open_files_counter, open_files_metric = _select_open_files_counter(proc)
    max_rss = proc.memory_info().rss
    open_files_peak = open_files_counter()
    logger.info("S4: PAT open_files metric=%s", open_files_metric)
    timer.info("S4: starting allocation loop (per pair -> tile plan rows)")

    batch_rows: list[tuple[int, str, int, int]] = []
    batch_index = 0

    last_key: Optional[tuple[int, str, int]] = None
    last_pair: Optional[tuple[int, str]] = None
    merchants_total = 0
    pairs_total = 0
    rows_emitted = 0
    ties_broken_total = 0
    alloc_sum_equals_requirements = True
    guard_moves_soft_total = 0
    guard_moves_residual_total = 0
    pairs_guard_touched = 0
    diversify_pairs_touched = 0
    diversify_bumps_total = 0
    pre_top1_values: list[float] = []
    post_top1_values: list[float] = []
    pre_hhi_values: list[float] = []
    post_hhi_values: list[float] = []
    pre_active_tile_values: list[float] = []
    post_active_tile_values: list[float] = []

    bytes_read_weights_total = 0
    bytes_read_index_total = 0

    dp_global: Optional[int] = None

    cache: OrderedDict[str, dict] = OrderedDict()
    seen_countries: set[str] = set()
    cache_hits = 0
    cache_misses = 0
    cache_evictions = 0
    heartbeat_last = time.monotonic()
    heartbeat_check_step = max(500, int((total_pairs or 5000) / 10))
    heartbeat_interval = 3.0

    def _load_country_assets(country_iso: str) -> dict:
        nonlocal bytes_read_weights_total
        nonlocal bytes_read_index_total
        nonlocal dp_global
        nonlocal max_rss
        nonlocal open_files_peak
        nonlocal cache_hits
        nonlocal cache_misses
        nonlocal cache_evictions
        if country_iso in cache:
            cache_hits += 1
            cache.move_to_end(country_iso)
            return cache[country_iso]

        cache_misses += 1
        tile_index_ids, bytes_index = _load_tile_index_country(tile_index_root, country_iso)
        bytes_read_index_total += bytes_index
        if tile_index_ids.size == 0:
            _emit_failure_event(
                logger,
                "E403_ZERO_TILE_UNIVERSE",
                seed,
                manifest_fingerprint,
                str(parameter_hash),
                {"legal_country_iso": country_iso},
            )
            raise EngineFailure(
                "F4",
                "E403_ZERO_TILE_UNIVERSE",
                "S4",
                MODULE_NAME,
                {"legal_country_iso": country_iso},
            )

        weight_tile_ids, weight_fp, dp_values, bytes_weights = _load_tile_weights_country(
            tile_weights_root, country_iso
        )
        bytes_read_weights_total += bytes_weights
        if weight_tile_ids.size == 0:
            _emit_failure_event(
                logger,
                "E402_MISSING_TILE_WEIGHTS",
                seed,
                manifest_fingerprint,
                str(parameter_hash),
                {"legal_country_iso": country_iso},
            )
            raise EngineFailure(
                "F4",
                "E402_MISSING_TILE_WEIGHTS",
                "S4",
                MODULE_NAME,
                {"legal_country_iso": country_iso},
            )

        if dp_values.size == 0:
            _emit_failure_event(
                logger,
                "E414_WEIGHT_TAMPER",
                seed,
                manifest_fingerprint,
                str(parameter_hash),
                {"detail": "dp_missing", "legal_country_iso": country_iso},
            )
            raise EngineFailure(
                "F4",
                "E414_WEIGHT_TAMPER",
                "S4",
                MODULE_NAME,
                {"detail": "dp_missing", "legal_country_iso": country_iso},
            )

        dp_unique = np.unique(dp_values)
        if dp_unique.size != 1:
            _emit_failure_event(
                logger,
                "E414_WEIGHT_TAMPER",
                seed,
                manifest_fingerprint,
                str(parameter_hash),
                {"detail": "dp_inconsistent", "legal_country_iso": country_iso},
            )
            raise EngineFailure(
                "F4",
                "E414_WEIGHT_TAMPER",
                "S4",
                MODULE_NAME,
                {"detail": "dp_inconsistent", "legal_country_iso": country_iso},
            )

        dp_value = int(dp_unique[0])
        if dp_global is None:
            dp_global = dp_value
        elif dp_value != dp_global:
            _emit_failure_event(
                logger,
                "E414_WEIGHT_TAMPER",
                seed,
                manifest_fingerprint,
                str(parameter_hash),
                {"detail": "dp_mismatch", "legal_country_iso": country_iso, "dp": int(dp_value)},
            )
            raise EngineFailure(
                "F4",
                "E414_WEIGHT_TAMPER",
                "S4",
                MODULE_NAME,
                {"detail": "dp_mismatch", "legal_country_iso": country_iso},
            )

        tile_index_sorted = np.sort(tile_index_ids)
        if tile_index_sorted.size > 1 and np.any(tile_index_sorted[1:] == tile_index_sorted[:-1]):
            _emit_failure_event(
                logger,
                "E407_PK_DUPLICATE",
                seed,
                manifest_fingerprint,
                str(parameter_hash),
                {"detail": "tile_index_duplicate_tile_id", "legal_country_iso": country_iso},
            )
            raise EngineFailure(
                "F4",
                "E407_PK_DUPLICATE",
                "S4",
                MODULE_NAME,
                {"detail": "tile_index_duplicate_tile_id", "legal_country_iso": country_iso},
            )

        order = np.argsort(weight_tile_ids)
        weight_tile_sorted = weight_tile_ids[order]
        weight_fp_sorted = weight_fp[order]
        if weight_tile_sorted.size > 1 and np.any(weight_tile_sorted[1:] == weight_tile_sorted[:-1]):
            _emit_failure_event(
                logger,
                "E407_PK_DUPLICATE",
                seed,
                manifest_fingerprint,
                str(parameter_hash),
                {"detail": "tile_weights_duplicate_tile_id", "legal_country_iso": country_iso},
            )
            raise EngineFailure(
                "F4",
                "E407_PK_DUPLICATE",
                "S4",
                MODULE_NAME,
                {"detail": "tile_weights_duplicate_tile_id", "legal_country_iso": country_iso},
            )

        if weight_tile_sorted.size != tile_index_sorted.size or not np.array_equal(
            weight_tile_sorted, tile_index_sorted
        ):
            missing = np.setdiff1d(tile_index_sorted, weight_tile_sorted, assume_unique=True)
            extra = np.setdiff1d(weight_tile_sorted, tile_index_sorted, assume_unique=True)
            if missing.size > 0:
                _emit_failure_event(
                    logger,
                    "E402_MISSING_TILE_WEIGHTS",
                    seed,
                    manifest_fingerprint,
                    str(parameter_hash),
                    {
                        "detail": "tile_weights_missing_tile_ids",
                        "legal_country_iso": country_iso,
                        "missing_count": int(missing.size),
                    },
                )
                raise EngineFailure(
                    "F4",
                    "E402_MISSING_TILE_WEIGHTS",
                    "S4",
                    MODULE_NAME,
                    {"legal_country_iso": country_iso},
                )
            if extra.size > 0:
                _emit_failure_event(
                    logger,
                    "E413_TILE_NOT_IN_INDEX",
                    seed,
                    manifest_fingerprint,
                    str(parameter_hash),
                    {
                        "detail": "tile_weights_extra_tile_ids",
                        "legal_country_iso": country_iso,
                        "extra_count": int(extra.size),
                    },
                )
                raise EngineFailure(
                    "F4",
                    "E413_TILE_NOT_IN_INDEX",
                    "S4",
                    MODULE_NAME,
                    {"legal_country_iso": country_iso},
                )

        if country_iso not in seen_countries:
            logger.info(
                "S4: loaded country assets country=%s tiles=%d dp=%d bytes_index=%d bytes_weights=%d cache=%d",
                country_iso,
                weight_tile_sorted.size,
                dp_value,
                bytes_index,
                bytes_weights,
                len(cache) + 1,
            )
            seen_countries.add(country_iso)
        rss_now = proc.memory_info().rss
        max_rss = max(max_rss, rss_now)
        open_files_peak = max(open_files_peak, open_files_counter())

        payload = {
            "tile_ids": weight_tile_sorted,
            "weight_fp": weight_fp_sorted,
            "dp": int(dp_value),
        }
        cache[country_iso] = payload
        cache.move_to_end(country_iso)
        if len(cache) > CACHE_COUNTRIES_MAX:
            cache.popitem(last=False)
            cache_evictions += 1
        return payload

    def _flush_batch() -> None:
        nonlocal batch_index, batch_rows
        if not batch_rows:
            return
        _write_batch(batch_rows, batch_index, alloc_plan_tmp, logger)
        batch_index += 1
        batch_rows = []

    def _emit_rows(
        merchant_id: int,
        legal_country_iso: str,
        tile_ids: np.ndarray,
        weight_fp: np.ndarray,
        dp_value: int,
        n_sites: int,
    ) -> None:
        nonlocal batch_rows, rows_emitted, ties_broken_total, alloc_sum_equals_requirements, last_key
        nonlocal guard_moves_soft_total, guard_moves_residual_total, pairs_guard_touched
        nonlocal diversify_pairs_touched, diversify_bumps_total
        nonlocal pre_top1_values, post_top1_values, pre_hhi_values, post_hhi_values
        nonlocal pre_active_tile_values, post_active_tile_values

        K = 10 ** int(dp_value)
        weight_fp_obj = weight_fp.astype(object)
        prod = weight_fp_obj * int(n_sites)
        z = prod // K
        rnum = prod % K

        base_sum = int(np.sum(z))
        shortfall = int(n_sites) - base_sum
        if shortfall < 0:
            _emit_failure_event(
                logger,
                "E404_ALLOCATION_MISMATCH",
                seed,
                manifest_fingerprint,
                str(parameter_hash),
                {"merchant_id": merchant_id, "legal_country_iso": legal_country_iso},
            )
            raise EngineFailure(
                "F4",
                "E404_ALLOCATION_MISMATCH",
                "S4",
                MODULE_NAME,
                {"merchant_id": merchant_id, "legal_country_iso": legal_country_iso},
            )

        if shortfall > 0:
            rnum_int = np.array(rnum, dtype=np.int64)
            bump_idx, diversified = _select_shortfall_bump_indices(
                tile_ids=tile_ids,
                residues_i64=rnum_int,
                shortfall=int(shortfall),
                n_sites=int(n_sites),
                merchant_id=int(merchant_id),
                legal_country_iso=str(legal_country_iso),
                policy=s4_policy,
            )
            bump = np.zeros(tile_ids.size, dtype=object)
            bump[bump_idx] = 1
            n_sites_tile = z + bump
            ties_broken_total += int(shortfall)
            if diversified:
                diversify_pairs_touched += 1
                diversify_bumps_total += int(shortfall)
        else:
            n_sites_tile = z

        n_sites_tile_i64 = np.array(n_sites_tile, dtype=np.int64)
        adjusted_i64, anti_diag = _apply_anticollapse_controls(
            counts_in=n_sites_tile_i64,
            weight_fp=weight_fp,
            tile_ids=tile_ids,
            n_sites=int(n_sites),
            policy=s4_policy,
        )
        n_sites_tile = adjusted_i64.astype(object)
        pre_top1_values.append(float(anti_diag["pair_top1_pre"]))
        post_top1_values.append(float(anti_diag["pair_top1_post"]))
        pre_hhi_values.append(float(anti_diag["pair_hhi_pre"]))
        post_hhi_values.append(float(anti_diag["pair_hhi_post"]))
        pre_active_tile_values.append(float(anti_diag["pair_active_tiles_pre"]))
        post_active_tile_values.append(float(anti_diag["pair_active_tiles_post"]))
        guard_moves_soft_total += int(anti_diag["moves_soft"])
        guard_moves_residual_total += int(anti_diag["moves_residual"])
        if int(anti_diag["moves_soft"]) > 0 or int(anti_diag["moves_residual"]) > 0:
            pairs_guard_touched += 1

        total_alloc = int(np.sum(n_sites_tile))
        if total_alloc != int(n_sites):
            alloc_sum_equals_requirements = False
            _emit_failure_event(
                logger,
                "E404_ALLOCATION_MISMATCH",
                seed,
                manifest_fingerprint,
                str(parameter_hash),
                {"merchant_id": merchant_id, "legal_country_iso": legal_country_iso},
            )
            raise EngineFailure(
                "F4",
                "E404_ALLOCATION_MISMATCH",
                "S4",
                MODULE_NAME,
                {"merchant_id": merchant_id, "legal_country_iso": legal_country_iso},
            )

        mask = np.array(n_sites_tile, dtype=object) > 0
        if not np.any(mask):
            _emit_failure_event(
                logger,
                "E412_ZERO_ROW_EMITTED",
                seed,
                manifest_fingerprint,
                str(parameter_hash),
                {"merchant_id": merchant_id, "legal_country_iso": legal_country_iso},
            )
            raise EngineFailure(
                "F4",
                "E412_ZERO_ROW_EMITTED",
                "S4",
                MODULE_NAME,
                {"merchant_id": merchant_id, "legal_country_iso": legal_country_iso},
            )

        tile_ids_out = tile_ids[mask]
        n_sites_out = np.array(n_sites_tile[mask], dtype=object)
        if np.any(np.array(n_sites_out, dtype=object) <= 0):
            _emit_failure_event(
                logger,
                "E412_ZERO_ROW_EMITTED",
                seed,
                manifest_fingerprint,
                str(parameter_hash),
                {"merchant_id": merchant_id, "legal_country_iso": legal_country_iso},
            )
            raise EngineFailure(
                "F4",
                "E412_ZERO_ROW_EMITTED",
                "S4",
                MODULE_NAME,
                {"merchant_id": merchant_id, "legal_country_iso": legal_country_iso},
            )

        for tile_id, count in zip(tile_ids_out, n_sites_out):
            key = (merchant_id, legal_country_iso, int(tile_id))
            if last_key is not None and key < last_key:
                _emit_failure_event(
                    logger,
                    "E408_UNSORTED",
                    seed,
                    manifest_fingerprint,
                    str(parameter_hash),
                    {"merchant_id": merchant_id, "legal_country_iso": legal_country_iso},
                )
                raise EngineFailure(
                    "F4",
                    "E408_UNSORTED",
                    "S4",
                    MODULE_NAME,
                    {"merchant_id": merchant_id, "legal_country_iso": legal_country_iso},
                )
            last_key = key
            batch_rows.append((merchant_id, legal_country_iso, int(tile_id), int(count)))
            rows_emitted += 1
            if len(batch_rows) >= BATCH_SIZE:
                _flush_batch()

    last_req_key: Optional[tuple[int, str]] = None

    def _handle_requirement(mid: int, iso: str, n_sites: int) -> None:
        nonlocal last_req_key, last_pair, merchants_total, pairs_total, max_rss, open_files_peak, heartbeat_last
        req_key = (mid, iso)
        if last_req_key is not None and req_key < last_req_key:
            _emit_failure_event(
                logger,
                "E408_UNSORTED",
                seed,
                manifest_fingerprint,
                str(parameter_hash),
                {"detail": "s3_requirements_unsorted"},
            )
            raise EngineFailure(
                "F4",
                "E408_UNSORTED",
                "S4",
                MODULE_NAME,
                {"detail": "s3_requirements_unsorted"},
            )
        if last_req_key is not None and req_key == last_req_key:
            _emit_failure_event(
                logger,
                "E407_PK_DUPLICATE",
                seed,
                manifest_fingerprint,
                str(parameter_hash),
                {"detail": "s3_requirements_duplicate_pair"},
            )
            raise EngineFailure(
                "F4",
                "E407_PK_DUPLICATE",
                "S4",
                MODULE_NAME,
                {"detail": "s3_requirements_duplicate_pair"},
            )
        last_req_key = req_key

        if iso not in iso_set:
            _emit_failure_event(
                logger,
                "E402_MISSING_TILE_WEIGHTS",
                seed,
                manifest_fingerprint,
                str(parameter_hash),
                {"detail": "iso_fk_missing", "legal_country_iso": iso},
            )
            raise EngineFailure(
                "F4",
                "E402_MISSING_TILE_WEIGHTS",
                "S4",
                MODULE_NAME,
                {"legal_country_iso": iso},
            )

        if n_sites <= 0:
            _emit_failure_event(
                logger,
                "E405_SCHEMA_INVALID",
                seed,
                manifest_fingerprint,
                str(parameter_hash),
                {"detail": "n_sites_non_positive", "merchant_id": mid, "legal_country_iso": iso},
            )
            raise EngineFailure(
                "F4",
                "E405_SCHEMA_INVALID",
                "S4",
                MODULE_NAME,
                {"merchant_id": mid, "legal_country_iso": iso},
            )

        if last_pair is None or last_pair[0] != mid:
            merchants_total += 1
        pairs_total += 1
        last_pair = (mid, iso)

        assets = _load_country_assets(iso)
        _emit_rows(mid, iso, assets["tile_ids"], assets["weight_fp"], assets["dp"], n_sites)

        if pairs_total % heartbeat_check_step == 0:
            now = time.monotonic()
            if now - heartbeat_last >= heartbeat_interval:
                elapsed = now - wall_start
                rate = pairs_total / elapsed if elapsed > 0 else 0.0
                if total_pairs:
                    logger.info(
                        "S4 heartbeat pairs_processed=%d/%d merchants=%d rows_emitted=%d cache_hit=%d cache_miss=%d evictions=%d (elapsed=%.2fs, rate=%.2f/s)",
                        pairs_total,
                        total_pairs,
                        merchants_total,
                        rows_emitted,
                        cache_hits,
                        cache_misses,
                        cache_evictions,
                        elapsed,
                        rate,
                    )
                else:
                    logger.info(
                        "S4 heartbeat pairs_processed=%d merchants=%d rows_emitted=%d cache_hit=%d cache_miss=%d evictions=%d (elapsed=%.2fs, rate=%.2f/s)",
                        pairs_total,
                        merchants_total,
                        rows_emitted,
                        cache_hits,
                        cache_misses,
                        cache_evictions,
                        elapsed,
                        rate,
                    )
                heartbeat_last = now

        rss_now = proc.memory_info().rss
        max_rss = max(max_rss, rss_now)
        open_files_peak = max(open_files_peak, open_files_counter())

    if _HAVE_PYARROW:
        for path in s3_files:
            pf = pq.ParquetFile(path)
            try:
                for rg in range(pf.num_row_groups):
                    table = pf.read_row_group(
                        rg, columns=["merchant_id", "legal_country_iso", "n_sites"]
                    )
                    merchant_ids = table.column("merchant_id").to_numpy(zero_copy_only=False)
                    countries = table.column("legal_country_iso").to_numpy(zero_copy_only=False)
                    n_sites_arr = table.column("n_sites").to_numpy(zero_copy_only=False)
                    for mid, iso, n_sites in zip(merchant_ids, countries, n_sites_arr):
                        _handle_requirement(int(mid), str(iso), int(n_sites))
                    if tracker:
                        tracker.update(table.num_rows)
            finally:
                _close_parquet_reader(pf)
    else:
        for path in s3_files:
            df = pl.read_parquet(path, columns=["merchant_id", "legal_country_iso", "n_sites"])
            for row in df.iter_rows(named=True):
                _handle_requirement(
                    int(row["merchant_id"]),
                    str(row["legal_country_iso"]),
                    int(row["n_sites"]),
                )
            if tracker:
                tracker.update(df.height)

    _flush_batch()
    timer.info(
        "S4: allocation loop completed (pairs_total=%d merchants_total=%d rows_emitted=%d)",
        pairs_total,
        merchants_total,
        rows_emitted,
    )
    logger.info(
        "S4: cache summary hits=%d misses=%d evictions=%d unique_countries=%d",
        cache_hits,
        cache_misses,
        cache_evictions,
        len(seen_countries),
    )

    determinism_hash, determinism_bytes = _hash_partition(alloc_plan_tmp)
    determinism_receipt = {
        "partition_path": str(alloc_plan_root),
        "sha256_hex": determinism_hash,
        "bytes_hashed": determinism_bytes,
    }

    _atomic_publish_dir(alloc_plan_tmp, alloc_plan_root, logger, "s4_alloc_plan")
    logger.info(
        "S4: allocation plan ready for S5 (rows_emitted=%d, pairs_total=%d)",
        rows_emitted,
        pairs_total,
    )

    wall_total = time.monotonic() - wall_start
    cpu_total = time.process_time() - cpu_start

    anti_collapse_summary = {
        "enabled": bool(s4_policy.enabled),
        "pairs_total": int(pairs_total),
        "pairs_guard_touched": int(pairs_guard_touched),
        "guard_touched_share": float(pairs_guard_touched / pairs_total) if pairs_total > 0 else 0.0,
        "pairs_diversified_touched": int(diversify_pairs_touched),
        "diversified_touched_share": (
            float(diversify_pairs_touched / pairs_total) if pairs_total > 0 else 0.0
        ),
        "diversification_bumps_total": int(diversify_bumps_total),
        "moves_soft_total": int(guard_moves_soft_total),
        "moves_residual_total": int(guard_moves_residual_total),
        "pair_top1_pre": _summary_stats(pre_top1_values),
        "pair_top1_post": _summary_stats(post_top1_values),
        "pair_hhi_pre": _summary_stats(pre_hhi_values),
        "pair_hhi_post": _summary_stats(post_hhi_values),
        "pair_active_tiles_pre": _summary_stats(pre_active_tile_values),
        "pair_active_tiles_post": _summary_stats(post_active_tile_values),
    }

    run_report = {
        "seed": seed,
        "manifest_fingerprint": manifest_fingerprint,
        "parameter_hash": parameter_hash,
        "rows_emitted": rows_emitted,
        "merchants_total": merchants_total,
        "pairs_total": pairs_total,
        "alloc_sum_equals_requirements": alloc_sum_equals_requirements,
        "ingress_versions": ingress_versions,
        "determinism_receipt": determinism_receipt,
        "anti_collapse_policy": {
            "policy_version": s4_policy.policy_version,
            "enabled": s4_policy.enabled,
            "country_share_soft_guard": s4_policy.country_share_soft_guard,
            "country_share_hard_guard": s4_policy.country_share_hard_guard,
            "reroute": {
                "enabled": s4_policy.reroute_enabled,
                "mode": s4_policy.reroute_mode,
                "max_moves_per_pair": s4_policy.max_moves_per_pair,
            },
            "residual_redistribution": {
                "enabled": s4_policy.residual_enabled,
                "min_active_tile_fraction": s4_policy.min_active_tile_fraction,
                "max_steps_per_pair": s4_policy.max_steps_per_pair,
            },
            "support_diversification": {
                "enabled": s4_policy.diversify_enabled,
                "apply_n_sites_max": s4_policy.diversify_apply_n_sites_max,
                "candidate_window_fraction": s4_policy.diversify_candidate_window_fraction,
                "candidate_window_min": s4_policy.diversify_candidate_window_min,
            },
            "deterministic_seed_namespace": s4_policy.deterministic_seed_namespace,
        },
        "anti_collapse_diagnostics": anti_collapse_summary,
        "pat": {
            "bytes_read_s3_total": bytes_read_s3_total,
            "bytes_read_weights_total": bytes_read_weights_total,
            "bytes_read_index_total": bytes_read_index_total,
            "rows_emitted": rows_emitted,
            "pairs_total": pairs_total,
            "ties_broken_total": ties_broken_total,
            "wall_clock_seconds_total": wall_total,
            "cpu_seconds_total": cpu_total,
            "workers_used": 1,
            "max_worker_rss_bytes": max_rss,
            "open_files_peak": open_files_peak,
            "open_files_metric": open_files_metric,
        },
    }
    _validate_payload(schema_1b, "#/control/s4_run_report", run_report)
    run_report_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(run_report_path, run_report)
    timer.info("S4: run report written (allocation summary + determinism receipt)")

    return S4Result(
        run_id=str(run_id),
        parameter_hash=str(parameter_hash),
        manifest_fingerprint=str(manifest_fingerprint),
        alloc_plan_path=alloc_plan_root,
        run_report_path=run_report_path,
    )
