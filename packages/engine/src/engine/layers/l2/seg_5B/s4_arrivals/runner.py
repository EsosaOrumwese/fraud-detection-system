"""Segment 5B S4 arrival synthesis runner."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Mapping
from zoneinfo import ZoneInfo

import polars as pl
import yaml

from engine.layers.l1.seg_1A.s0_foundations.l2.rng_logging import RNGLogWriter
from engine.layers.l2.seg_5B.shared.control_plane import SealedInventory, load_control_plane
from engine.layers.l2.seg_5B.shared.dictionary import load_dictionary, render_dataset_path, repository_root
from engine.layers.l2.seg_5B.shared.rng import derive_event
from engine.layers.l2.seg_5B.shared.run_report import SegmentStateKey, write_segment_state_run_report


@dataclass(frozen=True)
class ArrivalInputs:
    data_root: Path
    manifest_fingerprint: str
    parameter_hash: str
    seed: int
    run_id: str
    dictionary_path: Path | None = None


@dataclass(frozen=True)
class ArrivalResult:
    arrival_paths: dict[str, Path]
    summary_paths: dict[str, Path]
    run_report_path: Path


@dataclass
class AliasTable:
    values: list[object]
    probabilities: list[float]
    aliases: list[int]

    def sample(self, u: float) -> object:
        count = len(self.values)
        scaled = u * count
        idx = min(int(scaled), count - 1)
        frac = scaled - idx
        if frac >= self.probabilities[idx]:
            idx = self.aliases[idx]
        return self.values[idx]


class ArrivalRunner:
    """Build per-arrival events from bucket counts."""

    def run(self, inputs: ArrivalInputs) -> ArrivalResult:
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
        time_policy = _load_yaml(inventory, "arrival_time_placement_policy_5B")
        routing_policy = _load_yaml(inventory, "arrival_routing_policy_5B")
        _load_yaml(inventory, "arrival_rng_policy_5B")

        virtual_modes = _load_virtual_modes(inventory)
        settlement_tz = _load_virtual_settlement_tz(inventory)
        edge_alias_index = _load_edge_alias_index(inventory)
        edge_blob_bytes = _load_edge_alias_blob(inventory)
        edge_tz = _load_edge_tz(inventory)
        edge_universe_hash = _load_edge_universe_hash(inventory)
        zone_alloc_hash = _load_zone_alloc_hash(inventory)
        alias_policy_digest = _load_alias_layout_policy_digest(inventory)
        alias_index_payload = _load_alias_index(inventory)
        alias_blob_bytes = _load_alias_blob(inventory)
        _verify_alias_blob(alias_index_payload, alias_blob_bytes, alias_policy_digest)

        group_weights = _load_group_weights(inventory)
        site_lookup, site_tz = _load_site_lookup(inventory)

        rng_logger = RNGLogWriter(
            base_path=data_root,
            seed=inputs.seed,
            parameter_hash=inputs.parameter_hash,
            manifest_fingerprint=inputs.manifest_fingerprint,
            run_id=inputs.run_id,
        )

        max_arrivals = int(time_policy.get("guardrails", {}).get("max_arrivals_per_bucket", 200000))
        p_virtual_hybrid = float(routing_policy.get("hybrid_policy", {}).get("p_virtual_hybrid", 0.35))

        arrival_paths: dict[str, Path] = {}
        summary_paths: dict[str, Path] = {}
        group_alias_cache: dict[tuple[str, str], AliasTable] = {}
        site_alias_cache: dict[tuple[str, str], AliasTable] = {}
        for scenario in scenarios:
            count_path = data_root / render_dataset_path(
                dataset_id="s3_bucket_counts_5B",
                template_args={
                    "manifest_fingerprint": inputs.manifest_fingerprint,
                    "scenario_id": scenario.scenario_id,
                    "seed": inputs.seed,
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
            intensity_path = data_root / render_dataset_path(
                dataset_id="s2_realised_intensity_5B",
                template_args={
                    "manifest_fingerprint": inputs.manifest_fingerprint,
                    "scenario_id": scenario.scenario_id,
                    "seed": inputs.seed,
                },
                dictionary=dictionary,
            )
            if not count_path.exists():
                raise FileNotFoundError(f"s3_bucket_counts_5B missing at {count_path}")
            if not time_grid_path.exists():
                raise FileNotFoundError(f"s1_time_grid_5B missing at {time_grid_path}")
            if not intensity_path.exists():
                raise FileNotFoundError(f"s2_realised_intensity_5B missing at {intensity_path}")

            count_df = pl.read_parquet(count_path)
            time_grid_df = pl.read_parquet(time_grid_path)
            intensity_df = pl.read_parquet(intensity_path)
            intensity_df = intensity_df.select(
                [
                    "merchant_id",
                    "zone_representation",
                    "channel_group",
                    "bucket_index",
                    "lambda_realised",
                ]
            )
            count_df = count_df.join(
                intensity_df,
                on=["merchant_id", "zone_representation", "channel_group", "bucket_index"],
                how="left",
            )
            bucket_map = {
                int(row["bucket_index"]): (
                    _parse_rfc3339(str(row["bucket_start_utc"])),
                    _parse_rfc3339(str(row["bucket_end_utc"])),
                )
                for row in time_grid_df.to_dicts()
            }

            events = []
            summary_rows = []
            for row in count_df.sort(["merchant_id", "zone_representation", "bucket_index"]).to_dicts():
                count_n = int(row.get("count_N", 0))
                if count_n <= 0:
                    continue
                if count_n > max_arrivals:
                    raise ValueError("count_N exceeds max_arrivals_per_bucket guardrail")
                bucket_index = int(row["bucket_index"])
                bucket_start, bucket_end = bucket_map[bucket_index]
                duration_seconds = (bucket_end - bucket_start).total_seconds()

                merchant_id = str(row.get("merchant_id"))
                zone_rep = str(row.get("zone_representation"))
                legal_country_iso = zone_rep.split(":", 1)[0] if ":" in zone_rep else zone_rep
                vmode = virtual_modes.get(merchant_id, "NON_VIRTUAL")

                physical_count = 0
                virtual_count = 0
                bucket_events = []
                for seq in range(1, count_n + 1):
                    arrival_key = (
                        f"merchant_id={merchant_id}|zone={zone_rep}|"
                        f"bucket_index={bucket_index}|arrival_seq={seq}"
                    )
                    jitter_event = derive_event(
                        manifest_fingerprint=inputs.manifest_fingerprint,
                        parameter_hash=inputs.parameter_hash,
                        seed=inputs.seed,
                        scenario_id=scenario.scenario_id,
                        family_id="S4.arrival_time_jitter.v1",
                        domain_key=arrival_key,
                        draws=1,
                    )
                    rng_logger.log_event(
                        family="S4.arrival_time_jitter.v1",
                        module="5B.S4",
                        substream_label="arrival_time_jitter",
                        event="rng_event_arrival_time_jitter",
                        counter_before=jitter_event.before_state(),
                        counter_after=jitter_event.after_state(),
                        blocks=jitter_event.blocks,
                        draws=jitter_event.draws,
                        payload={
                            "scenario_id": scenario.scenario_id,
                            "domain_key": arrival_key,
                        },
                    )
                    u_time = jitter_event.uniforms()[0]
                    offset_us = int(u_time * duration_seconds * 1_000_000)
                    ts_utc = bucket_start + timedelta(microseconds=offset_us)
                    if ts_utc >= bucket_end:
                        ts_utc = bucket_end - timedelta(microseconds=1)

                    is_virtual = False
                    site_id = None
                    edge_id = None
                    tz_group_id = None
                    tzid_operational = None
                    tzid_settlement = None

                    site_event = None
                    u_group = None
                    u_site = None
                    if vmode == "NON_VIRTUAL":
                        site_event = derive_event(
                            manifest_fingerprint=inputs.manifest_fingerprint,
                            parameter_hash=inputs.parameter_hash,
                            seed=inputs.seed,
                            scenario_id=scenario.scenario_id,
                            family_id="S4.arrival_site_pick.v1",
                            domain_key=arrival_key,
                            draws=2,
                        )
                        rng_logger.log_event(
                            family="S4.arrival_site_pick.v1",
                            module="5B.S4",
                            substream_label="arrival_site_pick",
                            event="rng_event_arrival_site_pick",
                            counter_before=site_event.before_state(),
                            counter_after=site_event.after_state(),
                            blocks=site_event.blocks,
                            draws=site_event.draws,
                            payload={
                                "scenario_id": scenario.scenario_id,
                                "domain_key": arrival_key,
                            },
                        )
                        u_group, u_site = site_event.uniforms()
                        is_virtual = False
                    elif vmode == "HYBRID":
                        site_event = derive_event(
                            manifest_fingerprint=inputs.manifest_fingerprint,
                            parameter_hash=inputs.parameter_hash,
                            seed=inputs.seed,
                            scenario_id=scenario.scenario_id,
                            family_id="S4.arrival_site_pick.v1",
                            domain_key=arrival_key,
                            draws=2,
                        )
                        rng_logger.log_event(
                            family="S4.arrival_site_pick.v1",
                            module="5B.S4",
                            substream_label="arrival_site_pick",
                            event="rng_event_arrival_site_pick",
                            counter_before=site_event.before_state(),
                            counter_after=site_event.after_state(),
                            blocks=site_event.blocks,
                            draws=site_event.draws,
                            payload={
                                "scenario_id": scenario.scenario_id,
                                "domain_key": arrival_key,
                            },
                        )
                        u_group, u_site = site_event.uniforms()
                        is_virtual = u_group < p_virtual_hybrid
                    else:
                        is_virtual = True

                    if is_virtual:
                        virtual_count += 1
                        edge_id = _select_virtual_edge(
                            edge_alias_index,
                            edge_blob_bytes,
                            merchant_id,
                            u_edge=_edge_uniform(
                                rng_logger=rng_logger,
                                inputs=inputs,
                                scenario_id=scenario.scenario_id,
                                arrival_key=arrival_key,
                            ),
                        )
                        tzid_operational = edge_tz.get(edge_id)
                        if not tzid_operational:
                            raise ValueError(f"edge_catalogue_3B missing tzid_operational for edge_id={edge_id}")
                        tzid_settlement = settlement_tz.get(merchant_id)
                        if not tzid_settlement:
                            raise ValueError(f"virtual_settlement_3B missing tzid for merchant_id={merchant_id}")
                        tz_group_id = None
                        routing_hash = edge_universe_hash
                        tzid_primary = tzid_operational
                    else:
                        physical_count += 1
                        if u_group is None or u_site is None:
                            raise ValueError("arrival_site_pick uniforms missing for physical routing")
                        group_alias = _ensure_group_alias(
                            group_weights=group_weights,
                            cache=group_alias_cache,
                            merchant_id=merchant_id,
                            ts_utc=ts_utc,
                        )
                        tz_group_id = str(group_alias.sample(u_group))
                        site_alias = _ensure_site_alias(
                            site_lookup=site_lookup,
                            cache=site_alias_cache,
                            merchant_id=merchant_id,
                            tz_group_id=tz_group_id,
                        )
                        site_choice = int(site_alias.sample(u_site))
                        site_id = _site_id(merchant_id, site_choice)
                        tzid_primary = site_tz.get(site_id)
                        if not tzid_primary:
                            raise ValueError(f"site_timezones missing tzid for site_id={site_id}")
                        tzid_operational = tzid_primary
                        tzid_settlement = tzid_primary
                        routing_hash = zone_alloc_hash

                    tz_primary_obj = _safe_zone(tzid_primary or "Etc/UTC")
                    ts_local_primary = ts_utc.astimezone(tz_primary_obj)
                    tz_settlement_obj = _safe_zone(tzid_settlement or tzid_primary or "Etc/UTC")
                    ts_local_settlement = ts_utc.astimezone(tz_settlement_obj)
                    tz_operational_obj = _safe_zone(tzid_operational or tzid_primary or "Etc/UTC")
                    ts_local_operational = ts_utc.astimezone(tz_operational_obj)

                    bucket_events.append(
                        {
                            "manifest_fingerprint": inputs.manifest_fingerprint,
                            "parameter_hash": inputs.parameter_hash,
                            "seed": inputs.seed,
                            "scenario_id": scenario.scenario_id,
                            "merchant_id": merchant_id,
                            "zone_representation": zone_rep,
                            "channel_group": row.get("channel_group"),
                            "bucket_index": bucket_index,
                            "arrival_seq": seq,
                            "ts_utc": _format_rfc3339(ts_utc),
                            "tzid_primary": tzid_primary,
                            "ts_local_primary": _format_rfc3339(ts_local_primary),
                            "tzid_settlement": tzid_settlement,
                            "ts_local_settlement": _format_rfc3339(ts_local_settlement),
                            "tzid_operational": tzid_operational,
                            "ts_local_operational": _format_rfc3339(ts_local_operational),
                            "tz_group_id": tz_group_id,
                            "site_id": site_id,
                            "edge_id": edge_id,
                            "routing_universe_hash": routing_hash,
                            "lambda_realised": row.get("lambda_realised"),
                            "is_virtual": is_virtual,
                            "s4_spec_version": "1.0.0",
                        }
                    )

                bucket_events.sort(key=lambda item: (item["ts_utc"], item["arrival_seq"]))
                events.extend(bucket_events)

                summary_rows.append(
                    {
                        "manifest_fingerprint": inputs.manifest_fingerprint,
                        "parameter_hash": inputs.parameter_hash,
                        "seed": inputs.seed,
                        "scenario_id": scenario.scenario_id,
                        "merchant_id": merchant_id,
                        "zone_representation": zone_rep,
                        "channel_group": row.get("channel_group"),
                        "bucket_index": bucket_index,
                        "count_N": count_n,
                        "count_physical": physical_count,
                        "count_virtual": virtual_count,
                        "s4_spec_version": "1.0.0",
                    }
                )

            events_df = pl.DataFrame(events)
            arrival_path = _write_dataset(
                data_root,
                dictionary,
                dataset_id="arrival_events_5B",
                template_args={
                    "manifest_fingerprint": inputs.manifest_fingerprint,
                    "scenario_id": scenario.scenario_id,
                    "seed": inputs.seed,
                },
                df=events_df.sort(["merchant_id", "bucket_index", "ts_utc", "arrival_seq"]),
            )
            arrival_paths[scenario.scenario_id] = arrival_path

            summary_df = pl.DataFrame(summary_rows)
            summary_path = _write_dataset(
                data_root,
                dictionary,
                dataset_id="s4_arrival_summary_5B",
                template_args={
                    "manifest_fingerprint": inputs.manifest_fingerprint,
                    "scenario_id": scenario.scenario_id,
                    "seed": inputs.seed,
                },
                df=summary_df.sort(["merchant_id", "zone_representation", "bucket_index"]),
            )
            summary_paths[scenario.scenario_id] = summary_path

        run_report_path = _write_run_report(inputs, data_root, dictionary)
        return ArrivalResult(arrival_paths=arrival_paths, summary_paths=summary_paths, run_report_path=run_report_path)


def _load_yaml(inventory: SealedInventory, artifact_id: str) -> Mapping[str, object]:
    files = inventory.resolve_files(artifact_id)
    if not files:
        raise FileNotFoundError(f"{artifact_id} missing from sealed inputs")
    return yaml.safe_load(files[0].read_text(encoding="utf-8")) or {}


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


def _load_virtual_settlement_tz(inventory: SealedInventory) -> dict[str, str]:
    files = inventory.resolve_files("virtual_settlement_3B")
    if not files:
        return {}
    df = pl.read_parquet(files[0])
    mapping = {}
    for row in df.to_dicts():
        merchant_id = str(row.get("merchant_id"))
        tzid = row.get("tzid_settlement")
        if merchant_id and tzid:
            mapping[merchant_id] = str(tzid)
    return mapping


def _load_edge_alias_index(inventory: SealedInventory) -> dict[str, tuple[int, int]]:
    files = inventory.resolve_files("edge_alias_index_3B")
    if not files:
        raise FileNotFoundError("edge_alias_index_3B missing from sealed inputs")
    df = pl.read_parquet(files[0])
    mapping: dict[str, tuple[int, int]] = {}
    for row in df.to_dicts():
        if str(row.get("scope")) != "MERCHANT":
            continue
        merchant_id = str(row.get("merchant_id"))
        offset = row.get("blob_offset_bytes")
        length = row.get("blob_length_bytes")
        if merchant_id and offset is not None and length is not None:
            mapping[merchant_id] = (int(offset), int(length))
    return mapping


def _load_edge_alias_blob(inventory: SealedInventory) -> bytes:
    files = inventory.resolve_files("edge_alias_blob_3B")
    if not files:
        raise FileNotFoundError("edge_alias_blob_3B missing from sealed inputs")
    blob_path = files[0]
    if blob_path.is_dir():
        blob_path = blob_path / "edge_alias_blob_3B.bin"
    return blob_path.read_bytes()


def _load_edge_tz(inventory: SealedInventory) -> dict[str, str]:
    files = inventory.resolve_files("edge_catalogue_3B")
    if not files:
        return {}
    df = pl.read_parquet(files[0])
    mapping = {}
    for row in df.to_dicts():
        edge_id = str(row.get("edge_id"))
        tzid = row.get("tzid_operational")
        if edge_id and tzid:
            mapping[edge_id] = str(tzid)
    return mapping


def _load_edge_universe_hash(inventory: SealedInventory) -> str:
    files = inventory.resolve_files("edge_universe_hash_3B")
    if not files:
        return ""
    payload = json.loads(files[0].read_text(encoding="utf-8"))
    return str(payload.get("universe_hash", ""))


def _load_zone_alloc_hash(inventory: SealedInventory) -> str:
    files = inventory.resolve_files("zone_alloc_universe_hash")
    if not files:
        return ""
    payload = json.loads(files[0].read_text(encoding="utf-8"))
    return str(payload.get("routing_universe_hash", ""))


def _load_group_weights(inventory: SealedInventory) -> dict[tuple[str, str], tuple[list[str], list[float]]]:
    files = inventory.resolve_files("s4_group_weights")
    if not files:
        raise FileNotFoundError("s4_group_weights missing from sealed inputs")
    df = pl.read_parquet(files[0]).select(["merchant_id", "utc_day", "tz_group_id", "p_group"])
    mapping: dict[tuple[str, str], tuple[list[str], list[float]]] = {}
    for merchant_id, utc_day in df.select(["merchant_id", "utc_day"]).unique().iter_rows():
        subset = df.filter((pl.col("merchant_id") == merchant_id) & (pl.col("utc_day") == utc_day))
        subset = subset.sort("tz_group_id")
        tz_groups = [str(value) for value in subset.get_column("tz_group_id").to_list()]
        weights = [float(value) for value in subset.get_column("p_group").to_list()]
        mapping[(str(merchant_id), str(utc_day))] = (tz_groups, weights)
    return mapping


def _load_site_lookup(inventory: SealedInventory) -> tuple[dict[tuple[str, str], tuple[list[int], list[float]]], dict[int, str]]:
    site_weights_files = inventory.resolve_files("s1_site_weights")
    if not site_weights_files:
        raise FileNotFoundError("s1_site_weights missing from sealed inputs")
    site_weights = pl.read_parquet(site_weights_files[0]).select(
        ["merchant_id", "legal_country_iso", "site_order", "p_weight"]
    )
    site_tz_files = inventory.resolve_files("site_timezones")
    if not site_tz_files:
        raise FileNotFoundError("site_timezones missing from sealed inputs")
    site_tz = pl.read_parquet(site_tz_files[0]).select(
        ["merchant_id", "legal_country_iso", "site_order", "tzid"]
    )
    lookup = site_weights.join(site_tz, on=["merchant_id", "legal_country_iso", "site_order"], how="inner")
    if lookup.height == 0:
        raise ValueError("join of s1_site_weights and site_timezones produced zero rows")
    lookup = lookup.sort(["merchant_id", "tzid", "site_order"])
    site_map: dict[tuple[str, str], tuple[list[int], list[float]]] = {}
    tz_map: dict[int, str] = {}
    for row in lookup.to_dicts():
        merchant_id = str(row.get("merchant_id"))
        tzid = str(row.get("tzid"))
        site_order = int(row.get("site_order"))
        key = (merchant_id, tzid)
        entry = site_map.get(key)
        if entry is None:
            site_map[key] = ([site_order], [float(row.get("p_weight"))])
        else:
            entry[0].append(site_order)
            entry[1].append(float(row.get("p_weight")))
        tz_map[_site_id(merchant_id, site_order)] = tzid
    return site_map, tz_map


def _ensure_group_alias(
    *,
    group_weights: dict[tuple[str, str], tuple[list[str], list[float]]],
    cache: dict[tuple[str, str], AliasTable],
    merchant_id: str,
    ts_utc: datetime,
) -> AliasTable:
    utc_day = ts_utc.strftime("%Y-%m-%d")
    key = (merchant_id, utc_day)
    cached = cache.get(key)
    if cached is not None:
        return cached
    entry = group_weights.get(key)
    if entry is None:
        raise ValueError(f"s4_group_weights missing for merchant_id={merchant_id} day={utc_day}")
    tz_groups, weights = entry
    alias = _build_alias_table(tz_groups, weights)
    cache[key] = alias
    return alias


def _ensure_site_alias(
    *,
    site_lookup: dict[tuple[str, str], tuple[list[int], list[float]]],
    cache: dict[tuple[str, str], AliasTable],
    merchant_id: str,
    tz_group_id: str,
) -> AliasTable:
    key = (merchant_id, tz_group_id)
    cached = cache.get(key)
    if cached is not None:
        return cached
    entry = site_lookup.get((merchant_id, tz_group_id))
    if entry is None:
        raise ValueError(f"s1_site_weights missing for merchant_id={merchant_id} tzid={tz_group_id}")
    site_orders, weights = entry
    alias = _build_alias_table(site_orders, weights)
    cache[key] = alias
    return alias


def _select_virtual_edge(
    edge_alias_index: dict[str, tuple[int, int]],
    blob_bytes: bytes,
    merchant_id: str,
    u_edge: float,
) -> str:
    offsets = edge_alias_index.get(merchant_id)
    if offsets is None:
        raise ValueError(f"edge_alias_index_3B missing merchant_id={merchant_id}")
    offset, length = offsets
    slice_bytes = _edge_slice(blob_bytes, offset, length)
    payload = json.loads(slice_bytes.decode("utf-8"))
    edge_ids = [str(value) for value in payload.get("edge_ids", [])]
    weights = [float(value) for value in payload.get("weights", [])]
    if not edge_ids:
        raise ValueError(f"edge_alias_blob_3B has empty edge_ids for merchant_id={merchant_id}")
    return str(_select_weighted(edge_ids, weights, u_edge))


def _edge_slice(blob_bytes: bytes, offset: int, length: int) -> bytes:
    if len(blob_bytes) < 8:
        raise ValueError("edge_alias_blob_3B missing header")
    header_len = int.from_bytes(blob_bytes[:8], "little")
    base_offset = 8 + header_len
    start = offset
    end = offset + length
    if start < base_offset:
        raise ValueError("edge_alias_blob_3B offset points into header")
    return blob_bytes[start:end]


def _edge_uniform(
    *,
    rng_logger: RNGLogWriter,
    inputs: ArrivalInputs,
    scenario_id: str,
    arrival_key: str,
) -> float:
    event = derive_event(
        manifest_fingerprint=inputs.manifest_fingerprint,
        parameter_hash=inputs.parameter_hash,
        seed=inputs.seed,
        scenario_id=scenario_id,
        family_id="S4.arrival_edge_pick.v1",
        domain_key=arrival_key,
        draws=1,
    )
    rng_logger.log_event(
        family="S4.arrival_edge_pick.v1",
        module="5B.S4",
        substream_label="arrival_edge_pick",
        event="rng_event_arrival_edge_pick",
        counter_before=event.before_state(),
        counter_after=event.after_state(),
        blocks=event.blocks,
        draws=event.draws,
        payload={
            "scenario_id": scenario_id,
            "domain_key": arrival_key,
        },
    )
    return event.uniforms()[0]


def _select_weighted(values: list, weights: list[float], u: float):
    total = sum(weights)
    if total <= 0.0:
        raise ValueError("weights must sum to > 0")
    threshold = u * total
    cumulative = 0.0
    for value, weight in zip(values, weights):
        cumulative += weight
        if threshold <= cumulative:
            return value
    return values[-1]


def _build_alias_table(values: list[object], weights: list[float]) -> AliasTable:
    if not values:
        raise ValueError("alias table values must be non-empty")
    total = float(sum(weights))
    if total <= 0.0:
        raise ValueError("alias table weights must sum to > 0")
    normalised = [float(weight) / total for weight in weights]
    count = len(values)
    scaled = [value * count for value in normalised]
    probabilities = [0.0] * count
    aliases = [0] * count
    small = [idx for idx, value in enumerate(scaled) if value < 1.0]
    large = [idx for idx, value in enumerate(scaled) if value >= 1.0]
    while small and large:
        s = small.pop()
        l = large.pop()
        probabilities[s] = scaled[s]
        aliases[s] = l
        scaled[l] = (scaled[l] + scaled[s]) - 1.0
        if scaled[l] < 1.0:
            small.append(l)
        else:
            large.append(l)
    for idx in large + small:
        probabilities[idx] = 1.0
        aliases[idx] = idx
    return AliasTable(values=list(values), probabilities=probabilities, aliases=aliases)


def _load_alias_layout_policy_digest(inventory: SealedInventory) -> str:
    files = inventory.resolve_files("alias_layout_policy_v1")
    if not files:
        raise FileNotFoundError("alias_layout_policy_v1 missing from sealed inputs")
    data = files[0].read_bytes()
    return hashlib.sha256(data).hexdigest()


def _load_alias_index(inventory: SealedInventory) -> dict[str, object]:
    files = inventory.resolve_files("s2_alias_index")
    if not files:
        raise FileNotFoundError("s2_alias_index missing from sealed inputs")
    return json.loads(files[0].read_text(encoding="utf-8"))


def _load_alias_blob(inventory: SealedInventory) -> bytes:
    files = inventory.resolve_files("s2_alias_blob")
    if not files:
        raise FileNotFoundError("s2_alias_blob missing from sealed inputs")
    blob_path = files[0]
    if blob_path.is_dir():
        blob_path = blob_path / "alias.bin"
    return blob_path.read_bytes()


def _verify_alias_blob(index_payload: Mapping[str, object], blob_bytes: bytes, policy_digest: str) -> None:
    expected = index_payload.get("blob_sha256")
    if isinstance(expected, str):
        observed = hashlib.sha256(blob_bytes).hexdigest()
        if observed != expected:
            raise ValueError("s2_alias_blob digest mismatch with s2_alias_index")
    policy_expected = index_payload.get("policy_digest")
    if isinstance(policy_expected, str) and policy_expected and policy_digest and policy_expected != policy_digest:
        raise ValueError("alias_layout_policy_v1 digest mismatch with s2_alias_index")


def _site_id(merchant_id: str, site_order: int) -> int:
    return (int(merchant_id) << 32) | (site_order & 0xFFFFFFFF)


def _parse_rfc3339(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def _format_rfc3339(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _safe_zone(tzid: str) -> ZoneInfo:
    try:
        return ZoneInfo(tzid)
    except Exception:
        return ZoneInfo("Etc/UTC")


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
    inputs: ArrivalInputs,
    data_root: Path,
    dictionary: Mapping[str, object],
) -> Path:
    path = data_root / render_dataset_path(
        dataset_id="segment_state_runs", template_args={}, dictionary=dictionary
    )
    payload = {
        "layer": "layer2",
        "segment": "5B",
        "state": "S4",
        "parameter_hash": inputs.parameter_hash,
        "manifest_fingerprint": inputs.manifest_fingerprint,
        "run_id": inputs.run_id,
        "status": "PASS",
    }
    key = SegmentStateKey(
        layer="layer2",
        segment="5B",
        state="S4",
        manifest_fingerprint=inputs.manifest_fingerprint,
        parameter_hash=inputs.parameter_hash,
        run_id=inputs.run_id,
    )
    return write_segment_state_run_report(path=path, key=key, payload=payload)


__all__ = ["ArrivalInputs", "ArrivalResult", "ArrivalRunner"]
