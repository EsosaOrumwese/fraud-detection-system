"""Segment 5A S4 runner - scenario overlays on baseline intensities."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Mapping, Optional
from zoneinfo import ZoneInfo

import polars as pl
import yaml

from engine.layers.l2.seg_5A.shared.control_plane import SealedInventory, load_control_plane
from engine.layers.l2.seg_5A.shared.dictionary import load_dictionary, render_dataset_path
from engine.layers.l2.seg_5A.shared.run_report import SegmentStateKey, write_segment_state_run_report

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OverlaysInputs:
    data_root: Path
    manifest_fingerprint: str
    parameter_hash: str
    run_id: str
    dictionary_path: Optional[Path] = None


@dataclass(frozen=True)
class OverlaysResult:
    scenario_local_path: Path | None
    overlay_factors_path: Path | None
    scenario_utc_path: Path | None
    run_report_path: Path
    resumed: bool


class OverlaysRunner:
    """Apply deterministic scenario overlays to S3 baselines."""

    _S4_SPEC_VERSION = "1.0.0"

    def run(self, inputs: OverlaysInputs) -> OverlaysResult:
        dictionary = load_dictionary(inputs.dictionary_path)
        data_root = inputs.data_root.absolute()
        receipt, sealed_df, scenario_bindings = load_control_plane(
            data_root=data_root,
            manifest_fingerprint=inputs.manifest_fingerprint,
            parameter_hash=inputs.parameter_hash,
            dictionary_path=inputs.dictionary_path,
        )
        self._assert_upstream_pass(receipt)

        inventory = SealedInventory(
            dataframe=sealed_df,
            base_path=data_root,
            repo_root=Path.cwd(),
            template_args={
                "manifest_fingerprint": inputs.manifest_fingerprint,
                "fingerprint": inputs.manifest_fingerprint,
                "parameter_hash": inputs.parameter_hash,
            },
        )

        scenarios = scenario_bindings or []
        if not scenarios:
            logger.warning("No scenario bindings resolved; defaulting to baseline")
            from engine.layers.l2.seg_5A.shared.control_plane import ScenarioBinding

            scenarios = [ScenarioBinding(scenario_id="baseline")]

        scenario_local_path: Path | None = None
        overlay_factors_path: Path | None = None
        scenario_utc_path: Path | None = None
        resumed = True

        for binding in scenarios:
            scenario_id = binding.scenario_id
            logger.info("S4 overlays: scenario_id=%s", scenario_id)

            baseline_df = self._load_baseline(inventory=inventory, scenario_id=scenario_id)
            if baseline_df.is_empty():
                raise RuntimeError(f"S4_REQUIRED_INPUT_MISSING: baseline empty for scenario_id={scenario_id}")
            grid_df = self._load_shape_grid(inventory=inventory, scenario_id=scenario_id)
            bucket_span = int(grid_df["bucket_index"].max()) + 1
            if grid_df["bucket_index"].n_unique() != bucket_span:
                raise RuntimeError("S4_GRID_CONTIGUITY_FAILED: shape_grid_definition_5A bucket_index not contiguous")

            horizon_cfg = self._load_horizon_config(inventory=inventory, scenario_id=scenario_id)
            overlay_policy = self._load_overlay_policy(inventory=inventory)
            calendar_df = self._load_calendar(inventory=inventory, scenario_id=scenario_id)
            horizon_df = self._build_horizon(horizon_cfg)
            if horizon_df.is_empty():
                raise RuntimeError("S4_HORIZON_INVALID: horizon grid is empty after build")

            scenario_df, factors_df, bucket_minutes = self._compose_scenario(
                baseline=baseline_df,
                horizon=horizon_df,
                grid=grid_df,
                manifest_fingerprint=inputs.manifest_fingerprint,
                parameter_hash=inputs.parameter_hash,
                scenario_id=scenario_id,
                overlay_policy=overlay_policy,
                calendar=calendar_df,
            )
            scenario_local_path = data_root / render_dataset_path(
                dataset_id="merchant_zone_scenario_local_5A",
                template_args={"manifest_fingerprint": inputs.manifest_fingerprint, "scenario_id": scenario_id},
                dictionary=dictionary,
            )
            scenario_local_path.parent.mkdir(parents=True, exist_ok=True)
            resumed = resumed and scenario_local_path.exists()
            self._write_parquet(scenario_local_path, scenario_df)

            if factors_df is not None:
                overlay_factors_path = data_root / render_dataset_path(
                    dataset_id="merchant_zone_overlay_factors_5A",
                    template_args={"manifest_fingerprint": inputs.manifest_fingerprint, "scenario_id": scenario_id},
                    dictionary=dictionary,
                )
                overlay_factors_path.parent.mkdir(parents=True, exist_ok=True)
                self._write_parquet(overlay_factors_path, factors_df)

            # UTC projection using fixed offset per tzid (civil-time tables pending).
            utc_df = self._project_utc(
                scenario_df,
                manifest_fingerprint=inputs.manifest_fingerprint,
                parameter_hash=inputs.parameter_hash,
                scenario_id=scenario_id,
                bucket_minutes=bucket_minutes,
                horizon_len=horizon_df.height,
            )
            if utc_df is not None:
                scenario_utc_path = data_root / render_dataset_path(
                    dataset_id="merchant_zone_scenario_utc_5A",
                    template_args={"manifest_fingerprint": inputs.manifest_fingerprint, "scenario_id": scenario_id},
                    dictionary=dictionary,
                )
                scenario_utc_path.parent.mkdir(parents=True, exist_ok=True)
                self._write_parquet(scenario_utc_path, utc_df)

        run_report_path = (
            data_root / "reports/l2/5A/s4_overlays" / f"fingerprint={inputs.manifest_fingerprint}" / "run_report.json"
        )
        run_report_path.parent.mkdir(parents=True, exist_ok=True)
        report_payload = {
            "layer": "layer2",
            "segment": "5A",
            "state": "S4",
            "status": "PASS",
            "run_id": inputs.run_id,
            "manifest_fingerprint": inputs.manifest_fingerprint,
            "parameter_hash": inputs.parameter_hash,
            "scenario_ids": [binding.scenario_id for binding in scenarios],
            "scenario_local_path": str(scenario_local_path) if scenario_local_path else "",
            "overlay_factors_path": str(overlay_factors_path) if overlay_factors_path else "",
            "scenario_utc_path": str(scenario_utc_path) if scenario_utc_path else "",
            "resumed": resumed,
            "sealed_inputs_digest": receipt.get("sealed_inputs_digest"),
        }
        run_report_path.write_text(json.dumps(report_payload, indent=2, sort_keys=True), encoding="utf-8")

        key = SegmentStateKey(
            layer="layer2",
            segment="5A",
            state="S4",
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
                "scenario_local_path": str(scenario_local_path) if scenario_local_path else "",
                "overlay_factors_path": str(overlay_factors_path) if overlay_factors_path else "",
                "scenario_utc_path": str(scenario_utc_path) if scenario_utc_path else "",
                "resumed": resumed,
            },
        )

        return OverlaysResult(
            scenario_local_path=scenario_local_path,
            overlay_factors_path=overlay_factors_path,
            scenario_utc_path=scenario_utc_path,
            run_report_path=run_report_path,
            resumed=resumed,
        )

    def _assert_upstream_pass(self, receipt: Mapping[str, object]) -> None:
        upstream = receipt.get("verified_upstream_segments") or {}
        failing = [seg for seg, info in upstream.items() if isinstance(info, Mapping) and info.get("status") != "PASS"]
        if failing:
            raise RuntimeError(f"S4_UPSTREAM_NOT_PASS: upstream segments not PASS: {failing}")

    def _load_baseline(self, *, inventory: SealedInventory, scenario_id: str) -> pl.DataFrame:
        files = inventory.resolve_files("merchant_zone_baseline_local_5A", template_overrides={"scenario_id": scenario_id})
        df = pl.read_parquet(files)
        return df.with_columns(
            [
                pl.col("merchant_id").cast(pl.UInt64),
                pl.col("legal_country_iso").cast(pl.Utf8),
                pl.col("tzid").cast(pl.Utf8),
                pl.col("bucket_index").cast(pl.Int32),
                pl.col("lambda_local_base").cast(pl.Float64),
                pl.col("channel").cast(pl.Utf8).fill_null(""),
                pl.col("channel_group").cast(pl.Utf8).fill_null(""),
            ]
        )

    def _load_shape_grid(self, *, inventory: SealedInventory, scenario_id: str) -> pl.DataFrame:
        files = inventory.resolve_files("shape_grid_definition_5A", template_overrides={"scenario_id": scenario_id})
        df = pl.read_parquet(
            files,
            columns=[
                "parameter_hash",
                "scenario_id",
                "bucket_index",
                "local_day_of_week",
                "local_minutes_since_midnight",
                "bucket_duration_minutes",
            ],
        )
        return df.with_columns(
            [
                pl.col("parameter_hash").cast(pl.Utf8),
                pl.col("scenario_id").cast(pl.Utf8),
                pl.col("bucket_index").cast(pl.Int32),
                pl.col("local_day_of_week").cast(pl.Int32),
                pl.col("local_minutes_since_midnight").cast(pl.Int32),
                pl.col("bucket_duration_minutes").cast(pl.Int32),
            ]
        )

    def _load_horizon_config(self, *, inventory: SealedInventory, scenario_id: str) -> Mapping[str, object]:
        files = inventory.resolve_files("scenario_horizon_config_5A")
        cfg = yaml.safe_load(Path(files[0]).read_text(encoding="utf-8")) or {}
        scenarios = cfg.get("scenarios") or []
        for scenario in scenarios:
            if isinstance(scenario, Mapping) and scenario.get("id") == scenario_id:
                return scenario
        if scenarios and isinstance(scenarios[0], Mapping):
            return scenarios[0]
        return {"id": scenario_id or "baseline", "horizon_days": 7, "bucket_minutes": 60, "timezone": "local"}

    def _load_overlay_policy(self, *, inventory: SealedInventory) -> Mapping[str, object]:
        files = inventory.resolve_files("scenario_overlay_policy_5A")
        return yaml.safe_load(Path(files[0]).read_text(encoding="utf-8")) or {}

    def _load_calendar(self, *, inventory: SealedInventory, scenario_id: str) -> pl.DataFrame:
        files = inventory.resolve_files("scenario_calendar_5A", template_overrides={"scenario_id": scenario_id})
        df = pl.read_parquet(files)
        # Expect flexible columns; normalize some likely names.
        if "local_horizon_bucket_index" in df.columns:
            df = df.with_columns(pl.col("local_horizon_bucket_index").cast(pl.Int32))
        elif "bucket_index" in df.columns:
            df = df.with_columns(pl.col("bucket_index").cast(pl.Int32).alias("local_horizon_bucket_index"))
        return df

    def _build_horizon(self, cfg: Mapping[str, object]) -> pl.DataFrame:
        horizon_days = int(cfg.get("horizon_days") or 7)
        bucket_minutes = int(cfg.get("bucket_minutes") or 60)
        buckets = max(1, horizon_days * 24 * 60 // bucket_minutes)
        rows = []
        for idx in range(buckets):
            day_index = (idx * bucket_minutes) // (24 * 60)
            minutes_within_day = (idx * bucket_minutes) % (24 * 60)
            rows.append(
                {
                    "local_horizon_bucket_index": idx,
                    "bucket_minutes": bucket_minutes,
                    "local_day_index": day_index,
                    "local_minutes_since_midnight": minutes_within_day,
                }
            )
        return pl.DataFrame(rows)

    def _compose_scenario(
        self,
        *,
        baseline: pl.DataFrame,
        horizon: pl.DataFrame,
        grid: pl.DataFrame,
        manifest_fingerprint: str,
        parameter_hash: str,
        scenario_id: str,
        overlay_policy: Mapping[str, object],
        calendar: pl.DataFrame,
    ) -> tuple[pl.DataFrame, pl.DataFrame | None, int]:
        if horizon.is_empty():
            raise RuntimeError("S4_HORIZON_INVALID: horizon grid is empty")
        if grid.is_empty():
            raise RuntimeError("S4_GRID_INVALID: shape grid is empty")
        # Join baseline with grid to attach local day/time
        baseline_with_time = baseline.join(
            grid,
            on=["parameter_hash", "scenario_id", "bucket_index"],
            how="inner",
        )
        if baseline_with_time.is_empty():
            raise RuntimeError("S4_GRID_JOIN_EMPTY: baseline lacks grid time mapping")
        horizon_map = horizon.with_columns(
            (pl.col("local_day_index") % 7 + 1).alias("local_day_of_week"),
            pl.col("local_minutes_since_midnight"),
        )
        joined = baseline_with_time.join(
            horizon_map,
            on=["local_day_of_week", "local_minutes_since_midnight"],
            how="inner",
        )
        if joined.is_empty():
            raise RuntimeError("S4_BASELINE_JOIN_EMPTY: no overlap between baseline buckets and horizon")

        overlay_factor = float(
            overlay_policy.get("overlays", {}).get(scenario_id, {}).get("factors", {}).get("default", 1.0)
        )
        bucket_minutes = int(horizon["bucket_minutes"][0]) if "bucket_minutes" in horizon.columns else 60
        horizon_len = int(horizon.height)
        factors_by_bucket = self._resolve_calendar_factors(
            calendar, overlay_policy, scenario_id, overlay_factor, horizon_len=horizon_len
        )
        scenario_df = (
            joined.with_columns(
                [
                    pl.lit(manifest_fingerprint).alias("manifest_fingerprint"),
                    pl.lit(parameter_hash).alias("parameter_hash"),
                    pl.lit(scenario_id).alias("scenario_id"),
                    (pl.col("legal_country_iso") + pl.lit("::") + pl.col("tzid")).alias("zone_id"),
                    pl.col("local_horizon_bucket_index").cast(pl.Int32),
                    (
                        pl.col("lambda_local_base")
                        * pl.struct(["tzid", "local_horizon_bucket_index"]).map_elements(
                            lambda s: factors_by_bucket.get(
                                (str(s["tzid"]), int(s["local_horizon_bucket_index"])),
                                overlay_factor,
                            )
                        )
                    ).alias("lambda_local_scenario"),
                    pl.lit(self._S4_SPEC_VERSION).alias("s4_spec_version"),
                    pl.struct(["tzid", "local_horizon_bucket_index"]).map_elements(
                        lambda s: factors_by_bucket.get(
                            (str(s["tzid"]), int(s["local_horizon_bucket_index"])),
                            overlay_factor,
                        )
                    ).alias("overlay_factor_total"),
                ]
            )
            .select(
                [
                    "manifest_fingerprint",
                    "parameter_hash",
                    "scenario_id",
                    "merchant_id",
                    "legal_country_iso",
                    "tzid",
                    "zone_id",
                    "channel",
                    "channel_group",
                    "local_horizon_bucket_index",
                    "lambda_local_scenario",
                    "s4_spec_version",
                    "overlay_factor_total",
                ]
            )
        )
        factors_df = scenario_df.select(
            [
                "manifest_fingerprint",
                "parameter_hash",
                "scenario_id",
                "merchant_id",
                "legal_country_iso",
                "tzid",
                "zone_id",
                "channel",
                "channel_group",
                "local_horizon_bucket_index",
                "overlay_factor_total",
                "s4_spec_version",
            ]
        )
        return scenario_df, factors_df, bucket_minutes

    def _resolve_calendar_factors(
        self,
        calendar: pl.DataFrame,
        overlay_policy: Mapping[str, object],
        scenario_id: str,
        default_factor: float,
        horizon_len: int,
    ) -> dict[tuple[str, int], float]:
        factors: dict[tuple[str, int], float] = {}
        if calendar.is_empty():
            return factors
        policy_conf = overlay_policy.get("overlays", {}).get(scenario_id, {}) if isinstance(overlay_policy, Mapping) else {}
        base_events = policy_conf.get("events", []) or []
        precedence = policy_conf.get("precedence", []) or []
        bounds = policy_conf.get("bounds", {}) or {}
        factor_min = float(bounds.get("min", 0.0))
        factor_max = float(bounds.get("max", float("inf")))
        factor_map = {}
        for event in base_events:
            if not isinstance(event, Mapping):
                continue
            name = str(event.get("event_type") or "").strip()
            factor = float(event.get("factor", 1.0))
            if name:
                factor_map[name] = factor
        if "local_horizon_bucket_index" in calendar.columns:
            for row in calendar.to_dicts():
                idx = int(row.get("local_horizon_bucket_index", -1))
                if idx < 0:
                    continue
                tzid = str(row.get("tzid") or "")
                key = (tzid, idx % horizon_len)
                events: list[tuple[str, float]] = []
                event_type = str(row.get("event_type") or "").strip()
                if event_type:
                    events.append((event_type, factor_map.get(event_type, default_factor)))
                if "factor" in row and row.get("factor") is not None:
                    events.append(("factor", float(row.get("factor"))))
                if not events:
                    events.append(("default", default_factor))
                # apply precedence: ordered by precedence list then name
                events.sort(key=lambda ev: (precedence.index(ev[0]) if ev[0] in precedence else len(precedence), ev[0]))
                factor_value = 1.0
                for _, f in events:
                    factor_value *= f
                factor_value = max(factor_min, min(factor_value, factor_max))
                factors[key] = factor_value
        return factors

    @staticmethod
    def _utc_offset_minutes(tzid: str) -> int:
        try:
            tz = ZoneInfo(tzid)
            dt = datetime(2025, 1, 1)
            offset = tz.utcoffset(dt)
            return int(offset.total_seconds() // 60) if offset else 0
        except Exception:
            return 0

    def _project_utc(
        self,
        scenario_df: pl.DataFrame,
        *,
        manifest_fingerprint: str,
        parameter_hash: str,
        scenario_id: str,
        bucket_minutes: int,
        horizon_len: int,
    ) -> pl.DataFrame | None:
        if scenario_df.is_empty():
            return None

        def _utc_index(tzid: str, local_idx: int) -> int:
            offset = self._utc_offset_minutes(tzid)
            utc_idx = (local_idx * bucket_minutes - offset) // bucket_minutes
            return int(utc_idx % horizon_len)

        return (
            scenario_df.with_columns(
                [
                    pl.struct(["tzid", "local_horizon_bucket_index"])
                    .map_elements(lambda s: _utc_index(str(s["tzid"]), int(s["local_horizon_bucket_index"])))
                    .alias("utc_horizon_bucket_index"),
                    pl.lit(manifest_fingerprint).alias("manifest_fingerprint"),
                    pl.lit(parameter_hash).alias("parameter_hash"),
                    pl.lit(scenario_id).alias("scenario_id"),
                    pl.col("lambda_local_scenario").alias("lambda_utc_scenario"),
                    pl.lit(self._S4_SPEC_VERSION).alias("s4_spec_version"),
                ]
            )
            .select(
                [
                    "manifest_fingerprint",
                    "parameter_hash",
                    "scenario_id",
                    "merchant_id",
                    "legal_country_iso",
                    "tzid",
                    "zone_id",
                    "channel",
                    "channel_group",
                    "utc_horizon_bucket_index",
                    "lambda_utc_scenario",
                    "s4_spec_version",
                ]
            )
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
            raise RuntimeError(f"S4_OUTPUT_CONFLICT: existing dataset at {path} differs from recomputed output")
        df.write_parquet(path)


__all__ = ["OverlaysRunner", "OverlaysInputs", "OverlaysResult"]
