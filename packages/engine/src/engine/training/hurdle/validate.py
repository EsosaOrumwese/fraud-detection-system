"""Validation helpers for synthetic hurdle training corpora."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import polars as pl


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    messages: list[str]

    def raise_for_status(self) -> None:
        if not self.ok:
            raise ValueError("validation failed:\n- " + "\n- ".join(self.messages))

    def __bool__(self) -> bool:  # pragma: no cover - convenience
        return self.ok


def validate_simulation_run(run_dir: Path) -> ValidationResult:
    """Re-open a simulated run and ensure manifest/datasets are consistent."""

    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        return ValidationResult(ok=False, messages=["manifest.json missing"])

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    datasets = manifest.get("datasets", {})
    summary = manifest.get("summary", {})

    messages: list[str] = []

    def _require_dataset(name: str) -> Path | None:
        rel = datasets.get(name)
        if not rel:
            messages.append(f"dataset path missing for {name}")
            return None
        path = Path(rel)
        if not path.is_absolute():
            path = (manifest_path.parent / path).resolve()
        if not path.exists():
            messages.append(f"dataset {name} not found at {path}")
            return None
        return path

    logistic_path = _require_dataset("logistic")
    nb_path = _require_dataset("nb_mean")
    alias_path = _require_dataset("brand_aliases")
    channel_path = _require_dataset("channel_roster")

    logistic = None
    if logistic_path is not None:
        logistic = pl.read_parquet(logistic_path)
        expected_cols = {"brand_id", "country_iso", "mcc", "channel", "gdp_bucket", "is_multi"}
        if not expected_cols <= set(logistic.columns):
            messages.append("logistic frame missing expected columns")
        horizontal_nulls = logistic.select(
            pl.any_horizontal(
                pl.col(col).is_null() for col in ["brand_id", "country_iso", "mcc", "channel"]
            ).alias("has_null")
        )["has_null"]
        if bool(horizontal_nulls.any()):
            messages.append("logistic frame contains null key fields")
        logistic_multi = logistic["is_multi"].mean()
        if logistic_multi <= 0.01 or logistic_multi >= 0.99:
            messages.append(f"multi-site rate out of sanity corridor: {logistic_multi}")
        if int(summary.get("rows_logistic", -1)) != logistic.height:
            messages.append("manifest row count mismatch for logistic")
        valid_channels = {"CP", "CNP"}
        observed_channels = set(logistic["channel"].unique())
        if not observed_channels <= valid_channels:
            messages.append(f"unexpected channel tokens: {sorted(observed_channels - valid_channels)}")

    nb_mean_frame = None
    if nb_path is not None:
        nb_mean = pl.read_parquet(nb_path)
        nb_mean_frame = nb_mean
        if (nb_mean["k_domestic"] < 2).any():
            messages.append("nb_mean table contains counts < 2")
        if int(summary.get("rows_nb", -1)) != nb_mean.height:
            messages.append("manifest row count mismatch for nb_mean")
        if nb_mean.height > 0:
            if nb_mean.select(pl.col("k_domestic").is_null().any()).item():
                messages.append("nb_mean contains null k_domestic")

    if alias_path is not None and logistic is not None:
        aliases = pl.read_parquet(alias_path)
        if not {"brand_id", "merchant_id"} <= set(aliases.columns):
            messages.append("brand_aliases missing required columns")
        alias_row_nulls = aliases.select(
            pl.any_horizontal(
                pl.col(col).is_null() for col in ["brand_id", "merchant_id"]
            ).alias("has_null")
        )["has_null"]
        if bool(alias_row_nulls.any()):
            messages.append("brand_aliases contains null values")
        logistic_brands = set(logistic["brand_id"].unique())
        alias_brands = set(aliases["brand_id"].unique())
        if not logistic_brands <= alias_brands:
            missing = sorted(logistic_brands - alias_brands)
            messages.append(f"brand_aliases missing brands present in logistic: {missing[:5]}")

    if channel_path is not None and logistic is not None:
        roster = pl.read_parquet(channel_path)
        if not {"brand_id", "channel", "evidence"} <= set(roster.columns):
            messages.append("channel_roster missing required columns")
        roster_row_nulls = roster.select(
            pl.any_horizontal(
                pl.col(col).is_null() for col in ["brand_id", "channel"]
            ).alias("has_null")
        )["has_null"]
        if bool(roster_row_nulls.any()):
            messages.append("channel_roster contains null values")
        roster_channels = set(roster["channel"].unique())
        if not roster_channels <= {"CP", "CNP"}:
            messages.append(f"channel_roster unexpected channel tokens: {sorted(roster_channels - {'CP','CNP'})}")
        roster_brands = set(roster["brand_id"].unique())
        logistic_brands = set(logistic["brand_id"].unique())
        if logistic_brands and not logistic_brands <= roster_brands:
            missing = sorted(logistic_brands - roster_brands)
            messages.append(f"channel_roster missing brands from logistic: {missing[:5]}")

    ok = len(messages) == 0
    return ValidationResult(ok=ok, messages=messages)
