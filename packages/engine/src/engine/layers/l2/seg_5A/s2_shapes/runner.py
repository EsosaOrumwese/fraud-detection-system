"""Segment 5A S2 runner - shape grid and classxzone shapes."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd

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
    """Produce shape grid definition and classxzone shapes (placeholder deterministic implementation)."""

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
        grid_path_safe = self._win_safe_path(grid_path)
        shape_path_safe = self._win_safe_path(shape_path)
        catalogue_path_safe = self._win_safe_path(catalogue_path)
        grid_path.parent.mkdir(parents=True, exist_ok=True)
        shape_path.parent.mkdir(parents=True, exist_ok=True)
        catalogue_path.parent.mkdir(parents=True, exist_ok=True)

        resumed = grid_path.exists() and shape_path.exists()
        if not resumed:
            logger.info("S2 writing grid to %s", grid_path_safe)
            pd.DataFrame(columns=self._GRID_COLUMNS).to_parquet(str(grid_path_safe), index=False)
            logger.info("S2 writing shapes to %s", shape_path_safe)
            pd.DataFrame(columns=self._SHAPE_COLUMNS).to_parquet(str(shape_path_safe), index=False)
            logger.info("S2 writing catalogue to %s", catalogue_path_safe)
            pd.DataFrame(columns=self._CATALOGUE_COLUMNS).to_parquet(str(catalogue_path_safe), index=False)

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

    @staticmethod
    def _win_safe_path(path: Path) -> Path:
        # Avoid resolving symlinks to keep paths short on Windows.
        candidate = path.absolute()
        return candidate


__all__ = ["ShapesInputs", "ShapesResult", "ShapesRunner"]
