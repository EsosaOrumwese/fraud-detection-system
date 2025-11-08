"""Timetable cache builder for Segment 2A state S3."""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import shlex
import shutil
import subprocess
import tarfile
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Optional, Sequence

import pyarrow.parquet as pq
from zoneinfo import _common as zoneinfo_common

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

INT64_MIN = -(2**63)
TZ_SOURCE_FILES: tuple[str, ...] = (
    "africa",
    "antarctica",
    "asia",
    "australasia",
    "europe",
    "northamerica",
    "southamerica",
    "etcetera",
    "backward",
    "backzone",
    "factory",
    "systemv",
)


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
    adjustments_path: Optional[Path] = None


@dataclass(frozen=True)
class OffsetAdjustmentRecord:
    """Details about an offset normalization applied during compilation."""

    tzid: str
    transition_unix_utc: int
    raw_seconds: int
    adjusted_minutes: int
    reasons: tuple[str, ...]


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
    adjustments_count: int = 0


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
        adjustments_dir = self._resolve_adjustments_dir(
            data_root=data_root,
            manifest_fingerprint=config.manifest_fingerprint,
            dictionary=dictionary,
        )
        adjustments_file = adjustments_dir / "tz_offset_adjustments.json"
        if output_dir.exists():
            if config.resume:
                if not adjustments_file.exists():
                    raise err(
                        "E_S3_ADJUSTMENTS_MISSING",
                        f"tz_offset_adjustments missing at '{adjustments_file}' while resume requested",
                    )
                logger.info(
                    "Segment2A S3 resume detected (manifest=%s); skipping run",
                    config.manifest_fingerprint,
                )
                return TimetableResult(
                    manifest_fingerprint=config.manifest_fingerprint,
                    output_path=output_dir,
                    run_report_path=run_report_path,
                    resumed=True,
                    adjustments_path=adjustments_file,
                )
            raise err(
                "E_S3_OUTPUT_EXISTS",
                f"tz_timetable_cache already exists at '{output_dir}' "
                "- use resume to skip or delete the partition first",
            )

        status = "fail"
        warnings: list[str] = []
        errors: list[dict[str, object]] = []
        output_files: list[dict[str, object]] = []
        adjustments_path: Optional[Path] = None
        start_time = datetime.now(timezone.utc)
        try:
            output_files, adjustments_path = self._execute(
                data_root,
                dictionary,
                context,
                output_dir,
                adjustments_dir,
                stats,
                warnings,
            )
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
                output_files=output_files,
                adjustments_path=adjustments_path,
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
            adjustments_path=adjustments_path,
        )

    def _execute(
        self,
        data_root: Path,
        dictionary: Mapping[str, object],
        context: TimetableContext,
        output_dir: Path,
        adjustments_dir: Path,
        stats: TimetableStats,
        warnings: list[str],
    ) -> tuple[list[dict[str, object]], Path]:
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
        if adjustments_dir.exists():
            raise err(
                "E_S3_ADJUSTMENTS_EXISTS",
                f"tz_offset_adjustments already exists at '{adjustments_dir}' "
                "- use resume to skip or delete the partition first",
            )
        (
            transition_map,
            transition_changes,
            offset_min,
            offset_max,
            adjustments,
        ) = self._build_transition_map(
            context.assets, context.manifest_fingerprint, warnings
        )
        if not transition_map:
            raise err("2A-S3-021 INDEX_EMPTY", "compiled timetable index was empty")

        missing = sorted(set(tz_world_ids).difference(transition_map.keys()))
        stats.coverage_missing = missing[:5]
        if missing:
            raise err(
                "2A-S3-053 TZID_COVERAGE_MISMATCH",
                f"{len(missing)} tzids present in tz_world were missing from the cache "
                f"(examples: {stats.coverage_missing})",
            )

        stats.tzid_count = len(transition_map)
        stats.cache_tzids = len(transition_map)
        stats.transitions_total = transition_changes
        stats.offset_minutes_min = offset_min
        stats.offset_minutes_max = offset_max
        stats.adjustments_count = len(adjustments)

        canonical_bytes = self._build_canonical_index(transition_map)
        stats.rle_cache_bytes = len(canonical_bytes)
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

        final_manifest_path = output_dir / "tz_timetable_cache.json"
        final_index_path = output_dir / "tz_index.json"
        adjustments_file, adjustments_bytes = self._write_adjustments_file(
            target_dir=adjustments_dir,
            manifest_fingerprint=context.manifest_fingerprint,
            created_utc=context.verified_at_utc,
            adjustments=adjustments,
        )
        output_files = [
            {
                "name": "tz_timetable_cache.json",
                "bytes": final_manifest_path.stat().st_size,
                "path": str(final_manifest_path),
            },
            {
                "name": "tz_index.json",
                "bytes": stats.rle_cache_bytes,
                "path": str(final_index_path),
            },
            {
                "name": "tz_offset_adjustments.json",
                "bytes": adjustments_bytes,
                "path": str(adjustments_file),
            },
        ]

        self._emit_event(
            "EMIT",
            {
                "output_path": str(output_dir),
                "files": [
                    "tz_timetable_cache.json",
                    "tz_index.json",
                    "tz_offset_adjustments.json",
                ],
            },
            manifest_fingerprint=context.manifest_fingerprint,
        )
        self._emit_event(
            "ADJUSTMENTS",
            {
                "count": stats.adjustments_count,
                "path": str(adjustments_file),
            },
            manifest_fingerprint=context.manifest_fingerprint,
        )
        return output_files, adjustments_file

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

    def _resolve_adjustments_dir(
        self,
        *,
        data_root: Path,
        manifest_fingerprint: str,
        dictionary: Mapping[str, object],
    ) -> Path:
        rel = render_dataset_path(
            "tz_offset_adjustments",
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

    def _build_transition_map(
        self,
        assets: TimetableAssets,
        manifest_fingerprint: str,
        warnings: list[str],
    ) -> tuple[
        dict[str, list[list[int]]], int, int, int, list[OffsetAdjustmentRecord]
    ]:
        archive_path = self._resolve_archive_path(assets.tzdb_dir)
        transitions: dict[str, list[list[int]]] = {}
        transition_changes = 0
        offset_min: Optional[int] = None
        offset_max: Optional[int] = None
        adjustments: list[OffsetAdjustmentRecord] = []
        with tempfile.TemporaryDirectory(prefix="tzs3_compile_") as scratch_raw:
            scratch = Path(scratch_raw)
            source_dir = scratch / "src"
            zoneinfo_dir = scratch / "zoneinfo"
            source_dir.mkdir(parents=True, exist_ok=True)
            zoneinfo_dir.mkdir(parents=True, exist_ok=True)
            self._extract_archive(archive_path=archive_path, target_dir=source_dir)
            sources = [name for name in TZ_SOURCE_FILES if (source_dir / name).exists()]
            if not sources:
                raise err(
                    "2A-S3-041 TZDB_SOURCES_MISSING",
                    f"tzdb archive '{archive_path.name}' did not contain any recognised tz source files",
                )
            self._invoke_zic(
                source_dir=source_dir,
                output_dir=zoneinfo_dir,
                sources=sources,
                manifest_fingerprint=manifest_fingerprint,
            )
            zone_paths = self._collect_zoneinfo_paths(zoneinfo_dir)
            if not zone_paths:
                raise err(
                    "2A-S3-042 ZIC_EMPTY_OUTPUT",
                    "zic produced no compiled tzfiles; check the archive contents",
                )
            for tzid, file_path in zone_paths.items():
                entries = self._parse_zoneinfo_file(tzid, file_path, warnings, adjustments)
                transitions[tzid] = entries
                offsets = [entry[1] for entry in entries]
                tz_min = min(offsets) if offsets else None
                tz_max = max(offsets) if offsets else None
                if tz_min is not None:
                    offset_min = tz_min if offset_min is None else min(offset_min, tz_min)
                if tz_max is not None:
                    offset_max = tz_max if offset_max is None else max(offset_max, tz_max)
                transition_changes += max(0, len(entries) - 1)

        if offset_min is None:
            offset_min = 0
        if offset_max is None:
            offset_max = 0
        self._emit_event(
            "COMPILE",
            {
                "tzid_count": len(transitions),
                "transition_changes": transition_changes,
                "offset_minutes_min": offset_min,
                "offset_minutes_max": offset_max,
            },
            manifest_fingerprint=manifest_fingerprint,
        )
        return transitions, transition_changes, offset_min, offset_max, adjustments

    def _collect_zoneinfo_paths(self, zoneinfo_dir: Path) -> dict[str, Path]:
        excluded = {"posixrules", "localtime", "leapseconds"}
        zone_paths: dict[str, Path] = {}
        for candidate in zoneinfo_dir.rglob("*"):
            if not candidate.is_file():
                continue
            rel = candidate.relative_to(zoneinfo_dir).as_posix()
            if rel in excluded:
                continue
            if rel.startswith("posix/") or rel.startswith("right/"):
                continue
            zone_paths[rel] = candidate
        return zone_paths

    def _parse_zoneinfo_file(
        self,
        tzid: str,
        path: Path,
        warnings: list[str],
        adjustments: list[OffsetAdjustmentRecord],
    ) -> list[list[int]]:
        with path.open("rb") as handle:
            trans_idx, trans_list, utcoff, isdst, _, _ = zoneinfo_common.load_data(handle)
        if not utcoff:
            raise err(
                "2A-S3-061 TZ_NO_TYPES",
                f"compiled tzfile '{tzid}' did not contain any local time definitions",
            )
        initial_idx = self._select_initial_type(isdst)
        base_offset = self._seconds_to_minutes(
            tzid, utcoff[initial_idx], warnings, adjustments, INT64_MIN
        )
        entries: list[list[int]] = [[INT64_MIN, base_offset]]
        last_offset = base_offset
        for stamp, idx in zip(trans_list, trans_idx):
            offset = self._seconds_to_minutes(
                tzid, utcoff[idx], warnings, adjustments, int(stamp)
            )
            if offset == last_offset:
                continue
            entries.append([int(stamp), offset])
            last_offset = offset
        return entries

    @staticmethod
    def _select_initial_type(isdst: Sequence[int]) -> int:
        if not isdst:
            return 0
        for idx, flag in enumerate(isdst):
            if not flag:
                return idx
        return 0

    @staticmethod
    def _seconds_to_minutes(
        tzid: str,
        seconds: int,
        warnings: list[str],
        adjustments: list[OffsetAdjustmentRecord],
        transition_ts: int,
    ) -> int:
        reasons: list[str] = []
        if seconds % 60 != 0:
            minutes_float = seconds / 60
            rounded = int(math.copysign(1, minutes_float) * math.floor(abs(minutes_float) + 0.5))
            warnings.append(
                f"{tzid} offset {seconds}s rounded to {rounded} minute(s) for cache compatibility"
            )
            minutes = rounded
            reasons.append("round")
        else:
            minutes = int(seconds // 60)
        if minutes < -900 or minutes > 900:
            warnings.append(
                f"{tzid} offset {minutes} minute(s) clipped to [-900, 900] boundary"
            )
            minutes = max(-900, min(900, minutes))
            reasons.append("clip")
        if reasons:
            adjustments.append(
                OffsetAdjustmentRecord(
                    tzid=tzid,
                    transition_unix_utc=transition_ts,
                    raw_seconds=seconds,
                    adjusted_minutes=minutes,
                    reasons=tuple(reasons),
                )
            )
        return minutes

    def _invoke_zic(
        self,
        *,
        source_dir: Path,
        output_dir: Path,
        sources: Sequence[str],
        manifest_fingerprint: str,
    ) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        leapfile = source_dir / "leapseconds"
        cmd = ["zic", "-d", str(output_dir)]
        if leapfile.exists():
            cmd.extend(["-L", "leapseconds"])
        cmd.extend(sources)
        try:
            subprocess.run(cmd, cwd=source_dir, check=True)
            return
        except FileNotFoundError:
            # Fall back to bash-based execution (e.g., Windows with WSL)
            pass
        except subprocess.CalledProcessError as exc:
            raise err(
                "2A-S3-058 ZIC_FAILED",
                f"zic failed with exit code {exc.returncode}",
            ) from exc

        if os.name != "nt":
            raise err(
                "2A-S3-057 ZIC_MISSING",
                "zic binary not found on PATH; install tzcode tooling",
            )

        if not shutil.which("bash"):
            raise err(
                "2A-S3-057 ZIC_MISSING",
                "bash executable not found; unable to invoke zic via WSL",
            )

        wsl_source = self._to_wsl_path(source_dir)
        wsl_output = self._to_wsl_path(output_dir)
        leap_clause = "-L leapseconds " if leapfile.exists() else ""
        source_args = " ".join(shlex.quote(name) for name in sources)
        script = (
            f"cd {shlex.quote(wsl_source)} && "
            f"zic -d {shlex.quote(wsl_output)} {leap_clause}{source_args}"
        )
        proc = subprocess.run(
            ["bash", "-lc", script],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            details = proc.stderr.strip() or proc.stdout.strip() or "no stderr output"
            raise err("2A-S3-058 ZIC_FAILED", f"zic via bash failed: {details}")

        self._emit_event(
            "ZIC_FALLBACK",
            {
                "method": "bash",
                "source_dir": str(source_dir),
                "output_dir": str(output_dir),
            },
            manifest_fingerprint=manifest_fingerprint,
        )

    def _to_wsl_path(self, path: Path) -> str:
        if not shutil.which("wsl"):
            raise err(
                "2A-S3-057 ZIC_MISSING",
                "wsl executable not found; cannot translate Windows paths for zic",
            )
        escaped = str(path).replace("\\", "\\\\")
        proc = subprocess.run(
            ["wsl", "wslpath", "-a", escaped],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise err(
                "2A-S3-057 ZIC_MISSING",
                f"failed to map path '{path}' into WSL: {proc.stderr.strip()}",
            )
        return proc.stdout.strip()

    def _resolve_archive_path(self, tzdb_dir: Path) -> Path:
        archive_candidates = sorted(tzdb_dir.glob("*.tar.gz"))
        if not archive_candidates:
            raise err(
                "E_S3_TZDB_ARCHIVE_MISSING",
                f"no tzdata archive found under '{tzdb_dir}'",
            )
        return archive_candidates[0]

    def _extract_archive(self, *, archive_path: Path, target_dir: Path) -> None:
        target_dir.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive_path, "r:gz") as handle:
            self._safe_extract(handle, target_dir)

    @staticmethod
    def _safe_extract(tar_handle: tarfile.TarFile, target_dir: Path) -> None:
        target_dir = target_dir.resolve()
        for member in tar_handle.getmembers():
            member_path = (target_dir / member.name).resolve()
            if not str(member_path).startswith(str(target_dir)):
                raise err(
                    "2A-S3-054 TZDB_ARCHIVE_UNSAFE",
                    f"archive member '{member.name}' escapes extraction root '{target_dir}'",
                )
        tar_handle.extractall(target_dir)

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

    def _build_canonical_index(
        self, transitions: Mapping[str, Sequence[Sequence[int]]]
    ) -> bytes:
        entries: list[list[object]] = []
        for tzid in sorted(transitions.keys()):
            entries.append([tzid, transitions[tzid]])
        return json.dumps(entries, ensure_ascii=True, separators=(",", ":")).encode("utf-8")

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
        output_files: list[dict[str, object]],
        adjustments_path: Optional[Path],
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
            "adjustments": {
                "count": stats.adjustments_count,
                "path": str(adjustments_path) if adjustments_path else None,
            },
            "output": {
                "path": str(output_path),
                "created_utc": context.verified_at_utc,
                "files": output_files,
            },
            "warnings": warnings,
            "errors": errors,
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def _write_adjustments_file(
        self,
        *,
        target_dir: Path,
        manifest_fingerprint: str,
        created_utc: str,
        adjustments: Sequence[OffsetAdjustmentRecord],
    ) -> tuple[Path, int]:
        if target_dir.exists():
            raise err(
                "E_S3_ADJUSTMENTS_EXISTS",
                f"tz_offset_adjustments already exists at '{target_dir}'",
            )
        temp_dir = target_dir.parent / f".tmp.tz_adjustments.{uuid.uuid4().hex}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        try:
            file_path = temp_dir / "tz_offset_adjustments.json"
            payload = {
                "manifest_fingerprint": manifest_fingerprint,
                "created_utc": created_utc,
                "count": len(adjustments),
                "adjustments": [
                    {
                        "tzid": record.tzid,
                        "transition_unix_utc": record.transition_unix_utc,
                        "raw_seconds": record.raw_seconds,
                        "adjusted_minutes": record.adjusted_minutes,
                        "reasons": list(record.reasons),
                    }
                    for record in adjustments
                ],
            }
            file_path.write_text(
                json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
            )
            temp_dir.replace(target_dir)
        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
        final_file = target_dir / "tz_offset_adjustments.json"
        return final_file, final_file.stat().st_size
