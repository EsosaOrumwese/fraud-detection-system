"""Validator for Segment 1B state-5 site→tile assignment."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence

import polars as pl

from engine.layers.l1.seg_1B.s1_tile_index.l2.runner import compute_partition_digest

from ...shared.dictionary import load_dictionary, resolve_dataset_path
from ..exceptions import err
from ..l0.datasets import (
    S4AllocPlanPartition,
    load_iso_countries,
    load_s4_alloc_plan,
    load_tile_index_partition,
)


@dataclass(frozen=True)
class ValidatorConfig:
    """Configuration for validating S5 site→tile assignment output."""

    data_root: Path
    seed: str
    manifest_fingerprint: str
    parameter_hash: str
    dictionary: Optional[Mapping[str, object]] = None
    run_report_path: Optional[Path] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "data_root", self.data_root.expanduser().resolve())
        object.__setattr__(self, "seed", str(self.seed))
        object.__setattr__(self, "manifest_fingerprint", str(self.manifest_fingerprint))
        object.__setattr__(self, "parameter_hash", str(self.parameter_hash))


class S5SiteTileAssignmentValidator:
    """Validate S5 dataset, RNG logs, and control-plane artefacts."""

    def validate(self, config: ValidatorConfig) -> None:
        dictionary = config.dictionary or load_dictionary()
        dataset_path = resolve_dataset_path(
            "s5_site_tile_assignment",
            base_path=config.data_root,
            template_args={
                "seed": config.seed,
                "manifest_fingerprint": config.manifest_fingerprint,
                "parameter_hash": config.parameter_hash,
            },
            dictionary=dictionary,
        )
        if not dataset_path.exists():
            raise err(
                "E506_SCHEMA_INVALID",
                f"s5_site_tile_assignment partition '{dataset_path}' missing",
            )

        assignments = pl.read_parquet(_parquet_pattern(dataset_path)).select(
            ["merchant_id", "legal_country_iso", "site_order", "tile_id"]
        )
        _ensure_schema(assignments)
        _ensure_sort(assignments)
        _ensure_pk(assignments)

        alloc_plan = load_s4_alloc_plan(
            base_path=config.data_root,
            seed=config.seed,
            manifest_fingerprint=config.manifest_fingerprint,
            parameter_hash=config.parameter_hash,
            dictionary=dictionary,
        )
        tile_index = load_tile_index_partition(
            base_path=config.data_root,
            parameter_hash=config.parameter_hash,
            dictionary=dictionary,
        )
        iso_table, _ = load_iso_countries(
            base_path=config.data_root,
            dictionary=dictionary,
        )

        _validate_vs_alloc_plan(assignments, alloc_plan)
        _validate_tile_index(assignments, tile_index.frame)
        _validate_iso(assignments, iso_table.codes)

        run_report_path = (
            config.run_report_path
            if config.run_report_path is not None
            else resolve_dataset_path(
                "s5_run_report",
                base_path=config.data_root,
                template_args={
                    "seed": config.seed,
                    "manifest_fingerprint": config.manifest_fingerprint,
                    "parameter_hash": config.parameter_hash,
                },
                dictionary=dictionary,
            )
        )
        run_report = _load_run_report(run_report_path)
        _validate_run_report(
            report=run_report,
            dataset_path=dataset_path,
            dataset=assignments,
            config=config,
        )

        run_id = run_report["run_id"]
        rng_log_path = resolve_dataset_path(
            "rng_event_site_tile_assign",
            base_path=config.data_root,
            template_args={
                "seed": config.seed,
                "parameter_hash": config.parameter_hash,
                "run_id": run_id,
            },
            dictionary=dictionary,
        )
        events = _load_rng_events(rng_log_path)
        _validate_rng_events(
            events=events,
            dataset=assignments,
            config=config,
            run_report=run_report,
        )


def _parquet_pattern(path: Path) -> str:
    if path.is_dir():
        return str(path / "*.parquet")
    if path.suffix == ".parquet":
        return str(path)
    raise err(
        "E506_SCHEMA_INVALID",
        f"path '{path}' is neither parquet directory nor file",
    )


def _ensure_schema(frame: pl.DataFrame) -> None:
    expected = {"merchant_id", "legal_country_iso", "site_order", "tile_id"}
    columns = set(frame.columns)
    if columns != expected:
        raise err(
            "E506_SCHEMA_INVALID",
            f"s5_site_tile_assignment columns {columns} do not match expected {expected}",
        )


def _ensure_sort(frame: pl.DataFrame) -> None:
    if frame.height == 0:
        return
    sorted_rows = frame.sort(["merchant_id", "legal_country_iso", "site_order"]).rows()
    if frame.rows() != sorted_rows:
        raise err(
            "E509_UNSORTED",
            "s5_site_tile_assignment must be sorted by ['merchant_id','legal_country_iso','site_order']",
        )


def _ensure_pk(frame: pl.DataFrame) -> None:
    dupes = (
        frame.group_by(["merchant_id", "legal_country_iso", "site_order"])
        .agg(pl.len().alias("count"))
        .filter(pl.col("count") > 1)
    )
    if dupes.height:
        raise err("E502_PK_DUPLICATE_SITE", "duplicate site assignments detected")


def _validate_vs_alloc_plan(assignments: pl.DataFrame, alloc_plan: S4AllocPlanPartition) -> None:
    per_tile_counts = (
        assignments.group_by(["merchant_id", "legal_country_iso", "tile_id"])
        .agg(pl.len().alias("assigned_count"))
    )

    comparison = per_tile_counts.join(
        alloc_plan.frame,
        on=["merchant_id", "legal_country_iso", "tile_id"],
        how="full",
    ).fill_null(0)

    mismatches = comparison.filter(
        pl.col("assigned_count") != pl.col("n_sites_tile")
    )
    if mismatches.height:
        raise err(
            "E503_TILE_QUOTA_MISMATCH",
            "assignment counts do not match S4 per-tile quotas",
        )

    per_pair_assignments = (
        assignments.group_by(["merchant_id", "legal_country_iso"])
        .agg(pl.len().alias("assigned_sites"))
    )
    per_pair_quota = (
        alloc_plan.frame.group_by(["merchant_id", "legal_country_iso"])
        .agg(pl.col("n_sites_tile").sum().alias("required_sites"))
    )
    pair_join = per_pair_assignments.join(
        per_pair_quota,
        on=["merchant_id", "legal_country_iso"],
        how="full",
    ).fill_null(0)

    if pair_join.filter(pl.col("assigned_sites") != pl.col("required_sites")).height:
        raise err(
            "E504_SUM_TO_N_MISMATCH",
            "assignments do not conserve per-pair totals from S4",
        )


def _validate_tile_index(assignments: pl.DataFrame, tile_index: pl.DataFrame) -> None:
    missing = assignments.join(
        tile_index,
        left_on=["legal_country_iso", "tile_id"],
        right_on=["country_iso", "tile_id"],
        how="anti",
    )
    if missing.height:
        raise err(
            "E505_TILE_NOT_IN_INDEX",
            "assignments reference tiles absent from tile_index",
        )


def _validate_iso(assignments: pl.DataFrame, iso_codes: Iterable[str]) -> None:
    valid_codes = sorted(iso_codes)
    invalid = assignments.filter(~pl.col("legal_country_iso").is_in(valid_codes))
    if invalid.height:
        raise err("E302_FK_COUNTRY", "assignments reference ISO codes outside the canonical list")


def _load_run_report(path: Path) -> Mapping[str, object]:
    if not path.exists():
        raise err("E515_RUN_REPORT_MISSING_FIELDS", f"s5 run report missing at '{path}'")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise err("E515_RUN_REPORT_MISSING_FIELDS", f"s5 run report is not valid JSON: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise err("E515_RUN_REPORT_MISSING_FIELDS", "s5 run report must decode to a JSON object")
    return payload


def _validate_run_report(
    *,
    report: Mapping[str, object],
    dataset_path: Path,
    dataset: pl.DataFrame,
    config: ValidatorConfig,
) -> None:
    required_fields = {
        "seed",
        "manifest_fingerprint",
        "parameter_hash",
        "run_id",
        "rows_emitted",
        "pairs_total",
        "rng_events_emitted",
        "determinism_receipt",
    }
    missing = sorted(required_fields.difference(report.keys()))
    if missing:
        raise err(
            "E515_RUN_REPORT_MISSING_FIELDS",
            f"s5 run report missing required fields: {missing}",
        )

    if str(report["seed"]) != config.seed:
        raise err("E508_TOKEN_MISMATCH", "run report seed does not match configured seed")
    if report["manifest_fingerprint"] != config.manifest_fingerprint:
        raise err("E508_TOKEN_MISMATCH", "run report manifest_fingerprint mismatch")
    if report["parameter_hash"] != config.parameter_hash:
        raise err("E508_TOKEN_MISMATCH", "run report parameter_hash mismatch")

    rows_emitted = int(report["rows_emitted"])
    if rows_emitted != dataset.height:
        raise err("E504_SUM_TO_N_MISMATCH", "run report rows_emitted does not match dataset height")

    expected_pairs = (
        dataset.select(["merchant_id", "legal_country_iso"]).unique().height
    )
    if int(report["pairs_total"]) != expected_pairs:
        raise err(
            "E504_SUM_TO_N_MISMATCH",
            "run report pairs_total does not match dataset pair count",
        )

    expected_rng_events = report.get("expected_rng_events")
    if expected_rng_events is not None and int(expected_rng_events) != dataset.height:
        raise err(
            "E507_RNG_EVENT_MISMATCH",
            "run report expected_rng_events does not match dataset height",
        )

    receipt = report["determinism_receipt"]
    if not isinstance(receipt, Mapping):
        raise err("E410_NONDETERMINISTIC_OUTPUT", "determinism_receipt must be an object")
    if receipt.get("partition_path") != str(dataset_path):
        raise err("E410_NONDETERMINISTIC_OUTPUT", "determinism_receipt partition path mismatch")
    digest = receipt.get("sha256_hex")
    if not isinstance(digest, str):
        raise err("E410_NONDETERMINISTIC_OUTPUT", "determinism_receipt missing sha256_hex")
    actual_digest = compute_partition_digest(dataset_path)
    if actual_digest != digest:
        raise err("E410_NONDETERMINISTIC_OUTPUT", "determinism receipt digest mismatch")

    _ensure_non_negative(report, ["rng_events_emitted"])
    _ensure_non_negative(
        report,
        [
            "bytes_read_alloc_plan",
            "bytes_read_tile_index",
            "bytes_read_iso",
            "wall_clock_seconds_total",
            "cpu_seconds_total",
            "workers_used",
            "max_worker_rss_bytes",
            "open_files_peak",
            "quota_mismatches",
            "dup_sites",
            "tile_not_in_index",
            "fk_country_violations",
            "ties_broken_total",
        ],
        allow_missing=True,
    )


def _ensure_non_negative(
    payload: Mapping[str, object],
    fields: Sequence[str],
    *,
    allow_missing: bool = False,
) -> None:
    for field in fields:
        if field not in payload:
            if allow_missing:
                continue
            raise err("E515_RUN_REPORT_MISSING_FIELDS", f"run report missing field '{field}'")
        value = payload[field]
        if not isinstance(value, (int, float)):
            raise err("E515_RUN_REPORT_MISSING_FIELDS", f"run report field '{field}' must be numeric")
        if value < 0:
            raise err("E515_RUN_REPORT_MISSING_FIELDS", f"run report field '{field}' cannot be negative")


def _load_rng_events(path: Path) -> list[Mapping[str, object]]:
    if not path.exists():
        raise err(
            "E507_RNG_EVENT_MISMATCH",
            f"rng event partition missing at '{path}'",
        )
    files = sorted([p for p in path.glob("*.jsonl") if p.is_file()])
    if not files:
        raise err("E507_RNG_EVENT_MISMATCH", f"rng event partition '{path}' contains no files")

    events: list[Mapping[str, object]] = []
    for file in files:
        for line_number, line in enumerate(file.read_text(encoding="utf-8").splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise err(
                    "E507_RNG_EVENT_MISMATCH",
                    f"invalid JSON in RNG event log {file} line {line_number}: {exc}",
                ) from exc
            if not isinstance(payload, Mapping):
                raise err("E507_RNG_EVENT_MISMATCH", f"RNG event in {file} line {line_number} must be an object")
            events.append(payload)
    return events


def _validate_rng_events(
    *,
    events: Sequence[Mapping[str, object]],
    dataset: pl.DataFrame,
    config: ValidatorConfig,
    run_report: Mapping[str, object],
) -> None:
    event_count = len(events)
    if event_count != dataset.height:
        raise err(
            "E507_RNG_EVENT_MISMATCH",
            f"RNG event count ({event_count}) does not match dataset rows ({dataset.height})",
        )
    if int(run_report["rng_events_emitted"]) != event_count:
        raise err(
            "E507_RNG_EVENT_MISMATCH",
            "run report rng_events_emitted does not match log size",
        )

    try:
        seed_int = int(config.seed)
    except ValueError as exc:
        raise err("E501_INVALID_SEED", f"seed '{config.seed}' must be base-10 integer") from exc

    expected_keys = {
        "module",
        "substream_label",
        "seed",
        "parameter_hash",
        "manifest_fingerprint",
        "run_id",
        "blocks",
        "draws",
        "merchant_id",
        "legal_country_iso",
        "site_order",
        "tile_id",
        "u",
    }

    rows = []
    for idx, event in enumerate(events):
        missing = expected_keys.difference(event.keys())
        if missing:
            raise err(
                "E507_RNG_EVENT_MISMATCH",
                f"RNG event missing required fields {sorted(missing)}",
            )
        if event["module"] != "1B.s5_site_tile_assignment":
            raise err("E507_RNG_EVENT_MISMATCH", "RNG event module mismatch")
        if event["substream_label"] != "site_tile_assign":
            raise err("E507_RNG_EVENT_MISMATCH", "RNG event substream mismatch")
        if int(event["seed"]) != seed_int:
            raise err("E507_RNG_EVENT_MISMATCH", "RNG event seed does not match run seed")
        if event["parameter_hash"] != config.parameter_hash:
            raise err("E507_RNG_EVENT_MISMATCH", "RNG event parameter_hash mismatch")
        if event["manifest_fingerprint"] != config.manifest_fingerprint:
            raise err("E508_TOKEN_MISMATCH", "RNG event manifest_fingerprint mismatch")
        if event["run_id"] != run_report["run_id"]:
            raise err("E507_RNG_EVENT_MISMATCH", "RNG event run_id mismatch")
        if int(event["blocks"]) != 1:
            raise err("E507_RNG_EVENT_MISMATCH", "RNG event consumed unexpected block count")
        if str(event["draws"]) != "1":
            raise err("E507_RNG_EVENT_MISMATCH", "RNG event draws must equal '1'")
        u_value = float(event["u"])
        if not (0.0 < u_value < 1.0):
            raise err("E507_RNG_EVENT_MISMATCH", "RNG event uniform deviate outside (0,1)")

        rows.append(
            (
                int(event["merchant_id"]),
                str(event["legal_country_iso"]).upper(),
                int(event["site_order"]),
                int(event["tile_id"]),
            )
        )

    events_frame = (
        pl.DataFrame(
            rows,
            schema={
                "merchant_id": pl.UInt64,
                "legal_country_iso": pl.Utf8,
                "site_order": pl.Int64,
                "tile_id": pl.UInt64,
            },
            orient="row",
        )
    )

    dataset_sorted = (
        dataset.select(["merchant_id", "legal_country_iso", "site_order", "tile_id"])
        .with_columns(
            [
                pl.col("merchant_id").cast(pl.UInt64),
                pl.col("tile_id").cast(pl.UInt64),
            ]
        )
        .sort(["merchant_id", "legal_country_iso", "site_order"])
    )
    events_sorted = events_frame.sort(["merchant_id", "legal_country_iso", "site_order"])

    if dataset_sorted.rows() != events_sorted.rows():
        raise err(
            "E507_RNG_EVENT_MISMATCH",
            "RNG events do not align with dataset assignments",
        )


__all__ = ["S5SiteTileAssignmentValidator", "ValidatorConfig"]
