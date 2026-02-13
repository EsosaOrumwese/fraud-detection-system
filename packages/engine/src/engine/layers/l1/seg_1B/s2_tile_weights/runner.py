"""S2 tile weights runner for Segment 1B."""

from __future__ import annotations

import csv
import hashlib
import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Optional

import numpy as np
import polars as pl
import psutil
import rasterio
import yaml
from jsonschema import Draft202012Validator
from rasterio.windows import Window

from engine.contracts.loader import (
    find_dataset_entry,
    load_artefact_registry,
    load_dataset_dictionary,
    load_schema_pack,
)
from engine.contracts.source import ContractSource
from engine.core.config import EngineConfig
from engine.core.errors import EngineFailure, InputResolutionError, SchemaValidationError
from engine.core.logging import add_file_handler, get_logger
from engine.core.paths import RunPaths, resolve_input_path
from engine.core.time import utc_now_rfc3339_micro
from engine.core.run_receipt import pick_latest_run_receipt


MODULE_NAME = "1B.s2_tile_weights"
ALLOWED_BASIS = {"uniform", "area_m2", "population"}
TOP_FRACTIONS = {"top1": 0.01, "top5": 0.05, "top10": 0.10}
REGION_KEYS = (
    "Africa",
    "Asia",
    "Europe",
    "North America",
    "South America",
    "Oceania",
    "Other",
)


@dataclass(frozen=True)
class S2Result:
    run_id: str
    parameter_hash: str
    tile_weights_path: Path
    run_report_path: Path


@dataclass(frozen=True)
class BlendV2Policy:
    enabled: bool
    basis_mix: dict[str, float]
    region_floor_share: dict[str, float]
    country_cap_share_soft: float
    country_cap_share_hard: float
    topk_cap_targets: dict[str, float]
    concentration_penalty_strength: float
    deterministic_seed_namespace: str
    max_rebalance_iterations: int
    convergence_tolerance: float


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


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise InputResolutionError(f"Missing JSON file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        raise InputResolutionError(f"Missing YAML file: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


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


def _validate_payload(schema_pack: dict, path: str, payload: dict) -> None:
    schema = _schema_from_pack(schema_pack, path)
    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(payload))
    if errors:
        detail = errors[0].message if errors else "schema validation failed"
        raise SchemaValidationError(detail, [{"message": detail}])


def _emit_failure_event(logger, code: str, parameter_hash: str, detail: dict) -> None:
    payload = {"event": "S2_ERROR", "code": code, "at": utc_now_rfc3339_micro(), "parameter_hash": parameter_hash}
    payload.update(detail)
    logger.error("S2_ERROR %s", json.dumps(payload, ensure_ascii=True, sort_keys=True))


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
                "E108_WRITER_HYGIENE",
                "S2",
                MODULE_NAME,
                {"detail": "partition_exists_nonidentical", "dataset": label},
            )
        logger.info("S2: %s partition already exists with identical bytes", label)
        return
    final_root.parent.mkdir(parents=True, exist_ok=True)
    tmp_root.replace(final_root)


def _open_files_count(proc: psutil.Process) -> int:
    if hasattr(proc, "num_handles"):
        return proc.num_handles()
    if hasattr(proc, "num_fds"):
        return proc.num_fds()
    return 0


def _country_dirs(tile_index_root: Path) -> list[Path]:
    return sorted([path for path in tile_index_root.glob("country=*") if path.is_dir()])


def _country_from_dir(path: Path) -> str:
    name = path.name
    if "=" not in name:
        return name
    return name.split("=", 1)[1]


def _entry_version(entry: dict) -> Optional[str]:
    version = entry.get("version")
    if not version or not isinstance(version, str):
        return None
    if "{" in version:
        return None
    return version


def _safe_normalize(values: np.ndarray) -> np.ndarray:
    total = float(values.sum())
    if values.size == 0:
        return values.astype(np.float64, copy=True)
    if not np.isfinite(total) or total <= 0.0:
        return np.full(values.size, 1.0 / float(values.size), dtype=np.float64)
    return values.astype(np.float64, copy=False) / total


def _gini(values: np.ndarray) -> float:
    if values.size == 0:
        return 0.0
    clean = values[np.isfinite(values)]
    clean = clean[clean >= 0.0]
    if clean.size == 0:
        return 0.0
    ordered = np.sort(clean)
    total = float(ordered.sum())
    if total <= 0.0:
        return 0.0
    n = ordered.size
    coeffs = (2 * np.arange(1, n + 1) - n - 1).astype(np.float64)
    return float(np.dot(coeffs, ordered) / (n * total))


def _top_fraction_share(values: np.ndarray, fraction: float) -> float:
    if values.size == 0:
        return 0.0
    total = float(values.sum())
    if total <= 0.0:
        return 0.0
    k = max(1, int(np.ceil(values.size * float(fraction))))
    top = np.sort(values)[::-1][:k]
    return float(top.sum() / total)


def _macro_region(region: Optional[str], subregion: Optional[str]) -> str:
    region_s = (region or "").strip()
    subregion_s = (subregion or "").strip()
    lower_subregion = subregion_s.lower()
    if region_s in {"Africa", "Asia", "Europe", "Oceania"}:
        return region_s
    if region_s == "Americas":
        if "south" in lower_subregion or "latin america" in lower_subregion:
            return "South America"
        return "North America"
    if "south america" in lower_subregion or "latin america" in lower_subregion:
        return "South America"
    if "north america" in lower_subregion or "caribbean" in lower_subregion:
        return "North America"
    return "Other"


def _load_country_region_lookup(
    iso_path: Path,
    repo_root: Path,
) -> dict[str, str]:
    lookup: dict[str, str] = {}
    if iso_path.exists():
        iso_df = pl.read_parquet(iso_path, columns=["country_iso", "region", "subregion"])
        for row in iso_df.to_dicts():
            iso = str(row.get("country_iso") or "").strip().upper()
            if not iso:
                continue
            lookup[iso] = _macro_region(
                row.get("region") if isinstance(row, Mapping) else None,
                row.get("subregion") if isinstance(row, Mapping) else None,
            )
    if lookup and any(value != "Other" for value in lookup.values()):
        return lookup

    candidates = [
        repo_root
        / "reference"
        / "_untracked"
        / "reference"
        / "layer1"
        / "iso_canonical"
        / "v2025-10-09"
        / "iso_canonical.csv",
        repo_root
        / "reference"
        / "_untracked"
        / "reference"
        / "layer1"
        / "iso_canonical"
        / "v2025-10-08"
        / "iso_canonical.csv",
    ]
    for csv_path in candidates:
        if not csv_path.exists():
            continue
        with csv_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                iso = (row.get("country_iso") or "").strip().upper()
                if not iso:
                    continue
                lookup[iso] = _macro_region(row.get("region"), row.get("subregion"))
        if lookup:
            return lookup
    return lookup


def _parse_blend_policy(policy_payload: dict) -> BlendV2Policy:
    blend_block = policy_payload.get("blend_v2")
    if not isinstance(blend_block, dict):
        return BlendV2Policy(
            enabled=False,
            basis_mix={"uniform": 0.0, "area_m2": 0.0, "population": 0.0},
            region_floor_share={key: 0.0 for key in REGION_KEYS},
            country_cap_share_soft=1.0,
            country_cap_share_hard=1.0,
            topk_cap_targets={"top1": 1.0, "top5": 1.0, "top10": 1.0},
            concentration_penalty_strength=0.0,
            deterministic_seed_namespace="1B.S2.LEGACY",
            max_rebalance_iterations=1,
            convergence_tolerance=1.0e-9,
        )

    basis_mix_raw = blend_block.get("basis_mix") or {}
    basis_mix = {
        "uniform": float(basis_mix_raw.get("uniform", 0.0)),
        "area_m2": float(basis_mix_raw.get("area_m2", 0.0)),
        "population": float(basis_mix_raw.get("population", 0.0)),
    }
    region_floor_raw = blend_block.get("region_floor_share") or {}
    region_floor_share = {key: float(region_floor_raw.get(key, 0.0)) for key in REGION_KEYS}
    topk_raw = blend_block.get("topk_cap_targets") or {}
    topk_cap_targets = {
        "top1": float(topk_raw.get("top1", 1.0)),
        "top5": float(topk_raw.get("top5", 1.0)),
        "top10": float(topk_raw.get("top10", 1.0)),
    }
    return BlendV2Policy(
        enabled=bool(blend_block.get("enabled", False)),
        basis_mix=basis_mix,
        region_floor_share=region_floor_share,
        country_cap_share_soft=float(blend_block.get("country_cap_share_soft", 1.0)),
        country_cap_share_hard=float(blend_block.get("country_cap_share_hard", 1.0)),
        topk_cap_targets=topk_cap_targets,
        concentration_penalty_strength=float(blend_block.get("concentration_penalty_strength", 0.0)),
        deterministic_seed_namespace=str(
            blend_block.get("deterministic_seed_namespace", "1B.S2.BLEND_V2")
        ),
        max_rebalance_iterations=int(blend_block.get("max_rebalance_iterations", 24)),
        convergence_tolerance=float(blend_block.get("convergence_tolerance", 1.0e-9)),
    )


def _validate_blend_policy(blend: BlendV2Policy) -> Optional[str]:
    if not blend.enabled:
        return None
    mix_sum = float(sum(blend.basis_mix.values()))
    if mix_sum <= 0.0:
        return "basis_mix_sum_non_positive"
    if not np.isclose(mix_sum, 1.0, atol=1.0e-9):
        return "basis_mix_sum_not_one"
    if any(weight < 0.0 for weight in blend.basis_mix.values()):
        return "basis_mix_negative_component"
    if blend.country_cap_share_soft > blend.country_cap_share_hard:
        return "country_soft_cap_exceeds_hard_cap"
    floors_sum = float(sum(blend.region_floor_share.values()))
    if floors_sum > 1.0:
        return "region_floor_sum_gt_one"
    top1 = blend.topk_cap_targets["top1"]
    top5 = blend.topk_cap_targets["top5"]
    top10 = blend.topk_cap_targets["top10"]
    if not (0.0 < top1 <= top5 <= top10 <= 1.0):
        return "topk_caps_not_monotonic"
    if not (0.0 <= blend.concentration_penalty_strength <= 1.0):
        return "penalty_strength_out_of_range"
    if blend.max_rebalance_iterations < 1:
        return "max_rebalance_iterations_lt_one"
    if blend.convergence_tolerance <= 0.0:
        return "convergence_tolerance_non_positive"
    return None


def _rebalance_country_shares(
    country_order: list[str],
    region_by_country: dict[str, str],
    base_shares: np.ndarray,
    blend: BlendV2Policy,
) -> tuple[np.ndarray, dict]:
    shares = _safe_normalize(base_shares.copy())
    n = shares.size
    if n == 0:
        return shares, {"iterations": 0, "converged": True, "max_abs_delta": 0.0}
    if not blend.enabled:
        return shares, {"iterations": 0, "converged": True, "max_abs_delta": 0.0}

    region_to_idx: dict[str, list[int]] = {key: [] for key in REGION_KEYS}
    for idx, country_iso in enumerate(country_order):
        region = region_by_country.get(country_iso, "Other")
        if region not in region_to_idx:
            region = "Other"
        region_to_idx[region].append(idx)

    converged = False
    max_abs_delta = 0.0
    for iteration in range(1, blend.max_rebalance_iterations + 1):
        prev = shares.copy()

        for region in REGION_KEYS:
            idxs = region_to_idx.get(region, [])
            floor = blend.region_floor_share.get(region, 0.0)
            if not idxs or floor <= 0.0:
                continue
            current = float(shares[idxs].sum())
            if current + 1.0e-15 >= floor:
                continue
            deficit = floor - current
            donor_idx = np.array([i for i in range(n) if i not in idxs], dtype=np.int64)
            if donor_idx.size == 0:
                continue
            donor_total = float(shares[donor_idx].sum())
            if donor_total <= 0.0:
                continue
            deductions = deficit * (shares[donor_idx] / donor_total)
            shares[donor_idx] -= deductions
            recipient = shares[idxs]
            recipient_weights = _safe_normalize(recipient)
            shares[idxs] += deficit * recipient_weights

        hard = blend.country_cap_share_hard
        soft = blend.country_cap_share_soft
        excess = np.maximum(shares - hard, 0.0)
        excess_total = float(excess.sum())
        if excess_total > 0.0:
            shares -= excess
            gaps = np.maximum(soft - shares, 0.0)
            if float(gaps.sum()) <= 0.0:
                gaps = np.maximum(hard - shares, 0.0)
            if float(gaps.sum()) <= 0.0:
                gaps = np.ones(n, dtype=np.float64)
            shares += excess_total * _safe_normalize(gaps)

        order = np.argsort(-shares, kind="mergesort")
        for label in ("top1", "top5", "top10"):
            target = blend.topk_cap_targets[label]
            frac = TOP_FRACTIONS[label]
            k = max(1, int(np.ceil(frac * n)))
            top_idx = order[:k]
            top_sum = float(shares[top_idx].sum())
            if top_sum <= target:
                continue
            reduction = top_sum - target
            top_weights = _safe_normalize(shares[top_idx])
            shares[top_idx] -= reduction * top_weights
            tail_idx = order[k:]
            if tail_idx.size == 0:
                shares[top_idx] += reduction * top_weights
                continue
            tail_weights = _safe_normalize(shares[tail_idx])
            shares[tail_idx] += reduction * tail_weights
            order = np.argsort(-shares, kind="mergesort")

        alpha = blend.concentration_penalty_strength
        if alpha > 0.0:
            uniform = np.full(n, 1.0 / float(n), dtype=np.float64)
            shares = (1.0 - alpha) * shares + alpha * uniform

        shares = np.clip(shares, 1.0e-18, None)
        shares = _safe_normalize(shares)

        max_abs_delta = float(np.max(np.abs(shares - prev)))
        if max_abs_delta <= blend.convergence_tolerance:
            converged = True
            return shares, {
                "iterations": iteration,
                "converged": True,
                "max_abs_delta": max_abs_delta,
            }

    return shares, {
        "iterations": blend.max_rebalance_iterations,
        "converged": converged,
        "max_abs_delta": max_abs_delta,
    }


def run_s2(config: EngineConfig, run_id: Optional[str] = None) -> S2Result:
    logger = get_logger("engine.layers.l1.seg_1B.s2_tile_weights.l2.runner")
    timer = _StepTimer(logger)

    receipt_path, receipt = _resolve_run_receipt(config.runs_root, run_id)
    run_id = receipt.get("run_id")
    if not run_id:
        raise InputResolutionError("run_receipt missing run_id.")
    if receipt_path.parent.name != run_id:
        raise InputResolutionError("run_receipt path does not match embedded run_id.")
    parameter_hash = receipt.get("parameter_hash")
    if not parameter_hash:
        raise InputResolutionError("run_receipt missing parameter_hash.")

    run_paths = RunPaths(config.runs_root, run_id)
    run_log_path = run_paths.run_root / f"run_log_{run_id}.log"
    add_file_handler(run_log_path)

    source = ContractSource(config.contracts_root, config.contracts_layout)
    dict_path, dictionary = load_dataset_dictionary(source, "1B")
    registry_path, registry = load_artefact_registry(source, "1B")
    schema_1b_path, schema_1b = load_schema_pack(source, "1B", "1B")
    schema_ingress_path, _schema_ingress = load_schema_pack(source, "1A", "ingress.layer1")
    logger.info(
        "Contracts layout=%s root=%s dictionary=%s registry=%s schemas=%s,%s",
        config.contracts_layout,
        config.contracts_root,
        dict_path,
        registry_path,
        schema_1b_path,
        schema_ingress_path,
    )

    tile_index_entry = find_dataset_entry(dictionary, "tile_index").entry
    tile_weights_entry = find_dataset_entry(dictionary, "tile_weights").entry
    run_report_entry = find_dataset_entry(dictionary, "s2_run_report").entry
    iso_entry = find_dataset_entry(dictionary, "iso3166_canonical_2024").entry
    world_entry = find_dataset_entry(dictionary, "world_countries").entry
    population_entry = find_dataset_entry(dictionary, "population_raster_2025").entry
    policy_entry = find_dataset_entry(dictionary, "s2_tile_weights_policy").entry

    tile_index_root = _resolve_dataset_path(
        tile_index_entry,
        run_paths,
        config.external_roots,
        {"parameter_hash": str(parameter_hash)},
    )
    tile_weights_root = _resolve_dataset_path(
        tile_weights_entry,
        run_paths,
        config.external_roots,
        {"parameter_hash": str(parameter_hash)},
    )
    run_report_path = _resolve_dataset_path(
        run_report_entry,
        run_paths,
        config.external_roots,
        {"parameter_hash": str(parameter_hash)},
    )
    iso_path = _resolve_dataset_path(iso_entry, run_paths, config.external_roots, {})
    population_path = _resolve_dataset_path(
        population_entry, run_paths, config.external_roots, {}
    )
    policy_path = _resolve_dataset_path(policy_entry, run_paths, config.external_roots, {})

    if not tile_index_root.exists():
        _emit_failure_event(
            logger,
            "E101_TILE_INDEX_MISSING",
            str(parameter_hash),
            {"detail": "tile_index_path_missing", "path": str(tile_index_root)},
        )
        raise EngineFailure(
            "F4",
            "E101_TILE_INDEX_MISSING",
            "S2",
            MODULE_NAME,
            {"path": str(tile_index_root)},
        )

    policy_payload = _load_yaml(policy_path)
    _validate_payload(schema_1b, "#/policy/s2_tile_weights_policy", policy_payload)
    basis = policy_payload.get("basis")
    dp = policy_payload.get("dp")
    blend_policy = _parse_blend_policy(policy_payload)
    if basis not in ALLOWED_BASIS:
        _emit_failure_event(
            logger,
            "E105_NORMALIZATION",
            str(parameter_hash),
            {"detail": "invalid_basis", "basis": basis},
        )
        raise EngineFailure(
            "F4",
            "E105_NORMALIZATION",
            "S2",
            MODULE_NAME,
            {"basis": basis},
        )
    if not isinstance(dp, int) or dp < 0:
        _emit_failure_event(
            logger,
            "E105_NORMALIZATION",
            str(parameter_hash),
            {"detail": "invalid_dp", "dp": dp},
        )
        raise EngineFailure(
            "F4",
            "E105_NORMALIZATION",
            "S2",
            MODULE_NAME,
            {"dp": dp},
        )
    blend_policy_error = _validate_blend_policy(blend_policy)
    if blend_policy_error:
        _emit_failure_event(
            logger,
            "E105_NORMALIZATION",
            str(parameter_hash),
            {"detail": blend_policy_error},
        )
        raise EngineFailure(
            "F4",
            "E105_NORMALIZATION",
            "S2",
            MODULE_NAME,
            {"detail": blend_policy_error},
        )
    k_value = 10 ** dp
    logger.info(
        "S2: loaded policy basis=%s dp=%s K=%s blend_enabled=%s path=%s",
        basis,
        dp,
        k_value,
        blend_policy.enabled,
        policy_path,
    )
    if blend_policy.enabled:
        logger.info(
            "S2: blend_v2 mix uniform=%.6f area_m2=%.6f population=%.6f",
            blend_policy.basis_mix["uniform"],
            blend_policy.basis_mix["area_m2"],
            blend_policy.basis_mix["population"],
        )

    iso_start = time.monotonic()
    iso_df = pl.read_parquet(iso_path, columns=["country_iso", "region", "subregion"])
    iso_elapsed = time.monotonic() - iso_start
    iso_bytes = iso_path.stat().st_size
    io_baseline_vectors_bps = iso_bytes / iso_elapsed if iso_elapsed > 0 else 0.0
    iso_set = set(iso_df.get_column("country_iso").to_list())
    region_by_country = _load_country_region_lookup(iso_path, config.repo_root)

    bytes_read_vectors_total = iso_bytes
    logger.info(
        "S2: iso baseline bytes=%d elapsed=%.2fs baseline_bps=%.2f",
        iso_bytes,
        iso_elapsed,
        io_baseline_vectors_bps,
    )

    ingress_versions = {
        "iso3166": _entry_version(iso_entry) or "",
        "world_countries": _entry_version(world_entry) or "",
        "population_raster": _entry_version(population_entry) or None,
    }
    needs_population = basis == "population" or (
        blend_policy.enabled and blend_policy.basis_mix.get("population", 0.0) > 0.0
    )
    if not needs_population:
        ingress_versions["population_raster"] = None
    logger.info(
        "S2: ingress_versions iso=%s world=%s population=%s",
        ingress_versions["iso3166"],
        ingress_versions["world_countries"],
        ingress_versions["population_raster"],
    )

    country_dirs = _country_dirs(tile_index_root)
    if not country_dirs:
        _emit_failure_event(
            logger,
            "E101_TILE_INDEX_MISSING",
            str(parameter_hash),
            {"detail": "tile_index_empty", "path": str(tile_index_root)},
        )
        raise EngineFailure(
            "F4",
            "E101_TILE_INDEX_MISSING",
            "S2",
            MODULE_NAME,
            {"path": str(tile_index_root)},
        )

    raster = None
    bytes_per_pixel = 0
    io_baseline_raster_bps = 0.0
    if needs_population:
        raster = rasterio.open(population_path)
        bytes_per_pixel = np.dtype(raster.dtypes[0]).itemsize
        rows_to_read = min(raster.height, 512)
        if rows_to_read > 0:
            baseline_window = Window(0, 0, raster.width, rows_to_read)
            baseline_start = time.monotonic()
            baseline_array = raster.read(1, window=baseline_window)
            baseline_elapsed = time.monotonic() - baseline_start
            io_baseline_raster_bps = (
                baseline_array.nbytes / baseline_elapsed if baseline_elapsed > 0 else 0.0
            )
        logger.info(
            "S2: raster baseline bytes_per_pixel=%d baseline_bps=%.2f path=%s",
            bytes_per_pixel,
            io_baseline_raster_bps,
            population_path,
        )

    run_paths.tmp_root.mkdir(parents=True, exist_ok=True)
    tile_weights_tmp = run_paths.tmp_root / f"s2_tile_weights_{uuid.uuid4().hex}"
    tile_weights_tmp.mkdir(parents=True, exist_ok=True)

    proc = psutil.Process()
    wall_start = time.monotonic()
    cpu_start = time.process_time()
    max_rss = proc.memory_info().rss
    open_files_peak = _open_files_count(proc)

    countries_total = len(country_dirs)
    countries_processed = 0
    rows_emitted = 0
    bytes_read_tile_index_total = 0
    bytes_read_raster_total = 0
    io_baseline_ti_bps: Optional[float] = None
    country_summaries: list[dict] = []
    country_order: list[str] = []
    country_tiles_total: list[float] = []
    country_area_total: list[float] = []
    country_population_total: list[float] = []

    timer.info(f"S2: starting tile weights (countries={countries_total})")
    for country_dir in country_dirs:
        country_iso = _country_from_dir(country_dir)
        country_files = sorted([path for path in country_dir.rglob("*.parquet") if path.is_file()])
        if not country_files:
            _emit_failure_event(
                logger,
                "E101_TILE_INDEX_MISSING",
                str(parameter_hash),
                {"detail": "country_partition_empty", "country_iso": country_iso},
            )
            raise EngineFailure(
                "F4",
                "E101_TILE_INDEX_MISSING",
                "S2",
                MODULE_NAME,
                {"country_iso": country_iso},
            )
        file_bytes = sum(path.stat().st_size for path in country_files)
        bytes_read_tile_index_total += file_bytes

        columns = ["country_iso", "tile_id"]
        needs_area_column = basis == "area_m2" or (
            blend_policy.enabled and blend_policy.basis_mix.get("area_m2", 0.0) > 0.0
        )
        if needs_area_column:
            columns.append("pixel_area_m2")
        if needs_population:
            columns.extend(["centroid_lon", "centroid_lat"])
        read_start = time.monotonic()
        df = pl.read_parquet(country_files, columns=columns)
        read_elapsed = time.monotonic() - read_start
        if io_baseline_ti_bps is None:
            io_baseline_ti_bps = file_bytes / read_elapsed if read_elapsed > 0 else 0.0
            logger.info(
                "S2: tile_index baseline bytes=%d elapsed=%.2fs baseline_bps=%.2f",
                file_bytes,
                read_elapsed,
                io_baseline_ti_bps,
            )

        unique_countries = df.get_column("country_iso").unique().to_list()
        if len(unique_countries) != 1 or unique_countries[0] != country_iso:
            _emit_failure_event(
                logger,
                "E108_WRITER_HYGIENE",
                str(parameter_hash),
                {"detail": "mixed_country_partition", "country_iso": country_iso},
            )
            raise EngineFailure(
                "F4",
                "E108_WRITER_HYGIENE",
                "S2",
                MODULE_NAME,
                {"country_iso": country_iso},
            )
        if country_iso not in iso_set:
            _emit_failure_event(
                logger,
                "E101_TILE_INDEX_MISSING",
                str(parameter_hash),
                {"detail": "country_iso_not_in_iso3166", "country_iso": country_iso},
            )
            raise EngineFailure(
                "F4",
                "E101_TILE_INDEX_MISSING",
                "S2",
                MODULE_NAME,
                {"country_iso": country_iso},
            )

        tile_ids = df.get_column("tile_id").to_numpy()
        if tile_ids.size == 0:
            _emit_failure_event(
                logger,
                "E103_ZERO_COUNTRY",
                str(parameter_hash),
                {"country_iso": country_iso},
            )
            raise EngineFailure(
                "F4",
                "E103_ZERO_COUNTRY",
                "S2",
                MODULE_NAME,
                {"country_iso": country_iso},
            )
        if tile_ids.size > 1 and np.any(tile_ids[1:] < tile_ids[:-1]):
            _emit_failure_event(
                logger,
                "E108_WRITER_HYGIENE",
                str(parameter_hash),
                {"detail": "tile_id_not_sorted", "country_iso": country_iso},
            )
            raise EngineFailure(
                "F4",
                "E108_WRITER_HYGIENE",
                "S2",
                MODULE_NAME,
                {"country_iso": country_iso},
            )

        uniform_mass = np.ones(tile_ids.size, dtype=np.float64)
        area_mass = (
            df.get_column("pixel_area_m2").to_numpy().astype(np.float64, copy=False)
            if needs_area_column
            else uniform_mass
        )
        population_mass = np.zeros(tile_ids.size, dtype=np.float64)
        if needs_population:
            if raster is None:
                raise InputResolutionError("population basis requires raster handle.")
            lons = df.get_column("centroid_lon").to_numpy()
            lats = df.get_column("centroid_lat").to_numpy()
            samples = np.fromiter(
                (val[0] for val in raster.sample(zip(lons.tolist(), lats.tolist()))),
                dtype=np.float64,
                count=tile_ids.size,
            )
            nodata = raster.nodata
            if nodata is not None:
                samples = np.where(samples == nodata, 0.0, samples)
            population_mass = np.nan_to_num(samples, nan=0.0, posinf=0.0, neginf=0.0)
            bytes_read_raster_total += tile_ids.size * bytes_per_pixel

        if blend_policy.enabled:
            masses = (
                blend_policy.basis_mix["uniform"] * _safe_normalize(uniform_mass)
                + blend_policy.basis_mix["area_m2"] * _safe_normalize(area_mass)
                + blend_policy.basis_mix["population"] * _safe_normalize(population_mass)
            )
        elif basis == "uniform":
            masses = uniform_mass
        elif basis == "area_m2":
            masses = area_mass
        else:
            masses = population_mass

        if not np.all(np.isfinite(masses)) or np.any(masses < 0):
            _emit_failure_event(
                logger,
                "E105_NORMALIZATION",
                str(parameter_hash),
                {"detail": "invalid_mass_domain", "country_iso": country_iso},
            )
            raise EngineFailure(
                "F4",
                "E105_NORMALIZATION",
                "S2",
                MODULE_NAME,
                {"country_iso": country_iso},
            )

        country_order.append(country_iso)
        country_tiles_total.append(float(tile_ids.size))
        country_area_total.append(float(np.sum(area_mass)))
        country_population_total.append(float(np.sum(population_mass)))

        mass_sum_basis = float(masses.sum())
        zero_mass_fallback = False
        if mass_sum_basis == 0.0:
            zero_mass_fallback = True
            masses = np.ones(tile_ids.size, dtype=np.float64)
        mass_sum = float(masses.sum())
        if mass_sum == 0.0:
            _emit_failure_event(
                logger,
                "E104_ZERO_MASS",
                str(parameter_hash),
                {"country_iso": country_iso, "basis": basis},
            )
            raise EngineFailure(
                "F4",
                "E104_ZERO_MASS",
                "S2",
                MODULE_NAME,
                {"country_iso": country_iso, "basis": basis},
            )

        q = masses * float(k_value) / mass_sum
        z = np.floor(q).astype(np.int64)
        residues = q - z
        shortfall = int(k_value - int(z.sum()))
        if shortfall < 0 or shortfall > tile_ids.size:
            _emit_failure_event(
                logger,
                "E105_NORMALIZATION",
                str(parameter_hash),
                {
                    "detail": "invalid_shortfall",
                    "country_iso": country_iso,
                    "shortfall": shortfall,
                    "k_value": k_value,
                },
            )
            raise EngineFailure(
                "F4",
                "E105_NORMALIZATION",
                "S2",
                MODULE_NAME,
                {"country_iso": country_iso, "shortfall": shortfall},
            )
        if shortfall > 0:
            order = np.lexsort((tile_ids, -residues))
            bump = np.zeros(tile_ids.size, dtype=np.int8)
            bump[order[:shortfall]] = 1
            weight_fp = z + bump
        else:
            weight_fp = z

        post_sum = int(weight_fp.sum())
        if post_sum != k_value:
            _emit_failure_event(
                logger,
                "E105_NORMALIZATION",
                str(parameter_hash),
                {
                    "country_iso": country_iso,
                    "post_sum": post_sum,
                    "expected": k_value,
                },
            )
            raise EngineFailure(
                "F4",
                "E105_NORMALIZATION",
                "S2",
                MODULE_NAME,
                {"country_iso": country_iso, "post_sum": post_sum},
            )

        out_df = pl.DataFrame(
            {
                "country_iso": np.full(tile_ids.size, country_iso),
                "tile_id": tile_ids,
                "weight_fp": weight_fp,
                "dp": np.full(tile_ids.size, dp, dtype=np.int64),
                "basis": np.full(tile_ids.size, basis),
            }
        )
        out_path = tile_weights_tmp / f"part-{country_iso}.parquet"
        out_df.write_parquet(out_path, compression="zstd", row_group_size=200000)

        countries_processed += 1
        rows_emitted += tile_ids.size
        country_summaries.append(
            {
                "country_iso": country_iso,
                "macro_region": region_by_country.get(country_iso, "Other"),
                "tiles": int(tile_ids.size),
                "mass_sum": mass_sum_basis,
                "component_mass_tiles": float(tile_ids.size),
                "component_mass_area_m2": float(np.sum(area_mass)),
                "component_mass_population": float(np.sum(population_mass)),
                "prequant_sum_real": float((masses / mass_sum).sum()) if mass_sum > 0 else 0.0,
                "K": k_value,
                "postquant_sum_fp": post_sum,
                "residue_allocations": shortfall,
                "zero_mass_fallback": zero_mass_fallback,
            }
        )

        if zero_mass_fallback:
            logger.info(
                "S2: zero-mass fallback engaged country=%s tiles=%d",
                country_iso,
                tile_ids.size,
            )

        elapsed = time.monotonic() - wall_start
        rate = countries_processed / elapsed if elapsed > 0 else 0.0
        remaining = countries_total - countries_processed
        eta = remaining / rate if rate > 0 else 0.0
        logger.info(
            "S2 progress countries_processed=%d/%d rows_emitted=%d (elapsed=%.2fs, rate=%.2f/s, eta=%.2fs)",
            countries_processed,
            countries_total,
            rows_emitted,
            elapsed,
            rate,
            eta,
        )

        rss_now = proc.memory_info().rss
        max_rss = max(max_rss, rss_now)
        open_files_peak = max(open_files_peak, _open_files_count(proc))

    if raster is not None:
        raster.close()

    if io_baseline_ti_bps is None:
        io_baseline_ti_bps = 0.0

    country_tiles_arr = np.array(country_tiles_total, dtype=np.float64)
    country_area_arr = np.array(country_area_total, dtype=np.float64)
    country_population_arr = np.array(country_population_total, dtype=np.float64)
    if blend_policy.enabled:
        base_country_shares = (
            blend_policy.basis_mix["uniform"] * _safe_normalize(country_tiles_arr)
            + blend_policy.basis_mix["area_m2"] * _safe_normalize(country_area_arr)
            + blend_policy.basis_mix["population"] * _safe_normalize(country_population_arr)
        )
    elif basis == "uniform":
        base_country_shares = _safe_normalize(country_tiles_arr)
    elif basis == "area_m2":
        base_country_shares = _safe_normalize(country_area_arr)
    else:
        base_country_shares = _safe_normalize(country_population_arr)

    adjusted_country_shares, rebalance_diag = _rebalance_country_shares(
        country_order,
        region_by_country,
        base_country_shares,
        blend_policy,
    )
    country_share_topk = {
        key: _top_fraction_share(adjusted_country_shares, frac)
        for key, frac in TOP_FRACTIONS.items()
    }
    country_gini_proxy = _gini(adjusted_country_shares)
    region_share_vector: dict[str, float] = {key: 0.0 for key in REGION_KEYS}
    for idx, country_iso in enumerate(country_order):
        region = region_by_country.get(country_iso, "Other")
        if region not in region_share_vector:
            region = "Other"
        region_share_vector[region] += float(adjusted_country_shares[idx])

    determinism_hash, determinism_bytes = _hash_partition(tile_weights_tmp)
    determinism_receipt = {
        "partition_path": str(tile_weights_root),
        "sha256_hex": determinism_hash,
        "bytes_hashed": determinism_bytes,
    }

    _atomic_publish_dir(tile_weights_tmp, tile_weights_root, logger, "tile_weights")

    wall_total = time.monotonic() - wall_start
    cpu_total = time.process_time() - cpu_start

    pat = {
        "wall_clock_seconds_total": wall_total,
        "cpu_seconds_total": cpu_total,
        "countries_processed": countries_processed,
        "rows_emitted": rows_emitted,
        "bytes_read_tile_index_total": bytes_read_tile_index_total,
        "bytes_read_raster_total": bytes_read_raster_total,
        "bytes_read_vectors_total": bytes_read_vectors_total,
        "max_worker_rss_bytes": max_rss,
        "open_files_peak": open_files_peak,
        "workers_used": 1,
        "chunk_size": 0,
        "io_baseline_ti_bps": io_baseline_ti_bps,
        "io_baseline_raster_bps": io_baseline_raster_bps,
        "io_baseline_vectors_bps": io_baseline_vectors_bps,
    }

    run_report = {
        "parameter_hash": parameter_hash,
        "basis": basis,
        "dp": dp,
        "fallback_mode": policy_payload.get("fallback_mode", "legacy_basis_only"),
        "blend_v2_enabled": blend_policy.enabled,
        "blend_v2_basis_mix": blend_policy.basis_mix,
        "ingress_versions": ingress_versions,
        "rows_emitted": rows_emitted,
        "countries_total": countries_total,
        "country_gini_proxy": country_gini_proxy,
        "country_share_topk": country_share_topk,
        "region_share_vector": region_share_vector,
        "country_share_baseline_topk": {
            key: _top_fraction_share(base_country_shares, frac)
            for key, frac in TOP_FRACTIONS.items()
        },
        "country_gini_baseline_proxy": _gini(base_country_shares),
        "blend_v2_diagnostics": {
            "seed_namespace": blend_policy.deterministic_seed_namespace,
            "country_cap_share_soft": blend_policy.country_cap_share_soft,
            "country_cap_share_hard": blend_policy.country_cap_share_hard,
            "topk_cap_targets": blend_policy.topk_cap_targets,
            "region_floor_share": blend_policy.region_floor_share,
            "concentration_penalty_strength": blend_policy.concentration_penalty_strength,
            "max_rebalance_iterations": blend_policy.max_rebalance_iterations,
            "convergence_tolerance": blend_policy.convergence_tolerance,
            "convergence": rebalance_diag,
        },
        "determinism_receipt": determinism_receipt,
        "pat": pat,
        "country_summaries": country_summaries,
    }
    _validate_payload(schema_1b, "#/control/s2_run_report", run_report)
    run_report_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(run_report_path, run_report)
    timer.info("S2: run report written")

    return S2Result(
        run_id=str(run_id),
        parameter_hash=str(parameter_hash),
        tile_weights_path=tile_weights_root,
        run_report_path=run_report_path,
    )
