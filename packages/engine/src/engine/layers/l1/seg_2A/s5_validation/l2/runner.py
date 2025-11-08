"""Validation bundle builder for Segment 2A state S5."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Optional

from jsonschema import Draft202012Validator, ValidationError

from engine.layers.l1.seg_2A.s0_gate.exceptions import S0GateError, err
from engine.layers.l1.seg_2A.shared.dictionary import (
    load_dictionary,
    render_dataset_path,
)
from engine.layers.l1.seg_2A.shared.receipt import GateReceiptSummary, load_gate_receipt
from engine.layers.l1.seg_2A.shared.schema import load_schema
from engine.layers.l1.seg_2A.shared.tz_assets import load_tz_adjustments

from ..l1.context import (
    TzCacheManifestSummary,
    ValidationAssets,
    ValidationContext,
)

logger = logging.getLogger(__name__)


INDEX_FILENAME = "index.json"
FLAG_FILENAME = "_passed.flag"
_TZ_CACHE_VALIDATOR = Draft202012Validator(load_schema("#/cache/tz_timetable_cache"))
_S4_REPORT_VALIDATOR = Draft202012Validator(load_schema("#/validation/s4_legality_report"))


@dataclass(frozen=True)
class ValidationInputs:
    """User supplied configuration for running 2A.S5."""

    data_root: Path
    manifest_fingerprint: str
    resume: bool = False
    dictionary: Optional[Mapping[str, object]] = None
    dictionary_path: Optional[Path] = None


@dataclass(frozen=True)
class ValidationResult:
    """Outcome of the validation bundle runner."""

    manifest_fingerprint: str
    bundle_path: Path
    flag_path: Path
    run_report_path: Path
    resumed: bool


@dataclass
class ValidationStats:
    seeds: list[int] = field(default_factory=list)
    s4_missing: list[int] = field(default_factory=list)
    s4_failing: list[int] = field(default_factory=list)
    s4_covered: int = 0
    files_indexed: int = 0
    bytes_indexed: int = 0
    digest_hex: str = ""
    flag_value: str = ""
    flag_format_exact: bool = False
    digest_matches_flag: bool = False
    index_sorted_ascii_lex: bool = False
    index_path_root_scoped: bool = False
    includes_flag_in_index: bool = False
    adjustments_count: int = 0


@dataclass(frozen=True)
class IndexedFile:
    """Metadata for a staged file included in the bundle index."""

    path: str
    sha256_hex: str
    size_bytes: int

    def as_index_entry(self) -> dict[str, str]:
        return {"path": self.path, "sha256_hex": self.sha256_hex}


class ValidationRunner:
    """Runs Segment 2A State 5 (validation bundle + pass flag)."""

    RUN_REPORT_ROOT = Path("reports") / "l1" / "s5_validation"

    def run(self, config: ValidationInputs) -> ValidationResult:
        dictionary = config.dictionary or load_dictionary(config.dictionary_path)
        data_root = config.data_root.expanduser().resolve()
        logger.info(
            "Segment2A S5 starting (manifest=%s)",
            config.manifest_fingerprint,
        )
        run_report_path = self._resolve_run_report_path(
            data_root=data_root,
            manifest_fingerprint=config.manifest_fingerprint,
        )
        receipt = load_gate_receipt(
            base_path=data_root,
            manifest_fingerprint=config.manifest_fingerprint,
            dictionary=dictionary,
        )
        self._log_event(
            event="GATE",
            manifest_fingerprint=config.manifest_fingerprint,
            payload={
                "receipt_path": str(receipt.path),
                "verified_at_utc": receipt.verified_at_utc,
            },
        )
        context = self._prepare_context(
            data_root=data_root,
            dictionary=dictionary,
            manifest_fingerprint=config.manifest_fingerprint,
            receipt=receipt,
        )
        bundle_path = self._resolve_bundle_path(
            data_root=data_root,
            manifest_fingerprint=config.manifest_fingerprint,
            dictionary=dictionary,
        )
        flag_path = bundle_path / FLAG_FILENAME
        if bundle_path.exists():
            if config.resume:
                logger.info(
                    "Segment2A S5 resume detected (manifest=%s); skipping run",
                    config.manifest_fingerprint,
                )
                return ValidationResult(
                    manifest_fingerprint=config.manifest_fingerprint,
                    bundle_path=bundle_path,
                    flag_path=flag_path,
                    run_report_path=run_report_path,
                    resumed=True,
                )
            raise err(
                "E_S5_BUNDLE_EXISTS",
                f"validation bundle already exists at '{bundle_path}' "
                "- use resume to skip or delete the partition first",
            )

        stats = ValidationStats()
        warnings: list[str] = []
        errors: list[dict[str, object]] = []
        status = "fail"
        start_time = datetime.now(timezone.utc)

        try:
            self._execute(context, bundle_path, stats, warnings)
            status = "pass"
        except S0GateError as exc:
            errors.append(
                {"code": exc.code, "message": exc.detail, "context": {"stage": "execute"}}
            )
            logger.error("Segment2A S5 failed (%s)", exc.code)
            raise
        except Exception as exc:  # pragma: no cover - defensive
            errors.append(
                {
                    "code": "E_S5_UNEXPECTED",
                    "message": str(exc),
                    "context": {"stage": "execute"},
                }
            )
            logger.exception("Segment2A S5 encountered an unexpected error")
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
                bundle_path=bundle_path,
                flag_path=flag_path,
            )
            self._log_event(
                event="VALIDATION",
                manifest_fingerprint=context.manifest_fingerprint,
                payload={
                    "status": status,
                    "files_indexed": stats.files_indexed,
                    "errors": [entry["code"] for entry in errors],
                },
                severity="ERROR" if status != "pass" else "INFO",
            )

        logger.info(
            "Segment2A S5 completed (bundle=%s, flag=%s, files=%s)",
            bundle_path,
            flag_path,
            stats.files_indexed,
        )

        return ValidationResult(
            manifest_fingerprint=config.manifest_fingerprint,
            bundle_path=bundle_path,
            flag_path=flag_path,
            run_report_path=run_report_path,
            resumed=False,
        )

    def _execute(
        self,
        context: ValidationContext,
        bundle_path: Path,
        stats: ValidationStats,
        warnings: list[str],
    ) -> None:
        if context.tz_adjustments:
            stats.adjustments_count = context.tz_adjustments.count
        seeds = self._discover_seeds(
            context.assets.site_timezones_root, context.manifest_fingerprint
        )
        stats.seeds = seeds
        self._log_event(
            event="DISCOVERY",
            manifest_fingerprint=context.manifest_fingerprint,
            payload={
                "seeds_total": len(seeds),
                "seeds": seeds,
            },
        )

        bundle_path.parent.mkdir(parents=True, exist_ok=True)
        staging_dir = bundle_path.parent / f".tmp.validation_bundle.{uuid.uuid4().hex}"
        staging_dir.mkdir(parents=True, exist_ok=True)
        try:
            evidence_entries, missing_seeds, failing_seeds = self._collect_evidence(
                context, seeds, staging_dir
            )
            stats.s4_missing = missing_seeds
            stats.s4_failing = failing_seeds
            stats.s4_covered = len(seeds) - len(missing_seeds) - len(failing_seeds)
            self._log_event(
                event="EVIDENCE",
                manifest_fingerprint=context.manifest_fingerprint,
                payload={
                    "tz_cache_manifest": str(context.tz_cache_manifest.path),
                    "tzdb_release_tag": context.tz_cache_manifest.tzdb_release_tag,
                    "tz_index_digest": context.tz_cache_manifest.tz_index_digest,
                    "rle_cache_bytes": context.tz_cache_manifest.rle_cache_bytes,
                    "tz_offset_adjustments": str(context.tz_adjustments.path)
                    if context.tz_adjustments
                    else None,
                    "tz_offset_adjustments_count": stats.adjustments_count,
                    "seeds_total": len(seeds),
                    "s4_covered": stats.s4_covered,
                    "s4_missing": missing_seeds,
                    "s4_failing": failing_seeds,
                },
                severity="ERROR" if missing_seeds or failing_seeds else "INFO",
            )
            if missing_seeds:
                raise err(
                    "E_S5_S4_MISSING",
                    f"s4_legality_report missing for seeds: {', '.join(str(seed) for seed in missing_seeds)}",
                )
            if failing_seeds:
                raise err(
                    "E_S5_S4_NOT_PASS",
                    f"s4_legality_report not PASS for seeds: {', '.join(str(seed) for seed in failing_seeds)}",
                )
            if not evidence_entries:
                raise err("E_S5_NO_EVIDENCE", "no evidence files were staged for the bundle")
            evidence_entries.sort(key=lambda entry: entry.path)
            stats.index_sorted_ascii_lex = True
            stats.index_path_root_scoped = True
            stats.includes_flag_in_index = False
            index_path = staging_dir / INDEX_FILENAME
            index_payload = {"files": [entry.as_index_entry() for entry in evidence_entries]}
            index_path.write_text(json.dumps(index_payload, indent=2, sort_keys=True), encoding="utf-8")
            stats.files_indexed = len(evidence_entries)
            stats.bytes_indexed = sum(entry.size_bytes for entry in evidence_entries)
            self._log_event(
                event="INDEX",
                manifest_fingerprint=context.manifest_fingerprint,
                payload={
                    "files_indexed": stats.files_indexed,
                    "bytes_indexed": stats.bytes_indexed,
                    "ascii_sorted": stats.index_sorted_ascii_lex,
                    "root_scoped": stats.index_path_root_scoped,
                },
            )
            digest_hex = self._compute_bundle_digest(staging_dir, evidence_entries)
            stats.digest_hex = digest_hex
            stats.flag_value = digest_hex
            flag_path = staging_dir / FLAG_FILENAME
            flag_path.write_text(f"sha256_hex = {digest_hex}\n", encoding="utf-8")
            stats.flag_format_exact = True
            stats.digest_matches_flag = True
            self._log_event(
                event="DIGEST",
                manifest_fingerprint=context.manifest_fingerprint,
                payload={
                    "digest": digest_hex,
                    "flag": digest_hex,
                    "matches": True,
                },
            )
            staging_dir.replace(bundle_path)
        finally:
            if staging_dir.exists():
                shutil.rmtree(staging_dir, ignore_errors=True)

    def _prepare_context(
        self,
        *,
        data_root: Path,
        dictionary: Mapping[str, object],
        manifest_fingerprint: str,
        receipt: GateReceiptSummary,
    ) -> ValidationContext:
        site_template = render_dataset_path(
            "site_timezones",
            template_args={"seed": 0, "manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        site_root = (data_root / site_template).resolve()
        seed_root = site_root.parent.parent  # .../site_timezones/
        tz_cache_dir = (
            data_root
            / render_dataset_path(
                "tz_timetable_cache",
                template_args={"manifest_fingerprint": manifest_fingerprint},
                dictionary=dictionary,
            )
        ).resolve()
        manifest_path = tz_cache_dir / "tz_timetable_cache.json"
        if not manifest_path.exists():
            raise err(
                "E_S5_TZ_MANIFEST_MISSING",
                f"tz_timetable_cache manifest missing at '{manifest_path}'",
            )
        manifest_payload = self._load_json(manifest_path, code="E_S5_TZ_MANIFEST_INVALID")
        manifest_summary = self._validate_tz_cache_manifest(
            payload=manifest_payload,
            manifest_fingerprint=manifest_fingerprint,
            manifest_path=manifest_path,
        )
        assets = ValidationAssets(
            site_timezones_root=seed_root,
            tz_cache_dir=tz_cache_dir,
        )
        adjustments_summary = load_tz_adjustments(
            base_path=data_root,
            manifest_fingerprint=manifest_fingerprint,
            dictionary=dictionary,
        )
        return ValidationContext(
            data_root=data_root,
            manifest_fingerprint=manifest_fingerprint,
            receipt_path=receipt.path,
            verified_at_utc=receipt.verified_at_utc,
            dictionary=dictionary,
            assets=assets,
            tz_cache_manifest=manifest_summary,
            tz_adjustments=adjustments_summary,
        )

    def _discover_seeds(self, site_root: Path, manifest_fingerprint: str) -> list[int]:
        seeds: list[int] = []
        if not site_root.exists():
            return seeds
        for seed_dir in site_root.glob("seed=*"):
            seed_value = self._parse_seed_dir(seed_dir.name)
            if seed_value is None:
                continue
            fingerprint_dir = seed_dir / f"fingerprint={manifest_fingerprint}"
            if fingerprint_dir.exists():
                seeds.append(seed_value)
        seeds.sort()
        return seeds

    @staticmethod
    def _parse_seed_dir(name: str) -> Optional[int]:
        match = re.match(r"seed=(\d+)$", name)
        if not match:
            return None
        try:
            return int(match.group(1))
        except ValueError:
            return None

    def _collect_evidence(
        self,
        context: ValidationContext,
        seeds: list[int],
        staging_dir: Path,
    ) -> tuple[list[IndexedFile], list[int], list[int]]:
        entries: list[IndexedFile] = []
        missing: list[int] = []
        failing: list[int] = []
        entries.append(
            self._stage_file(
                source=context.tz_cache_manifest.path,
                staging_dir=staging_dir,
                relative_path="evidence/s3/tz_timetable_cache.manifest.json",
            )
        )
        if context.tz_adjustments:
            entries.append(
                self._stage_file(
                    source=context.tz_adjustments.path,
                    staging_dir=staging_dir,
                    relative_path="evidence/s3/tz_offset_adjustments.json",
                )
            )
        for seed in seeds:
            s4_path = (
                context.data_root
                / render_dataset_path(
                    "s4_legality_report",
                    template_args={
                        "seed": seed,
                        "manifest_fingerprint": context.manifest_fingerprint,
                    },
                    dictionary=context.dictionary,
                )
            ).resolve()
            if not s4_path.exists():
                missing.append(seed)
                continue
            payload = self._load_json(s4_path, code="E_S5_S4_INVALID")
            self._validate_s4_report(
                payload=payload,
                manifest_fingerprint=context.manifest_fingerprint,
                seed=seed,
            )
            if payload.get("status") != "PASS":
                failing.append(seed)
                continue
            entries.append(
                self._stage_file(
                    source=s4_path,
                    staging_dir=staging_dir,
                    relative_path=f"evidence/s4/seed={seed}/s4_legality_report.json",
                )
            )
        return entries, missing, failing

    def _load_json(self, path: Path, *, code: str) -> dict[str, object]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise err(code, f"'{path}' is not valid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise err(code, f"'{path}' must decode to a JSON object")
        return payload

    def _validate_s4_report(
        self,
        *,
        payload: Mapping[str, object],
        manifest_fingerprint: str,
        seed: int,
    ) -> None:
        try:
            _S4_REPORT_VALIDATOR.validate(payload)
        except ValidationError as exc:  # pragma: no cover - schema edge cases
            raise err(
                "E_S5_S4_SCHEMA",
                f"s4_legality_report violates schema: {exc.message}",
            ) from exc
        manifest_value = payload.get("manifest_fingerprint")
        if manifest_value != manifest_fingerprint:
            raise err(
                "E_S5_S4_MISMATCH",
                f"s4_legality_report manifest '{manifest_value}' expected '{manifest_fingerprint}'",
            )
        seed_value = payload.get("seed")
        if seed_value != seed:
            raise err(
                "E_S5_S4_SEED_MISMATCH",
                f"s4_legality_report seed '{seed_value}' expected '{seed}'",
            )

    def _validate_tz_cache_manifest(
        self,
        *,
        payload: Mapping[str, object],
        manifest_fingerprint: str,
        manifest_path: Path,
    ) -> TzCacheManifestSummary:
        try:
            _TZ_CACHE_VALIDATOR.validate(payload)
        except ValidationError as exc:  # pragma: no cover - schema edge cases
            raise err(
                "E_S5_TZ_MANIFEST_SCHEMA",
                f"tz_timetable_cache manifest violates schema: {exc.message}",
            ) from exc
        manifest_value = payload.get("manifest_fingerprint")
        if manifest_value != manifest_fingerprint:
            raise err(
                "E_S5_TZ_MANIFEST_FINGERPRINT",
                f"tz_timetable_cache manifest fingerprint '{manifest_value}' expected '{manifest_fingerprint}'",
            )
        try:
            rle_cache_bytes = int(payload["rle_cache_bytes"])
        except (KeyError, TypeError, ValueError) as exc:
            raise err(
                "E_S5_TZ_MANIFEST_RLE",
                "tz_timetable_cache manifest missing numeric rle_cache_bytes",
            ) from exc
        if rle_cache_bytes <= 0:
            raise err(
                "E_S5_TZ_MANIFEST_EMPTY",
                "tz_timetable_cache manifest rle_cache_bytes must be greater than zero",
            )
        return TzCacheManifestSummary(
            path=manifest_path,
            tzdb_release_tag=str(payload["tzdb_release_tag"]),
            tzdb_archive_sha256=str(payload["tzdb_archive_sha256"]),
            tz_index_digest=str(payload["tz_index_digest"]),
            rle_cache_bytes=rle_cache_bytes,
            created_utc=str(payload["created_utc"]),
        )

    def _validate_relative_path(self, relative_path: str) -> None:
        normalized = relative_path.replace("\\", "/")
        if normalized.startswith("/") or normalized.startswith("."):
            raise err(
                "E_S5_INDEX_PATH_INVALID",
                f"bundle entry path '{relative_path}' must be relative to the bundle root",
            )
        for segment in normalized.split("/"):
            if segment in ("", ".", ".."):
                raise err(
                    "E_S5_INDEX_PATH_INVALID",
                    f"bundle entry path '{relative_path}' contains forbidden segment '{segment}'",
                )

    def _stage_file(self, source: Path, staging_dir: Path, relative_path: str) -> IndexedFile:
        self._validate_relative_path(relative_path)
        dest_path = staging_dir / relative_path
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest_path)
        digest = self._hash_file(dest_path)
        size_bytes = dest_path.stat().st_size
        return IndexedFile(path=relative_path, sha256_hex=digest, size_bytes=size_bytes)

    @staticmethod
    def _hash_file(path: Path) -> str:
        hasher = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _compute_bundle_digest(
        self,
        staging_dir: Path,
        entries: list[IndexedFile],
    ) -> str:
        hasher = hashlib.sha256()
        for entry in entries:
            target = staging_dir / entry.path
            with target.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    hasher.update(chunk)
        return hasher.hexdigest()

    def _resolve_bundle_path(
        self,
        *,
        data_root: Path,
        manifest_fingerprint: str,
        dictionary: Mapping[str, object],
    ) -> Path:
        rel = render_dataset_path(
            "validation_bundle_2A",
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

    def _write_run_report(
        self,
        *,
        path: Path,
        context: ValidationContext,
        stats: ValidationStats,
        warnings: list[str],
        errors: list[dict[str, object]],
        status: str,
        started_at: datetime,
        finished_at: datetime,
        bundle_path: Path,
        flag_path: Path,
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        durations = max(
            0, int((finished_at - started_at).total_seconds() * 1000)
        )
        payload = {
            "segment": "2A",
            "state": "S5",
            "status": status,
            "manifest_fingerprint": context.manifest_fingerprint,
            "started_utc": started_at.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "finished_utc": finished_at.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "durations": {"wall_ms": durations},
            "s0": {
                "receipt_path": str(context.receipt_path),
                "verified_at_utc": context.verified_at_utc,
            },
            "inputs": {
                "cache": {
                    "path": str(context.assets.tz_cache_dir),
                    "manifest_path": str(context.tz_cache_manifest.path),
                    "tzdb_release_tag": context.tz_cache_manifest.tzdb_release_tag,
                    "tz_index_digest": context.tz_cache_manifest.tz_index_digest,
                    "rle_cache_bytes": context.tz_cache_manifest.rle_cache_bytes,
                },
                "adjustments": {
                    "path": str(context.tz_adjustments.path)
                    if context.tz_adjustments
                    else None,
                    "count": stats.adjustments_count,
                },
            },
            "seeds": {
                "discovered": len(stats.seeds),
                "list": stats.seeds,
            },
            "s4": {
                "covered": stats.s4_covered,
                "missing": len(stats.s4_missing),
                "failing": len(stats.s4_failing),
                "sample_missing": stats.s4_missing[:5],
            },
            "bundle": {
                "path": str(bundle_path),
                "files_indexed": stats.files_indexed,
                "bytes_indexed": stats.bytes_indexed,
                "index_sorted_ascii_lex": stats.index_sorted_ascii_lex,
                "index_path_root_scoped": stats.index_path_root_scoped,
                "includes_flag_in_index": stats.includes_flag_in_index,
            },
            "digest": {
                "computed_sha256": stats.digest_hex or None,
                "matches_flag": stats.digest_matches_flag,
            },
            "flag": {
                "path": str(flag_path),
                "value": stats.flag_value or None,
                "format_exact": stats.flag_format_exact,
            },
            "warnings": warnings,
            "errors": errors,
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def _log_event(
        self,
        *,
        event: str,
        manifest_fingerprint: str,
        payload: Mapping[str, object],
        severity: str = "INFO",
    ) -> None:
        record: dict[str, object] = {
            "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "segment": "2A",
            "state": "S5",
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
