"""Segment 5A S1 runner - merchant demand profiles driven by policy files."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

import polars as pl
import yaml

from engine.layers.l2.seg_5A.shared.control_plane import (
    SealedInventory,
    load_control_plane,
)
from engine.layers.l2.seg_5A.shared.dictionary import load_dictionary, render_dataset_path, repository_root
from engine.layers.l2.seg_5A.shared.run_report import SegmentStateKey, write_segment_state_run_report

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProfilesInputs:
    data_root: Path
    manifest_fingerprint: str
    parameter_hash: str
    run_id: str
    dictionary_path: Optional[Path] = None


@dataclass(frozen=True)
class ProfilesResult:
    profile_path: Path
    class_profile_path: Path | None
    run_report_path: Path
    resumed: bool


class ProfilesRunner:
    """Produce merchant demand profiles using governed class/scale policies."""

    _PROFILE_SCHEMA = {
        "manifest_fingerprint": pl.Utf8,
        "parameter_hash": pl.Utf8,
        "merchant_id": pl.UInt64,
        "legal_country_iso": pl.Utf8,
        "tzid": pl.Utf8,
        "demand_class": pl.Utf8,
        "demand_subclass": pl.Utf8,
        "profile_id": pl.Utf8,
        "weekly_volume_expected": pl.Float64,
        "scale_factor": pl.Float64,
        "weekly_volume_unit": pl.Utf8,
        "high_variability_flag": pl.Boolean,
        "low_volume_flag": pl.Boolean,
        "virtual_preferred_flag": pl.Boolean,
        "class_source": pl.Utf8,
    }

    _CLASS_PROFILE_SCHEMA = {
        "manifest_fingerprint": pl.Utf8,
        "parameter_hash": pl.Utf8,
        "merchant_id": pl.UInt64,
        "primary_demand_class": pl.Utf8,
        "classes_seen": pl.List(pl.Utf8),
        "weekly_volume_total_expected": pl.Float64,
        "scale_factor_total": pl.Float64,
    }

    def run(self, inputs: ProfilesInputs) -> ProfilesResult:
        dictionary = load_dictionary(inputs.dictionary_path)
        data_root = inputs.data_root.absolute()
        receipt, sealed_df, scenario_bindings = load_control_plane(
            data_root=data_root,
            manifest_fingerprint=inputs.manifest_fingerprint,
            parameter_hash=inputs.parameter_hash,
            dictionary_path=inputs.dictionary_path,
        )
        repo_root = repository_root()
        template_args = {
            "manifest_fingerprint": inputs.manifest_fingerprint,
            "fingerprint": inputs.manifest_fingerprint,
            "parameter_hash": inputs.parameter_hash,
        }
        inventory = SealedInventory(
            dataframe=sealed_df,
            base_path=data_root,
            repo_root=repo_root,
            template_args=template_args,
        )

        profile_path = data_root / render_dataset_path(
            dataset_id="merchant_zone_profile_5A",
            template_args={"manifest_fingerprint": inputs.manifest_fingerprint},
            dictionary=dictionary,
        )
        class_profile_path = data_root / render_dataset_path(
            dataset_id="merchant_class_profile_5A",
            template_args={"manifest_fingerprint": inputs.manifest_fingerprint},
            dictionary=dictionary,
        )
        profile_path.parent.mkdir(parents=True, exist_ok=True)
        class_profile_path.parent.mkdir(parents=True, exist_ok=True)

        scenario_label = scenario_bindings[0].scenario_id if scenario_bindings else "baseline"
        resumed = profile_path.exists()
        if not resumed:
            class_policy = self._load_policy(inventory, "merchant_class_policy_5A")
            scale_policy = self._load_policy(inventory, "demand_scale_policy_5A")
            merchants = self._load_merchants(inventory)
            zones = self._load_zone_domain(inventory)
            profiles = self._build_profiles(
                zones=zones,
                merchants=merchants,
                manifest_fingerprint=inputs.manifest_fingerprint,
                parameter_hash=inputs.parameter_hash,
                class_policy=class_policy,
                scale_policy=scale_policy,
                scenario_label=scenario_label,
            )
            class_profiles = self._summarise_classes(profiles)
            profiles.write_parquet(profile_path)
            class_profiles.write_parquet(class_profile_path)

        run_report_path = data_root / render_dataset_path(
            dataset_id="s1_run_report_5A",
            template_args={"manifest_fingerprint": inputs.manifest_fingerprint},
            dictionary=dictionary,
        )
        run_report_path.parent.mkdir(parents=True, exist_ok=True)
        run_report = {
            "layer": "layer2",
            "segment": "5A",
            "state": "S1",
            "status": "PASS",
            "run_id": inputs.run_id,
            "manifest_fingerprint": inputs.manifest_fingerprint,
            "parameter_hash": inputs.parameter_hash,
            "profile_path": str(profile_path),
            "class_profile_path": str(class_profile_path),
            "resumed": resumed,
            "sealed_inputs_digest": receipt.get("sealed_inputs_digest"),
            "scenario_ids": [binding.scenario_id for binding in scenario_bindings],
        }
        run_report_path.write_text(json.dumps(run_report, indent=2, sort_keys=True), encoding="utf-8")
        key = SegmentStateKey(
            layer="layer2",
            segment="5A",
            state="S1",
            manifest_fingerprint=inputs.manifest_fingerprint,
            parameter_hash=inputs.parameter_hash,
            run_id=inputs.run_id,
        )
        segment_state_path = data_root / render_dataset_path(
            dataset_id="segment_state_runs", template_args={}, dictionary=dictionary
        )
        write_segment_state_run_report(
            path=segment_state_path,
            key=key,
            payload={
                **key.as_dict(),
                "status": "PASS",
                "run_report_path": str(run_report_path),
                "profile_path": str(profile_path),
                "class_profile_path": str(class_profile_path),
                "resumed": resumed,
            },
        )
        return ProfilesResult(
            profile_path=profile_path,
            class_profile_path=class_profile_path,
            run_report_path=run_report_path,
            resumed=resumed,
        )

    def _load_policy(self, inventory: SealedInventory, dataset_id: str) -> Mapping[str, object]:
        files = inventory.resolve_files(dataset_id)
        policy_path = files[0]
        return yaml.safe_load(policy_path.read_text(encoding="utf-8")) or {}

    def _load_merchants(self, inventory: SealedInventory) -> pl.DataFrame:
        files = inventory.resolve_files("transaction_schema_merchant_ids")
        try:
            df = pl.read_parquet(files, columns=["merchant_id", "mcc", "channel", "home_country_iso"])
        except Exception as exc:
            logger.warning(
                "Falling back to CSV for transaction_schema_merchant_ids due to parquet read issue: %s", exc
            )
            df = self._load_merchants_csv_fallback(files)
        return (
            df.with_columns(
                [
                    pl.col("merchant_id").cast(pl.UInt64),
                    pl.col("mcc").cast(pl.Utf8).fill_null(""),
                    pl.col("channel").cast(pl.Utf8).fill_null(""),
                    pl.col("home_country_iso").cast(pl.Utf8).fill_null(""),
                ]
            )
            .unique(subset=["merchant_id"])
        )

    def _load_merchants_csv_fallback(self, files: list[Path]) -> pl.DataFrame:
        """Gracefully handle legacy parquet encodings by reading the sibling CSV if present."""

        for path in files:
            csv_candidate = path.with_suffix(".csv")
            if csv_candidate.exists():
                return pl.read_csv(
                    csv_candidate,
                    columns=["merchant_id", "mcc", "channel", "home_country_iso"],
                    dtypes={
                        "merchant_id": pl.Utf8,
                        "mcc": pl.Utf8,
                        "channel": pl.Utf8,
                        "home_country_iso": pl.Utf8,
                    },
                )
        raise RuntimeError("S1_MERCHANT_LOAD_FAILED: unable to read transaction_schema_merchant_ids (parquet and CSV)")

    def _load_zone_domain(self, inventory: SealedInventory) -> pl.DataFrame:
        files = inventory.resolve_files("zone_alloc")
        lazy = pl.scan_parquet([str(path) for path in files]).select(
            ["merchant_id", "legal_country_iso", "tzid"]
        )
        return (
            lazy.collect()
            .with_columns(
                [
                    pl.col("merchant_id").cast(pl.UInt64),
                    pl.col("legal_country_iso").cast(pl.Utf8),
                    pl.col("tzid").cast(pl.Utf8),
                ]
            )
            .unique(subset=["merchant_id", "legal_country_iso", "tzid"])
        )

    def _class_for_row(self, row: Mapping[str, object], class_policy: Mapping[str, object]) -> str:
        default_class = class_policy.get("default_class", "retail_daytime")
        rules = class_policy.get("rules") or []
        mcc = str(row.get("mcc") or "").strip()
        channel = str(row.get("channel") or "").strip().lower()
        for rule in rules:
            if not isinstance(rule, Mapping):
                continue
            cond = rule.get("when") or {}
            if not isinstance(cond, Mapping):
                continue
            channel_ok = True
            if isinstance(cond.get("channel_group"), list):
                channel_ok = channel in [str(x).lower() for x in cond["channel_group"]]
            mcc_ok = True
            if isinstance(cond.get("mcc_prefix"), list):
                mcc_ok = any(mcc.startswith(str(pref)) for pref in cond["mcc_prefix"])
            if channel_ok and mcc_ok and isinstance(rule.get("class"), str):
                return rule["class"]
        return default_class

    def _scale_for_class(self, demand_class: str, scale_policy: Mapping[str, object]) -> Mapping[str, object]:
        defaults = scale_policy.get("defaults") or {}
        classes = scale_policy.get("classes") or {}
        selected = classes.get(demand_class, {})
        if not isinstance(selected, Mapping):
            selected = {}
        return {
            "weekly_volume_expected": float(
                selected.get("weekly_volume_expected", defaults.get("weekly_volume_expected", 100.0))
            ),
            "weekly_volume_unit": str(selected.get("weekly_volume_unit", defaults.get("weekly_volume_unit", "transactions"))),
            "scale_factor": float(selected.get("scale_factor", defaults.get("scale_factor", 1.0))),
            "high_variability_flag": bool(selected.get("high_variability_flag", False)),
            "low_volume_flag": bool(selected.get("low_volume_flag", False)),
        }

    def _build_profiles(
        self,
        *,
        zones: pl.DataFrame,
        merchants: pl.DataFrame,
        manifest_fingerprint: str,
        parameter_hash: str,
        class_policy: Mapping[str, object],
        scale_policy: Mapping[str, object],
        scenario_label: str,
    ) -> pl.DataFrame:
        if zones.is_empty():
            logger.warning("zone_alloc resolved to zero rows; emitting empty profile table")
            return pl.DataFrame(schema=self._PROFILE_SCHEMA)

        domain = zones.join(merchants, on="merchant_id", how="left")
        if domain.is_empty():
            return pl.DataFrame(schema=self._PROFILE_SCHEMA)

        class_udf = pl.struct(["mcc", "channel"]).map_elements(
            lambda s: self._class_for_row(s, class_policy),
            return_dtype=pl.Utf8,
        )
        df = domain.select(
            [
                pl.lit(manifest_fingerprint).alias("manifest_fingerprint"),
                pl.lit(parameter_hash).alias("parameter_hash"),
                pl.col("merchant_id").cast(pl.UInt64),
                pl.col("legal_country_iso").cast(pl.Utf8),
                pl.col("tzid").cast(pl.Utf8).fill_null("Etc/UTC"),
                pl.col("mcc").cast(pl.Utf8).fill_null("").alias("mcc"),
                pl.col("channel").cast(pl.Utf8).fill_null("").alias("channel"),
            ]
        ).with_columns(
            [
                class_udf.alias("demand_class"),
                pl.lit(None, dtype=pl.Utf8).alias("demand_subclass"),
                pl.concat_str(
                    [
                        pl.col("merchant_id").cast(pl.Utf8),
                        pl.lit("-"),
                        pl.col("tzid"),
                        pl.lit(f"-{scenario_label}"),
                    ]
                ).alias("profile_id"),
                pl.lit(0.0).alias("weekly_volume_expected"),
                pl.lit(1.0).alias("scale_factor"),
                pl.lit("transactions").alias("weekly_volume_unit"),
                pl.lit(False).alias("high_variability_flag"),
                pl.lit(False).alias("low_volume_flag"),
                pl.lit(False).alias("virtual_preferred_flag"),
                pl.lit(class_policy.get("version", "v1")).alias("class_source"),
            ]
        )

        def apply_scale(row: dict) -> dict:
            scale = self._scale_for_class(str(row["demand_class"]), scale_policy)
            row["weekly_volume_expected"] = scale["weekly_volume_expected"]
            row["weekly_volume_unit"] = scale["weekly_volume_unit"]
            row["scale_factor"] = scale["scale_factor"]
            row["high_variability_flag"] = scale["high_variability_flag"]
            row["low_volume_flag"] = scale["low_volume_flag"]
            return row

        records = [apply_scale(record) for record in df.to_dicts()]
        profile_df = pl.DataFrame(records, schema=self._PROFILE_SCHEMA)
        return profile_df

    def _summarise_classes(self, profiles: pl.DataFrame) -> pl.DataFrame:
        if profiles.is_empty():
            return pl.DataFrame(schema=self._CLASS_PROFILE_SCHEMA)
        aggregates = (
            profiles.group_by("merchant_id")
            .agg(
                [
                    pl.first("manifest_fingerprint").alias("manifest_fingerprint"),
                    pl.first("parameter_hash").alias("parameter_hash"),
                    pl.first("demand_class").alias("primary_demand_class"),
                    pl.col("demand_class").alias("classes_seen"),
                    pl.sum("weekly_volume_expected").alias("weekly_volume_total_expected"),
                    pl.sum("scale_factor").alias("scale_factor_total"),
                ]
            )
            .select(self._CLASS_PROFILE_SCHEMA.keys())
        )
        return aggregates


__all__ = ["ProfilesRunner", "ProfilesInputs", "ProfilesResult"]
