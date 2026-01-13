"""S2 tile weights runner for Segment 1B."""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

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


MODULE_NAME = "1B.s2_tile_weights"
ALLOWED_BASIS = {"uniform", "area_m2", "population"}


@dataclass(frozen=True)
class S2Result:
    run_id: str
    parameter_hash: str
    tile_weights_path: Path
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
    k_value = 10 ** dp
    logger.info(
        "S2: loaded policy basis=%s dp=%s K=%s path=%s",
        basis,
        dp,
        k_value,
        policy_path,
    )

    iso_start = time.monotonic()
    iso_df = pl.read_parquet(iso_path, columns=["country_iso"])
    iso_elapsed = time.monotonic() - iso_start
    iso_bytes = iso_path.stat().st_size
    io_baseline_vectors_bps = iso_bytes / iso_elapsed if iso_elapsed > 0 else 0.0
    iso_set = set(iso_df.get_column("country_iso").to_list())

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
    if basis != "population":
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
    if basis == "population":
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
        if basis == "area_m2":
            columns.append("pixel_area_m2")
        if basis == "population":
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

        if basis == "uniform":
            masses = np.ones(tile_ids.size, dtype=np.float64)
        elif basis == "area_m2":
            masses = df.get_column("pixel_area_m2").to_numpy()
        else:
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
            samples = np.nan_to_num(samples, nan=0.0, posinf=0.0, neginf=0.0)
            masses = samples
            bytes_read_raster_total += tile_ids.size * bytes_per_pixel

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
                "tiles": int(tile_ids.size),
                "mass_sum": mass_sum_basis,
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
        "ingress_versions": ingress_versions,
        "rows_emitted": rows_emitted,
        "countries_total": countries_total,
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
