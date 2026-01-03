"""Segment 5B S3 bucket count runner."""

from __future__ import annotations

import json
import logging
import math
import os
import shutil
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import polars as pl
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from engine.layers.l1.seg_1A.s0_foundations.l2.rng_logging import RNGLogWriter
from engine.layers.l2.seg_5B.shared.control_plane import SealedInventory, load_control_plane
from engine.layers.l2.seg_5B.shared.dictionary import load_dictionary, render_dataset_path, repository_root
from engine.layers.l2.seg_5B.shared.rng import derive_event, gamma_one_u_approx, poisson_one_u
from engine.layers.l2.seg_5B.shared.run_report import SegmentStateKey, write_segment_state_run_report

logger = logging.getLogger(__name__)
U64_MAX = 2**64 - 1


@dataclass(frozen=True)
class CountInputs:
    data_root: Path
    manifest_fingerprint: str
    parameter_hash: str
    seed: int
    run_id: str
    dictionary_path: Path | None = None


@dataclass(frozen=True)
class CountResult:
    count_paths: dict[str, Path]
    run_report_path: Path


@dataclass(frozen=True)
class _CountLawContext:
    count_law: str
    lambda_zero_eps: float
    poisson_exact_lambda_max: float
    poisson_n_cap_exact: int
    max_count_per_bucket: int
    base_by_band: Mapping[str, float]
    class_multipliers: Mapping[str, float]
    kappa_bounds: tuple[float, float]


@dataclass(frozen=True)
class _RowGroupChunk:
    start: int
    stop: int
    row_count: int
    counts_part: Path
    event_part: Path


class CountRunner:
    """Convert realised intensities into bucket counts."""

    def run(self, inputs: CountInputs) -> CountResult:
        dictionary = load_dictionary(inputs.dictionary_path)
        data_root = inputs.data_root.expanduser().absolute()
        receipt, sealed_df, scenarios = load_control_plane(
            data_root=data_root,
            manifest_fingerprint=inputs.manifest_fingerprint,
            parameter_hash=inputs.parameter_hash,
            dictionary_path=inputs.dictionary_path,
        )
        inventory = SealedInventory(
            dataframe=sealed_df,
            base_path=data_root,
            repo_root=repository_root(),
            template_args={
                "manifest_fingerprint": inputs.manifest_fingerprint,
                "parameter_hash": inputs.parameter_hash,
                "seed": str(inputs.seed),
            },
        )
        count_policy = _load_yaml(inventory, "arrival_count_config_5B")
        ctx = _build_count_context(count_policy)
        count_law = ctx.count_law
        count_paths: dict[str, Path] = {}
        events_dir = _rng_events_dir(
            data_root=data_root,
            family="S3.bucket_count.v1",
            seed=inputs.seed,
            parameter_hash=inputs.parameter_hash,
            run_id=inputs.run_id,
        )
        trace_dir = _rng_trace_dir(
            data_root=data_root,
            seed=inputs.seed,
            parameter_hash=inputs.parameter_hash,
            run_id=inputs.run_id,
        )
        _reset_rng_logs(events_dir=events_dir, trace_dir=trace_dir)
        rng_totals = _load_rng_summary(trace_dir)
        trace_totals: dict[tuple[str, str], dict[str, int]] = {}

        logger.info("5B.S3 bucket counts start scenarios=%s", len(scenarios))
        for scenario in scenarios:
            logger.info("5B.S3 scenario start scenario_id=%s", scenario.scenario_id)
            scenario_timer = time.perf_counter()
            intensity_path = data_root / render_dataset_path(
                dataset_id="s2_realised_intensity_5B",
                template_args={
                    "manifest_fingerprint": inputs.manifest_fingerprint,
                    "scenario_id": scenario.scenario_id,
                    "seed": inputs.seed,
                },
                dictionary=dictionary,
            )
            grouping_path = data_root / render_dataset_path(
                dataset_id="s1_grouping_5B",
                template_args={
                    "manifest_fingerprint": inputs.manifest_fingerprint,
                    "scenario_id": scenario.scenario_id,
                },
                dictionary=dictionary,
            )
            if not intensity_path.exists():
                raise FileNotFoundError(f"s2_realised_intensity_5B missing at {intensity_path}")
            if not grouping_path.exists():
                raise FileNotFoundError(f"s1_grouping_5B missing at {grouping_path}")

            intensity_parquet = pq.ParquetFile(intensity_path)
            required_columns = [
                "merchant_id",
                "zone_representation",
                "bucket_index",
                "lambda_realised",
            ]
            optional_columns = ["channel_group", "demand_class", "scenario_band"]
            available = set(intensity_parquet.schema.names)
            missing_required = [col for col in required_columns if col not in available]
            if missing_required:
                raise ValueError(f"s2_realised_intensity_5B missing columns: {missing_required}")
            read_columns = required_columns + [col for col in optional_columns if col in available]
            has_channel_group = "channel_group" in read_columns
            has_demand_class = "demand_class" in read_columns
            has_scenario_band = "scenario_band" in read_columns
            needs_grouping = count_law == "nb2" or not has_demand_class or not has_scenario_band

            demand_class_map: dict[tuple[str, str, str], str] = {}
            scenario_band_map: dict[tuple[str, str, str], str] = {}
            if needs_grouping:
                grouping_df = pl.read_parquet(grouping_path)
                if "demand_class" not in grouping_df.columns:
                    raise ValueError("s1_grouping_5B missing demand_class")
                grouping_df = grouping_df.with_columns(
                    pl.col("merchant_id").cast(pl.Utf8).alias("merchant_id"),
                    pl.col("zone_representation").cast(pl.Utf8).alias("zone_representation"),
                    (
                        pl.when(
                            pl.col("channel_group").is_null()
                            | (pl.col("channel_group").cast(pl.Utf8).str.strip_chars() == "")
                        )
                        .then(pl.lit("unknown"))
                        .otherwise(pl.col("channel_group").cast(pl.Utf8))
                        if "channel_group" in grouping_df.columns
                        else pl.lit("unknown")
                    ).alias("channel_group"),
                    pl.col("demand_class").cast(pl.Utf8).alias("demand_class"),
                    (
                        pl.col("scenario_band").cast(pl.Utf8).alias("scenario_band")
                        if "scenario_band" in grouping_df.columns
                        else pl.lit("")
                    ),
                ).select(
                    [
                        "merchant_id",
                        "zone_representation",
                        "channel_group",
                        "demand_class",
                        "scenario_band",
                    ]
                )
                grouping_cols = grouping_df.select(
                    [
                        "merchant_id",
                        "zone_representation",
                        "channel_group",
                        "demand_class",
                        "scenario_band",
                    ]
                )
                merchants = grouping_cols.get_column("merchant_id").to_list()
                zones = grouping_cols.get_column("zone_representation").to_list()
                channels = grouping_cols.get_column("channel_group").to_list()
                demand_classes = grouping_cols.get_column("demand_class").to_list()
                scenario_bands = grouping_cols.get_column("scenario_band").to_list()
                for merchant_id, zone_rep, channel_group, demand_class, scenario_band in zip(
                    merchants, zones, channels, demand_classes, scenario_bands
                ):
                    key = (merchant_id, zone_rep, channel_group)
                    demand_class_map[key] = demand_class
                    if scenario_band:
                        scenario_band_map[key] = scenario_band

                class_values = {value for value in demand_class_map.values() if value}
                if class_values:
                    class_df = pl.DataFrame({"demand_class": sorted(class_values)})
                    missing_classes = _missing_classes(
                        class_df,
                        count_law=ctx.count_law,
                        class_multipliers=ctx.class_multipliers,
                    )
                    if missing_classes:
                        raise ValueError(
                            f"arrival_count_config_5B missing class multipliers for {missing_classes}"
                        )

            total_rows = intensity_parquet.metadata.num_rows
            output_path = data_root / render_dataset_path(
                dataset_id="s3_bucket_counts_5B",
                template_args={
                    "manifest_fingerprint": inputs.manifest_fingerprint,
                    "scenario_id": scenario.scenario_id,
                    "seed": inputs.seed,
                },
                dictionary=dictionary,
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)

            row_group_sizes = _row_group_sizes(intensity_parquet)
            row_group_count = len(row_group_sizes)
            max_workers = _resolve_max_workers(row_group_count=row_group_count)
            parts_dir = output_path.parent / "_parts"
            event_parts_dir = events_dir / "_parts"
            parts_dir.mkdir(parents=True, exist_ok=True)
            event_parts_dir.mkdir(parents=True, exist_ok=True)
            chunks = _build_row_group_chunks(
                row_group_sizes=row_group_sizes,
                parts_dir=parts_dir,
                event_parts_dir=event_parts_dir,
                max_workers=max_workers,
            )
            logger.info(
                "5B.S3 scenario prep scenario_id=%s rows=%d row_groups=%d workers=%d",
                scenario.scenario_id,
                total_rows,
                row_group_count,
                max_workers,
            )
            if not chunks:
                _write_empty_s3(output_path)
                _ensure_rng_logs(events_dir, trace_dir, rng_totals, inputs)
                count_paths[scenario.scenario_id] = output_path
                logger.info(
                    "5B.S3 scenario complete scenario_id=%s rows=%d elapsed=%.2fs rate=%.1f rows/s",
                    scenario.scenario_id,
                    total_rows,
                    0.0,
                    0.0,
                )
                continue

            processed_rows = 0
            start_time = time.monotonic()
            last_log = start_time
            log_interval = 60.0
            log_every_rows = max(100000, int(total_rows * 0.01))
            scenario_band_value = "baseline" if scenario.is_baseline else "stress"
            worker_args = {
                "base_path": data_root,
                "intensity_path": intensity_path,
                "read_columns": read_columns,
                "has_channel_group": has_channel_group,
                "has_demand_class": has_demand_class,
                "has_scenario_band": has_scenario_band,
                "needs_grouping": needs_grouping,
                "demand_class_map": demand_class_map,
                "scenario_band_map": scenario_band_map,
                "scenario_band_default": scenario_band_value,
                "ctx": ctx,
                "manifest_fingerprint": inputs.manifest_fingerprint,
                "parameter_hash": inputs.parameter_hash,
                "seed": inputs.seed,
                "scenario_id": scenario.scenario_id,
                "run_id": inputs.run_id,
            }
            if max_workers <= 1 or len(chunks) == 1:
                for chunk in chunks:
                    logger.info(
                        "5B.S3 chunk start scenario_id=%s rg=%d-%d rows=%d",
                        scenario.scenario_id,
                        chunk.start,
                        chunk.stop - 1,
                        chunk.row_count,
                    )
                    _process_row_group_chunk(
                        row_group_start=chunk.start,
                        row_group_stop=chunk.stop,
                        counts_part_path=chunk.counts_part,
                        event_filename=str(chunk.event_part.relative_to(events_dir)),
                        **worker_args,
                    )
                    processed_rows += chunk.row_count
                    now = time.monotonic()
                    if processed_rows >= log_every_rows or (now - last_log) >= log_interval:
                        _log_progress(
                            scenario_id=scenario.scenario_id,
                            processed_rows=processed_rows,
                            total_rows=total_rows,
                            start_time=start_time,
                            now=now,
                        )
                        last_log = now
            else:
                max_workers = min(max_workers, len(chunks))
                with ProcessPoolExecutor(max_workers=max_workers) as executor:
                    futures: dict[object, _RowGroupChunk] = {}
                    for chunk in chunks:
                        logger.info(
                            "5B.S3 chunk scheduled scenario_id=%s rg=%d-%d rows=%d",
                            scenario.scenario_id,
                            chunk.start,
                            chunk.stop - 1,
                            chunk.row_count,
                        )
                        future = executor.submit(
                            _process_row_group_chunk,
                            row_group_start=chunk.start,
                            row_group_stop=chunk.stop,
                            counts_part_path=chunk.counts_part,
                            event_filename=str(chunk.event_part.relative_to(events_dir)),
                            **worker_args,
                        )
                        futures[future] = chunk
                    for future in as_completed(futures):
                        chunk = futures[future]
                        future.result()
                        processed_rows += chunk.row_count
                        now = time.monotonic()
                        if processed_rows >= log_every_rows or (now - last_log) >= log_interval:
                            _log_progress(
                                scenario_id=scenario.scenario_id,
                                processed_rows=processed_rows,
                                total_rows=total_rows,
                                start_time=start_time,
                                now=now,
                            )
                            last_log = now

            _merge_count_parts(chunks, output_path)
            _merge_event_parts(
                chunks=chunks,
                events_dir=events_dir,
                trace_dir=trace_dir,
                totals=rng_totals,
                trace_totals=trace_totals,
                inputs=inputs,
            )
            _cleanup_parts(chunks=chunks, parts_dir=parts_dir, event_parts_dir=event_parts_dir)
            count_paths[scenario.scenario_id] = output_path
            scenario_elapsed = time.perf_counter() - scenario_timer
            rate = total_rows / scenario_elapsed if scenario_elapsed > 0 else 0.0
            logger.info(
                "5B.S3 scenario complete scenario_id=%s rows=%d elapsed=%.2fs rate=%.1f rows/s",
                scenario.scenario_id,
                total_rows,
                scenario_elapsed,
                rate,
            )

        run_report_path = _write_run_report(inputs, data_root, dictionary)
        return CountResult(count_paths=count_paths, run_report_path=run_report_path)


def _load_yaml(inventory: SealedInventory, artifact_id: str) -> Mapping[str, object]:
    files = inventory.resolve_files(artifact_id)
    if not files:
        raise FileNotFoundError(f"{artifact_id} missing from sealed inputs")
    return yaml.safe_load(files[0].read_text(encoding="utf-8")) or {}


def _resolve_max_workers(*, row_group_count: int) -> int:
    raw = os.environ.get("S3_MAX_WORKERS")
    if raw:
        try:
            parsed = int(raw)
        except ValueError:
            parsed = 0
        if parsed > 0:
            return min(parsed, max(row_group_count, 1))
    cpu_total = os.cpu_count() or 1
    return min(cpu_total, max(row_group_count, 1))


def _row_group_sizes(parquet: pq.ParquetFile) -> list[int]:
    metadata = parquet.metadata
    if metadata is None:
        return []
    return [metadata.row_group(idx).num_rows for idx in range(metadata.num_row_groups)]


def _build_row_group_chunks(
    *,
    row_group_sizes: Sequence[int],
    parts_dir: Path,
    event_parts_dir: Path,
    max_workers: int,
) -> list[_RowGroupChunk]:
    row_group_count = len(row_group_sizes)
    if row_group_count == 0:
        return []
    target_tasks = max(1, min(row_group_count, max_workers * 2))
    chunk_size = max(1, math.ceil(row_group_count / target_tasks))
    chunks: list[_RowGroupChunk] = []
    for start in range(0, row_group_count, chunk_size):
        stop = min(start + chunk_size, row_group_count)
        row_count = int(sum(row_group_sizes[start:stop]))
        part_label = f"rg{start:05d}-{stop - 1:05d}"
        counts_part = parts_dir / f"counts-{part_label}.parquet"
        event_part = event_parts_dir / f"events-{part_label}.jsonl"
        chunks.append(
            _RowGroupChunk(
                start=start,
                stop=stop,
                row_count=row_count,
                counts_part=counts_part,
                event_part=event_part,
            )
        )
    return chunks


def _process_row_group_chunk(
    *,
    base_path: Path,
    intensity_path: Path,
    read_columns: Sequence[str],
    row_group_start: int,
    row_group_stop: int,
    counts_part_path: Path,
    event_filename: str,
    has_channel_group: bool,
    has_demand_class: bool,
    has_scenario_band: bool,
    needs_grouping: bool,
    demand_class_map: Mapping[tuple[str, str, str], str],
    scenario_band_map: Mapping[tuple[str, str, str], str],
    scenario_band_default: str,
    ctx: _CountLawContext,
    manifest_fingerprint: str,
    parameter_hash: str,
    seed: int,
    scenario_id: str,
    run_id: str,
) -> None:
    intensity_parquet = pq.ParquetFile(intensity_path)
    rng_logger = RNGLogWriter(
        base_path=base_path,
        seed=seed,
        parameter_hash=parameter_hash,
        manifest_fingerprint=manifest_fingerprint,
        run_id=run_id,
        emit_trace=False,
        emit_summary=False,
        event_filename=event_filename,
    )
    buffers = _init_buffers()
    buffered = 0
    writer: pq.ParquetWriter | None = None
    flush_every = 100000
    scenario_band_value = scenario_band_default
    mf = manifest_fingerprint
    ph = parameter_hash
    seed_value = seed
    scenario_id_value = scenario_id
    lambda_zero_eps = ctx.lambda_zero_eps
    demand_lookup = demand_class_map
    scenario_lookup = scenario_band_map
    draw_count = _draw_count
    for rg_index in range(row_group_start, row_group_stop):
        table = intensity_parquet.read_row_group(rg_index, columns=read_columns)
        if table.num_rows == 0:
            continue
        batch_df = pl.from_arrow(table)
        batch_df = batch_df.with_columns(
            pl.col("merchant_id").cast(pl.Utf8).alias("merchant_id"),
            pl.col("zone_representation").cast(pl.Utf8).alias("zone_representation"),
            (
                pl.when(
                    pl.col("channel_group").is_null()
                    | (pl.col("channel_group").cast(pl.Utf8).str.strip_chars() == "")
                )
                .then(pl.lit("unknown"))
                .otherwise(pl.col("channel_group").cast(pl.Utf8))
                if has_channel_group
                else pl.lit("unknown")
            ).alias("channel_group"),
            (
                pl.col("demand_class").cast(pl.Utf8).alias("demand_class")
                if has_demand_class
                else pl.lit("")
            ),
            (
                pl.col("scenario_band").cast(pl.Utf8).alias("scenario_band")
                if has_scenario_band
                else pl.lit("")
            ),
        )
        merchant_ids = batch_df.get_column("merchant_id").to_list()
        zone_reps = batch_df.get_column("zone_representation").to_list()
        channel_groups = batch_df.get_column("channel_group").to_list()
        bucket_indexes = batch_df.get_column("bucket_index").to_list()
        lambda_values = batch_df.get_column("lambda_realised").to_list()
        demand_classes = batch_df.get_column("demand_class").to_list()
        scenario_bands = batch_df.get_column("scenario_band").to_list()

        buf_manifest = buffers["manifest_fingerprint"]
        buf_param = buffers["parameter_hash"]
        buf_seed = buffers["seed"]
        buf_scenario = buffers["scenario_id"]
        buf_merchant = buffers["merchant_id"]
        buf_zone = buffers["zone_representation"]
        buf_channel = buffers["channel_group"]
        buf_bucket = buffers["bucket_index"]
        buf_count = buffers["count_N"]
        buf_spec = buffers["s3_spec_version"]

        for merchant_id, zone_rep, channel_group, bucket_index, lam, demand_class, scenario_band in zip(
            merchant_ids,
            zone_reps,
            channel_groups,
            bucket_indexes,
            lambda_values,
            demand_classes,
            scenario_bands,
        ):
            demand_class_value = demand_class or ""
            scenario_band_value_row = scenario_band or ""
            if needs_grouping and (not demand_class_value or not scenario_band_value_row):
                meta_key = (merchant_id, zone_rep, channel_group)
                if not demand_class_value:
                    demand_class_value = demand_lookup.get(meta_key, "")
                if not scenario_band_value_row:
                    scenario_band_value_row = scenario_lookup.get(meta_key, "")
            if not demand_class_value:
                raise ValueError(
                    "demand_class missing for intensity row "
                    f"(merchant_id={merchant_id}, zone_representation={zone_rep}, channel_group={channel_group})"
                )
            if not scenario_band_value_row:
                scenario_band_value_row = scenario_band_value
            lam_value = float(lam or 0.0)
            if lam_value <= lambda_zero_eps:
                count = 0
            else:
                count = draw_count(
                    ctx,
                    rng_logger=rng_logger,
                    manifest_fingerprint=mf,
                    parameter_hash=ph,
                    seed=seed_value,
                    scenario_id=scenario_id_value,
                    merchant_id=merchant_id,
                    zone_rep=zone_rep,
                    bucket_index=int(bucket_index),
                    lambda_value=lam_value,
                    scenario_band=scenario_band_value_row,
                    demand_class=demand_class_value,
                )
            buf_manifest.append(mf)
            buf_param.append(ph)
            buf_seed.append(seed_value)
            buf_scenario.append(scenario_id_value)
            buf_merchant.append(merchant_id)
            buf_zone.append(zone_rep)
            buf_channel.append(channel_group)
            buf_bucket.append(int(bucket_index))
            buf_count.append(int(count))
            buf_spec.append("1.0.0")
            buffered += 1
            if buffered >= flush_every:
                writer = _write_parquet_batch(counts_part_path, buffers, writer)
                buffered = 0
                _reset_buffers(buffers)

    if buffered:
        writer = _write_parquet_batch(counts_part_path, buffers, writer)
        buffered = 0
        _reset_buffers(buffers)
    if writer is None:
        _write_empty_s3(counts_part_path)
    else:
        writer.close()
    rng_logger.close()


def _merge_count_parts(chunks: Sequence[_RowGroupChunk], output_path: Path) -> None:
    writer: pq.ParquetWriter | None = None
    for chunk in chunks:
        part = chunk.counts_part
        part_file = pq.ParquetFile(part)
        for rg_index in range(part_file.metadata.num_row_groups):
            table = part_file.read_row_group(rg_index)
            if writer is None:
                writer = pq.ParquetWriter(output_path, table.schema)
            writer.write_table(table)
    if writer is None:
        _write_empty_s3(output_path)
    else:
        writer.close()


def _merge_event_parts(
    *,
    chunks: Sequence[_RowGroupChunk],
    events_dir: Path,
    trace_dir: Path,
    totals: dict[str, int],
    trace_totals: dict[tuple[str, str], dict[str, int]],
    inputs: CountInputs,
) -> None:
    events_dir.mkdir(parents=True, exist_ok=True)
    trace_dir.mkdir(parents=True, exist_ok=True)
    event_path = events_dir / "part-00000.jsonl"
    trace_path = trace_dir / "rng_trace_log.jsonl"

    events_total = int(totals.get("events_total", 0))
    draws_total = int(totals.get("draws_total", 0))
    blocks_total = int(totals.get("blocks_total", 0))
    with event_path.open("a", encoding="utf-8") as event_handle, trace_path.open(
        "a", encoding="utf-8"
    ) as trace_handle:
        for chunk in chunks:
            part_path = chunk.event_part
            if not part_path.exists():
                continue
            with part_path.open("r", encoding="utf-8") as part_handle:
                for line in part_handle:
                    event_handle.write(line)
                    record = json.loads(line)
                    draws = int(record.get("draws", 0) or 0)
                    blocks = int(record.get("blocks", 0) or 0)
                    events_total = min(events_total + 1, U64_MAX)
                    draws_total = min(draws_total + max(0, draws), U64_MAX)
                    blocks_total = min(blocks_total + max(0, blocks), U64_MAX)
                    module = str(record.get("module", ""))
                    substream = str(record.get("substream_label", ""))
                    key = (module, substream)
                    totals_entry = trace_totals.setdefault(
                        key, {"events": 0, "blocks": 0, "draws": 0}
                    )
                    totals_entry["events"] = min(totals_entry["events"] + 1, U64_MAX)
                    totals_entry["blocks"] = min(totals_entry["blocks"] + blocks, U64_MAX)
                    totals_entry["draws"] = min(totals_entry["draws"] + max(0, draws), U64_MAX)
                    trace_record = {
                        "ts_utc": record.get("ts_utc"),
                        "module": module,
                        "substream_label": substream,
                        "events_total": totals_entry["events"],
                        "blocks_total": totals_entry["blocks"],
                        "draws_total": totals_entry["draws"],
                        "rng_counter_before_hi": record.get("rng_counter_before_hi"),
                        "rng_counter_before_lo": record.get("rng_counter_before_lo"),
                        "rng_counter_after_hi": record.get("rng_counter_after_hi"),
                        "rng_counter_after_lo": record.get("rng_counter_after_lo"),
                        "run_id": record.get("run_id", inputs.run_id),
                        "seed": record.get("seed", inputs.seed),
                    }
                    trace_handle.write(json.dumps(trace_record, sort_keys=True))
                    trace_handle.write("\n")

    totals["events_total"] = int(events_total)
    totals["draws_total"] = int(draws_total)
    totals["blocks_total"] = int(blocks_total)
    _write_rng_summary(trace_dir=trace_dir, totals=totals, inputs=inputs)


def _log_progress(
    *,
    scenario_id: str,
    processed_rows: int,
    total_rows: int,
    start_time: float,
    now: float,
) -> None:
    elapsed = max(now - start_time, 0.0)
    rate = processed_rows / elapsed if elapsed > 0 else 0.0
    remaining = max(total_rows - processed_rows, 0)
    eta = remaining / rate if rate > 0 else 0.0
    logger.info(
        "5B.S3 progress %s/%s rows (scenario_id=%s, elapsed=%.1fs, rate=%.2f/s, eta=%.1fs)",
        processed_rows,
        total_rows,
        scenario_id,
        elapsed,
        rate,
        eta,
    )


def _cleanup_parts(*, chunks: Sequence[_RowGroupChunk], parts_dir: Path, event_parts_dir: Path) -> None:
    for chunk in chunks:
        if chunk.counts_part.exists():
            chunk.counts_part.unlink()
        if chunk.event_part.exists():
            chunk.event_part.unlink()
    if parts_dir.exists():
        shutil.rmtree(parts_dir, ignore_errors=True)
    if event_parts_dir.exists():
        shutil.rmtree(event_parts_dir, ignore_errors=True)


def _rng_events_dir(
    *, data_root: Path, family: str, seed: int, parameter_hash: str, run_id: str
) -> Path:
    return (
        data_root
        / "logs"
        / "rng"
        / "events"
        / family
        / f"seed={seed}"
        / f"parameter_hash={parameter_hash}"
        / f"run_id={run_id}"
    )


def _rng_trace_dir(*, data_root: Path, seed: int, parameter_hash: str, run_id: str) -> Path:
    return (
        data_root
        / "logs"
        / "rng"
        / "trace"
        / f"seed={seed}"
        / f"parameter_hash={parameter_hash}"
        / f"run_id={run_id}"
    )


def _reset_rng_logs(*, events_dir: Path, trace_dir: Path) -> None:
    if events_dir.exists():
        event_file = events_dir / "part-00000.jsonl"
        if event_file.exists():
            event_file.unlink()
        parts_dir = events_dir / "_parts"
        if parts_dir.exists():
            shutil.rmtree(parts_dir, ignore_errors=True)
    if trace_dir.exists():
        trace_file = trace_dir / "rng_trace_log.jsonl"
        if trace_file.exists():
            trace_file.unlink()
        summary_file = trace_dir / "rng_totals.json"
        if summary_file.exists():
            summary_file.unlink()


def _load_rng_summary(trace_dir: Path) -> dict[str, int]:
    summary_path = trace_dir / "rng_totals.json"
    if not summary_path.exists():
        return {"events_total": 0, "draws_total": 0, "blocks_total": 0}
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"events_total": 0, "draws_total": 0, "blocks_total": 0}
    return {
        "events_total": int(payload.get("events_total", 0) or 0),
        "draws_total": int(payload.get("draws_total", 0) or 0),
        "blocks_total": int(payload.get("blocks_total", 0) or 0),
    }


def _write_rng_summary(*, trace_dir: Path, totals: Mapping[str, int], inputs: CountInputs) -> None:
    summary_path = trace_dir / "rng_totals.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "seed": inputs.seed,
        "parameter_hash": inputs.parameter_hash,
        "manifest_fingerprint": inputs.manifest_fingerprint,
        "run_id": inputs.run_id,
        "events_total": int(totals.get("events_total", 0)),
        "draws_total": int(totals.get("draws_total", 0)),
        "blocks_total": int(totals.get("blocks_total", 0)),
    }
    summary_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def _write_empty_s3(output_path: Path) -> None:
    empty_table = pa.table({name: [] for name in _S3_OUTPUT_SCHEMA.names}, schema=_S3_OUTPUT_SCHEMA)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(empty_table, output_path)


def _ensure_rng_logs(
    events_dir: Path, trace_dir: Path, totals: Mapping[str, int], inputs: CountInputs
) -> None:
    events_dir.mkdir(parents=True, exist_ok=True)
    trace_dir.mkdir(parents=True, exist_ok=True)
    event_path = events_dir / "part-00000.jsonl"
    trace_path = trace_dir / "rng_trace_log.jsonl"
    if not event_path.exists():
        event_path.write_text("", encoding="utf-8")
    if not trace_path.exists():
        trace_path.write_text("", encoding="utf-8")
    _write_rng_summary(trace_dir=trace_dir, totals=totals, inputs=inputs)


def _missing_classes(
    df: pl.DataFrame, *, count_law: str, class_multipliers: Mapping[str, float]
) -> list[str]:
    if count_law != "nb2":
        return []
    classes = {str(value) for value in df.get_column("demand_class").unique().to_list()}
    return sorted([value for value in classes if value not in class_multipliers])


def _draw_count(
    ctx: _CountLawContext,
    *,
    rng_logger: RNGLogWriter,
    manifest_fingerprint: str,
    parameter_hash: str,
    seed: int,
    scenario_id: str,
    merchant_id: str,
    zone_rep: str,
    bucket_index: int,
    lambda_value: float,
    scenario_band: str,
    demand_class: str,
) -> int:
    if lambda_value <= ctx.lambda_zero_eps:
        return 0
    count_law = ctx.count_law
    domain_key = f"merchant_id={merchant_id}|zone={zone_rep}|bucket_index={bucket_index}"
    if count_law == "poisson":
        event = derive_event(
            manifest_fingerprint=manifest_fingerprint,
            parameter_hash=parameter_hash,
            seed=seed,
            scenario_id=scenario_id,
            family_id="S3.bucket_count.v1",
            domain_key=domain_key,
            draws=1,
        )
        rng_logger.log_event(
            family="S3.bucket_count.v1",
            module="5B.S3",
            substream_label="bucket_count",
            event="rng_event_bucket_count",
            counter_before=event.before_state(),
            counter_after=event.after_state(),
            blocks=event.blocks,
            draws=event.draws,
            payload={
                "scenario_id": scenario_id,
                "domain_key": domain_key,
            },
        )
        u = event.uniforms()[0]
        return poisson_one_u(
            u=u,
            lam=lambda_value,
            lam_exact_max=ctx.poisson_exact_lambda_max,
            n_cap_exact=ctx.poisson_n_cap_exact,
            max_count=ctx.max_count_per_bucket,
        )
    if count_law != "nb2":
        raise ValueError("unsupported count_law_id")

    base_by_band = ctx.base_by_band
    class_mult = ctx.class_multipliers
    bounds = ctx.kappa_bounds
    kappa = float(base_by_band.get(scenario_band, base_by_band.get("baseline", 30.0)))
    kappa *= float(class_mult.get(demand_class, 1.0))
    kappa = max(float(bounds[0]), min(float(bounds[1]), kappa))

    event = derive_event(
        manifest_fingerprint=manifest_fingerprint,
        parameter_hash=parameter_hash,
        seed=seed,
        scenario_id=scenario_id,
        family_id="S3.bucket_count.v1",
        domain_key=domain_key,
        draws=2,
    )
    rng_logger.log_event(
        family="S3.bucket_count.v1",
        module="5B.S3",
        substream_label="bucket_count",
        event="rng_event_bucket_count",
        counter_before=event.before_state(),
        counter_after=event.after_state(),
        blocks=event.blocks,
        draws=event.draws,
        payload={
            "scenario_id": scenario_id,
            "domain_key": domain_key,
        },
    )
    u1, u2 = event.uniforms()
    lambda_gamma = gamma_one_u_approx(lambda_value, kappa, u1)
    return poisson_one_u(
        u=u2,
        lam=lambda_gamma,
        lam_exact_max=ctx.poisson_exact_lambda_max,
        n_cap_exact=ctx.poisson_n_cap_exact,
        max_count=ctx.max_count_per_bucket,
    )


def _build_count_context(cfg: Mapping[str, object]) -> _CountLawContext:
    count_law = str(cfg.get("count_law_id", "poisson"))
    lambda_zero_eps = float(cfg.get("lambda_zero_eps", 1e-6))
    sampler = cfg.get("poisson_sampler", {}) or {}
    nb2_cfg = cfg.get("nb2", {}) or {}
    kappa_cfg = nb2_cfg.get("kappa_law", {}) or {}
    base_by_band = kappa_cfg.get("base_by_scenario_band", {}) or {}
    class_mult = kappa_cfg.get("class_multipliers", {}) or {}
    bounds = kappa_cfg.get("kappa_bounds", [2.0, 200.0])
    return _CountLawContext(
        count_law=count_law,
        lambda_zero_eps=lambda_zero_eps,
        poisson_exact_lambda_max=float(sampler.get("poisson_exact_lambda_max", 50.0)),
        poisson_n_cap_exact=int(sampler.get("poisson_n_cap_exact", 200000)),
        max_count_per_bucket=int(cfg.get("max_count_per_bucket", 200000)),
        base_by_band={str(k): float(v) for k, v in base_by_band.items()},
        class_multipliers={str(k): float(v) for k, v in class_mult.items()},
        kappa_bounds=(float(bounds[0]), float(bounds[1])),
    )


def _write_dataset(
    data_root: Path,
    dictionary: Mapping[str, object],
    *,
    dataset_id: str,
    template_args: Mapping[str, object],
    df: pl.DataFrame,
) -> Path:
    path_template = render_dataset_path(dataset_id=dataset_id, template_args=template_args, dictionary=dictionary)
    output_path = data_root / path_template
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(output_path)
    return output_path


def _write_parquet_batch(
    output_path: Path, buffers: Mapping[str, list[object]], writer: pq.ParquetWriter | None
) -> pq.ParquetWriter:
    table = pa.table(buffers, schema=_S3_OUTPUT_SCHEMA)
    if writer is None:
        writer = pq.ParquetWriter(output_path, table.schema)
    writer.write_table(table)
    return writer


def _init_buffers() -> dict[str, list[object]]:
    return {name: [] for name in _S3_OUTPUT_SCHEMA.names}


def _reset_buffers(buffers: Mapping[str, list[object]]) -> None:
    for values in buffers.values():
        values.clear()


_S3_OUTPUT_SCHEMA = pa.schema(
    [
        ("manifest_fingerprint", pa.string()),
        ("parameter_hash", pa.string()),
        ("seed", pa.uint64()),
        ("scenario_id", pa.string()),
        ("merchant_id", pa.string()),
        ("zone_representation", pa.string()),
        ("channel_group", pa.string()),
        ("bucket_index", pa.int64()),
        ("count_N", pa.int64()),
        ("s3_spec_version", pa.string()),
    ]
)


def _write_run_report(
    inputs: CountInputs,
    data_root: Path,
    dictionary: Mapping[str, object],
) -> Path:
    path = data_root / render_dataset_path(
        dataset_id="segment_state_runs", template_args={}, dictionary=dictionary
    )
    payload = {
        "layer": "layer2",
        "segment": "5B",
        "state": "S3",
        "parameter_hash": inputs.parameter_hash,
        "manifest_fingerprint": inputs.manifest_fingerprint,
        "run_id": inputs.run_id,
        "status": "PASS",
    }
    key = SegmentStateKey(
        layer="layer2",
        segment="5B",
        state="S3",
        manifest_fingerprint=inputs.manifest_fingerprint,
        parameter_hash=inputs.parameter_hash,
        run_id=inputs.run_id,
    )
    return write_segment_state_run_report(path=path, key=key, payload=payload)


__all__ = ["CountInputs", "CountResult", "CountRunner"]
