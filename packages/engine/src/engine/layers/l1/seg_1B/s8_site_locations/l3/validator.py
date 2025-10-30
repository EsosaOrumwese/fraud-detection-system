"""Validator for Segment 1B state-8 site_locations."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional, Tuple

import polars as pl

from ..exceptions import err
from ..l0.datasets import S7SiteSynthesisPartition, load_s7_site_synthesis, resolve_site_locations_path
from ...shared.dictionary import get_dataset_entry, load_dictionary


@dataclass(frozen=True)
class ValidatorConfig:
    """Configuration for validating S8 outputs."""

    data_root: Path
    seed: str
    manifest_fingerprint: str
    parameter_hash: str
    dictionary: Optional[Mapping[str, object]] = None
    run_summary_path: Optional[Path] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "data_root", self.data_root.expanduser().resolve())
        object.__setattr__(self, "seed", str(self.seed))
        object.__setattr__(self, "manifest_fingerprint", str(self.manifest_fingerprint))
        object.__setattr__(self, "parameter_hash", str(self.parameter_hash))


class S8SiteLocationsValidator:
    """Validate S8 outputs according to the specification."""

    def validate(self, config: ValidatorConfig) -> None:
        dictionary = config.dictionary or load_dictionary()

        dataset_path = resolve_site_locations_path(
            base_path=config.data_root,
            seed=config.seed,
            manifest_fingerprint=config.manifest_fingerprint,
            dictionary=dictionary,
        )
        if not dataset_path.exists():
            raise err(
                "E801_ROW_MISSING",
                f"site_locations partition missing at '{dataset_path}'",
            )

        dataset = self._read_dataset(dataset_path)
        self._validate_schema(dataset)
        self._validate_writer_sort(dataset)
        self._ensure_unique_pk(dataset)
        tokens = _partition_tokens(dataset_path)
        expected_tokens = {
            "seed": config.seed,
            "manifest_fingerprint": config.manifest_fingerprint,
        }
        if tokens != expected_tokens:
            raise err(
                "E805_PARTITION_OR_IDENTITY",
                f"site_locations path tokens {tokens} != expected {expected_tokens}",
            )

        s7_partition = load_s7_site_synthesis(
            base_path=config.data_root,
            seed=config.seed,
            manifest_fingerprint=config.manifest_fingerprint,
            parameter_hash=config.parameter_hash,
            dictionary=dictionary,
        )

        self._validate_final_flag(dictionary)
        self._validate_parity(dataset, s7_partition.frame)

        run_summary_path = (
            config.run_summary_path
            if config.run_summary_path is not None
            else dataset_path.parent / "s8_run_summary.json"
        )
        self._validate_run_summary(
            run_summary_path=run_summary_path,
            dataset=dataset,
            synthesis=s7_partition,
        )

    # -- dataset helpers -------------------------------------------------

    def _read_dataset(self, path: Path) -> pl.DataFrame:
        return (
            pl.scan_parquet(str(path / "*.parquet"))
            .select([
                "merchant_id",
                "legal_country_iso",
                "site_order",
                "lon_deg",
                "lat_deg",
            ])
            .collect()
        )

    def _validate_schema(self, frame: pl.DataFrame) -> None:
        expected = {
            "merchant_id",
            "legal_country_iso",
            "site_order",
            "lon_deg",
            "lat_deg",
        }
        if set(frame.columns) != expected:
            raise err(
                "E804_SCHEMA_VIOLATION",
                "site_locations columns do not match schema",
            )

    def _validate_writer_sort(self, frame: pl.DataFrame) -> None:
        if frame.height == 0:
            return
        if frame.rows() != frame.sort(["merchant_id", "legal_country_iso", "site_order"]).rows():
            raise err(
                "E806_WRITER_SORT_VIOLATION",
                "site_locations must be sorted by ['merchant_id','legal_country_iso','site_order']",
            )

    def _ensure_unique_pk(self, frame: pl.DataFrame) -> None:
        dupes = (
            frame.group_by(["merchant_id", "legal_country_iso", "site_order"])
            .agg(pl.len().alias("count"))
            .filter(pl.col("count") > 1)
        )
        if dupes.height:
            raise err("E803_DUP_KEY", "site_locations contains duplicate primary keys")

    def _validate_parity(self, dataset: pl.DataFrame, synthesis: pl.DataFrame) -> None:
        dataset_keys = _key_set(dataset)
        s7_keys = _key_set(synthesis)
        missing = s7_keys - dataset_keys
        extra = dataset_keys - s7_keys
        if missing:
            raise err("E801_ROW_MISSING", f"site_locations missing {len(missing)} S7 rows")
        if extra:
            raise err("E802_ROW_EXTRA", f"site_locations contains {len(extra)} rows not in S7")

    def _validate_final_flag(self, dictionary: Mapping[str, object]) -> None:
        entry = get_dataset_entry("site_locations", dictionary=dictionary)
        final_flag = entry.get("final_in_layer")
        if final_flag not in (True, "true", "True"):
            raise err("E811_FINAL_FLAG_MISMATCH", "site_locations dictionary entry must be final_in_layer=true")

    def _validate_run_summary(
        self,
        *,
        run_summary_path: Path,
        dataset: pl.DataFrame,
        synthesis: S7SiteSynthesisPartition,
    ) -> None:
        if not run_summary_path.exists():
            raise err("E805_PARTITION_OR_IDENTITY", f"s8 run summary missing at '{run_summary_path}'")
        try:
            payload = json.loads(run_summary_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise err("E804_SCHEMA_VIOLATION", f"s8 run summary is not valid JSON: {exc}") from exc
        if not isinstance(payload, Mapping):
            raise err("E804_SCHEMA_VIOLATION", "s8 run summary must be a JSON object")

        identity = payload.get("identity")
        if not isinstance(identity, Mapping):
            raise err("E804_SCHEMA_VIOLATION", "run summary missing identity block")
        s7_tokens = _s7_partition_tokens(synthesis.path)
        if str(identity.get("seed")) != s7_tokens["seed"]:
            raise err("E805_PARTITION_OR_IDENTITY", "run summary seed mismatch")
        if identity.get("manifest_fingerprint") != s7_tokens["manifest_fingerprint"]:
            raise err("E805_PARTITION_OR_IDENTITY", "run summary manifest mismatch")
        if identity.get("parameter_hash_consumed") != s7_tokens["parameter_hash"]:
            raise err("E809_PARTITION_SHIFT_VIOLATION", "run summary parameter_hash_consumed mismatch")

        sizes = payload.get("sizes")
        if not isinstance(sizes, Mapping):
            raise err("E804_SCHEMA_VIOLATION", "run summary missing sizes block")
        if sizes.get("rows_s7") != synthesis.frame.height:
            raise err("E804_SCHEMA_VIOLATION", "run summary rows_s7 mismatch")
        if sizes.get("rows_s8") != dataset.height:
            raise err("E804_SCHEMA_VIOLATION", "run summary rows_s8 mismatch")
        if bool(sizes.get("parity_ok")) != (synthesis.frame.height == dataset.height):
            raise err("E804_SCHEMA_VIOLATION", "run summary parity flag mismatch")

        validation_counters = payload.get("validation_counters")
        if not isinstance(validation_counters, Mapping):
            raise err("E804_SCHEMA_VIOLATION", "run summary missing validation counters")
        expected_zero_fields = (
            "schema_fail_count",
            "path_embed_mismatches",
            "writer_sort_violations",
            "order_leak_indicators",
        )
        for field in expected_zero_fields:
            if int(validation_counters.get(field, 0)) != 0:
                raise err("E804_SCHEMA_VIOLATION", f"run summary field '{field}' expected zero")

        by_country_summary = payload.get("by_country")
        if not isinstance(by_country_summary, Mapping):
            raise err("E804_SCHEMA_VIOLATION", "run summary missing by_country block")

        s7_counts = _counts_by_country(synthesis.frame)
        s8_counts = _counts_by_country(dataset)
        for iso, s7_count in s7_counts.items():
            summary_entry = by_country_summary.get(iso)
            if not isinstance(summary_entry, Mapping):
                raise err("E804_SCHEMA_VIOLATION", f"run summary missing by_country entry for {iso}")
            rows_s8 = s8_counts.get(iso, 0)
            if summary_entry.get("rows_s7") != s7_count:
                raise err("E804_SCHEMA_VIOLATION", f"run summary rows_s7 mismatch for {iso}")
            if summary_entry.get("rows_s8") != rows_s8:
                raise err("E804_SCHEMA_VIOLATION", f"run summary rows_s8 mismatch for {iso}")
            expected_parity = s7_count == rows_s8
            if bool(summary_entry.get("parity_ok")) != expected_parity:
                raise err("E804_SCHEMA_VIOLATION", f"run summary parity mismatch for {iso}")


def _key_set(frame: pl.DataFrame) -> set[Tuple[int, str, int]]:
    return {
        (int(row[0]), str(row[1]).upper(), int(row[2]))
        for row in frame.select(["merchant_id", "legal_country_iso", "site_order"]).iter_rows()
    }


def _counts_by_country(frame: pl.DataFrame) -> Mapping[str, int]:
    return {
        str(row[0]).upper(): int(row[1])
        for row in frame.group_by("legal_country_iso").len().iter_rows()
    }


def _partition_tokens(path: Path) -> Mapping[str, str]:
    tokens: dict[str, str] = {}
    for part in path.parts:
        if "=" in part:
            key, value = part.split("=", 1)
            tokens[key] = value
    tokens.pop("parameter_hash", None)
    output: dict[str, str] = {
        "seed": tokens.get("seed", ""),
        "manifest_fingerprint": tokens.get("fingerprint", ""),
    }
    return output


def _s7_partition_tokens(path: Path) -> Mapping[str, str]:
    tokens: dict[str, str] = {}
    for part in path.parts:
        if "=" in part:
            key, value = part.split("=", 1)
            tokens[key] = value
    return {
        "seed": tokens.get("seed", ""),
        "manifest_fingerprint": tokens.get("fingerprint", ""),
        "parameter_hash": tokens.get("parameter_hash", ""),
    }


__all__ = ["S8SiteLocationsValidator", "ValidatorConfig"]
