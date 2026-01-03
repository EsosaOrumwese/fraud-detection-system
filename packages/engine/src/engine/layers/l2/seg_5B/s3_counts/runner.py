"""Segment 5B S3 bucket count runner."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

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
        count_law = str(count_policy.get("count_law_id", "poisson"))
        lambda_zero_eps = float(count_policy.get("lambda_zero_eps", 1e-6))
        rng_logger = RNGLogWriter(
            base_path=data_root,
            seed=inputs.seed,
            parameter_hash=inputs.parameter_hash,
            manifest_fingerprint=inputs.manifest_fingerprint,
            run_id=inputs.run_id,
        )

        count_paths: dict[str, Path] = {}
        logger.info("5B.S3 bucket counts start scenarios=%s", len(scenarios))
        try:
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
                        missing_classes = _missing_classes(class_df, count_policy)
                        if missing_classes:
                            raise ValueError(
                                f"arrival_count_config_5B missing class multipliers for {missing_classes}"
                            )

                total_rows = intensity_parquet.metadata.num_rows

                buffers = _init_buffers()
                buffered = 0
                writer: pq.ParquetWriter | None = None
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
                log_every = 50000
                log_interval = 120.0
                start_time = time.monotonic()
                last_log = start_time
                row_index = 0
                flush_every = 100000
                scenario_band_value = "baseline" if scenario.is_baseline else "stress"
                mf = inputs.manifest_fingerprint
                ph = inputs.parameter_hash
                seed = inputs.seed
                scenario_id = scenario.scenario_id
                for batch in intensity_parquet.iter_batches(batch_size=100000, columns=read_columns):
                    batch_df = pl.from_arrow(batch)
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
                        row_index += 1
                        demand_class_value = demand_class or ""
                        scenario_band_value_row = scenario_band or ""
                        if needs_grouping and (not demand_class_value or not scenario_band_value_row):
                            meta_key = (merchant_id, zone_rep, channel_group)
                            if not demand_class_value:
                                demand_class_value = demand_class_map.get(meta_key, "")
                            if not scenario_band_value_row:
                                scenario_band_value_row = scenario_band_map.get(meta_key, "")
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
                            count = _draw_count(
                                count_policy,
                                rng_logger=rng_logger,
                                manifest_fingerprint=mf,
                                parameter_hash=ph,
                                seed=seed,
                                scenario_id=scenario_id,
                                merchant_id=merchant_id,
                                zone_rep=zone_rep,
                                bucket_index=int(bucket_index),
                                lambda_value=lam_value,
                                scenario_band=scenario_band_value_row,
                                demand_class=demand_class_value,
                            )
                        buf_manifest.append(mf)
                        buf_param.append(ph)
                        buf_seed.append(seed)
                        buf_scenario.append(scenario_id)
                        buf_merchant.append(merchant_id)
                        buf_zone.append(zone_rep)
                        buf_channel.append(channel_group)
                        buf_bucket.append(int(bucket_index))
                        buf_count.append(int(count))
                        buf_spec.append("1.0.0")
                        buffered += 1

                        if buffered >= flush_every:
                            writer = _write_parquet_batch(output_path, buffers, writer)
                            buffered = 0
                            _reset_buffers(buffers)
                        now = time.monotonic()
                        if row_index % log_every == 0 or (now - last_log) >= log_interval:
                            elapsed = max(now - start_time, 0.0)
                            rate = row_index / elapsed if elapsed > 0 else 0.0
                            remaining = total_rows - row_index
                            eta = remaining / rate if rate > 0 else 0.0
                            logger.info(
                                "5B.S3 progress %s/%s rows (scenario_id=%s, elapsed=%.1fs, rate=%.2f/s, eta=%.1fs)",
                                row_index,
                                total_rows,
                                scenario.scenario_id,
                                elapsed,
                                rate,
                                eta,
                            )
                            last_log = now

                if buffered:
                    writer = _write_parquet_batch(output_path, buffers, writer)
                    buffered = 0
                    _reset_buffers(buffers)
                if writer is None:
                    empty_table = pa.table({name: [] for name in _S3_OUTPUT_SCHEMA.names}, schema=_S3_OUTPUT_SCHEMA)
                    pq.write_table(empty_table, output_path)
                else:
                    writer.close()
                count_path = output_path
                count_paths[scenario.scenario_id] = count_path
                scenario_elapsed = time.perf_counter() - scenario_timer
                rate = total_rows / scenario_elapsed if scenario_elapsed > 0 else 0.0
                logger.info(
                    "5B.S3 scenario complete scenario_id=%s rows=%d elapsed=%.2fs rate=%.1f rows/s",
                    scenario.scenario_id,
                    total_rows,
                    scenario_elapsed,
                    rate,
                )
        finally:
            rng_logger.close()

        run_report_path = _write_run_report(inputs, data_root, dictionary)
        return CountResult(count_paths=count_paths, run_report_path=run_report_path)


def _load_yaml(inventory: SealedInventory, artifact_id: str) -> Mapping[str, object]:
    files = inventory.resolve_files(artifact_id)
    if not files:
        raise FileNotFoundError(f"{artifact_id} missing from sealed inputs")
    return yaml.safe_load(files[0].read_text(encoding="utf-8")) or {}


def _missing_classes(df: pl.DataFrame, cfg: Mapping[str, object]) -> list[str]:
    count_law = str(cfg.get("count_law_id", "poisson"))
    if count_law != "nb2":
        return []
    class_mult = cfg.get("nb2", {}).get("kappa_law", {}).get("class_multipliers", {}) or {}
    classes = {str(value) for value in df.get_column("demand_class").unique().to_list()}
    return sorted([value for value in classes if value not in class_mult])


def _draw_count(
    cfg: Mapping[str, object],
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
    lambda_zero_eps = float(cfg.get("lambda_zero_eps", 1e-6))
    if lambda_value <= lambda_zero_eps:
        return 0
    count_law = str(cfg.get("count_law_id", "poisson"))
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
        sampler = cfg.get("poisson_sampler", {}) or {}
        return poisson_one_u(
            u=u,
            lam=lambda_value,
            lam_exact_max=float(sampler.get("poisson_exact_lambda_max", 50.0)),
            n_cap_exact=int(sampler.get("poisson_n_cap_exact", 200000)),
            max_count=int(cfg.get("max_count_per_bucket", 200000)),
        )
    if count_law != "nb2":
        raise ValueError("unsupported count_law_id")

    nb2_cfg = cfg.get("nb2", {}) or {}
    kappa_cfg = nb2_cfg.get("kappa_law", {}) or {}
    base_by_band = kappa_cfg.get("base_by_scenario_band", {}) or {}
    class_mult = kappa_cfg.get("class_multipliers", {}) or {}
    bounds = kappa_cfg.get("kappa_bounds", [2.0, 200.0])
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
    sampler = cfg.get("poisson_sampler", {}) or {}
    return poisson_one_u(
        u=u2,
        lam=lambda_gamma,
        lam_exact_max=float(sampler.get("poisson_exact_lambda_max", 50.0)),
        n_cap_exact=int(sampler.get("poisson_n_cap_exact", 200000)),
        max_count=int(cfg.get("max_count_per_bucket", 200000)),
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
