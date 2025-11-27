"""Segment 5A S1 runner - merchant demand profiles."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import polars as pl

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
    """Produce merchant demand profiles (placeholder deterministic implementation)."""

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
            # Placeholder: emit empty frames with schema to keep pipeline moving until policies land.
            pl.DataFrame(schema=self._PROFILE_SCHEMA).write_parquet(profile_path)
            pl.DataFrame(schema=self._CLASS_PROFILE_SCHEMA).write_parquet(class_profile_path)

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
        # Also append to segment_state_runs
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


__all__ = ["ProfilesInputs", "ProfilesResult", "ProfilesRunner"]
