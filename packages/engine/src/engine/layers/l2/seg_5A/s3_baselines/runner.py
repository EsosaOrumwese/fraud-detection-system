"""Segment 5A S3 runner - baseline merchant×zone weekly intensities."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

import polars as pl

from engine.layers.l2.seg_5A.shared.control_plane import load_control_plane
from engine.layers.l2.seg_5A.shared.dictionary import load_dictionary, render_dataset_path
from engine.layers.l2.seg_5A.shared.run_report import SegmentStateKey, write_segment_state_run_report

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BaselineInputs:
    data_root: Path
    manifest_fingerprint: str
    parameter_hash: str
    run_id: str
    dictionary_path: Optional[Path] = None


@dataclass(frozen=True)
class BaselineResult:
    baseline_path: Path | None
    class_baseline_path: Path | None
    run_report_path: Path
    resumed: bool


class BaselineRunner:
    """Compose S1 base scale with S2 shapes to emit baseline intensities."""

    _BASELINE_SCHEMA = {
        "manifest_fingerprint": pl.Utf8,
        "parameter_hash": pl.Utf8,
        "scenario_id": pl.Utf8,
        "merchant_id": pl.UInt64,
        "legal_country_iso": pl.Utf8,
        "tzid": pl.Utf8,
        "zone_id": pl.Utf8,
        "channel": pl.Utf8,
        "channel_group": pl.Utf8,
        "bucket_index": pl.Int32,
        "lambda_local_base": pl.Float64,
        "s3_spec_version": pl.Utf8,
        "scale_source": pl.Utf8,
        "weekly_volume_expected": pl.Float64,
        "scale_factor": pl.Float64,
        "baseline_clip_applied": pl.Boolean,
    }

    _CLASS_BASELINE_SCHEMA = {
        "manifest_fingerprint": pl.Utf8,
        "parameter_hash": pl.Utf8,
        "scenario_id": pl.Utf8,
        "demand_class": pl.Utf8,
        "legal_country_iso": pl.Utf8,
        "tzid": pl.Utf8,
        "zone_id": pl.Utf8,
        "channel": pl.Utf8,
        "channel_group": pl.Utf8,
        "bucket_index": pl.Int32,
        "lambda_local_base_class": pl.Float64,
        "s3_spec_version": pl.Utf8,
    }

    _S3_SPEC_VERSION = "1.0.0"

    def run(self, inputs: BaselineInputs) -> BaselineResult:
        dictionary = load_dictionary(inputs.dictionary_path)
        data_root = inputs.data_root.absolute()
        receipt, sealed_df, scenario_bindings = load_control_plane(
            data_root=data_root,
            manifest_fingerprint=inputs.manifest_fingerprint,
            parameter_hash=inputs.parameter_hash,
            dictionary_path=inputs.dictionary_path,
        )
        self._assert_upstream_pass(receipt)
        scenarios = scenario_bindings or []
        if not scenarios:
            logger.warning("No scenario bindings resolved; defaulting to baseline")
            from engine.layers.l2.seg_5A.shared.control_plane import ScenarioBinding

            scenarios = [ScenarioBinding(scenario_id="baseline")]

        baseline_path: Path | None = None
        class_baseline_path: Path | None = None
        resumed = True

        for binding in scenarios:
            scenario_id = binding.scenario_id
            logger.info("S3 baseline: scenario_id=%s", scenario_id)
            baseline_path = data_root / render_dataset_path(
                dataset_id="merchant_zone_baseline_local_5A",
                template_args={"manifest_fingerprint": inputs.manifest_fingerprint, "scenario_id": scenario_id},
                dictionary=dictionary,
            )
            baseline_path.parent.mkdir(parents=True, exist_ok=True)

            profile_df = self._load_profiles(
                data_root=data_root, dictionary=dictionary, manifest_fingerprint=inputs.manifest_fingerprint
            )
            shapes_df = self._load_shapes(
                data_root=data_root, dictionary=dictionary, parameter_hash=inputs.parameter_hash, scenario_id=scenario_id
            )
            if shapes_df.is_empty():
                raise RuntimeError(f"S3_SHAPE_JOIN_FAILED: no shapes available for scenario_id={scenario_id}")
            grid_df = self._load_shape_grid(
                data_root=data_root, dictionary=dictionary, parameter_hash=inputs.parameter_hash, scenario_id=scenario_id
            )

            baseline_df = self._compose_baseline(
                profiles=profile_df,
                shapes=shapes_df,
                grid=grid_df,
                manifest_fingerprint=inputs.manifest_fingerprint,
                parameter_hash=inputs.parameter_hash,
                scenario_id=scenario_id,
            )
            class_df = self._aggregate_class(baseline_df)

            resumed = resumed and baseline_path.exists()
            self._write_parquet(baseline_path, baseline_df)
            if class_df is not None:
                class_baseline_path = data_root / render_dataset_path(
                    dataset_id="class_zone_baseline_local_5A",
                    template_args={"manifest_fingerprint": inputs.manifest_fingerprint, "scenario_id": scenario_id},
                    dictionary=dictionary,
                )
                class_baseline_path.parent.mkdir(parents=True, exist_ok=True)
                self._write_parquet(class_baseline_path, class_df)

        run_report_path = (
            data_root / "reports/l2/5A/s3_baselines" / f"fingerprint={inputs.manifest_fingerprint}" / "run_report.json"
        )
        run_report_path.parent.mkdir(parents=True, exist_ok=True)
        report_payload = {
            "layer": "layer2",
            "segment": "5A",
            "state": "S3",
            "status": "PASS",
            "run_id": inputs.run_id,
            "manifest_fingerprint": inputs.manifest_fingerprint,
            "parameter_hash": inputs.parameter_hash,
            "baseline_path": str(baseline_path) if baseline_path else "",
            "class_baseline_path": str(class_baseline_path) if class_baseline_path else "",
            "resumed": resumed,
            "scenario_ids": [binding.scenario_id for binding in scenarios],
            "sealed_inputs_digest": receipt.get("sealed_inputs_digest"),
        }
        run_report_path.write_text(json.dumps(report_payload, indent=2, sort_keys=True), encoding="utf-8")

        key = SegmentStateKey(
            layer="layer2",
            segment="5A",
            state="S3",
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
                "baseline_path": str(baseline_path) if baseline_path else "",
                "class_baseline_path": str(class_baseline_path) if class_baseline_path else "",
                "resumed": resumed,
            },
        )

        return BaselineResult(
            baseline_path=baseline_path,
            class_baseline_path=class_baseline_path,
            run_report_path=run_report_path,
            resumed=resumed,
        )

    def _assert_upstream_pass(self, receipt: Mapping[str, object]) -> None:
        upstream = receipt.get("verified_upstream_segments") or {}
        failing = [
            seg for seg, info in upstream.items() if isinstance(info, Mapping) and info.get("status") != "PASS"
        ]
        if failing:
            raise RuntimeError(f"S3_UPSTREAM_NOT_PASS: upstream segments not PASS: {failing}")

    def _load_profiles(
        self, *, data_root: Path, dictionary: Mapping[str, object], manifest_fingerprint: str
    ) -> pl.DataFrame:
        path = data_root / render_dataset_path(
            dataset_id="merchant_zone_profile_5A",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        if not path.exists():
            raise FileNotFoundError(f"S3_REQUIRED_INPUT_MISSING: merchant_zone_profile_5A missing at {path}")
        df = pl.read_parquet(path)
        if df.is_empty():
            raise RuntimeError("S3_REQUIRED_INPUT_MISSING: merchant_zone_profile_5A is empty")
        if "channel" not in df.columns:
            df = df.with_columns(pl.lit("").alias("channel"))
        return (
            df.with_columns(
                [
                    pl.col("merchant_id").cast(pl.UInt64),
                    pl.col("legal_country_iso").cast(pl.Utf8),
                    pl.col("tzid").cast(pl.Utf8),
                    pl.col("demand_class").cast(pl.Utf8),
                    pl.col("weekly_volume_expected").cast(pl.Float64).fill_null(0.0),
                    pl.col("scale_factor").cast(pl.Float64).fill_null(0.0),
                    pl.col("channel").cast(pl.Utf8).fill_null(""),
                ]
            )
            .select(
                [
                    "merchant_id",
                    "legal_country_iso",
                    "tzid",
                    "demand_class",
                    "weekly_volume_expected",
                    "scale_factor",
                    "channel",
                ]
            )
            .unique(subset=["merchant_id", "legal_country_iso", "tzid", "channel"])
        )

    def _load_shapes(
        self, *, data_root: Path, dictionary: Mapping[str, object], parameter_hash: str, scenario_id: str
    ) -> pl.DataFrame:
        path = data_root / render_dataset_path(
            dataset_id="class_zone_shape_5A",
            template_args={"parameter_hash": parameter_hash, "scenario_id": scenario_id},
            dictionary=dictionary,
        )
        if not path.exists():
            raise FileNotFoundError(f"S3_REQUIRED_INPUT_MISSING: class_zone_shape_5A missing at {path}")
        df = pl.read_parquet(
            path,
            columns=[
                "parameter_hash",
                "scenario_id",
                "demand_class",
                "legal_country_iso",
                "tzid",
                "channel_group",
                "bucket_index",
                "shape_value",
            ],
        )
        df = df.with_columns(
            [
                pl.col("parameter_hash").cast(pl.Utf8),
                pl.col("scenario_id").cast(pl.Utf8),
                pl.col("demand_class").cast(pl.Utf8),
                pl.col("legal_country_iso").cast(pl.Utf8),
                pl.col("tzid").cast(pl.Utf8),
                pl.col("channel_group").cast(pl.Utf8).fill_null(""),
                pl.col("bucket_index").cast(pl.Int32),
                pl.col("shape_value").cast(pl.Float64),
            ]
        )
        return df.filter(pl.col("scenario_id") == scenario_id)

    def _load_shape_grid(
        self, *, data_root: Path, dictionary: Mapping[str, object], parameter_hash: str, scenario_id: str
    ) -> pl.DataFrame:
        path = data_root / render_dataset_path(
            dataset_id="shape_grid_definition_5A",
            template_args={"parameter_hash": parameter_hash, "scenario_id": scenario_id},
            dictionary=dictionary,
        )
        if not path.exists():
            raise FileNotFoundError(f"S3_REQUIRED_INPUT_MISSING: shape_grid_definition_5A missing at {path}")
        df = pl.read_parquet(path, columns=["parameter_hash", "scenario_id", "bucket_index"])
        df = df.with_columns(
            [
                pl.col("parameter_hash").cast(pl.Utf8),
                pl.col("scenario_id").cast(pl.Utf8),
                pl.col("bucket_index").cast(pl.Int32),
            ]
        )
        if df.is_empty():
            raise RuntimeError("S3_REQUIRED_INPUT_MISSING: shape_grid_definition_5A is empty")
        return df

    def _compose_baseline(
        self,
        *,
        profiles: pl.DataFrame,
        shapes: pl.DataFrame,
        grid: pl.DataFrame,
        manifest_fingerprint: str,
        parameter_hash: str,
        scenario_id: str,
    ) -> pl.DataFrame:
        if profiles.is_empty():
            return pl.DataFrame(schema=self._BASELINE_SCHEMA)

        max_bucket = grid["bucket_index"].max()
        bucket_span = int(max_bucket) + 1
        if grid["bucket_index"].n_unique() != bucket_span:
            raise RuntimeError("S3_REQUIRED_INPUT_MISSING: shape_grid_definition_5A has non-contiguous bucket_index")
        joined = profiles.join(
            shapes,
            on=["demand_class", "legal_country_iso", "tzid"],
            how="inner",
        )
        if joined.is_empty():
            raise RuntimeError("S3_SHAPE_JOIN_FAILED: no overlap between profiles and shapes")

        if joined.filter(pl.col("shape_value").is_null()).height > 0:
            raise RuntimeError("S3_SHAPE_JOIN_FAILED: null shape_value after join")
        expected = profiles.height * bucket_span
        if joined.height != expected:
            raise RuntimeError(
                f"S3_DOMAIN_ALIGNMENT_FAILED: expected {expected} rows (domain x buckets) but got {joined.height}"
            )

        base = (
            joined.with_columns(
                [
                    pl.lit(manifest_fingerprint).alias("manifest_fingerprint"),
                    pl.lit(parameter_hash).alias("parameter_hash"),
                    pl.lit(scenario_id).alias("scenario_id"),
                    pl.concat_str(
                        [pl.col("legal_country_iso"), pl.lit("::"), pl.col("tzid")]
                    ).alias("zone_id"),
                    (pl.col("weekly_volume_expected") * pl.col("shape_value")).alias("lambda_local_base"),
                    pl.lit(self._S3_SPEC_VERSION).alias("s3_spec_version"),
                    pl.lit("weekly_volume_expected").alias("scale_source"),
                    pl.lit(False).alias("baseline_clip_applied"),
                ]
            )
            .select(list(self._BASELINE_SCHEMA.keys()))
        )

        self._assert_weekly_sums(base)
        return base

    def _assert_weekly_sums(self, baseline: pl.DataFrame) -> None:
        grouped = (
            baseline.group_by(["merchant_id", "legal_country_iso", "tzid", "channel"])
            .agg(
                [
                    pl.sum("lambda_local_base").alias("weekly_sum"),
                    pl.first("weekly_volume_expected").alias("weekly_volume_expected"),
                ]
            )
            .with_columns(
                [
                    (pl.col("weekly_sum") - pl.col("weekly_volume_expected")).alias("delta"),
                ]
            )
        )
        violations = grouped.filter(
            pl.col("delta").abs() > (pl.col("weekly_volume_expected").abs() * 1e-8 + 1e-6)
        )
        if violations.height > 0:
            sample = violations.head(5).to_dicts()
            raise RuntimeError(f"S3_INTENSITY_NUMERIC_INVALID: weekly sum mismatch for {violations.height} rows; sample={sample}")

    def _aggregate_class(self, baseline: pl.DataFrame) -> pl.DataFrame | None:
        if baseline.is_empty():
            return pl.DataFrame(schema=self._CLASS_BASELINE_SCHEMA)
        if "demand_class" not in baseline.columns:
            return None
        return (
            baseline.group_by(
                [
                    "manifest_fingerprint",
                    "parameter_hash",
                    "scenario_id",
                    "demand_class",
                    "legal_country_iso",
                    "tzid",
                    "zone_id",
                    "channel",
                    "channel_group",
                    "bucket_index",
                ]
            )
            .agg(pl.sum("lambda_local_base").alias("lambda_local_base_class"))
            .with_columns(pl.lit(self._S3_SPEC_VERSION).alias("s3_spec_version"))
            .select(list(self._CLASS_BASELINE_SCHEMA.keys()))
        )

    def _write_parquet(self, path: Path, df: pl.DataFrame) -> None:
        if path.exists():
            existing = pl.read_parquet(path)
            try:
                equal = existing.frame_equal(df)
            except AttributeError:
                equal = existing.equals(df)
            if equal:
                return
            raise RuntimeError(f"S3_OUTPUT_CONFLICT: existing dataset at {path} differs from recomputed output")
        df.write_parquet(path)


__all__ = ["BaselineRunner", "BaselineInputs", "BaselineResult"]
