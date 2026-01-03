"""Segment 5B S2 realised intensity runner."""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import polars as pl
import pyarrow.parquet as pq
import yaml

from engine.layers.l1.seg_1A.s0_foundations.l2.rng_logging import RNGLogWriter
from engine.layers.l2.seg_5B.shared.control_plane import SealedInventory, load_control_plane
from engine.layers.l2.seg_5B.shared.dictionary import load_dictionary, render_dataset_path, repository_root
from engine.layers.l2.seg_5B.shared.rng import box_muller_from_pair, derive_event
from engine.layers.l2.seg_5B.shared.run_report import SegmentStateKey, write_segment_state_run_report

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IntensityInputs:
    data_root: Path
    manifest_fingerprint: str
    parameter_hash: str
    seed: int
    run_id: str
    dictionary_path: Path | None = None


@dataclass(frozen=True)
class IntensityResult:
    intensity_paths: dict[str, Path]
    latent_field_paths: dict[str, Path]
    run_report_path: Path


class IntensityRunner:
    """Build realised intensities from 5A surfaces and LGCP config."""

    def run(self, inputs: IntensityInputs) -> IntensityResult:
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
        lgcp_policy = _load_yaml(inventory, "arrival_lgcp_config_5B")
        diagnostics = bool(lgcp_policy.get("diagnostics", {}).get("emit_latent_field_diagnostic", False))
        latent_model_id = str(lgcp_policy.get("latent_model_id", "none"))
        rng_logger = RNGLogWriter(
            base_path=data_root,
            seed=inputs.seed,
            parameter_hash=inputs.parameter_hash,
            manifest_fingerprint=inputs.manifest_fingerprint,
            run_id=inputs.run_id,
        )

        intensity_paths: dict[str, Path] = {}
        latent_paths: dict[str, Path] = {}

        logger.info("5B.S2 realised intensity start scenarios=%s", len(scenarios))
        for scenario in scenarios:
            logger.info("5B.S2 scenario start scenario_id=%s", scenario.scenario_id)
            grouping_path = data_root / render_dataset_path(
                dataset_id="s1_grouping_5B",
                template_args={
                    "manifest_fingerprint": inputs.manifest_fingerprint,
                    "scenario_id": scenario.scenario_id,
                },
                dictionary=dictionary,
            )
            time_grid_path = data_root / render_dataset_path(
                dataset_id="s1_time_grid_5B",
                template_args={
                    "manifest_fingerprint": inputs.manifest_fingerprint,
                    "scenario_id": scenario.scenario_id,
                },
                dictionary=dictionary,
            )
            if not grouping_path.exists():
                raise FileNotFoundError(f"s1_grouping_5B missing at {grouping_path}")
            if not time_grid_path.exists():
                raise FileNotFoundError(f"s1_time_grid_5B missing at {time_grid_path}")

            grouping_df = pl.read_parquet(grouping_path)
            time_grid_df = pl.read_parquet(time_grid_path)
            bucket_count = time_grid_df.height

            files = inventory.resolve_files(
                "merchant_zone_scenario_local_5A", template_overrides={"scenario_id": scenario.scenario_id}
            )
            if not files:
                raise FileNotFoundError(f"merchant_zone_scenario_local_5A missing for {scenario.scenario_id}")
            source_df = pl.read_parquet(files[0])
            zone_rep = (
                source_df["legal_country_iso"].cast(pl.Utf8) + ":" + source_df["tzid"].cast(pl.Utf8)
            ).alias("zone_representation")
            channel = (
                source_df["channel_group"].fill_null("unknown").cast(pl.Utf8)
                if "channel_group" in source_df.columns
                else pl.lit("unknown")
            )
            intensity_df = source_df.select(
                [
                    pl.col("merchant_id").cast(pl.Utf8).alias("merchant_id"),
                    zone_rep,
                    channel.alias("channel_group"),
                    pl.col("local_horizon_bucket_index").cast(pl.Int64).alias("bucket_index"),
                    pl.col("lambda_local_scenario").cast(pl.Float64).alias("lambda_target"),
                ]
            )

            intensity_df = intensity_df.join(
                grouping_df.select(
                    [
                        "merchant_id",
                        "zone_representation",
                        "channel_group",
                        "group_id",
                        "scenario_band",
                        "demand_class",
                        "virtual_band",
                        "zone_group_id",
                    ]
                ),
                on=["merchant_id", "zone_representation", "channel_group"],
                how="left",
            )
            if intensity_df["group_id"].null_count() > 0:
                raise ValueError("group_id missing for some intensity rows")

            logger.info(
                "5B.S2 scenario inputs scenario_id=%s intensity_rows=%s buckets=%s",
                scenario.scenario_id,
                intensity_df.height,
                bucket_count,
            )
            if latent_model_id == "none":
                realised_df = intensity_df.with_columns(
                    (pl.col("lambda_target").clip_min(0.0).alias("lambda_realised")),
                    (pl.lit(0.0).alias("lambda_random_component")),
                )
                realised_df = realised_df.with_columns(
                    pl.lit(inputs.manifest_fingerprint).alias("manifest_fingerprint"),
                    pl.lit(inputs.parameter_hash).alias("parameter_hash"),
                    pl.lit(inputs.seed).alias("seed"),
                    pl.lit(scenario.scenario_id).alias("scenario_id"),
                    pl.lit("1.0.0").alias("s2_spec_version"),
                    pl.lit("arrival_rng_policy_5B").alias("rng_token"),
                    pl.col("lambda_target").alias("lambda_baseline"),
                ).select(
                    [
                        "manifest_fingerprint",
                        "parameter_hash",
                        "seed",
                        "scenario_id",
                        "merchant_id",
                        "zone_representation",
                        "channel_group",
                        "bucket_index",
                        "lambda_baseline",
                        "lambda_realised",
                        "lambda_random_component",
                        "rng_token",
                        "s2_spec_version",
                        "demand_class",
                        "scenario_band",
                        "virtual_band",
                        "zone_group_id",
                    ]
                )
                intensity_path = _write_dataset(
                    data_root,
                    dictionary,
                    dataset_id="s2_realised_intensity_5B",
                    template_args={
                        "manifest_fingerprint": inputs.manifest_fingerprint,
                        "scenario_id": scenario.scenario_id,
                        "seed": inputs.seed,
                    },
                    df=realised_df.sort(["merchant_id", "zone_representation", "bucket_index"]),
                )
                intensity_paths[scenario.scenario_id] = intensity_path
                continue

            latent_config = _prepare_latent_policy(lgcp_policy, latent_model_id)
            groups = (
                intensity_df.select(
                    ["group_id", "scenario_band", "demand_class", "channel_group", "virtual_band"]
                )
                .unique()
                .sort("group_id")
            )
            required_classes = {
                str(value) for value in groups.get_column("demand_class").unique().to_list()
            }
            missing_classes = sorted(
                [value for value in required_classes if value not in latent_config["class_mult"]]
            )
            if missing_classes:
                raise ValueError(
                    f"arrival_lgcp_config_5B missing class multipliers for {missing_classes}"
                )

            output_path = data_root / render_dataset_path(
                dataset_id="s2_realised_intensity_5B",
                template_args={
                    "manifest_fingerprint": inputs.manifest_fingerprint,
                    "scenario_id": scenario.scenario_id,
                    "seed": inputs.seed,
                },
                dictionary=dictionary,
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            temp_output_path = output_path.with_name(f"{output_path.stem}.tmp{output_path.suffix}")
            output_schema = {
                "manifest_fingerprint": pl.Utf8,
                "parameter_hash": pl.Utf8,
                "seed": pl.UInt64,
                "scenario_id": pl.Utf8,
                "merchant_id": pl.Utf8,
                "zone_representation": pl.Utf8,
                "channel_group": pl.Utf8,
                "bucket_index": pl.Int64,
                "lambda_baseline": pl.Float64,
                "lambda_realised": pl.Float64,
                "lambda_random_component": pl.Float64,
                "rng_token": pl.Utf8,
                "s2_spec_version": pl.Utf8,
                "demand_class": pl.Utf8,
                "scenario_band": pl.Utf8,
                "virtual_band": pl.Utf8,
                "zone_group_id": pl.Utf8,
            }
            latent_path = None
            latent_writer: pq.ParquetWriter | None = None
            latent_rows: list[Mapping[str, object]] = []
            if diagnostics:
                latent_path = data_root / render_dataset_path(
                    dataset_id="s2_latent_field_5B",
                    template_args={
                        "manifest_fingerprint": inputs.manifest_fingerprint,
                        "scenario_id": scenario.scenario_id,
                        "seed": inputs.seed,
                    },
                    dictionary=dictionary,
                )
                latent_path.parent.mkdir(parents=True, exist_ok=True)
            latent_schema = {
                "manifest_fingerprint": pl.Utf8,
                "parameter_hash": pl.Utf8,
                "seed": pl.UInt64,
                "scenario_id": pl.Utf8,
                "group_id": pl.Utf8,
                "bucket_index": pl.Int64,
                "latent_value": pl.Float64,
                "latent_mean": pl.Float64,
                "latent_std": pl.Float64,
                "s2_spec_version": pl.Utf8,
            }

            sorted_df = intensity_df.sort(
                ["group_id", "bucket_index", "merchant_id", "zone_representation"]
            )
            total_rows = sorted_df.height
            row_index = 0
            log_every = 50000
            log_interval = 120.0
            start_time = time.monotonic()
            last_log = start_time
            current_group_id = None
            current_factors: list[float] = []
            current_latent: list[float] = []
            current_sigma = 0.0
            output_rows: list[Mapping[str, object]] = []
            output_writer: pq.ParquetWriter | None = None
            flush_every = 100000

            for row in sorted_df.iter_rows(named=True):
                row_index += 1
                group_id = row.get("group_id")
                if group_id is None:
                    raise ValueError("group_id missing for intensity row")
                if group_id != current_group_id:
                    if diagnostics and latent_rows:
                        latent_writer = _write_parquet_batch(
                            latent_path,
                            latent_rows,
                            latent_writer,
                            schema=latent_schema,
                        )
                        latent_rows.clear()
                    scenario_band = str(row.get("scenario_band"))
                    demand_class = str(row.get("demand_class"))
                    channel_group = str(row.get("channel_group"))
                    virtual_band = str(row.get("virtual_band"))
                    current_latent, current_factors, current_sigma = _draw_latent_series(
                        inputs=inputs,
                        scenario_id=scenario.scenario_id,
                        group_id=str(group_id),
                        bucket_count=bucket_count,
                        latent_model_id=latent_model_id,
                        rng_logger=rng_logger,
                        config=latent_config,
                        scenario_band=scenario_band,
                        demand_class=demand_class,
                        channel_group=channel_group,
                        virtual_band=virtual_band,
                    )
                    if diagnostics:
                        for bucket_index in range(bucket_count):
                            latent_rows.append(
                                {
                                    "manifest_fingerprint": inputs.manifest_fingerprint,
                                    "parameter_hash": inputs.parameter_hash,
                                    "seed": inputs.seed,
                                    "scenario_id": scenario.scenario_id,
                                    "group_id": str(group_id),
                                    "bucket_index": bucket_index,
                                    "latent_value": float(current_latent[bucket_index]),
                                    "latent_mean": 0.0,
                                    "latent_std": float(current_sigma),
                                    "s2_spec_version": "1.0.0",
                                }
                            )
                    current_group_id = group_id

                bucket_index_value = row.get("bucket_index")
                if bucket_index_value is None:
                    raise ValueError("bucket_index missing for intensity row")
                bucket_index = int(bucket_index_value)
                if bucket_index < 0 or bucket_index >= len(current_factors):
                    raise ValueError("bucket_index outside latent factor range")
                factor = float(current_factors[bucket_index])
                lambda_target = float(row.get("lambda_target") or 0.0)
                lambda_realised = max(lambda_target * factor, 0.0)
                if latent_config["lambda_max_enabled"] and lambda_realised > latent_config["lambda_max"]:
                    lambda_realised = latent_config["lambda_max"]
                output_rows.append(
                    {
                        "manifest_fingerprint": inputs.manifest_fingerprint,
                        "parameter_hash": inputs.parameter_hash,
                        "seed": inputs.seed,
                        "scenario_id": scenario.scenario_id,
                        "merchant_id": row.get("merchant_id"),
                        "zone_representation": row.get("zone_representation"),
                        "channel_group": row.get("channel_group"),
                        "bucket_index": row.get("bucket_index"),
                        "lambda_baseline": lambda_target,
                        "lambda_realised": lambda_realised,
                        "lambda_random_component": lambda_realised - lambda_target,
                        "rng_token": "arrival_rng_policy_5B",
                        "s2_spec_version": "1.0.0",
                        "demand_class": row.get("demand_class"),
                        "scenario_band": row.get("scenario_band"),
                        "virtual_band": row.get("virtual_band"),
                        "zone_group_id": row.get("zone_group_id"),
                    }
                )
                if len(output_rows) >= flush_every:
                    output_writer = _write_parquet_batch(
                        temp_output_path,
                        output_rows,
                        output_writer,
                        schema=output_schema,
                    )
                    output_rows.clear()
                now = time.monotonic()
                if row_index % log_every == 0 or (now - last_log) >= log_interval:
                    elapsed = max(now - start_time, 0.0)
                    rate = row_index / elapsed if elapsed > 0 else 0.0
                    remaining = total_rows - row_index
                    eta = remaining / rate if rate > 0 else 0.0
                    logger.info(
                        "5B.S2 progress %s/%s rows (scenario_id=%s, elapsed=%.1fs, rate=%.2f/s, eta=%.1fs)",
                        row_index,
                        total_rows,
                        scenario.scenario_id,
                        elapsed,
                        rate,
                        eta,
                    )
                    last_log = now

            if output_rows:
                output_writer = _write_parquet_batch(
                    temp_output_path,
                    output_rows,
                    output_writer,
                    schema=output_schema,
                )
                output_rows.clear()
            if output_writer is None:
                empty_df = pl.DataFrame(schema=output_schema)
                empty_df.write_parquet(output_path)
            else:
                output_writer.close()
                sorted_lazy = pl.scan_parquet(temp_output_path).sort(
                    ["scenario_id", "merchant_id", "zone_representation", "channel_group", "bucket_index"]
                )
                sorted_lazy.sink_parquet(output_path)
                try:
                    temp_output_path.unlink()
                except FileNotFoundError:
                    pass
            intensity_paths[scenario.scenario_id] = output_path

            if diagnostics and latent_path is not None:
                if latent_rows:
                    latent_writer = _write_parquet_batch(
                        latent_path,
                        latent_rows,
                        latent_writer,
                        schema=latent_schema,
                    )
                    latent_rows.clear()
                if latent_writer is None:
                    empty_latent = pl.DataFrame(schema=latent_schema)
                    empty_latent.write_parquet(latent_path)
                else:
                    latent_writer.close()
                latent_paths[scenario.scenario_id] = latent_path

        run_report_path = _write_run_report(inputs, data_root, dictionary)
        return IntensityResult(
            intensity_paths=intensity_paths,
            latent_field_paths=latent_paths,
            run_report_path=run_report_path,
        )


def _load_yaml(inventory: SealedInventory, artifact_id: str) -> Mapping[str, object]:
    files = inventory.resolve_files(artifact_id)
    if not files:
        raise FileNotFoundError(f"{artifact_id} missing from sealed inputs")
    return yaml.safe_load(files[0].read_text(encoding="utf-8")) or {}


def _write_parquet_batch(
    output_path: Path,
    rows: list[Mapping[str, object]],
    writer: pq.ParquetWriter | None,
    *,
    schema: Mapping[str, pl.DataType] | None = None,
) -> pq.ParquetWriter:
    df = pl.DataFrame(rows, schema=schema)
    table = df.to_arrow()
    if writer is None:
        writer = pq.ParquetWriter(output_path, table.schema)
    writer.write_table(table)
    return writer


def _prepare_latent_policy(policy: Mapping[str, object], latent_model_id: str) -> dict[str, object]:
    if latent_model_id not in {"log_gaussian_ou_v1", "log_gaussian_iid_v1"}:
        raise ValueError(f"unsupported latent_model_id '{latent_model_id}'")
    kernel = policy.get("kernel", {}) or {}
    kernel_kind = str(kernel.get("kind", "ou_ar1_buckets_v1"))
    if latent_model_id == "log_gaussian_ou_v1" and kernel_kind != "ou_ar1_buckets_v1":
        raise ValueError("kernel.kind must be ou_ar1_buckets_v1 for log_gaussian_ou_v1")
    if latent_model_id == "log_gaussian_iid_v1" and kernel_kind != "iid_v1":
        raise ValueError("kernel.kind must be iid_v1 for log_gaussian_iid_v1")

    hyper = policy.get("hyperparam_law", {}) or {}
    sigma_cfg = hyper.get("sigma", {}) or {}
    length_cfg = hyper.get("length_scale_buckets", {}) or {}
    clipping = policy.get("clipping", {}) or {}

    return {
        "latent_model_id": latent_model_id,
        "base_sigma_by_band": sigma_cfg.get("base_by_scenario_band", {}) or {},
        "class_mult": sigma_cfg.get("class_multipliers", {}) or {},
        "channel_mult": sigma_cfg.get("channel_multipliers", {}) or {},
        "virtual_mult": sigma_cfg.get("virtual_multipliers", {}) or {},
        "sigma_bounds": sigma_cfg.get("sigma_bounds", [0.05, 1.2]),
        "base_L_by_band": length_cfg.get("base_by_scenario_band", {}) or {},
        "class_L_mult": length_cfg.get("class_multipliers", {}) or {},
        "L_bounds": length_cfg.get("length_scale_bounds", [2.0, 168.0]),
        "min_factor": float(clipping.get("min_factor", 0.2)),
        "max_factor": float(clipping.get("max_factor", 5.0)),
        "lambda_max_enabled": bool(clipping.get("lambda_max_enabled", False)),
        "lambda_max": float(clipping.get("lambda_max", 1e9)),
    }


def _draw_latent_series(
    *,
    inputs: IntensityInputs,
    scenario_id: str,
    group_id: str,
    bucket_count: int,
    latent_model_id: str,
    rng_logger: RNGLogWriter,
    config: Mapping[str, object],
    scenario_band: str,
    demand_class: str,
    channel_group: str,
    virtual_band: str,
) -> tuple[list[float], list[float], float]:
    base_sigma_by_band = config["base_sigma_by_band"]
    class_mult = config["class_mult"]
    channel_mult = config["channel_mult"]
    virtual_mult = config["virtual_mult"]
    sigma_bounds = config["sigma_bounds"]
    base_L_by_band = config["base_L_by_band"]
    class_L_mult = config["class_L_mult"]
    L_bounds = config["L_bounds"]
    min_factor = float(config["min_factor"])
    max_factor = float(config["max_factor"])

    sigma = float(base_sigma_by_band.get(scenario_band, base_sigma_by_band.get("baseline", 0.25)))
    sigma *= float(class_mult.get(demand_class, 1.0))
    sigma *= float(channel_mult.get(channel_group, channel_mult.get("default", 1.0)))
    sigma *= float(virtual_mult.get(virtual_band, virtual_mult.get("default", 1.0)))
    sigma = max(float(sigma_bounds[0]), min(float(sigma_bounds[1]), sigma))

    length_scale = float(base_L_by_band.get(scenario_band, base_L_by_band.get("baseline", 24.0)))
    length_scale *= float(class_L_mult.get(demand_class, 1.0))
    length_scale = max(float(L_bounds[0]), min(float(L_bounds[1]), length_scale))

    draws = 2 * bucket_count
    domain_key = f"group_id={group_id}"
    event = derive_event(
        manifest_fingerprint=inputs.manifest_fingerprint,
        parameter_hash=inputs.parameter_hash,
        seed=inputs.seed,
        scenario_id=scenario_id,
        family_id="S2.latent_vector.v1",
        domain_key=domain_key,
        draws=draws,
    )
    rng_logger.log_event(
        family="S2.latent_vector.v1",
        module="5B.S2",
        substream_label="latent_vector",
        event="rng_event_latent_vector",
        counter_before=event.before_state(),
        counter_after=event.after_state(),
        blocks=event.blocks,
        draws=event.draws,
        payload={
            "scenario_id": scenario_id,
            "domain_key": domain_key,
            "group_id": group_id,
        },
    )
    uniforms = event.uniforms()
    normals: list[float] = []
    for idx in range(0, len(uniforms), 2):
        normals.append(box_muller_from_pair(uniforms[idx], uniforms[idx + 1]))
    if len(normals) != bucket_count:
        raise ValueError("latent normal draw count mismatch")

    if latent_model_id == "log_gaussian_iid_v1":
        Z = [value * sigma for value in normals]
    else:
        phi = math.exp(-1.0 / max(length_scale, 1e-6))
        eps_std = sigma * math.sqrt(max(1.0 - phi * phi, 0.0))
        Z = [0.0] * bucket_count
        Z[0] = normals[0] * sigma
        for idx in range(1, bucket_count):
            Z[idx] = phi * Z[idx - 1] + normals[idx] * eps_std

    factor = [math.exp(value - 0.5 * sigma * sigma) for value in Z]
    factor = [min(max(value, min_factor), max_factor) for value in factor]
    return Z, factor, sigma


def _generate_latent_field(
    intensity_df: pl.DataFrame,
    policy: Mapping[str, object],
    *,
    inputs: IntensityInputs,
    scenario_id: str,
    bucket_count: int,
    latent_model_id: str,
    rng_logger: RNGLogWriter,
) -> pl.DataFrame | None:
    if latent_model_id == "none":
        return None
    if latent_model_id not in {"log_gaussian_ou_v1", "log_gaussian_iid_v1"}:
        raise ValueError(f"unsupported latent_model_id '{latent_model_id}'")

    kernel = policy.get("kernel", {}) or {}
    kernel_kind = str(kernel.get("kind", "ou_ar1_buckets_v1"))
    if latent_model_id == "log_gaussian_ou_v1" and kernel_kind != "ou_ar1_buckets_v1":
        raise ValueError("kernel.kind must be ou_ar1_buckets_v1 for log_gaussian_ou_v1")
    if latent_model_id == "log_gaussian_iid_v1" and kernel_kind != "iid_v1":
        raise ValueError("kernel.kind must be iid_v1 for log_gaussian_iid_v1")
    hyper = policy.get("hyperparam_law", {}) or {}
    sigma_cfg = hyper.get("sigma", {}) or {}
    length_cfg = hyper.get("length_scale_buckets", {}) or {}

    base_sigma_by_band = sigma_cfg.get("base_by_scenario_band", {}) or {}
    class_mult = sigma_cfg.get("class_multipliers", {}) or {}
    channel_mult = sigma_cfg.get("channel_multipliers", {}) or {}
    virtual_mult = sigma_cfg.get("virtual_multipliers", {}) or {}
    sigma_bounds = sigma_cfg.get("sigma_bounds", [0.05, 1.2])

    base_L_by_band = length_cfg.get("base_by_scenario_band", {}) or {}
    class_L_mult = length_cfg.get("class_multipliers", {}) or {}
    L_bounds = length_cfg.get("length_scale_bounds", [2.0, 168.0])

    clipping = policy.get("clipping", {}) or {}
    min_factor = float(clipping.get("min_factor", 0.2))
    max_factor = float(clipping.get("max_factor", 5.0))

    groups = (
        intensity_df.select(
            ["group_id", "scenario_band", "demand_class", "channel_group", "virtual_band"]
        )
        .unique()
        .sort("group_id")
    )

    required_classes = {str(value) for value in groups.get_column("demand_class").unique().to_list()}
    missing_classes = sorted([value for value in required_classes if value not in class_mult])
    if missing_classes:
        raise ValueError(f"arrival_lgcp_config_5B missing class multipliers for {missing_classes}")

    rows = []
    total_groups = groups.height
    log_every = 50
    log_interval = 120.0
    start_time = time.monotonic()
    last_log = start_time
    group_index = 0
    for row in groups.iter_rows(named=True):
        group_index += 1
        scenario_band = str(row.get("scenario_band"))
        demand_class = str(row.get("demand_class"))
        channel_group = str(row.get("channel_group"))
        virtual_band = str(row.get("virtual_band"))

        sigma = float(base_sigma_by_band.get(scenario_band, base_sigma_by_band.get("baseline", 0.25)))
        sigma *= float(class_mult.get(demand_class, 1.0))
        sigma *= float(channel_mult.get(channel_group, channel_mult.get("default", 1.0)))
        sigma *= float(virtual_mult.get(virtual_band, virtual_mult.get("default", 1.0)))
        sigma = max(float(sigma_bounds[0]), min(float(sigma_bounds[1]), sigma))

        length_scale = float(base_L_by_band.get(scenario_band, base_L_by_band.get("baseline", 24.0)))
        length_scale *= float(class_L_mult.get(demand_class, 1.0))
        length_scale = max(float(L_bounds[0]), min(float(L_bounds[1]), length_scale))

        draws = 2 * bucket_count
        domain_key = f"group_id={row['group_id']}"
        event = derive_event(
            manifest_fingerprint=inputs.manifest_fingerprint,
            parameter_hash=inputs.parameter_hash,
            seed=inputs.seed,
            scenario_id=scenario_id,
            family_id="S2.latent_vector.v1",
            domain_key=domain_key,
            draws=draws,
        )
        rng_logger.log_event(
            family="S2.latent_vector.v1",
            module="5B.S2",
            substream_label="latent_vector",
            event="rng_event_latent_vector",
            counter_before=event.before_state(),
            counter_after=event.after_state(),
            blocks=event.blocks,
            draws=event.draws,
            payload={
                "scenario_id": scenario_id,
                "domain_key": domain_key,
                "group_id": row["group_id"],
            },
        )

        uniforms = event.uniforms()
        normals = []
        for idx in range(0, len(uniforms), 2):
            normals.append(box_muller_from_pair(uniforms[idx], uniforms[idx + 1]))
        if len(normals) != bucket_count:
            raise ValueError("latent normal draw count mismatch")

        if latent_model_id == "log_gaussian_iid_v1":
            Z = [value * sigma for value in normals]
        else:
            phi = math.exp(-1.0 / max(length_scale, 1e-6))
            eps_std = sigma * math.sqrt(max(1.0 - phi * phi, 0.0))
            Z = [0.0] * bucket_count
            Z[0] = normals[0] * sigma
            for idx in range(1, bucket_count):
                Z[idx] = phi * Z[idx - 1] + normals[idx] * eps_std

        factor = [math.exp(value - 0.5 * sigma * sigma) for value in Z]
        factor = [min(max(value, min_factor), max_factor) for value in factor]

        for bucket_index in range(bucket_count):
            rows.append(
                {
                    "group_id": row["group_id"],
                    "bucket_index": bucket_index,
                    "latent_value": float(Z[bucket_index]),
                    "latent_mean": 0.0,
                    "latent_std": float(sigma),
                    "factor": float(factor[bucket_index]),
                }
            )
        now = time.monotonic()
        if group_index % log_every == 0 or (now - last_log) >= log_interval:
            elapsed = max(now - start_time, 0.0)
            rate = group_index / elapsed if elapsed > 0 else 0.0
            remaining = total_groups - group_index
            eta = remaining / rate if rate > 0 else 0.0
            logger.info(
                "5B.S2 latent field progress %s/%s groups (scenario_id=%s, buckets=%s, elapsed=%.1fs, rate=%.2f/s, eta=%.1fs)",
                group_index,
                total_groups,
                scenario_id,
                bucket_count,
                elapsed,
                rate,
                eta,
            )
            last_log = now

    return pl.DataFrame(rows)


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


def _write_run_report(
    inputs: IntensityInputs,
    data_root: Path,
    dictionary: Mapping[str, object],
) -> Path:
    path = data_root / render_dataset_path(
        dataset_id="segment_state_runs", template_args={}, dictionary=dictionary
    )
    payload = {
        "layer": "layer2",
        "segment": "5B",
        "state": "S2",
        "parameter_hash": inputs.parameter_hash,
        "manifest_fingerprint": inputs.manifest_fingerprint,
        "run_id": inputs.run_id,
        "status": "PASS",
    }
    key = SegmentStateKey(
        layer="layer2",
        segment="5B",
        state="S2",
        manifest_fingerprint=inputs.manifest_fingerprint,
        parameter_hash=inputs.parameter_hash,
        run_id=inputs.run_id,
    )
    return write_segment_state_run_report(path=path, key=key, payload=payload)


__all__ = ["IntensityInputs", "IntensityResult", "IntensityRunner"]
