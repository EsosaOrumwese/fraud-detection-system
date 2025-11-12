"""Legality report builder for Segment 2A state S4."""

from __future__ import annotations

import json
import logging
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Optional

import polars as pl

from engine.layers.l1.seg_2A.s0_gate.exceptions import S0GateError, err
from engine.layers.l1.seg_2A.shared.dictionary import (
    load_dictionary,
    render_dataset_path,
    resolve_dataset_path,
)
from engine.layers.l1.seg_2A.shared.receipt import (
    GateReceiptSummary,
    load_determinism_receipt,
    load_gate_receipt,
)
from engine.layers.l1.seg_2A.shared.tz_assets import load_tz_adjustments

from ..l1.context import LegalityAssets, LegalityContext

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LegalityInputs:
    """User supplied configuration for running 2A.S4."""

    data_root: Path
    seed: int
    manifest_fingerprint: str
    resume: bool = False
    dictionary: Optional[Mapping[str, object]] = None
    dictionary_path: Optional[Path] = None


@dataclass(frozen=True)
class LegalityResult:
    """Outcome of the legality runner."""

    seed: int
    manifest_fingerprint: str
    output_path: Path
    run_report_path: Path
    resumed: bool


@dataclass
class LegalityStats:
    sites_total: int = 0
    tzids_total: int = 0
    gap_windows_total: int = 0
    fold_windows_total: int = 0
    missing_tzids: list[str] = field(default_factory=list)
    adjustments_count: int = 0
    adjustments_tzids: list[str] = field(default_factory=list)


class LegalityRunner:
    """Runs Segment 2A State 4 (legality report)."""

    RUN_REPORT_ROOT = Path("reports") / "l1" / "s4_legality"

    def run(self, config: LegalityInputs) -> LegalityResult:
        dictionary = config.dictionary or load_dictionary(config.dictionary_path)
        data_root = config.data_root.expanduser().resolve()
        logger.info(
            "Segment2A S4 starting (seed=%s, manifest=%s)",
            config.seed,
            config.manifest_fingerprint,
        )
        run_report_path = self._resolve_run_report_path(
            data_root=data_root,
            manifest_fingerprint=config.manifest_fingerprint,
            seed=config.seed,
        )
        receipt = load_gate_receipt(
            base_path=data_root,
            manifest_fingerprint=config.manifest_fingerprint,
            dictionary=dictionary,
        )
        determinism_receipt = load_determinism_receipt(
            base_path=data_root,
            manifest_fingerprint=config.manifest_fingerprint,
        )
        context = self._prepare_context(
            data_root=data_root,
            dictionary=dictionary,
            manifest_fingerprint=config.manifest_fingerprint,
            seed=config.seed,
            receipt=receipt,
            determinism_receipt=determinism_receipt,
        )
        output_path = self._resolve_output_path(
            data_root=data_root,
            manifest_fingerprint=config.manifest_fingerprint,
            seed=config.seed,
            dictionary=dictionary,
        )
        if output_path.exists():
            if config.resume:
                logger.info(
                    "Segment2A S4 resume detected (seed=%s, manifest=%s); skipping run",
                    config.seed,
                    config.manifest_fingerprint,
                )
                return LegalityResult(
                    seed=config.seed,
                    manifest_fingerprint=config.manifest_fingerprint,
                    output_path=output_path,
                    run_report_path=run_report_path,
                    resumed=True,
                )
            raise err(
                "E_S4_OUTPUT_EXISTS",
                f"s4_legality_report already exists at '{output_path}' "
                "- use resume to skip or delete the partition first",
            )

        stats = LegalityStats()
        status = "fail"
        warnings: list[str] = []
        errors: list[dict[str, object]] = []
        start_time = datetime.now(timezone.utc)
        output_bytes = 0
        try:
            output_bytes, status = self._execute(context, output_path, stats, warnings)
        except S0GateError as exc:
            errors.append({"code": exc.code, "message": exc.detail})
            logger.error("Segment2A S4 failed (%s)", exc.code)
            raise
        except Exception as exc:  # pragma: no cover - defensive
            errors.append({"code": "E_S4_UNEXPECTED", "message": str(exc)})
            logger.exception("Segment2A S4 encountered an unexpected error")
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
                output_path=output_path,
                output_bytes=output_bytes,
            )

        logger.info(
            "Segment2A S4 completed (sites=%s, tzids=%s, output=%s)",
            stats.sites_total,
            stats.tzids_total,
            output_path,
        )
        return LegalityResult(
            seed=config.seed,
            manifest_fingerprint=config.manifest_fingerprint,
            output_path=output_path,
            run_report_path=run_report_path,
            resumed=False,
        )

    def _execute(
        self,
        context: LegalityContext,
        output_path: Path,
        stats: LegalityStats,
        warnings: list[str],
    ) -> tuple[int, str]:
        if context.tz_adjustments:
            stats.adjustments_count = context.tz_adjustments.count
            stats.adjustments_tzids = list(context.tz_adjustments.tzids)
        tzid_usage, sites_total = self._load_site_timezones(context.assets.site_timezones_path)
        stats.sites_total = sites_total
        stats.tzids_total = len(tzid_usage)
        cache_index = self._load_cache_index(context.assets)

        gap_total = 0
        fold_total = 0
        missing_tzids: list[str] = []
        for tzid in tzid_usage:
            entries = cache_index.get(tzid)
            if entries is None:
                missing_tzids.append(tzid)
                continue
            tz_gap, tz_fold = self._count_windows(entries)
            gap_total += tz_gap
            fold_total += tz_fold

        stats.gap_windows_total = gap_total
        stats.fold_windows_total = fold_total
        stats.missing_tzids = missing_tzids[:]

        status = "PASS" if not missing_tzids else "FAIL"
        if missing_tzids:
            warnings.append(
                f"{len(missing_tzids)} tzids present in site_timezones were missing from tz_timetable_cache"
            )

        output_bytes = self._write_output_report(
            context=context,
            output_path=output_path,
            stats=stats,
            status=status,
        )
        return output_bytes, status

    def _prepare_context(
        self,
        *,
        data_root: Path,
        dictionary: Mapping[str, object],
        manifest_fingerprint: str,
        seed: int,
        receipt: GateReceiptSummary,
        determinism_receipt: Mapping[str, object],
    ) -> LegalityContext:
        site_rel = render_dataset_path(
            "site_timezones",
            template_args={"seed": seed, "manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        site_path = (data_root / site_rel).resolve()
        if not site_path.exists():
            raise err(
                "E_S4_SITE_TZ_MISSING",
                f"site_timezones partition missing at '{site_path}'",
            )
        cache_rel = render_dataset_path(
            "tz_timetable_cache",
            template_args={"manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        cache_dir = (data_root / cache_rel).resolve()
        manifest_path = cache_dir / "tz_timetable_cache.json"
        index_path = cache_dir / "tz_index.json"
        if not manifest_path.exists() or not index_path.exists():
            raise err(
                "E_S4_CACHE_MISSING",
                f"tz_timetable_cache payload missing under '{cache_dir}'",
            )
        adjustments_summary = load_tz_adjustments(
            base_path=data_root,
            manifest_fingerprint=manifest_fingerprint,
            dictionary=dictionary,
        )
        assets = LegalityAssets(
            site_timezones_path=site_path,
            tz_cache_dir=cache_dir,
            tz_cache_manifest_path=manifest_path,
            tz_cache_index_path=index_path,
        )
        return LegalityContext(
            data_root=data_root,
            seed=seed,
            manifest_fingerprint=manifest_fingerprint,
            receipt_path=receipt.path,
            verified_at_utc=receipt.verified_at_utc,
            assets=assets,
            tz_adjustments=adjustments_summary,
            determinism_receipt=determinism_receipt,
        )

    def _load_site_timezones(self, path: Path) -> tuple[list[str], int]:
        if not path.exists():
            raise err("E_S4_SITE_TZ_MISSING", f"'{path}' missing")
        if path.is_dir():
            sources = sorted(p.as_posix() for p in path.rglob("*.parquet"))
            if not sources:
                raise err(
                    "E_S4_SITE_TZ_EMPTY",
                    f"no parquet files found under '{path}'",
                )
        else:
            sources = [path.as_posix()]
        table = (
            pl.scan_parquet(sources)
            .select("tzid")
            .collect()
        )
        sites_total = table.height
        if sites_total == 0:
            return [], 0
        tzids = (
            table.get_column("tzid")
            .cast(pl.Utf8)
            .drop_nulls()
            .unique()
            .to_list()
        )
        tzid_list = sorted(str(tzid) for tzid in tzids if tzid)
        return tzid_list, sites_total

    def _load_cache_index(self, assets: LegalityAssets) -> dict[str, list[list[int]]]:
        payload = json.loads(assets.tz_cache_index_path.read_text(encoding="utf-8"))
        cache: dict[str, list[list[int]]] = {}
        for entry in payload:
            if not isinstance(entry, list) or len(entry) != 2:
                raise err(
                    "E_S4_CACHE_FORMAT",
                    f"tz_index.json entry malformed: {entry!r}",
                )
            tzid, transitions = entry
            cache[str(tzid)] = [
                [int(point[0]), int(point[1])] for point in transitions
            ]
        return cache

    @staticmethod
    def _count_windows(entries: list[list[int]]) -> tuple[int, int]:
        if len(entries) < 2:
            return 0, 0
        gap_total = 0
        fold_total = 0
        for idx in range(len(entries) - 1):
            current_offset = entries[idx][1]
            next_offset = entries[idx + 1][1]
            delta = next_offset - current_offset
            if delta > 0:
                gap_total += delta
            elif delta < 0:
                fold_total += abs(delta)
        return gap_total, fold_total

    def _write_output_report(
        self,
        *,
        context: LegalityContext,
        output_path: Path,
        stats: LegalityStats,
        status: str,
    ) -> int:
        payload = {
            "segment": "2A",
            "state": "S4",
            "manifest_fingerprint": context.manifest_fingerprint,
            "seed": context.seed,
            "generated_utc": context.verified_at_utc,
            "status": status,
            "counts": {
                "sites_total": stats.sites_total,
                "tzids_total": stats.tzids_total,
                "gap_windows_total": stats.gap_windows_total,
                "fold_windows_total": stats.fold_windows_total,
            },
        }
        if stats.missing_tzids:
            payload["missing_tzids"] = stats.missing_tzids
            payload["notes"] = "Coverage gap detected between site_timezones and tz_timetable_cache"
        else:
            payload["missing_tzids"] = []
        target_dir = output_path.parent
        target_dir.mkdir(parents=True, exist_ok=True)
        temp_dir = target_dir / f".tmp.s4_report.{uuid.uuid4().hex}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        try:
            temp_file = temp_dir / output_path.name
            temp_file.write_text(
                json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
            )
            temp_file.replace(output_path)
        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
        return output_path.stat().st_size

    def _resolve_output_path(
        self,
        *,
        data_root: Path,
        manifest_fingerprint: str,
        seed: int,
        dictionary: Mapping[str, object],
    ) -> Path:
        rel = render_dataset_path(
            "s4_legality_report",
            template_args={"seed": seed, "manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        full_path = (data_root / rel).resolve()
        full_path.parent.mkdir(parents=True, exist_ok=True)
        return full_path

    def _resolve_run_report_path(
        self,
        *,
        data_root: Path,
        manifest_fingerprint: str,
        seed: int,
    ) -> Path:
        return (
            data_root
            / self.RUN_REPORT_ROOT
            / f"seed={seed}"
            / f"fingerprint={manifest_fingerprint}"
            / "run_report.json"
        ).resolve()

    def _write_run_report(
        self,
        *,
        path: Path,
        context: LegalityContext,
        stats: LegalityStats,
        warnings: list[str],
        errors: list[dict[str, object]],
        status: str,
        started_at: datetime,
        finished_at: datetime,
        output_path: Path,
        output_bytes: int,
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        durations = max(
            0, int((finished_at - started_at).total_seconds() * 1000)
        )
        payload = {
            "segment": "2A",
            "state": "S4",
            "status": status,
            "seed": context.seed,
            "manifest_fingerprint": context.manifest_fingerprint,
            "started_utc": started_at.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "finished_utc": finished_at.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "durations": {"wall_ms": durations},
            "s0": {
                "receipt_path": str(context.receipt_path),
                "verified_at_utc": context.verified_at_utc,
            },
            "inputs": {
                "site_timezones": str(context.assets.site_timezones_path),
                "tz_timetable_cache": str(context.assets.tz_cache_dir),
            },
            "adjustments": {
                "path": str(context.tz_adjustments.path)
                if context.tz_adjustments
                else None,
                "count": stats.adjustments_count,
                "tzids_sample": stats.adjustments_tzids[:5],
            },
            "counts": {
                "sites_total": stats.sites_total,
                "tzids_total": stats.tzids_total,
                "gap_windows_total": stats.gap_windows_total,
                "fold_windows_total": stats.fold_windows_total,
            },
            "missing_tzids": stats.missing_tzids,
            "output": {
                "path": str(output_path),
                "bytes": output_bytes,
                "generated_utc": context.verified_at_utc,
            },
            "warnings": warnings,
            "errors": errors,
            "determinism": context.determinism_receipt,
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
