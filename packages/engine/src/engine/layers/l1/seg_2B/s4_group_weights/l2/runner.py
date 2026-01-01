"""S4 group mix generator for Segment 2B."""

from __future__ import annotations

import json
import logging
import os
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Mapping, Optional, Sequence

import polars as pl

from ...shared.dictionary import load_dictionary, render_dataset_path, repository_root
from ...shared.receipt import (
    GateReceiptSummary,
    SealedInputRecord,
    load_gate_receipt,
    load_sealed_inputs_inventory,
)
from ...shared.schema import load_schema
from ...shared.sealed_assets import verify_sealed_digest
from ...s0_gate.exceptions import err

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class S4GroupWeightsInputs:
    """Configuration required to execute Segment 2B S4."""

    data_root: Path
    seed: int | str
    manifest_fingerprint: str
    seg2a_manifest_fingerprint: str
    dictionary_path: Optional[Path] = None
    resume: bool = False
    emit_run_report_stdout: bool = True

    def __post_init__(self) -> None:
        data_root = self.data_root.expanduser().resolve()
        object.__setattr__(self, "data_root", data_root)
        seed_value = str(self.seed)
        if not seed_value:
            raise err("2B-S4-070", "seed must be provided for S4")
        object.__setattr__(self, "seed", seed_value)
        manifest = self.manifest_fingerprint.lower()
        if len(manifest) != 64:
            raise err(
                "2B-S4-070",
                "manifest_fingerprint must be 64 hex characters",
            )
        int(manifest, 16)
        object.__setattr__(self, "manifest_fingerprint", manifest)
        seg2a_manifest = self.seg2a_manifest_fingerprint.lower()
        if len(seg2a_manifest) != 64:
            raise err(
                "2B-S4-070",
                "seg2a_manifest_fingerprint must be 64 hex characters",
            )
        int(seg2a_manifest, 16)
        object.__setattr__(self, "seg2a_manifest_fingerprint", seg2a_manifest)


@dataclass(frozen=True)
class S4GroupWeightsResult:
    """Outcome of the S4 runner."""

    manifest_fingerprint: str
    output_path: Path
    run_report_path: Path
    resumed: bool


class S4GroupWeightsRunner:
    """Runs Segment 2B State 4."""

    RUN_REPORT_ROOT = Path("reports") / "l1" / "s4_group_weights"
    NORMALISATION_EPS = 1e-12

    def run(self, config: S4GroupWeightsInputs) -> S4GroupWeightsResult:
        dictionary = load_dictionary(config.dictionary_path)
        receipt = load_gate_receipt(
            base_path=config.data_root,
            manifest_fingerprint=config.manifest_fingerprint,
            dictionary=dictionary,
        )
        sealed_assets = self._load_sealed_inventory_map(
            config=config,
            dictionary=dictionary,
        )
        output_dir = self._resolve_dataset_path(
            dataset_id="s4_group_weights", config=config, dictionary=dictionary
        )
        if output_dir.exists():
            if config.resume:
                logger.info(
                    "Segment2B S4 resume detected (seed=%s, manifest=%s); skipping run",
                    config.seed,
                    config.manifest_fingerprint,
                )
                run_report_path = self._resolve_run_report_path(config=config)
                return S4GroupWeightsResult(
                    manifest_fingerprint=config.manifest_fingerprint,
                    output_path=output_dir,
                    run_report_path=run_report_path,
                    resumed=True,
                )
            raise err(
                "2B-S4-080",
                f"s4_group_weights already exists at '{output_dir}' - use resume or delete partition first",
            )

        weights = self._load_site_weights(config=config, dictionary=dictionary)
        tz_lookup = self._load_site_timezones(
            config=config,
            dictionary=dictionary,
            sealed_assets=sealed_assets,
        )
        base_shares = self._aggregate_base_shares(weights=weights, tz_lookup=tz_lookup)
        base_share_delta = self._validate_base_share_totals(base_shares=base_shares)
        tz_counts = (
            base_shares.group_by("merchant_id")
            .agg(pl.col("tz_group_id").n_unique().alias("tz_groups_required"))
        )
        day_effects = self._load_day_effects(config=config, dictionary=dictionary)
        combined = self._combine_factors(base_shares=base_shares, day_effects=day_effects)
        if combined.height == 0:
            raise err(
                "2B-S4-050",
                "renormalisation produced zero rows; ensure S1 and S3 emitted rows for this run",
            )
        combined = combined.with_columns(
            [
                (pl.col("base_share") * pl.col("gamma"))
                .alias("mass_raw")
                .fill_nan(0.0),
            ]
        )
        combined = combined.with_columns(
            pl.col("mass_raw")
            .sum()
            .over(["merchant_id", "utc_day"])
            .alias("denom_raw")
        )
        denom_invalid = combined.filter(pl.col("denom_raw") <= 0.0)
        if denom_invalid.height:
            sample = denom_invalid.select(["merchant_id", "utc_day", "denom_raw"]).head(5)
            raise err(
                "2B-S4-051",
                f"renormalisation denominator <= 0 for merchant/day sample: {sample.to_dicts()}",
            )
        combined = combined.with_columns(
            (pl.col("mass_raw") / pl.col("denom_raw")).alias("p_group_raw")
        )
        combined = combined.with_columns(
            pl.when(pl.col("p_group_raw") < -self.NORMALISATION_EPS)
            .then(None)
            .when(pl.col("p_group_raw") < 0)
            .then(0.0)
            .otherwise(pl.col("p_group_raw"))
            .alias("p_group")
        )
        negative = combined.filter(pl.col("p_group").is_null())
        if negative.height:
            raise err(
                "2B-S4-057",
                f"normalised weights dropped below tolerance for sample rows: {negative.head(5).to_dicts()}",
            )
        combined = combined.with_columns(
            pl.col("p_group")
            .sum()
            .over(["merchant_id", "utc_day"])
            .alias("p_total")
        )
        zero_totals = combined.filter(pl.col("p_total") <= 0.0)
        if zero_totals.height:
            raise err(
                "2B-S4-051",
                f"normalisation total <= 0 for sample merchant/day keys: {zero_totals.head(5).to_dicts()}",
            )
        combined = combined.with_columns(
            (pl.col("p_group") / pl.col("p_total")).alias("p_group")
        ).drop(["p_total", "p_group_raw"])
        combined = combined.with_columns(
            pl.lit(receipt.verified_at_utc).alias("created_utc")
        )

        combined = combined.sort(["merchant_id", "utc_day", "tz_group_id"])
        output_dir.parent.mkdir(parents=True, exist_ok=True)
        self._validate_output_schema(rows=combined)
        bytes_written = self._publish_rows(rows=combined, output_dir=output_dir)

        merchants_total = combined["merchant_id"].n_unique()
        rows_expected, days_total = self._validate_coverage(
            combined=combined, tz_counts=tz_counts
        )
        rows_total = combined.height
        if rows_total != rows_expected:
            raise err(
                "2B-S4-050",
                f"rows written ({rows_total}) differ from expected coverage ({rows_expected})",
            )
        tz_groups_total = combined["tz_group_id"].n_unique()
        max_abs_p_delta = self._validate_p_group_totals(combined=combined)
        rows_total = combined.height
        dictionary_resolution = self._catalogue_resolution(dictionary=dictionary)
        output_rel = render_dataset_path(
            "s4_group_weights",
            template_args={
                "seed": config.seed,
                "manifest_fingerprint": config.manifest_fingerprint,
            },
            dictionary=dictionary,
        )
        run_report = self._build_run_report(
            config=config,
            receipt=receipt,
            merchants_total=merchants_total,
            tz_groups_total=tz_groups_total,
            days_total=days_total,
            rows_total=rows_total,
            rows_expected=rows_expected,
            bytes_written=bytes_written,
            dictionary_resolution=dictionary_resolution,
            output_path=output_rel,
            max_abs_base_share_delta=base_share_delta,
            max_abs_p_group_delta=max_abs_p_delta,
        )
        run_report_path = self._resolve_run_report_path(config=config)
        run_report_path.parent.mkdir(parents=True, exist_ok=True)
        run_report_path.write_text(json.dumps(run_report, indent=2), encoding="utf-8")
        if config.emit_run_report_stdout:
            print(json.dumps(run_report, indent=2))  # pragma: no cover

        return S4GroupWeightsResult(
            manifest_fingerprint=config.manifest_fingerprint,
            output_path=output_dir,
            run_report_path=run_report_path,
            resumed=False,
        )

    # ------------------------------------------------------------------ loaders

    def _load_site_weights(
        self, *, config: S4GroupWeightsInputs, dictionary: Mapping[str, object]
    ) -> pl.DataFrame:
        path = self._resolve_dataset_path(
            dataset_id="s1_site_weights", config=config, dictionary=dictionary
        )
        try:
            weights = pl.read_parquet(
                path,
                columns=["merchant_id", "legal_country_iso", "site_order", "p_weight"],
            )
        except Exception as exc:  # pragma: no cover
            raise err("2B-S4-020", f"failed to read s1_site_weights: {exc}") from exc
        weights = weights.with_columns(
            [
                pl.col("merchant_id").cast(pl.UInt64, strict=False),
                pl.col("legal_country_iso").cast(pl.Utf8, strict=False),
                pl.col("site_order").cast(pl.Int32, strict=False),
                pl.col("p_weight").cast(pl.Float64, strict=False),
            ]
        )
        invalid = weights.filter(
            pl.col("merchant_id").is_null()
            | pl.col("legal_country_iso").is_null()
            | pl.col("site_order").is_null()
            | pl.col("p_weight").is_null()
        )
        if invalid.height:
            raise err(
                "2B-S4-040",
                f"s1_site_weights contains invalid rows: {invalid.head(5).to_dicts()}",
            )
        return weights

    def _load_site_timezones(
        self,
        *,
        config: S4GroupWeightsInputs,
        dictionary: Mapping[str, object],
        sealed_assets: Mapping[str, SealedInputRecord],
    ) -> pl.DataFrame:
        tz_rel = render_dataset_path(
            "site_timezones",
            template_args={
                "seed": config.seed,
                "manifest_fingerprint": config.manifest_fingerprint,
            },
            dictionary=dictionary,
        )
        path = self._resolve_optional_pin(
            asset_id="site_timezones",
            sealed_assets=sealed_assets,
            expected_catalog_path=tz_rel,
            error_code="2B-S4-022",
            data_root=config.data_root,
        )
        try:
            tz_lookup = pl.read_parquet(
                path,
                columns=[
                    "merchant_id",
                    "legal_country_iso",
                    "site_order",
                    "tzid",
                ],
            )
        except Exception as exc:  # pragma: no cover
            raise err("2B-S4-020", f"failed to read site_timezones: {exc}") from exc
        tz_lookup = tz_lookup.with_columns(
            [
                pl.col("merchant_id").cast(pl.UInt64, strict=False),
                pl.col("legal_country_iso").cast(pl.Utf8, strict=False),
                pl.col("site_order").cast(pl.Int32, strict=False),
                pl.col("tzid").cast(pl.Utf8, strict=False),
            ]
        )
        invalid = tz_lookup.filter(
            pl.col("merchant_id").is_null()
            | pl.col("legal_country_iso").is_null()
            | pl.col("site_order").is_null()
            | pl.col("tzid").is_null()
        )
        if invalid.height:
            raise err(
                "2B-S4-040",
                f"site_timezones contains invalid rows: {invalid.head(5).to_dicts()}",
            )
        duplicates = (
            tz_lookup.group_by(["merchant_id", "legal_country_iso", "site_order"])
            .len()
            .rename({"len": "count"})
            .filter(pl.col("count") > 1)
        )
        if duplicates.height:
            raise err(
                "2B-S4-041",
                f"site_timezones has duplicate entries for sample keys: {duplicates.head(5).to_dicts()}",
            )
        return tz_lookup

    def _load_day_effects(
        self, *, config: S4GroupWeightsInputs, dictionary: Mapping[str, object]
    ) -> pl.DataFrame:
        path = self._resolve_dataset_path(
            dataset_id="s3_day_effects", config=config, dictionary=dictionary
        )
        try:
            effects = pl.read_parquet(
                path,
                columns=["merchant_id", "utc_day", "tz_group_id", "gamma"],
            )
        except Exception as exc:  # pragma: no cover
            raise err("2B-S4-020", f"failed to read s3_day_effects: {exc}") from exc
        effects = effects.with_columns(
            [
                pl.col("merchant_id").cast(pl.UInt64, strict=False),
                pl.col("utc_day").cast(pl.Utf8, strict=False),
                pl.col("tz_group_id").cast(pl.Utf8, strict=False),
                pl.col("gamma").cast(pl.Float64, strict=False),
            ]
        )
        invalid = effects.filter(
            pl.col("merchant_id").is_null()
            | pl.col("utc_day").is_null()
            | pl.col("tz_group_id").is_null()
            | pl.col("gamma").is_null()
        )
        if invalid.height:
            raise err(
                "2B-S4-057",
                f"s3_day_effects contains invalid rows: {invalid.head(5).to_dicts()}",
            )
        nonpositive = effects.filter(pl.col("gamma") <= 0.0)
        if nonpositive.height:
            raise err(
                "2B-S4-057",
                f"gamma <= 0 detected for sample rows: {nonpositive.head(5).to_dicts()}",
            )
        return effects

    # ------------------------------------------------------------------ transforms

    def _aggregate_base_shares(
        self, *, weights: pl.DataFrame, tz_lookup: pl.DataFrame
    ) -> pl.DataFrame:
        joined = weights.join(
            tz_lookup,
            on=["merchant_id", "legal_country_iso", "site_order"],
            how="inner",
        )
        if joined.height != weights.height:
            raise err(
                "2B-S4-040",
                "site_timezones missing rows for some s1_site_weights keys",
            )
        grouped = (
            joined.group_by(["merchant_id", "tzid"])
            .agg(pl.col("p_weight").sum().alias("base_share"))
            .rename({"tzid": "tz_group_id"})
        )
        zero_mass = grouped.filter(pl.col("base_share") <= 0.0)
        if zero_mass.height:
            raise err(
                "2B-S4-052",
                f"aggregated base_share <= 0 detected for sample rows: {zero_mass.head(5).to_dicts()}",
            )
        return grouped

    def _validate_base_share_totals(self, *, base_shares: pl.DataFrame) -> float:
        totals = (
            base_shares.group_by("merchant_id")
            .agg(pl.col("base_share").sum().alias("base_sum"))
            .with_columns((pl.col("base_sum") - 1.0).alias("delta"))
        )
        if totals.height == 0:
            raise err("2B-S4-052", "base share aggregation produced zero merchants")
        offending = totals.filter(pl.col("delta").abs() > self.NORMALISATION_EPS)
        if offending.height:
            raise err(
                "2B-S4-052",
                f"base_share totals deviate from 1 beyond tolerance: {offending.head(5).to_dicts()}",
            )
        max_abs = float(
            totals.select(pl.col("delta").abs().max()).to_series().to_list()[0] or 0.0
        )
        return max_abs

    def _combine_factors(
        self, *, base_shares: pl.DataFrame, day_effects: pl.DataFrame
    ) -> pl.DataFrame:
        combined = day_effects.join(
            base_shares,
            on=["merchant_id", "tz_group_id"],
            how="inner",
        )
        if combined.height != day_effects.height:
            raise err(
                "2B-S4-050",
                "base_share missing for some gamma rows",
            )
        return combined

    def _validate_coverage(
        self,
        *,
        combined: pl.DataFrame,
        tz_counts: pl.DataFrame,
    ) -> tuple[int, int]:
        coverage = (
            combined.group_by(["merchant_id", "utc_day"])
            .agg(
                pl.len().alias("rows"),
                pl.col("tz_group_id").n_unique().alias("tz_groups_present"),
            )
            .join(tz_counts, on="merchant_id", how="left")
        )
        missing_merchants = set(tz_counts["merchant_id"].to_list()) - set(
            coverage["merchant_id"].to_list()
        )
        if missing_merchants:
            raise err(
                "2B-S4-050",
                f"no day coverage found for merchants: {sorted(list(missing_merchants))[:5]}",
            )
        missing = coverage.filter(
            (pl.col("tz_groups_required").is_null())
            | (pl.col("rows") != pl.col("tz_groups_required"))
            | (pl.col("tz_groups_present") != pl.col("tz_groups_required"))
        )
        if missing.height:
            raise err(
                "2B-S4-050",
                f"tz-group coverage incomplete for sample merchant/day keys: {missing.head(5).to_dicts()}",
            )
        rows_expected = int(
            coverage.select(pl.col("tz_groups_required").sum())
            .to_series()
            .to_list()[0]
            or 0
        )
        days_total = coverage.height
        return rows_expected, days_total

    def _validate_p_group_totals(self, *, combined: pl.DataFrame) -> float:
        totals = (
            combined.group_by(["merchant_id", "utc_day"])
            .agg(pl.col("p_group").sum().alias("total_mass"))
            .with_columns((pl.col("total_mass") - 1.0).alias("delta"))
        )
        offending = totals.filter(pl.col("delta").abs() > self.NORMALISATION_EPS)
        if offending.height:
            raise err(
                "2B-S4-051",
                f"normalised weights deviate from 1 beyond tolerance: {offending.head(5).to_dicts()}",
            )
        max_abs = float(
            totals.select(pl.col("delta").abs().max()).to_series().to_list()[0] or 0.0
        )
        return max_abs

    # ------------------------------------------------------------------ IO helpers

    def _publish_rows(self, *, rows: pl.DataFrame, output_dir: Path) -> int:
        output_dir.parent.mkdir(parents=True, exist_ok=True)
        staging_dir = output_dir.parent / f".s4_group_weights_{uuid.uuid4().hex}"
        staging_dir.mkdir(parents=True, exist_ok=False)
        try:
            part_path = staging_dir / "part-00000.parquet"
            rows.write_parquet(part_path, compression="zstd")
            self._fsync_file(part_path)
            os.replace(staging_dir, output_dir)
        except Exception:
            shutil.rmtree(staging_dir, ignore_errors=True)
            raise
        bytes_written = sum(f.stat().st_size for f in output_dir.glob("*.parquet"))
        return bytes_written

    # ------------------------------------------------------------------ sealed asset helpers

    def _load_sealed_inventory_map(
        self,
        *,
        config: S4GroupWeightsInputs,
        dictionary: Mapping[str, object],
    ) -> Mapping[str, SealedInputRecord]:
        records = load_sealed_inputs_inventory(
            base_path=config.data_root,
            manifest_fingerprint=config.manifest_fingerprint,
            dictionary=dictionary,
        )
        return {record.asset_id: record for record in records}

    def _require_sealed_asset(
        self,
        *,
        asset_id: str,
        sealed_assets: Mapping[str, SealedInputRecord],
        code: str,
    ) -> SealedInputRecord:
        record = sealed_assets.get(asset_id)
        if record is None:
            raise err(code, f"sealed asset '{asset_id}' not present in S0 sealed_inputs_v1")
        return record

    def _resolve_sealed_path(
        self,
        *,
        record: SealedInputRecord,
        data_root: Path,
        error_code: str,
    ) -> Path:
        candidate = (data_root / record.catalog_path).resolve()
        if candidate.exists():
            return candidate
        repo_candidate = (repository_root() / record.catalog_path).resolve()
        if repo_candidate.exists():
            return repo_candidate
        raise err(
            error_code,
            f"sealed asset '{record.asset_id}' path '{record.catalog_path}' not found under data root or repo",
        )

    def _resolve_optional_pin(
        self,
        *,
        asset_id: str,
        sealed_assets: Mapping[str, SealedInputRecord],
        expected_catalog_path: str,
        error_code: str,
        data_root: Path,
    ) -> Path:
        record = self._require_sealed_asset(
            asset_id=asset_id,
            sealed_assets=sealed_assets,
            code=error_code,
        )
        sealed_path = record.catalog_path.rstrip("/\\")
        expected_path = expected_catalog_path.rstrip("/\\")
        if sealed_path != expected_path:
            raise err(
                error_code,
                f"sealed asset '{asset_id}' path mismatch between sealed_inputs_v1 '{record.catalog_path}' "
                f"and dictionary '{expected_catalog_path}'",
            )
        resolved = self._resolve_sealed_path(
            record=record,
            data_root=data_root,
            error_code=error_code,
        )
        verify_sealed_digest(
            asset_id=asset_id,
            path=resolved,
            expected_hex=record.sha256_hex,
            code=error_code,
        )
        return resolved

    def _resolve_dataset_path(
        self,
        *,
        dataset_id: str,
        config: S4GroupWeightsInputs,
        dictionary: Mapping[str, object],
    ) -> Path:
        template_args = {
            "seed": config.seed,
            "manifest_fingerprint": config.manifest_fingerprint,
        }
        if dataset_id in {"site_timezones", "tz_timetable_cache"}:
        template_args["manifest_fingerprint"] = config.manifest_fingerprint
        rel = render_dataset_path(dataset_id, template_args=template_args, dictionary=dictionary)
        return (config.data_root / rel).resolve()

    def _resolve_run_report_path(self, *, config: S4GroupWeightsInputs) -> Path:
        return (
            config.data_root
            / self.RUN_REPORT_ROOT
            / f"seed={config.seed}"
            / f"fingerprint={config.manifest_fingerprint}"
            / "run_report.json"
        ).resolve()

    def _catalogue_resolution(self, *, dictionary: Mapping[str, object]) -> Mapping[str, str]:
        catalogue = dictionary.get("catalogue") or {}
        return {
            "dictionary_version": str(catalogue.get("dictionary_version", "unknown")),
            "registry_version": str(catalogue.get("registry_version", "unknown")),
        }

    def _build_run_report(
        self,
        *,
        config: S4GroupWeightsInputs,
        receipt: GateReceiptSummary,
        merchants_total: int,
        tz_groups_total: int,
        days_total: int,
        rows_total: int,
        rows_expected: int,
        bytes_written: int,
        dictionary_resolution: Mapping[str, str],
        output_path: str,
        max_abs_base_share_delta: float,
        max_abs_p_group_delta: float,
    ) -> dict:
        validators = [
            {
                "id": "V-20",
                "status": "PASS",
                "codes": [],
                "metrics": {"max_abs_base_share_delta": max_abs_base_share_delta},
            },
            {
                "id": "V-21",
                "status": "PASS",
                "codes": [],
                "metrics": {"max_abs_p_group_delta": max_abs_p_group_delta},
            },
            {
                "id": "V-22",
                "status": "PASS",
                "codes": [],
                "metrics": {"rows_expected": rows_expected, "rows_written": rows_total},
            },
        ]
        run_report = {
            "component": "2B.S4",
            "fingerprint": config.manifest_fingerprint,
            "seed": config.seed,
            "created_utc": receipt.verified_at_utc,
            "catalogue_resolution": dictionary_resolution,
            "inputs_summary": {
                "weights": "s1_site_weights",
                "site_timezones": "site_timezones",
                "day_effects": "s3_day_effects",
                "merchants_total": merchants_total,
                "tz_groups_total": tz_groups_total,
                "days_total": days_total,
            },
            "counts": {
                "rows_total": rows_total,
                "rows_expected": rows_expected,
                "merchants_total": merchants_total,
                "tz_groups_total": tz_groups_total,
                "days_total": days_total,
            },
            "output": {
                "id": "s4_group_weights",
                "path": output_path,
                "bytes_written": bytes_written,
            },
            "summary": {"overall_status": "PASS", "warn_count": 0, "fail_count": 0},
            "validators": validators,
        }
        return run_report

    @staticmethod
    def _fsync_file(path: Path) -> None:
        try:
            with path.open("rb") as handle:
                os.fsync(handle.fileno())
        except (OSError, AttributeError):  # pragma: no cover
            logger.debug("fsync skipped for %s", path)

    def _validate_output_schema(self, *, rows: pl.DataFrame) -> None:
        schema = load_schema("#/plan/s4_group_weights")
        required_cols = [
            "merchant_id",
            "utc_day",
            "tz_group_id",
            "p_group",
            "base_share",
            "gamma",
            "created_utc",
            "mass_raw",
            "denom_raw",
        ]
        if set(rows.columns) != set(required_cols):
            raise err(
                "2B-S4-030",
                f"s4_group_weights columns {rows.columns} do not match schema {required_cols}",
            )
        expected_types = {
            "merchant_id": pl.UInt64,
            "utc_day": pl.Utf8,
            "tz_group_id": pl.Utf8,
            "p_group": pl.Float64,
            "base_share": pl.Float64,
            "gamma": pl.Float64,
            "created_utc": pl.Utf8,
            "mass_raw": pl.Float64,
            "denom_raw": pl.Float64,
        }
        for name, dtype in expected_types.items():
            actual = rows.schema.get(name)
            if actual != dtype:
                raise err(
                    "2B-S4-030",
                    f"column '{name}' has dtype {actual}, expected {dtype}",
                )
