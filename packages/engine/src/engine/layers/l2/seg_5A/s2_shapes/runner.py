"""Segment 5A S2 runner - weekly shapes driven by the shape library policy."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

import pandas as pd
import polars as pl
import yaml

from engine.layers.l2.seg_5A.shared.control_plane import SealedInventory, load_control_plane
from engine.layers.l2.seg_5A.shared.dictionary import load_dictionary, render_dataset_path, repository_root
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
    grid_path: Path | None
    shape_path: Path | None
    catalogue_path: Path | None
    run_report_path: Path
    resumed: bool


class ShapesRunner:
    """Produce shape grid definition and class/zone shapes based on policy templates."""

    def run(self, inputs: ShapesInputs) -> ShapesResult:
        dictionary = load_dictionary(inputs.dictionary_path)
        data_root = inputs.data_root.absolute()
        receipt, sealed_df, scenario_bindings = load_control_plane(
            data_root=data_root,
            manifest_fingerprint=inputs.manifest_fingerprint,
            parameter_hash=inputs.parameter_hash,
            dictionary_path=inputs.dictionary_path,
        )
        template_args = {
            "manifest_fingerprint": inputs.manifest_fingerprint,
            "fingerprint": inputs.manifest_fingerprint,
            "parameter_hash": inputs.parameter_hash,
        }
        inventory = SealedInventory(
            dataframe=sealed_df,
            base_path=data_root,
            repo_root=repository_root(),
            template_args=template_args,
        )

        shape_library = self._load_shape_library(inventory)
        domain = self._load_domain(
            data_root=data_root,
            dictionary=dictionary,
            manifest_fingerprint=inputs.manifest_fingerprint,
        )
        if domain.is_empty():
            logger.warning("merchant_zone_profile_5A is empty; emitting no shapes")

        scenarios = scenario_bindings or [ScenarioStub("baseline")]

        resumed = True
        last_grid_path: Path | None = None
        last_shape_path: Path | None = None
        last_catalogue_path: Path | None = None

        for binding in scenarios:
            scenario_id = binding.scenario_id
            scenario_args = {"parameter_hash": inputs.parameter_hash, "scenario_id": scenario_id}
            grid_path = data_root / render_dataset_path(
                dataset_id="shape_grid_definition_5A", template_args=scenario_args, dictionary=dictionary
            )
            shape_path = data_root / render_dataset_path(
                dataset_id="class_zone_shape_5A", template_args=scenario_args, dictionary=dictionary
            )
            catalogue_path = data_root / render_dataset_path(
                dataset_id="class_shape_catalogue_5A", template_args=scenario_args, dictionary=dictionary
            )
            for target in (grid_path, shape_path, catalogue_path):
                target.parent.mkdir(parents=True, exist_ok=True)

            if not (grid_path.exists() and shape_path.exists() and catalogue_path.exists()):
                resumed = False
                grid_df, shape_df, catalogue_df = self._build_scenario_outputs(
                    parameter_hash=inputs.parameter_hash,
                    scenario_id=scenario_id,
                    domain=domain,
                    shape_library=shape_library,
                )
                self._write_parquet(grid_path, grid_df)
                self._write_parquet(shape_path, shape_df)
                self._write_parquet(catalogue_path, catalogue_df)

            last_grid_path = grid_path
            last_shape_path = shape_path
            last_catalogue_path = catalogue_path

        run_report_path = (
            data_root / "reports/l2/5A/s2_shapes" / f"fingerprint={inputs.manifest_fingerprint}" / "run_report.json"
        )
        run_report_path.parent.mkdir(parents=True, exist_ok=True)
        report_payload = {
            "layer": "layer2",
            "segment": "5A",
            "state": "S2",
            "status": "PASS",
            "run_id": inputs.run_id,
            "manifest_fingerprint": inputs.manifest_fingerprint,
            "parameter_hash": inputs.parameter_hash,
            "grid_path": str(last_grid_path) if last_grid_path else "",
            "shape_path": str(last_shape_path) if last_shape_path else "",
            "catalogue_path": str(last_catalogue_path) if last_catalogue_path else "",
            "resumed": resumed,
            "scenario_ids": [binding.scenario_id for binding in scenarios],
            "sealed_inputs_digest": receipt.get("sealed_inputs_digest"),
        }
        run_report_path.write_text(json.dumps(report_payload, indent=2, sort_keys=True), encoding="utf-8")

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
                "grid_path": str(last_grid_path) if last_grid_path else "",
                "shape_path": str(last_shape_path) if last_shape_path else "",
                "catalogue_path": str(last_catalogue_path) if last_catalogue_path else "",
                "resumed": resumed,
            },
        )

        return ShapesResult(
            grid_path=last_grid_path,
            shape_path=last_shape_path,
            catalogue_path=last_catalogue_path,
            run_report_path=run_report_path,
            resumed=resumed,
        )

    def _load_shape_library(self, inventory: SealedInventory) -> Mapping[str, object]:
        files = inventory.resolve_files("shape_library_5A")
        lib_path = files[0]
        return yaml.safe_load(lib_path.read_text(encoding="utf-8")) or {}

    def _load_domain(self, data_root: Path, dictionary: Mapping[str, object], manifest_fingerprint: str) -> pl.DataFrame:
        profile_path = data_root / render_dataset_path(
            dataset_id="merchant_zone_profile_5A",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        if not profile_path.exists():
            raise FileNotFoundError(f"merchant_zone_profile_5A missing at {profile_path}")
        return (
            pl.read_parquet(
                profile_path,
                columns=["merchant_id", "legal_country_iso", "tzid", "demand_class"],
            )
            .with_columns(
                [
                    pl.col("merchant_id").cast(pl.UInt64),
                    pl.col("legal_country_iso").cast(pl.Utf8),
                    pl.col("tzid").cast(pl.Utf8),
                    pl.col("demand_class").cast(pl.Utf8),
                ]
            )
            .unique(subset=["demand_class", "legal_country_iso", "tzid"])
        )

    def _build_scenario_outputs(
        self,
        *,
        parameter_hash: str,
        scenario_id: str,
        domain: pl.DataFrame,
        shape_library: Mapping[str, object],
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        time_grid = shape_library.get("time_grid") or {}
        bucket_minutes = max(1, int(time_grid.get("bucket_minutes", 60)))
        buckets_per_week = int(time_grid.get("buckets_per_week", 168))
        buckets_per_day = time_grid.get("buckets_per_day")
        if isinstance(buckets_per_day, int) and buckets_per_day > 0:
            resolved_buckets_per_day = buckets_per_day
        else:
            derived = buckets_per_week // 7
            if derived <= 0:
                derived = (24 * 60) // bucket_minutes
            resolved_buckets_per_day = max(1, derived)
        policy_version = shape_library.get("version", "v1")

        grid_rows: list[dict[str, object]] = []
        for idx in range(buckets_per_week):
            day_index = (idx // resolved_buckets_per_day) % 7
            bucket_within_day = idx % resolved_buckets_per_day
            minutes_within_day = (bucket_within_day * bucket_minutes) % (24 * 60)
            grid_rows.append(
                {
                    "parameter_hash": parameter_hash,
                    "scenario_id": scenario_id,
                    "bucket_index": idx,
                    "local_day_of_week": day_index + 1,
                    "local_minutes_since_midnight": int(minutes_within_day),
                    "bucket_duration_minutes": bucket_minutes,
                    "is_weekend": (day_index + 1) in (6, 7),
                    "is_nominal_open_hours": 8 * 60 <= minutes_within_day < 22 * 60,
                    "time_grid_version": policy_version,
                }
            )

        templates = shape_library.get("templates") or []
        if not templates:
            templates = [{"demand_class": "default", "type": "flat"}]
        template_map: dict[str, Mapping[str, object]] = {}
        for template in templates:
            demand_class = str(template.get("demand_class") or "default")
            template_map.setdefault(demand_class, dict(template))

        shape_rows: list[dict[str, object]] = []
        catalogue_rows: dict[tuple[str, str, str, str], dict[str, object]] = {}
        domain_records = domain.to_dicts()
        for entry in domain_records:
            demand_class = str(entry.get("demand_class") or "default")
            template = template_map.get(demand_class) or template_map.get("default") or dict(templates[0])
            channel_group = str(template.get("channel_group") or "all")
            template_type = str(template.get("type") or "flat")
            values = self._render_shape(
                template_type=template_type,
                buckets_per_week=buckets_per_week,
                buckets_per_day=resolved_buckets_per_day,
                bucket_minutes=bucket_minutes,
            )
            total = sum(values) or 1.0
            values = [v / total for v in values]
            zone_id = f"{entry.get('legal_country_iso')}::{entry.get('tzid')}"
            for idx, value in enumerate(values):
                shape_rows.append(
                    {
                        "parameter_hash": parameter_hash,
                        "scenario_id": scenario_id,
                        "demand_class": demand_class,
                        "legal_country_iso": entry.get("legal_country_iso"),
                        "tzid": entry.get("tzid"),
                        "zone_id": zone_id,
                        "channel_group": channel_group,
                        "bucket_index": idx,
                        "shape_value": float(value),
                        "s2_spec_version": "v1",
                        "template_id": template_type,
                        "adjustment_flags": [],
                        "notes": "",
                    }
                )
            template_params = {
                key: value
                for key, value in template.items()
                if key not in {"demand_class"}
            }
            if "type" not in template_params:
                template_params["type"] = template_type
            if "channel_group" not in template_params and channel_group:
                template_params["channel_group"] = channel_group
            catalogue_key = (parameter_hash, scenario_id, demand_class, channel_group)
            if catalogue_key not in catalogue_rows:
                catalogue_rows[catalogue_key] = {
                    "parameter_hash": parameter_hash,
                    "scenario_id": scenario_id,
                    "demand_class": demand_class,
                    "channel_group": channel_group,
                    "template_id": template_type,
                    "template_type": template_type,
                    "template_params": template_params,
                    "policy_version": policy_version,
                }

        grid_df = pd.DataFrame(grid_rows)
        shape_df = pd.DataFrame(shape_rows)
        catalogue_df = pd.DataFrame(list(catalogue_rows.values()))
        return grid_df, shape_df, catalogue_df

    def _write_parquet(self, path: Path, frame: pd.DataFrame) -> None:
        if path.exists():
            existing = pd.read_parquet(path)
            if not existing.equals(frame):
                raise RuntimeError(f"existing dataset at {path} differs from recomputed output")
            return
        frame.to_parquet(path, index=False)

    @staticmethod
    def _render_shape(
        *,
        template_type: str,
        buckets_per_week: int,
        buckets_per_day: int,
        bucket_minutes: int,
    ) -> list[float]:
        if template_type == "flat":
            return [1.0 for _ in range(buckets_per_week)]
        values = []
        if template_type == "weekday_peaks":
            for idx in range(buckets_per_week):
                day = (idx // buckets_per_day) % 7
                values.append(2.0 if day < 5 else 0.5)
            return values
        if template_type == "weekend_heavy":
            for idx in range(buckets_per_week):
                day = (idx // buckets_per_day) % 7
                values.append(0.5 if day < 5 else 2.0)
            return values
        if template_type == "commute_peaks":
            for idx in range(buckets_per_week):
                hour = ((idx % buckets_per_day) * bucket_minutes) // 60
                values.append(2.0 if hour in (8, 17) else 0.5)
            return values
        if template_type == "weekday_flat":
            for idx in range(buckets_per_week):
                day = (idx // buckets_per_day) % 7
                values.append(1.5 if day < 5 else 0.5)
            return values
        if template_type == "daytime_skew":
            for idx in range(buckets_per_week):
                hour = ((idx % buckets_per_day) * bucket_minutes) // 60
                values.append(2.0 if 8 <= hour <= 20 else 0.3)
            return values
        if template_type == "morning_evening":
            for idx in range(buckets_per_week):
                hour = ((idx % buckets_per_day) * bucket_minutes) // 60
                values.append(2.0 if hour in (7, 8, 17, 18, 19) else 0.5)
            return values
        if template_type == "lunch_dinner":
            for idx in range(buckets_per_week):
                hour = ((idx % buckets_per_day) * bucket_minutes) // 60
                values.append(2.0 if hour in (12, 13, 19, 20) else 0.6)
            return values
        if template_type == "weekend_evening":
            for idx in range(buckets_per_week):
                day = (idx // buckets_per_day) % 7
                hour = ((idx % buckets_per_day) * bucket_minutes) // 60
                values.append(2.2 if day >= 5 and 18 <= hour <= 23 else 0.6)
            return values
        if template_type == "late_evening":
            for idx in range(buckets_per_week):
                hour = ((idx % buckets_per_day) * bucket_minutes) // 60
                values.append(1.8 if 20 <= hour <= 23 else 0.7)
            return values
        # Fallback to flat template
        return [1.0 for _ in range(buckets_per_week)]


@dataclass(frozen=True)
class ScenarioStub:
    scenario_id: str


__all__ = ["ShapesRunner", "ShapesInputs", "ShapesResult"]
