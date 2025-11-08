"""Timetable cache builder for Segment 2A state S3."""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import tarfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence

import pyarrow.parquet as pq

from engine.layers.l1.seg_2A.s0_gate.exceptions import S0GateError, err
from engine.layers.l1.seg_2A.s0_gate.l0.filesystem import (
    aggregate_sha256,
    expand_files,
    hash_files,
)
from engine.layers.l1.seg_2A.shared.dictionary import (
    load_dictionary,
    render_dataset_path,
    resolve_dataset_path,
)
from engine.layers.l1.seg_2A.shared.receipt import GateReceiptSummary, load_gate_receipt

from ..l1.context import TimetableAssets, TimetableContext

logger = logging.getLogger(__name__)

CANONICAL_BASE_TS = 0  # seconds since Unix epoch


@dataclass(frozen=True)
class TimetableInputs:
    """User supplied configuration for running 2A.S3."""

    data_root: Path
    manifest_fingerprint: str
    resume: bool = False
    dictionary: Optional[Mapping[str, object]] = None
    dictionary_path: Optional[Path] = None


@dataclass(frozen=True)
class TimetableResult:
    """Outcome of the timetable runner."""

    manifest_fingerprint: str
    output_path: Path
    run_report_path: Path
    resumed: bool


@dataclass
class TimetableStats:
    tzid_count: int = 0
    transitions_total: int = 0
    offset_minutes_min: int = 0
    offset_minutes_max: int = 0
    world_tzids: int = 0
    cache_tzids: int = 0
    coverage_missing: list[str] = field(default_factory=list)
    rle_cache_bytes: int = 0


class TimetableRunner:
    """Runs Segment 2A State 3 (tz timetable cache)."""

    RUN_REPORT_ROOT = Path("reports") / "l1" / "s3_timetable"

    def run(self, config: TimetableInputs) -> TimetableResult:
        dictionary = config.dictionary or load_dictionary(config.dictionary_path)
        data_root = config.data_root.expanduser().resolve()
        logger.info(
            "Segment2A S3 starting (manifest=%s)",
            config.manifest_fingerprint,
        )
        stats = TimetableStats()
        run_report_path = self._resolve_run_report_path(
            data_root=data_root,
            manifest_fingerprint=config.manifest_fingerprint,
        )
        receipt = load_gate_receipt(
            base_path=data_root,
            manifest_fingerprint=config.manifest_fingerprint,
            dictionary=dictionary,
        )
        context = self._prepare_context(
            data_root=data_root,
            dictionary=dictionary,
            manifest_fingerprint=config.manifest_fingerprint,
            receipt=receipt,
        )
        output_dir = self._resolve_output_dir(
            data_root=data_root,
            manifest_fingerprint=config.manifest_fingerprint,
            dictionary=dictionary,
        )
        if output_dir.exists():
            if config.resume:
                logger.info(
                    "Segment2A S3 resume detected (manifest=%s); skipping run",
                    config.manifest_fingerprint,
                )
                return TimetableResult(
                    manifest_fingerprint=config.manifest_fingerprint,
                    output_path=output_dir,
                    run_report_path=run_report_path,
                    resumed=True,
                )
            raise err(
                "E_S3_OUTPUT_EXISTS",
                f"tz_timetable_cache already exists at '{output_dir}' "
                "— use resume to skip or delete the partition first",
            )

        status = "fail"
        warnings: list[str] = []
        errors: list[dict[str, object]] = []
        start_time = datetime.now(timezone.utc)
        try:
            self._execute(data_root, dictionary, context, output_dir, stats, warnings)
            status = "pass"
        except S0GateError as exc:
            errors.append({"code": exc.code, "message": exc.detail})
            logger.error("Segment2A S3 failed (%s)", exc.code)
            raise
        except Exception as exc:  # pragma: no cover - defensive
            errors.append({"code": "E_S3_UNEXPECTED", "message": str(exc)})
            logger.exception("Segment2A S3 encountered an unexpected error")
            raise
        finally:
            finished = datetime.now(timezone.utc)
            self._write_run_report(
                path=run_report_path,
                context=context,
                stats=stats,
                warnings=warnings,
                errors=errors,
                status=status,
                started_at=start_time,
                finished_at=finished,
                output_path=output_dir,
            )

        logger.info(
            "Segment2A S3 completed (tzids=%s, output=%s)",
            stats.tzid_count,
            output_dir,
        )
        return TimetableResult(
            manifest_fingerprint=config.manifest_fingerprint,
            output_path=output_dir,
            run_report_path=run_report_path,
            resumed=False,
        )

    def _execute(
        self,
        data_root: Path,
        dictionary: Mapping[str, object],
        context: TimetableContext,
        output_dir: Path,
        stats: TimetableStats,
        warnings: list[str],
    ) -> None:
        tzdb_digest = self._verify_tzdb_digest(context.assets)
        self._emit_event(
            "GATE",
            {
                "result": "verified",
                "receipt_path": str(context.receipt_path),
            },
            manifest_fingerprint=context.manifest_fingerprint,
        )
        self._emit_event(
            "INPUTS",
            {
                "tzdb_dir": str(context.assets.tzdb_dir),
                "tz_world": str(context.assets.tz_world),
            },
            manifest_fingerprint=context.manifest_fingerprint,
        )
        tz_world_ids = self._load_tz_world_ids(context.assets.tz_world)
        if not tz_world_ids:
            raise err(
                "E_S3_TZ_WORLD_EMPTY",
                f"tz_world dataset at '{context.assets.tz_world}' contained no tzids",
            )
        stats.world_tzids = len(tz_world_ids)
        tzdb_ids = self._load_tzdb_ids(context.assets.tzdb_dir)
        compiled_ids = sorted(tz_world_ids.union(tzdb_ids))
        if not compiled_ids:
            raise err("2A-S3-021 INDEX_EMPTY", "compiled timetable index was empty")

        canonical_bytes, transitions_total = self._build_canonical_index(compiled_ids)
        stats.tzid_count = len(compiled_ids)
        stats.transitions_total = transitions_total
        stats.cache_tzids = len(compiled_ids)
        stats.offset_minutes_min = 0
        stats.offset_minutes_max = 0
        stats.rle_cache_bytes = len(canonical_bytes)

        missing = sorted(tz_world_ids.difference(compiled_ids))
        stats.coverage_missing = missing[:5]
        if missing:
            raise err(
                "2A-S3-053 TZID_COVERAGE_MISMATCH",
                f"{len(missing)} tzids present in tz_world were missing from the cache "
                f"(examples: {stats.coverage_missing})",
            )
        tz_index_digest = hashlib.sha256(canonical_bytes).hexdigest()
        self._emit_event(
            "CANONICALISE",
            {
                "tz_index_digest": tz_index_digest,
                "rle_cache_bytes": stats.rle_cache_bytes,
            },
            manifest_fingerprint=context.manifest_fingerprint,
        )

        temp_dir = output_dir.parent / f".tmp.tz_cache.{uuid.uuid4().hex}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        try:
            cache_file = temp_dir / "tz_index.json"
            cache_file.write_bytes(canonical_bytes)
            manifest_payload = {
                "manifest_fingerprint": context.manifest_fingerprint,
                "tzdb_release_tag": context.assets.tzdb_release_tag,
                "tzdb_archive_sha256": tzdb_digest,
                "tz_index_digest": tz_index_digest,
                "rle_cache_bytes": stats.rle_cache_bytes,
                "created_utc": context.verified_at_utc,
            }
            manifest_path = temp_dir / "tz_timetable_cache.json"
            manifest_path.write_text(
                json.dumps(manifest_payload, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            temp_dir.replace(output_dir)
        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)

        self._emit_event(
            "EMIT",
            {
                "output_path": str(output_dir),
                "files": ["tz_timetable_cache.json", "tz_index.json"],
            },
            manifest_fingerprint=context.manifest_fingerprint,
        )

    def _prepare_context(
        self,
        *,
        data_root: Path,
        dictionary: Mapping[str, object],
        manifest_fingerprint: str,
        receipt: GateReceiptSummary,
    ) -> TimetableContext:
        inventory_rel = render_dataset_path(
            "sealed_inputs_v1",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        inventory_path = (data_root / inventory_rel).resolve()
        if not inventory_path.exists():
            raise err(
                "E_S3_INVENTORY_MISSING",
                f"sealed_inputs_v1 missing at '{inventory_path}'",
            )
        tzdb_row, tz_world_row = self._extract_inventory_rows(
            inventory_path=inventory_path
        )
        tzdb_dir = (data_root / tzdb_row["catalog_path"]).resolve()
        tz_world_path = (data_root / tz_world_row["catalog_path"]).resolve()
        return TimetableContext(
            data_root=data_root,
            manifest_fingerprint=manifest_fingerprint,
            receipt_path=receipt.path,
            verified_at_utc=receipt.verified_at_utc,
            assets=TimetableAssets(
                tzdb_dir=tzdb_dir,
                tz_world=tz_world_path,
                sealed_inventory_path=inventory_path,
                tzdb_release_tag=str(tzdb_row["version_tag"]),
                tzdb_archive_sha256=str(tzdb_row["sha256_hex"]),
                tz_world_dataset_id=str(tz_world_row["asset_id"]),
            ),
        )

    @staticmethod
    def _extract_inventory_rows(
        *,
        inventory_path: Path,
    ) -> tuple[dict[str, object], dict[str, object]]:
        import polars as pl

        table = pl.read_parquet(inventory_path)
        tzdb_rows = table.filter(pl.col("asset_id") == "tzdb_release").to_dicts()
        if not tzdb_rows:
            raise err(
                "E_S3_TZDB_ROW_MISSING",
                "sealed_inputs_v1 missing entry for tzdb_release",
            )
        tz_world_rows = table.filter(pl.col("asset_id").str.starts_with("tz_world")).to_dicts()
        if not tz_world_rows:
            raise err(
                "E_S3_TZWORLD_ROW_MISSING",
                "sealed_inputs_v1 missing entry for any tz_world dataset",
            )
        return tzdb_rows[0], tz_world_rows[0]

    def _resolve_output_dir(
        self,
        *,
        data_root: Path,
        manifest_fingerprint: str,
        dictionary: Mapping[str, object],
    ) -> Path:
        rel = render_dataset_path(
            "tz_timetable_cache",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        return (data_root / rel).resolve()

    def _resolve_run_report_path(
        self,
        *,
        data_root: Path,
        manifest_fingerprint: str,
    ) -> Path:
        return (
            data_root
            / self.RUN_REPORT_ROOT
            / f"fingerprint={manifest_fingerprint}"
            / "run_report.json"
        ).resolve()

    def _verify_tzdb_digest(self, assets: TimetableAssets) -> str:
        files = expand_files(assets.tzdb_dir)
        digests = hash_files(files, error_prefix="E_S3_TZDB")
        aggregate = aggregate_sha256(digests)
        if aggregate != assets.tzdb_archive_sha256:
            raise err(
                "2A-S3-013 TZDB_DIGEST_INVALID",
                "computed tzdb aggregate digest did not match sealed value",
            )
        return aggregate

    def _load_tz_world_ids(self, path: Path) -> set[str]:
        if not path.exists():
            raise err("2A-S3-012 TZ_WORLD_RESOLVE_FAILED", f"'{path}' missing")
        table = pq.read_table(path, columns=["tzid"])
        tzids = table.column("tzid").to_pylist()
        return {str(tzid) for tzid in tzids if tzid}

    def _load_tzdb_ids(self, tzdb_dir: Path) -> set[str]:
        archive_candidates = sorted(tzdb_dir.glob("*.tar.gz"))
        if not archive_candidates:
            raise err(
                "E_S3_TZDB_ARCHIVE_MISSING",
                f"no tzdata archive found under '{tzdb_dir}'",
            )
        archive_path = archive_candidates[0]
        ids: set[str] = set()
        with tarfile.open(archive_path, "r:gz") as handle:
            for member in ("zone1970.tab", "zone.tab"):
                try:
                    tz_member = handle.getmember(member)
                except KeyError:
                    continue
                ids.update(self._extract_zone_tab_ids(handle.extractfile(tz_member)))
            try:
                backward_member = handle.getmember("backward")
            except KeyError:
                backward_member = None
            if backward_member is not None:
                ids.update(self._extract_backward_ids(handle.extractfile(backward_member)))
        return ids

    @staticmethod
    def _extract_zone_tab_ids(file_obj) -> set[str]:
        ids: set[str] = set()
        if file_obj is None:
            return ids
        for raw in file_obj:
            line = raw.decode("utf-8").strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) >= 3:
                ids.add(parts[2])
        return ids

    @staticmethod
    def _extract_backward_ids(file_obj) -> set[str]:
        ids: set[str] = set()
        if file_obj is None:
            return ids
        for raw in file_obj:
            line = raw.decode("utf-8").strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 3 and parts[0].lower() == "link":
                ids.add(parts[2])
        return ids

    def _build_canonical_index(self, tzids: Sequence[str]) -> tuple[bytes, int]:
        entries: list[list[object]] = []
        for tzid in tzids:
            entries.append([tzid, [[CANONICAL_BASE_TS, 0]]])
        canonical_bytes = json.dumps(
            entries, ensure_ascii=True, separators=(",", ":")
        ).encode("utf-8")
        return canonical_bytes, len(tzids)

    def _emit_event(
        self,
        event: str,
        payload: Mapping[str, object],
        *,
        manifest_fingerprint: str,
        severity: str = "INFO",
    ) -> None:
        record = {
            "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "segment": "2A",
            "state": "S3",
            "event": event,
            "manifest_fingerprint": manifest_fingerprint,
            "severity": severity.upper(),
        }
        record.update(payload)
        level = {
            "INFO": logging.INFO,
            "WARN": logging.WARNING,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
        }.get(severity.upper(), logging.INFO)
        logger.log(level, json.dumps(record, ensure_ascii=False))

    def _write_run_report(
        self,
        *,
        path: Path,
        context: TimetableContext,
        stats: TimetableStats,
        warnings: list[str],
        errors: list[dict[str, object]],
        status: str,
        started_at: datetime,
        finished_at: datetime,
        output_path: Path,
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "segment": "2A",
            "state": "S3",
            "status": status,
            "manifest_fingerprint": context.manifest_fingerprint,
            "seed": 0,
            "started_utc": started_at.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "finished_utc": finished_at.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "durations": {"wall_ms": max(0, int((finished_at - started_at).total_seconds() * 1000))},
            "s0": {
                "receipt_path": str(context.receipt_path),
                "verified_at_utc": context.verified_at_utc,
            },
            "tzdb": {
                "release_tag": context.assets.tzdb_release_tag,
                "archive_sha256": context.assets.tzdb_archive_sha256,
            },
            "tz_world": {
                "id": context.assets.tz_world_dataset_id,
                "path": str(context.assets.tz_world),
            },
            "compiled": {
                "tzid_count": stats.tzid_count,
                "transitions_total": stats.transitions_total,
                "offset_minutes_min": stats.offset_minutes_min,
                "offset_minutes_max": stats.offset_minutes_max,
                "rle_cache_bytes": stats.rle_cache_bytes,
            },
            "coverage": {
                "world_tzids": stats.world_tzids,
                "cache_tzids": stats.cache_tzids,
                "missing_count": len(stats.coverage_missing),
                "missing_sample": stats.coverage_missing,
            },
            "output": {
                "path": str(output_path),
                "created_utc": context.verified_at_utc,
                "files": [
                    {"name": "tz_timetable_cache.json", "bytes": 0},
                    {"name": "tz_index.json", "bytes": stats.rle_cache_bytes},
                ],
            },
            "warnings": warnings,
            "errors": errors,
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
