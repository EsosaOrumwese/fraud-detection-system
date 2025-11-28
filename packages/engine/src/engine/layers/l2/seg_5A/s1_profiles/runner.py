"""Segment 5A S1 runner - merchant demand profiles driven by policy files."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

import polars as pl
import yaml

from engine.layers.l2.seg_5A.shared.dictionary import load_dictionary, render_dataset_path
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

        resumed = profile_path.exists()
        if not resumed:
            class_policy = self._load_policy(data_root, dictionary, "merchant_class_policy_5A")
            scale_policy = self._load_policy(data_root, dictionary, "demand_scale_policy_5A")
            merchants = self._load_merchants()
            profiles = self._build_profiles(
                merchants=merchants,
                manifest_fingerprint=inputs.manifest_fingerprint,
                parameter_hash=inputs.parameter_hash,
                class_policy=class_policy,
                scale_policy=scale_policy,
            )
            class_profiles = self._summarise_classes(profiles)
            profiles.write_parquet(profile_path)
            class_profiles.write_parquet(class_profile_path)

        run_report_path = data_root / "reports/l2/5A/s1_profiles" / f"fingerprint={inputs.manifest_fingerprint}" / "run_report.json"
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
        segment_state_path = data_root / "reports/l2/segment_states/segment_state_runs.jsonl"
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

    def _load_policy(self, data_root: Path, dictionary: Mapping[str, object], dataset_id: str) -> Mapping[str, object]:
        policy_path = data_root / render_dataset_path(dataset_id=dataset_id, template_args={}, dictionary=dictionary)
        if not policy_path.exists():
            raise FileNotFoundError(f"policy '{dataset_id}' missing at {policy_path}")
        return yaml.safe_load(policy_path.read_text(encoding="utf-8")) or {}

    def _load_merchants(self) -> pl.DataFrame:
        base = Path("reference/layer1/transaction_schema_merchant_ids/v2025-10-09/transaction_schema_merchant_ids")
        parquet_path = base.with_suffix(".parquet")
        csv_path = base.with_suffix(".csv")
        if parquet_path.exists():
            return pl.read_parquet(parquet_path)
        if csv_path.exists():
            return pl.read_csv(
                csv_path, dtypes={"merchant_id": pl.UInt64, "mcc": pl.Utf8, "channel": pl.Utf8, "home_country_iso": pl.Utf8}
            )
        logger.warning("Merchant reference not found; emitting empty profiles.")
        return pl.DataFrame(schema={"merchant_id": pl.UInt64, "mcc": pl.Utf8, "channel": pl.Utf8, "home_country_iso": pl.Utf8})

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
            "weekly_volume_expected": float(selected.get("weekly_volume_expected", defaults.get("weekly_volume_expected", 100.0))),
            "weekly_volume_unit": str(selected.get("weekly_volume_unit", defaults.get("weekly_volume_unit", "transactions"))),
            "scale_factor": float(selected.get("scale_factor", defaults.get("scale_factor", 1.0))),
            "high_variability_flag": bool(selected.get("high_variability_flag", False)),
            "low_volume_flag": bool(selected.get("low_volume_flag", False)),
        }

    def _build_profiles(
        self,
        *,
        merchants: pl.DataFrame,
        manifest_fingerprint: str,
        parameter_hash: str,
        class_policy: Mapping[str, object],
        scale_policy: Mapping[str, object],
    ) -> pl.DataFrame:
        if merchants.is_empty():
            return pl.DataFrame(schema=self._PROFILE_SCHEMA)

        class_udf = pl.struct(["mcc", "channel"]).map_elements(lambda s: self._class_for_row(s, class_policy))
        df = merchants.select(
            [
                pl.lit(manifest_fingerprint).alias("manifest_fingerprint"),
                pl.lit(parameter_hash).alias("parameter_hash"),
                pl.col("merchant_id").cast(pl.UInt64),
                pl.col("home_country_iso").cast(pl.Utf8).alias("legal_country_iso"),
                pl.lit("Etc/UTC").alias("tzid"),
                class_udf.alias("demand_class"),
                pl.lit(None, dtype=pl.Utf8).alias("demand_subclass"),
                pl.lit(None, dtype=pl.Utf8).alias("profile_id"),
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

        records = [apply_scale(r) for r in df.to_dicts()]
        return pl.DataFrame(records, schema=self._PROFILE_SCHEMA)

    def _summarise_classes(self, profiles: pl.DataFrame) -> pl.DataFrame:
        if profiles.is_empty():
            return pl.DataFrame(schema=self._CLASS_PROFILE_SCHEMA)
        return (
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


__all__ = ["ProfilesRunner", "ProfilesInputs", "ProfilesResult"]
