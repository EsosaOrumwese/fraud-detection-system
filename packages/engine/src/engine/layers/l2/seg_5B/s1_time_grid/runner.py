"""Segment 5B S1 time grid and grouping runner."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from typing import Mapping

import polars as pl
import yaml

from engine.layers.l2.seg_5B.shared.control_plane import ScenarioBinding, SealedInventory, load_control_plane
from engine.layers.l2.seg_5B.shared.dictionary import load_dictionary, render_dataset_path, repository_root
from engine.layers.l2.seg_5B.shared.run_report import SegmentStateKey, write_segment_state_run_report

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TimeGridInputs:
    data_root: Path
    manifest_fingerprint: str
    parameter_hash: str
    run_id: str
    dictionary_path: Path | None = None


@dataclass(frozen=True)
class TimeGridResult:
    time_grid_paths: dict[str, Path]
    grouping_paths: dict[str, Path]
    run_report_path: Path


class TimeGridRunner:
    """Build scenario time grids and deterministic grouping for 5B."""

    def run(self, inputs: TimeGridInputs) -> TimeGridResult:
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
            },
        )
        time_policy = _load_yaml(inventory, "time_grid_policy_5B")
        group_policy = _load_yaml(inventory, "grouping_policy_5B")

        time_grid_paths: dict[str, Path] = {}
        grouping_paths: dict[str, Path] = {}
        for scenario in scenarios:
            logger.info("5B.S1 scenario=%s building time grid + grouping", scenario.scenario_id)
            grid_df = _build_time_grid(scenario, time_policy, inputs.manifest_fingerprint, inputs.parameter_hash)
            path = _write_dataset(
                data_root,
                dictionary,
                dataset_id="s1_time_grid_5B",
                template_args={
                    "manifest_fingerprint": inputs.manifest_fingerprint,
                    "scenario_id": scenario.scenario_id,
                },
                df=grid_df,
            )
            time_grid_paths[scenario.scenario_id] = path

            grouping_df = _build_grouping(
                scenario,
                inventory,
                group_policy,
                inputs.manifest_fingerprint,
                inputs.parameter_hash,
            )
            group_path = _write_dataset(
                data_root,
                dictionary,
                dataset_id="s1_grouping_5B",
                template_args={
                    "manifest_fingerprint": inputs.manifest_fingerprint,
                    "scenario_id": scenario.scenario_id,
                },
                df=grouping_df,
            )
            grouping_paths[scenario.scenario_id] = group_path

        run_report_path = _write_run_report(inputs, data_root)
        return TimeGridResult(time_grid_paths=time_grid_paths, grouping_paths=grouping_paths, run_report_path=run_report_path)


def _load_yaml(inventory: SealedInventory, artifact_id: str) -> Mapping[str, object]:
    files = inventory.resolve_files(artifact_id)
    if not files:
        raise FileNotFoundError(f"{artifact_id} missing from sealed inputs")
    return yaml.safe_load(files[0].read_text(encoding="utf-8")) or {}


def _parse_rfc3339(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def _format_rfc3339(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _build_time_grid(
    scenario: ScenarioBinding,
    policy: Mapping[str, object],
    manifest_fingerprint: str,
    parameter_hash: str,
) -> pl.DataFrame:
    if not scenario.horizon_start_utc or not scenario.horizon_end_utc:
        raise ValueError(f"scenario {scenario.scenario_id} missing horizon bounds")
    start = _parse_rfc3339(str(scenario.horizon_start_utc))
    end = _parse_rfc3339(str(scenario.horizon_end_utc))
    bucket_seconds = int(policy.get("bucket_duration_seconds", 3600))
    if bucket_seconds not in (900, 1800, 3600):
        raise ValueError("bucket_duration_seconds must be 900, 1800, or 3600")
    bucket_index_base = int(policy.get("bucket_index_base", 0))
    if bucket_index_base != 0:
        raise ValueError("bucket_index_base must be 0")
    bucket_index_origin = str(policy.get("bucket_index_origin", "horizon_start_utc"))
    if bucket_index_origin != "horizon_start_utc":
        raise ValueError("bucket_index_origin must be horizon_start_utc")
    alignment = str(policy.get("alignment_mode"))
    if alignment != "require_aligned_v1":
        raise ValueError("alignment_mode must be require_aligned_v1")
    if start.second != 0 or start.microsecond != 0:
        raise ValueError("horizon_start_utc not aligned to seconds")
    if end.second != 0 or end.microsecond != 0:
        raise ValueError("horizon_end_utc not aligned to seconds")
    if (start.minute * 60) % bucket_seconds != 0:
        raise ValueError("horizon_start_utc misaligned to bucket duration")
    if (end.minute * 60) % bucket_seconds != 0:
        raise ValueError("horizon_end_utc misaligned to bucket duration")
    total_seconds = int((end - start).total_seconds())
    if total_seconds % bucket_seconds != 0:
        raise ValueError("horizon length not divisible by bucket_duration_seconds")
    bucket_count = total_seconds // bucket_seconds

    guardrails = policy.get("guardrails", {}) or {}
    min_days = int(guardrails.get("min_horizon_days", 28))
    max_days = int(guardrails.get("max_horizon_days", 370))
    max_buckets = int(guardrails.get("max_buckets_per_scenario", 200000))
    horizon_days = total_seconds / 86400.0
    if horizon_days < min_days or horizon_days > max_days:
        raise ValueError("horizon length outside guardrails")
    if bucket_count > max_buckets:
        raise ValueError("bucket_count exceeds guardrails")

    emit_local = bool(policy.get("local_annotations", {}).get("emit", False))
    weekend_days = policy.get("local_annotations", {}).get("weekend_days", [6, 7])

    logger.info("5B.S1 time grid: scenario=%s buckets=%d", scenario.scenario_id, bucket_count)
    rows = []
    log_every = 10000
    log_interval_s = 120.0
    last_log = time.monotonic()
    for idx in range(bucket_count):
        now = time.monotonic()
        if idx == 0 or (idx + 1) % log_every == 0 or now - last_log >= log_interval_s:
            logger.info(
                "5B.S1 time grid: scenario=%s bucket %d/%d",
                scenario.scenario_id,
                idx + 1,
                bucket_count,
            )
            last_log = now
        bucket_start = start + timedelta(seconds=bucket_seconds * idx)
        bucket_end = bucket_start + timedelta(seconds=bucket_seconds)
        row = {
            "manifest_fingerprint": manifest_fingerprint,
            "parameter_hash": parameter_hash,
            "scenario_id": scenario.scenario_id,
            "bucket_index": bucket_index_base + idx,
            "bucket_start_utc": _format_rfc3339(bucket_start),
            "bucket_end_utc": _format_rfc3339(bucket_end),
            "bucket_duration_seconds": bucket_seconds,
            "scenario_is_baseline": bool(scenario.is_baseline),
            "scenario_is_stress": bool(scenario.is_stress),
            "s1_spec_version": "1.0.0",
        }
        if emit_local:
            local = bucket_start
            row["local_day_of_week"] = local.weekday() + 1
            row["local_minutes_since_midnight"] = local.hour * 60 + local.minute
            row["is_weekend"] = (local.weekday() + 1) in weekend_days
        rows.append(row)
    return pl.DataFrame(rows)


def _build_grouping(
    scenario: ScenarioBinding,
    inventory: SealedInventory,
    policy: Mapping[str, object],
    manifest_fingerprint: str,
    parameter_hash: str,
) -> pl.DataFrame:
    files = inventory.resolve_files("merchant_zone_scenario_local_5A", template_overrides={"scenario_id": scenario.scenario_id})
    if not files:
        raise FileNotFoundError(f"merchant_zone_scenario_local_5A missing for {scenario.scenario_id}")
    source = pl.read_parquet(files[0])
    zone_rep = (source["legal_country_iso"].cast(pl.Utf8) + ":" + source["tzid"].cast(pl.Utf8)).alias("zone_representation")
    if "channel_group" in source.columns:
        channel = source["channel_group"].fill_null("unknown").cast(pl.Utf8)
    else:
        channel = pl.lit("unknown")
    virtual_modes = _load_virtual_modes(inventory)
    base = source.select(
        [
            pl.col("merchant_id").cast(pl.Utf8).alias("merchant_id"),
            zone_rep,
            channel.alias("channel_group"),
            pl.lit(scenario.scenario_id).alias("scenario_id"),
            pl.lit(bool(scenario.is_baseline)).alias("scenario_is_baseline"),
            pl.lit(bool(scenario.is_stress)).alias("scenario_is_stress"),
            pl.col("demand_class").cast(pl.Utf8).alias("demand_class"),
        ]
    ).unique()

    zone_group_buckets = int(policy.get("zone_group_buckets", 16))
    in_stratum_buckets = int(policy.get("in_stratum_buckets", 32))
    group_format = str(
        policy.get(
            "group_id_format",
            "g|{scenario_band}|{demand_class}|{channel_group}|{virtual_band}|{zone_group_id}|b{b:02d}",
        )
    )

    zone_group_cache: dict[str, str] = {}
    virtual_band_cache: dict[str, str] = {}
    is_baseline = bool(scenario.is_baseline)
    is_stress = bool(scenario.is_stress)
    if is_baseline == is_stress:
        raise ValueError("scenario flags must set exactly one of baseline/stress")
    scenario_band_value = "baseline" if is_baseline else "stress"

    def zone_group_id(tzid: str) -> str:
        cached = zone_group_cache.get(tzid)
        if cached is not None:
            return cached
        digest = hashlib.sha256(f"5B.zone_group|{tzid}".encode("utf-8")).digest()
        bucket = digest[0] % zone_group_buckets
        value = f"zg{bucket:02d}"
        zone_group_cache[tzid] = value
        return value

    def virtual_band(merchant_id: str) -> str:
        cached = virtual_band_cache.get(merchant_id)
        if cached is not None:
            return cached
        mode = virtual_modes.get(merchant_id)
        if mode is None:
            raise ValueError(f"virtual_classification_3B missing merchant_id={merchant_id}")
        value = "virtual" if mode != "NON_VIRTUAL" else "physical"
        virtual_band_cache[merchant_id] = value
        return value

    def group_id_for(row: dict[str, object], zone_group: str, vband: str) -> str:
        msg = (
            "5B.group|"
            f"{row['scenario_id']}|{row['demand_class']}|{row['channel_group']}|"
            f"{vband}|{zone_group}|{row['merchant_id']}"
        )
        digest = hashlib.sha256(msg.encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:8], "big") % in_stratum_buckets
        return group_format.format(
            scenario_band=row["scenario_band"],
            demand_class=row["demand_class"],
            channel_group=row["channel_group"],
            virtual_band=vband,
            zone_group_id=zone_group,
            b=bucket,
        )

    logger.info("5B.S1 grouping: scenario=%s rows=%d", scenario.scenario_id, base.height)
    output_rows = []
    log_every = 25000
    log_interval_s = 120.0
    last_log = time.monotonic()
    for idx, row in enumerate(base.iter_rows(named=True), start=1):
        now = time.monotonic()
        if idx == 1 or idx % log_every == 0 or now - last_log >= log_interval_s:
            logger.info(
                "5B.S1 grouping: scenario=%s row %d/%d",
                scenario.scenario_id,
                idx,
                base.height,
            )
            last_log = now
        zone_rep = str(row["zone_representation"])
        tzid = zone_rep.split(":", 1)[-1]
        zone_group = zone_group_id(tzid)
        vband = virtual_band(str(row["merchant_id"]))
        grouping_key = (
            f"{scenario_band_value}|{row['demand_class']}|{row['channel_group']}|"
            f"{vband}|{zone_group}"
        )
        group_id = group_id_for(
            {
                "scenario_id": row["scenario_id"],
                "scenario_band": scenario_band_value,
                "demand_class": row["demand_class"],
                "channel_group": row["channel_group"],
                "merchant_id": row["merchant_id"],
            },
            zone_group,
            vband,
        )
        output_rows.append(
            {
                "manifest_fingerprint": manifest_fingerprint,
                "parameter_hash": parameter_hash,
                "scenario_id": row["scenario_id"],
                "merchant_id": row["merchant_id"],
                "zone_representation": zone_rep,
                "channel_group": row["channel_group"],
                "group_id": group_id,
                "grouping_key": grouping_key,
                "scenario_band": scenario_band_value,
                "demand_class": row["demand_class"],
                "virtual_band": vband,
                "zone_group_id": zone_group,
                "s1_spec_version": "1.0.0",
            }
        )

    output_df = pl.DataFrame(output_rows)
    _apply_grouping_realism(output_df, policy)
    return output_df.sort(["merchant_id", "zone_representation", "channel_group"])


def _apply_grouping_realism(df: pl.DataFrame, policy: Mapping[str, object]) -> None:
    targets = policy.get("realism_targets", {}) or {}
    min_groups = int(targets.get("min_groups_per_scenario", 1))
    max_groups = int(targets.get("max_groups_per_scenario", 1000000))
    min_median = int(targets.get("min_group_members_median", 1))
    max_single_share = float(targets.get("max_single_group_share", 1.0))

    groups = df.group_by("group_id").len().rename({"len": "count"})
    counts = groups["count"].to_list() if groups.height else []
    if not counts:
        raise ValueError("grouping produced no rows")
    n_groups = len(counts)
    if n_groups < min_groups or n_groups > max_groups:
        raise ValueError("grouping group count outside realism targets")
    if median(counts) < min_median:
        raise ValueError("grouping median membership below realism targets")
    max_share = max(counts) / max(sum(counts), 1)
    if max_share > max_single_share:
        raise ValueError("grouping max group share above realism targets")
    multi_member_fraction = sum(1 for count in counts if count > 1) / max(len(counts), 1)
    if multi_member_fraction < 0.8:
        raise ValueError("grouping multi-member fraction below realism targets")


def _load_virtual_modes(inventory: SealedInventory) -> dict[str, str]:
    files = inventory.resolve_files("virtual_classification_3B")
    if not files:
        raise FileNotFoundError("virtual_classification_3B missing from sealed inputs")
    df = pl.read_parquet(files[0])
    modes: dict[str, str] = {}
    for row in df.to_dicts():
        merchant_id = str(row.get("merchant_id"))
        if not merchant_id:
            continue
        mode = row.get("virtual_mode")
        if mode is not None:
            modes[merchant_id] = str(mode)
        else:
            modes[merchant_id] = "VIRTUAL_ONLY" if bool(row.get("is_virtual")) else "NON_VIRTUAL"
    return modes


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


def _write_run_report(inputs: TimeGridInputs, data_root: Path) -> Path:
    path = data_root / render_dataset_path(
        dataset_id="segment_state_runs", template_args={}, dictionary=load_dictionary(inputs.dictionary_path)
    )
    payload = {
        "layer": "layer2",
        "segment": "5B",
        "state": "S1",
        "parameter_hash": inputs.parameter_hash,
        "manifest_fingerprint": inputs.manifest_fingerprint,
        "run_id": inputs.run_id,
        "status": "PASS",
    }
    key = SegmentStateKey(
        layer="layer2",
        segment="5B",
        state="S1",
        manifest_fingerprint=inputs.manifest_fingerprint,
        parameter_hash=inputs.parameter_hash,
        run_id=inputs.run_id,
    )
    return write_segment_state_run_report(path=path, key=key, payload=payload)


__all__ = ["TimeGridInputs", "TimeGridResult", "TimeGridRunner"]
