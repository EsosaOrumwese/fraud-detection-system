"""Segment 5A S2 runner - weekly shapes driven by the shape library policy."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

import pandas as pd
import yaml

from engine.layers.l2.seg_5A.shared.dictionary import load_dictionary, render_dataset_path
from engine.layers.l2.seg_5A.shared.run_report import SegmentStateKey, write_segment_state_run_report

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ShapesInputs:
    data_root: Path
    manifest_fingerprint: str
    parameter_hash: str
    run_id: str
    dictionary_path: Optional[Path] = None


@dataclass(frozen=True)
class ShapesResult:
    grid_path: Path
    shape_path: Path
    catalogue_path: Path | None
    run_report_path: Path
    resumed: bool


class ShapesRunner:
    """Produce shape grid definition and classxzone shapes based on policy templates."""

    _GRID_COLUMNS = [
        "parameter_hash",
        "scenario_id",
        "bucket_index",
        "local_day_of_week",
        "local_minutes_since_midnight",
        "bucket_duration_minutes",
        "is_weekend",
        "is_nominal_open_hours",
        "time_grid_version",
    ]

    _SHAPE_COLUMNS = [
        "parameter_hash",
        "scenario_id",
        "demand_class",
        "legal_country_iso",
        "tzid",
        "zone_id",
        "channel_group",
        "bucket_index",
        "shape_value",
        "s2_spec_version",
        "template_id",
        "adjustment_flags",
        "notes",
    ]

    _CATALOGUE_COLUMNS = [
        "parameter_hash",
        "scenario_id",
        "demand_class",
        "channel_group",
        "template_id",
        "template_type",
        "template_params",
        "policy_version",
    ]

    def run(self, inputs: ShapesInputs) -> ShapesResult:
        dictionary = load_dictionary(inputs.dictionary_path)
        data_root = inputs.data_root.absolute()
        shape_library = self._load_shape_library(data_root, dictionary)

        grid_path = data_root / render_dataset_path(
            dataset_id="shape_grid_definition_5A",
            template_args={"parameter_hash": inputs.parameter_hash, "scenario_id": "baseline"},
            dictionary=dictionary,
        )
        shape_path = data_root / render_dataset_path(
            dataset_id="class_zone_shape_5A",
            template_args={"parameter_hash": inputs.parameter_hash, "scenario_id": "baseline"},
            dictionary=dictionary,
        )
        catalogue_path = data_root / render_dataset_path(
            dataset_id="class_shape_catalogue_5A",
            template_args={"parameter_hash": inputs.parameter_hash, "scenario_id": "baseline"},
            dictionary=dictionary,
        )
        grid_path.parent.mkdir(parents=True, exist_ok=True)
        shape_path.parent.mkdir(parents=True, exist_ok=True)
        catalogue_path.parent.mkdir(parents=True, exist_ok=True)

        resumed = grid_path.exists() and shape_path.exists()
        if not resumed:
            grid_df, shape_df, catalogue_df = self._build_shapes(inputs, shape_library)
            grid_df.to_parquet(grid_path, index=False)
            shape_df.to_parquet(shape_path, index=False)
            catalogue_df.to_parquet(catalogue_path, index=False)

        run_report_path = (
            data_root / "reports/l2/5A/s2_shapes" / f"fingerprint={inputs.manifest_fingerprint}" / "run_report.json"
        )
        run_report_path.parent.mkdir(parents=True, exist_ok=True)
        run_report = {
            "layer": "layer2",
            "segment": "5A",
            "state": "S2",
            "status": "PASS",
            "run_id": inputs.run_id,
            "manifest_fingerprint": inputs.manifest_fingerprint,
            "parameter_hash": inputs.parameter_hash,
            "grid_path": str(grid_path),
            "shape_path": str(shape_path),
            "catalogue_path": str(catalogue_path),
            "resumed": resumed,
        }
        run_report_path.write_text(json.dumps(run_report, indent=2, sort_keys=True), encoding="utf-8")

        key = SegmentStateKey(
            layer="layer2",
            segment="5A",
            state="S2",
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
                "grid_path": str(grid_path),
                "shape_path": str(shape_path),
                "catalogue_path": str(catalogue_path),
                "resumed": resumed,
            },
        )

        return ShapesResult(
            grid_path=grid_path,
            shape_path=shape_path,
            catalogue_path=catalogue_path,
            run_report_path=run_report_path,
            resumed=resumed,
        )

    def _load_shape_library(self, data_root: Path, dictionary: Mapping[str, object]) -> Mapping[str, object]:
        lib_path = data_root / render_dataset_path(dataset_id="shape_library_5A", template_args={}, dictionary=dictionary)
        if not lib_path.exists():
            raise FileNotFoundError(f"shape library missing at {lib_path}")
        return yaml.safe_load(lib_path.read_text(encoding="utf-8")) or {}

    def _build_shapes(
        self, inputs: ShapesInputs, shape_library: Mapping[str, object]
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        time_grid = shape_library.get("time_grid") or {}
        bucket_minutes = int(time_grid.get("bucket_minutes", 60))
        buckets_per_week = int(time_grid.get("buckets_per_week", 168))
        templates = shape_library.get("templates") or []
        policy_version = shape_library.get("version", "v1")
        scenario_id = "baseline"

        grid_rows = []
        for idx in range(buckets_per_week):
            day = idx // (24 * 60 // bucket_minutes)
            minute = (idx % (24 * 60 // bucket_minutes)) * bucket_minutes
            grid_rows.append(
                {
                    "parameter_hash": inputs.parameter_hash,
                    "scenario_id": scenario_id,
                    "bucket_index": idx,
                    "local_day_of_week": day % 7,
                    "local_minutes_since_midnight": minute,
                    "bucket_duration_minutes": bucket_minutes,
                    "is_weekend": day % 7 in (5, 6),
                    "is_nominal_open_hours": 8 * 60 <= minute <= 22 * 60,
                    "time_grid_version": policy_version,
                }
            )

        shape_rows = []
        catalogue_rows = []
        template_rows = templates if isinstance(templates, list) else []
        # If no templates, create a single flat template so downstream has something to read.
        if not template_rows:
            template_rows = [{"demand_class": "retail_daytime", "type": "flat"}]
        for template in template_rows:
            demand_class = str(template.get("demand_class", "retail_daytime"))
            channel_group = template.get("channel_group")
            template_type = str(template.get("type", "flat"))
            values = self._render_shape(template_type, buckets_per_week)
            total = sum(values) or 1.0
            values = [v / total for v in values]
            for idx, val in enumerate(values):
                shape_rows.append(
                    {
                        "parameter_hash": inputs.parameter_hash,
                        "scenario_id": scenario_id,
                        "demand_class": demand_class,
                        "legal_country_iso": "XX",
                        "tzid": "Etc/UTC",
                        "zone_id": "global",
                        "channel_group": channel_group if channel_group is not None else "all",
                        "bucket_index": idx,
                        "shape_value": float(val),
                        "s2_spec_version": "v1",
                        "template_id": template_type,
                        "adjustment_flags": None,
                        "notes": None,
                    }
                )
            catalogue_rows.append(
                {
                    "parameter_hash": inputs.parameter_hash,
                    "scenario_id": scenario_id,
                    "demand_class": demand_class,
                    "channel_group": channel_group if channel_group is not None else "all",
                    "template_id": template_type,
                    "template_type": template_type,
                    "template_params": json.dumps({"type": template_type}),
                    "policy_version": policy_version,
                }
            )

        return (
            pd.DataFrame(grid_rows, columns=self._GRID_COLUMNS),
            pd.DataFrame(shape_rows, columns=self._SHAPE_COLUMNS),
            pd.DataFrame(catalogue_rows, columns=self._CATALOGUE_COLUMNS),
        )

    @staticmethod
    def _render_shape(template_type: str, buckets_per_week: int) -> list[float]:
        if template_type == "flat":
            return [1.0 for _ in range(buckets_per_week)]
        if template_type == "weekday_peaks":
            values = []
            for idx in range(buckets_per_week):
                day = idx // 24
                values.append(2.0 if day < 5 else 0.5)
            return values
        if template_type == "weekend_heavy":
            values = []
            for idx in range(buckets_per_week):
                day = idx // 24
                values.append(0.5 if day < 5 else 2.0)
            return values
        if template_type == "commute_peaks":
            values = []
            for idx in range(buckets_per_week):
                hour = idx % 24
                values.append(2.0 if hour in (8, 17) else 0.5)
            return values
        if template_type == "weekday_flat":
            values = []
            for idx in range(buckets_per_week):
                day = idx // 24
                values.append(1.5 if day < 5 else 0.5)
            return values
        if template_type == "daytime_skew":
            values = []
            for idx in range(buckets_per_week):
                hour = idx % 24
                values.append(2.0 if 8 <= hour <= 20 else 0.3)
            return values
        if template_type == "morning_evening":
            values = []
            for idx in range(buckets_per_week):
                hour = idx % 24
                values.append(2.0 if hour in (7, 8, 17, 18, 19) else 0.5)
            return values
        if template_type == "lunch_dinner":
            values = []
            for idx in range(buckets_per_week):
                hour = idx % 24
                values.append(2.0 if hour in (12, 13, 19, 20) else 0.6)
            return values
        if template_type == "weekend_evening":
            values = []
            for idx in range(buckets_per_week):
                day = idx // 24
                hour = idx % 24
                values.append(2.2 if day >= 5 and 18 <= hour <= 23 else 0.6)
            return values
        if template_type == "late_evening":
            values = []
            for idx in range(buckets_per_week):
                hour = idx % 24
                values.append(1.8 if 20 <= hour <= 23 else 0.7)
            return values
        # Fallback to flat
        return [1.0 for _ in range(buckets_per_week)]


__all__ = ["ShapesRunner", "ShapesInputs", "ShapesResult"]
