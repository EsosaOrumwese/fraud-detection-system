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

from ...shared.dictionary import load_dictionary, render_dataset_path
from ...shared.receipt import GateReceiptSummary, load_gate_receipt
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
            raise err("E_S4_SEED_EMPTY", "seed must be provided for S4")
        object.__setattr__(self, "seed", seed_value)
        manifest = self.manifest_fingerprint.lower()
        if len(manifest) != 64:
            raise err(
                "E_S4_MANIFEST_FINGERPRINT",
                "manifest_fingerprint must be 64 hex characters",
            )
        int(manifest, 16)
        object.__setattr__(self, "manifest_fingerprint", manifest)
        seg2a_manifest = self.seg2a_manifest_fingerprint.lower()
        if len(seg2a_manifest) != 64:
            raise err(
                "E_S4_SEG2A_MANIFEST",
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

    def run(self, config: S4GroupWeightsInputs) -> S4GroupWeightsResult:
        dictionary = load_dictionary(config.dictionary_path)
        receipt = load_gate_receipt(
            base_path=config.data_root,
            manifest_fingerprint=config.manifest_fingerprint,
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
                "E_S4_OUTPUT_EXISTS",
                f"s4_group_weights already exists at '{output_dir}' - use resume or delete partition first",
            )

        weights = self._load_site_weights(config=config, dictionary=dictionary)
        tz_lookup = self._load_site_timezones(config=config, dictionary=dictionary)
        base_shares = self._aggregate_base_shares(weights=weights, tz_lookup=tz_lookup)
        day_effects = self._load_day_effects(config=config, dictionary=dictionary)
        combined = self._combine_factors(base_shares=base_shares, day_effects=day_effects)
        if combined.height == 0:
            raise err(
                "E_S4_NO_ROWS",
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
                "E_S4_ZERO_DENOM",
                f"renormalisation denominator <= 0 for merchant/day sample: {sample.to_dicts()}",
            )
        combined = combined.with_columns(
            (pl.col("mass_raw") / pl.col("denom_raw")).alias("p_group")
        )
        combined = combined.with_columns(
            pl.lit(receipt.verified_at_utc).alias("created_utc")
        )

        combined = combined.sort(["merchant_id", "utc_day", "tz_group_id"])
        output_dir.parent.mkdir(parents=True, exist_ok=True)
        bytes_written = self._publish_rows(rows=combined, output_dir=output_dir)

        merchants_total = combined["merchant_id"].n_unique()
        days_total = combined["utc_day"].n_unique()
        tz_groups_total = combined["tz_group_id"].n_unique()
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
            bytes_written=bytes_written,
            dictionary_resolution=dictionary_resolution,
            output_path=output_rel,
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
            raise err("E_S4_SITE_WEIGHTS_IO", f"failed to read s1_site_weights: {exc}") from exc
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
                "E_S4_SITE_WEIGHTS_SCHEMA",
                f"s1_site_weights contains invalid rows: {invalid.head(5).to_dicts()}",
            )
        return weights

    def _load_site_timezones(
        self, *, config: S4GroupWeightsInputs, dictionary: Mapping[str, object]
    ) -> pl.DataFrame:
        path = self._resolve_dataset_path(
            dataset_id="site_timezones", config=config, dictionary=dictionary
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
            raise err("E_S4_TZ_LOOKUP_IO", f"failed to read site_timezones: {exc}") from exc
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
                "E_S4_TZ_LOOKUP_SCHEMA",
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
                "E_S4_TZ_LOOKUP_DUPLICATE",
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
            raise err("E_S4_DAY_EFFECTS_IO", f"failed to read s3_day_effects: {exc}") from exc
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
                "E_S4_DAY_EFFECTS_SCHEMA",
                f"s3_day_effects contains invalid rows: {invalid.head(5).to_dicts()}",
            )
        nonpositive = effects.filter(pl.col("gamma") <= 0.0)
        if nonpositive.height:
            raise err(
                "E_S4_DAY_EFFECTS_GAMMA",
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
                "E_S4_TZ_LOOKUP_MISSING",
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
                "E_S4_ZERO_BASE_SHARE",
                f"aggregated base_share <= 0 detected for sample rows: {zero_mass.head(5).to_dicts()}",
            )
        return grouped

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
                "E_S4_MISSING_BASE_SHARE",
                "base_share missing for some gamma rows",
            )
        return combined

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
            template_args["manifest_fingerprint"] = config.seg2a_manifest_fingerprint
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
        bytes_written: int,
        dictionary_resolution: Mapping[str, str],
        output_path: str,
    ) -> dict:
        validators = [
            {"id": "V-20", "status": "PASS", "codes": []},
            {"id": "V-21", "status": "PASS", "codes": []},
            {"id": "V-22", "status": "PASS", "codes": []},
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
