"""Overrides and final tz assignment for Segment 2A state S2."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Mapping, Optional

import polars as pl
import pyarrow.dataset as pa_ds
import pyarrow.parquet as pq
import yaml

from engine.layers.l1.seg_2A.s0_gate.exceptions import S0GateError, err
from engine.layers.l1.seg_2A.shared.dictionary import (
    load_dictionary,
    render_dataset_path,
    resolve_dataset_path,
)
from engine.layers.l1.seg_2A.shared.receipt import (
    GateReceiptSummary,
    SealedInputRecord,
    load_determinism_receipt,
    load_gate_receipt,
)
from engine.layers.l1.seg_2A.shared.sealed_assets import (
    build_sealed_asset_map,
    ensure_catalog_path,
    require_sealed_asset,
    resolve_sealed_path,
    verify_sealed_digest,
)

from ..l1.context import OverridesAssets, OverridesContext

logger = logging.getLogger(__name__)

_S1_COLUMNS = [
    "merchant_id",
    "legal_country_iso",
    "site_order",
    "tzid_provisional",
    "nudge_lat_deg",
    "nudge_lon_deg",
]


@dataclass
class OverridePolicyMetadata:
    """Metadata and counters derived from the tz_overrides policy."""

    semver: str
    sha256_digest: str
    expired_skipped: int = 0
    dup_scope_target: int = 0


@dataclass(frozen=True)
class OverridesInputs:
    """User supplied configuration for running 2A.S2."""

    data_root: Path
    seed: int
    manifest_fingerprint: str
    upstream_manifest_fingerprint: str
    chunk_size: int = 250_000
    resume: bool = False
    dictionary: Optional[Mapping[str, object]] = None
    dictionary_path: Optional[Path] = None


@dataclass(frozen=True)
class OverridesResult:
    """Outcome of the overrides runner."""

    seed: int
    manifest_fingerprint: str
    output_path: Path
    run_report_path: Path
    overrides_applied: Mapping[str, int]
    resumed: bool


class OverridesRunner:
    """Runs Segment 2A State 2 (overrides and finalisation)."""

    def run(self, config: OverridesInputs) -> OverridesResult:
        dictionary = config.dictionary or load_dictionary(config.dictionary_path)
        data_root = config.data_root.expanduser().resolve()
        stats = ProcessingStats()
        start_wall = time.perf_counter()
        started_at = _utc_now()
        receipt: GateReceiptSummary | None = None
        context: OverridesContext | None = None
        output_dir: Path | None = None
        policy_meta: OverridePolicyMetadata | None = None
        run_report_path: Path | None = None
        mcc_digest: str | None = None
        warnings_accum: set[str] = set()
        mcc_overrides_present = False

        logger.info(
            "Segment2A S2 starting (seed=%s, manifest=%s)",
            config.seed,
            config.manifest_fingerprint,
        )
        try:
            receipt = load_gate_receipt(
                base_path=data_root,
                manifest_fingerprint=config.manifest_fingerprint,
                dictionary=dictionary,
            )
            sealed_assets = build_sealed_asset_map(
                base_path=data_root,
                manifest_fingerprint=config.manifest_fingerprint,
                dictionary=dictionary,
            )
            determinism_receipt = load_determinism_receipt(
                base_path=data_root,
                manifest_fingerprint=config.manifest_fingerprint,
            )
            self._emit_event(
                "GATE",
                {
                    "result": "verified",
                    "receipt_path": str(receipt.path),
                },
                config=config,
            )
            context = self._prepare_context(
                data_root=data_root,
                seed=config.seed,
                manifest_fingerprint=config.manifest_fingerprint,
                upstream_manifest_fingerprint=config.upstream_manifest_fingerprint,
                dictionary=dictionary,
                receipt=receipt,
                sealed_assets=sealed_assets,
                determinism_receipt=determinism_receipt,
            )
            output_dir = self._resolve_output_dir(
                data_root=data_root,
                seed=config.seed,
                manifest_fingerprint=config.manifest_fingerprint,
                dictionary=dictionary,
            )
            run_report_candidate = self._resolve_run_report_path(
                data_root=data_root,
                seed=config.seed,
                manifest_fingerprint=config.manifest_fingerprint,
            )
            if output_dir.exists():
                if config.resume:
                    logger.info(
                        "Segment2A S2 resume detected (seed=%s, manifest=%s); skipping run",
                        config.seed,
                        config.manifest_fingerprint,
                    )
                    return OverridesResult(
                        seed=config.seed,
                        manifest_fingerprint=config.manifest_fingerprint,
                        output_path=output_dir,
                        run_report_path=run_report_candidate,
                        overrides_applied={"site": 0, "mcc": 0, "country": 0},
                        resumed=True,
                    )
                raise err(
                    "E_S2_OUTPUT_EXISTS",
                    f"site_timezones already exists at '{output_dir}' "
                    "— use resume to skip or delete the partition first",
                )
            output_dir.mkdir(parents=True, exist_ok=True)

            self._emit_event(
                "INPUTS",
                {
                    "s1_tz_lookup": str(context.assets.s1_tz_lookup),
                    "tz_overrides": str(context.assets.tz_overrides),
                    "merchant_mcc_map": (
                        str(context.assets.merchant_mcc_map)
                        if context.assets.merchant_mcc_map
                        else None
                    ),
                },
                config=config,
            )

            tzid_whitelist = self._load_tzid_whitelist(context.assets.tz_world)
            override_index, policy_meta = self._load_override_policy(
                policy_path=context.assets.tz_overrides,
                cutoff_date=_to_date(receipt.verified_at_utc),
                tzid_whitelist=tzid_whitelist,
                has_mcc_map=context.assets.merchant_mcc_map is not None,
            )
            mcc_overrides_present = override_index.mcc_present
            stats.expired_skipped = policy_meta.expired_skipped
            stats.dup_scope_target = policy_meta.dup_scope_target

            self._emit_event(
                "OVERRIDES",
                {
                    "site_entries": len(override_index.site),
                    "mcc_entries": len(override_index.mcc),
                    "country_entries": len(override_index.country),
                    "expired_skipped": policy_meta.expired_skipped,
                    "dup_scope_target": policy_meta.dup_scope_target,
                },
                config=config,
            )

            mcc_mapping, mcc_digest = self._load_mcc_mapping(context.assets.merchant_mcc_map)
            if override_index.mcc_present and not mcc_mapping:
                warning_code = "2A-S2-022 MCC_MAPPING_MISSING"
                warnings_accum.add(warning_code)
                logger.warning(
                    "Segment2A S2 detected MCC overrides but no merchant→MCC mapping "
                    "was sealed; MCC scope overrides are inactive for this run.",
                )

            stats = self._process_lookup(
                context=context,
                output_dir=output_dir,
                override_index=override_index,
                mcc_mapping=mcc_mapping,
                tzid_whitelist=tzid_whitelist,
                chunk_size=max(1, config.chunk_size),
                stats=stats,
            )

            if not stats.writer_order_ok:
                warnings_accum.add("2A-S2-070 WRITER_ORDER_NONCOMPLIANT")

            warnings_out = sorted(warnings_accum.union(stats.warnings))
            errors_out: list[dict[str, str]] = []
            run_report_path = self._write_run_report(
                config=config,
                context=context,
                output_dir=output_dir,
                receipt=receipt,
                stats=stats,
                policy_meta=policy_meta,
                warnings=warnings_out,
                errors=errors_out,
                status="pass",
                start_wall=start_wall,
                started_at=started_at,
                mcc_digest=mcc_digest,
                mcc_overrides_present=mcc_overrides_present,
            )
            self._emit_validation_events(config=config, stats=stats)
            self._emit_event(
                "EMIT",
                {
                    "output_path": str(output_dir),
                    "rows_emitted": stats.rows_emitted,
                    "overrides_total": sum(stats.overrides_by_scope.values()),
                },
                config=config,
            )
            logger.info(
                "Segment2A S2 completed (rows=%s, overrides=%s, output=%s)",
                stats.total_rows,
                dict(stats.overrides_by_scope),
                output_dir,
            )
            return OverridesResult(
                seed=config.seed,
                manifest_fingerprint=config.manifest_fingerprint,
                output_path=output_dir,
                run_report_path=run_report_path,
                overrides_applied=dict(stats.overrides_by_scope),
                resumed=False,
            )
        except S0GateError as exc:
            errors_out = [{"code": exc.code, "message": exc.detail}]
            warnings_out = sorted(warnings_accum.union(stats.warnings))
            run_report_path = self._write_run_report(
                config=config,
                context=context,
                output_dir=output_dir,
                receipt=receipt,
                stats=stats,
                policy_meta=policy_meta,
                warnings=warnings_out,
                errors=errors_out,
                status="fail",
                start_wall=start_wall,
                started_at=started_at,
                mcc_digest=mcc_digest,
                mcc_overrides_present=mcc_overrides_present,
            )
            self._emit_event(
                "VALIDATION",
                {"id": "runtime", "result": "fail", "code": exc.code},
                config=config,
                severity="ERROR",
            )
            logger.error(
                "Segment2A S2 failed (%s); run-report at %s",
                exc.code,
                run_report_path,
            )
            raise
        except Exception as exc:
            errors_out = [{"code": "E_S2_UNEXPECTED", "message": str(exc)}]
            warnings_out = sorted(warnings_accum.union(stats.warnings))
            run_report_path = self._write_run_report(
                config=config,
                context=context,
                output_dir=output_dir,
                receipt=receipt,
                stats=stats,
                policy_meta=policy_meta,
                warnings=warnings_out,
                errors=errors_out,
                status="fail",
                start_wall=start_wall,
                started_at=started_at,
                mcc_digest=mcc_digest,
                mcc_overrides_present=mcc_overrides_present,
            )
            self._emit_event(
                "VALIDATION",
                {"id": "runtime", "result": "fail", "code": "E_S2_UNEXPECTED"},
                config=config,
                severity="ERROR",
            )
            logger.exception(
                "Segment2A S2 encountered an unexpected error; run-report at %s",
                run_report_path,
            )
            raise

    def _prepare_context(
        self,
        *,
        data_root: Path,
        seed: int,
        manifest_fingerprint: str,
        upstream_manifest_fingerprint: str,
        dictionary: Mapping[str, object],
        receipt: GateReceiptSummary,
        sealed_assets: Mapping[str, SealedInputRecord],
        determinism_receipt: Mapping[str, object],
    ) -> OverridesContext:
        assets = self._resolve_assets(
            data_root=data_root,
            seed=seed,
            manifest_fingerprint=manifest_fingerprint,
            upstream_manifest_fingerprint=upstream_manifest_fingerprint,
            dictionary=dictionary,
            receipt=receipt,
            sealed_assets=sealed_assets,
        )
        return OverridesContext(
            data_root=data_root,
            seed=seed,
            manifest_fingerprint=manifest_fingerprint,
            upstream_manifest_fingerprint=upstream_manifest_fingerprint,
            receipt_path=receipt.path,
            verified_at_utc=receipt.verified_at_utc,
            assets=assets,
            sealed_assets=sealed_assets,
            determinism_receipt=determinism_receipt,
        )

    def _resolve_output_dir(
        self,
        *,
        data_root: Path,
        seed: int,
        manifest_fingerprint: str,
        dictionary: Mapping[str, object],
    ) -> Path:
        output_rel = render_dataset_path(
            "site_timezones",
            template_args={"seed": seed, "manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        return (data_root / output_rel).resolve()

    def _resolve_run_report_path(
        self,
        *,
        data_root: Path,
        seed: int,
        manifest_fingerprint: str,
    ) -> Path:
        return (
            data_root
            / "reports"
            / "l1"
            / "s2_overrides"
            / f"seed={seed}"
            / f"fingerprint={manifest_fingerprint}"
            / "run_report.json"
        ).resolve()

    def _emit_event(
        self,
        event: str,
        payload: Mapping[str, object | None],
        *,
        config: OverridesInputs,
        severity: str = "INFO",
    ) -> None:
        timestamp = _format_ts(_utc_now())
        base = {
            "timestamp_utc": timestamp,
            "segment": "2A",
            "state": "S2",
            "event": event,
            "seed": config.seed,
            "manifest_fingerprint": config.manifest_fingerprint,
            "severity": severity.upper(),
        }
        base.update(payload)
        record = json.dumps(base, sort_keys=True)
        level = {
            "INFO": logging.INFO,
            "WARN": logging.WARNING,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
        }.get(severity.upper(), logging.INFO)
        logger.log(level, record)

    def _emit_validation_events(
        self,
        *,
        config: OverridesInputs,
        stats: ProcessingStats,
    ) -> None:
        checks = [
            ("V-12", stats.coverage_mismatch == 0),
            ("V-13", stats.pk_duplicates == 0),
            ("V-15b", stats.tzid_not_in_tz_world == 0),
            ("V-19", stats.writer_order_ok),
        ]
        for check_id, passed in checks:
            self._emit_event(
                "VALIDATION",
                {"id": check_id, "result": "pass" if passed else "fail"},
                config=config,
                severity="INFO" if passed else "WARN",
            )

    def _write_run_report(
        self,
        *,
        config: OverridesInputs,
        context: OverridesContext | None,
        output_dir: Path | None,
        receipt: GateReceiptSummary | None,
        stats: ProcessingStats,
        policy_meta: OverridePolicyMetadata | None,
        warnings: list[str],
        errors: list[Mapping[str, object]],
        status: str,
        start_wall: float,
        started_at: datetime,
        mcc_digest: str | None,
        mcc_overrides_present: bool,
    ) -> Path:
        data_root = (
            context.data_root
            if context is not None
            else config.data_root.expanduser().resolve()
        )
        report_path = self._resolve_run_report_path(
            data_root=data_root,
            seed=config.seed,
            manifest_fingerprint=config.manifest_fingerprint,
        )
        finished_at = _utc_now()
        duration_ms = max(0, int((time.perf_counter() - start_wall) * 1000))
        overrides_by_scope = {
            scope: stats.overrides_by_scope.get(scope, 0)
            for scope in ("site", "mcc", "country")
        }
        overrides_total = sum(overrides_by_scope.values())
        distinct_tzids = len(stats.distinct_tzids)
        coverage = stats.coverage_mismatch
        s1_path = (
            str(context.assets.s1_tz_lookup)
            if context is not None
            else None
        )
        tz_world_entry = None
        if context is not None:
            tz_world_record = context.sealed_assets.get("tz_world_2025a")
            if tz_world_record is not None:
                tz_world_entry = {
                    "id": tz_world_record.asset_id,
                    "path": str(context.assets.tz_world),
                    "sha256_digest": tz_world_record.sha256_hex,
                }
        tz_overrides_meta = policy_meta or OverridePolicyMetadata(
            semver="unknown",
            sha256_digest="",
        )
        mcc_mapping_entry = None
        if mcc_overrides_present and context is not None:
            mcc_record = context.sealed_assets.get("merchant_mcc_map")
            mcc_mapping_entry = {
                "id": "merchant_mcc_map",
                "sha256_digest": mcc_record.sha256_hex if mcc_record else mcc_digest,
                "path": (
                    str(context.assets.merchant_mcc_map)
                    if context.assets.merchant_mcc_map
                    else None
                ),
            }
        output_created_utc = (
            context.verified_at_utc
            if context is not None
            else (receipt.verified_at_utc if receipt else None)
        )
        payload = {
            "segment": "2A",
            "state": "S2",
            "status": status,
            "manifest_fingerprint": config.manifest_fingerprint,
            "seed": config.seed,
            "started_utc": _format_ts(started_at),
            "finished_utc": _format_ts(finished_at),
            "durations": {"wall_ms": duration_ms},
            "s0": {
                "receipt_path": str(receipt.path) if receipt else None,
                "verified_at_utc": receipt.verified_at_utc if receipt else None,
            },
            "inputs": {
                "s1_tz_lookup": {"path": s1_path},
                "tz_overrides": {
                    "semver": tz_overrides_meta.semver,
                    "sha256_digest": tz_overrides_meta.sha256_digest,
                    "path": str(context.assets.tz_overrides) if context else None,
                },
                "mcc_mapping": mcc_mapping_entry,
                "tz_world": tz_world_entry,
            },
            "counts": {
                "sites_total": stats.total_rows,
                "rows_emitted": stats.rows_emitted,
                "overridden_total": overrides_total,
                "overridden_by_scope": overrides_by_scope,
                "override_no_effect": stats.override_no_effect,
                "expired_skipped": stats.expired_skipped,
                "dup_scope_target": stats.dup_scope_target,
                "mcc_targets_missing": stats.mcc_targets_missing,
                "distinct_tzids": distinct_tzids,
            },
            "checks": {
                "pk_duplicates": stats.pk_duplicates,
                "coverage_mismatch": coverage,
                "null_tzid": stats.null_tzid,
                "unknown_tzid": stats.unknown_tzid,
                "tzid_not_in_tz_world": stats.tzid_not_in_tz_world,
            },
            "output": {
                "path": str(output_dir) if output_dir else None,
                "format": "parquet",
                "created_utc": output_created_utc,
            },
            "catalogue": {"writer_order_ok": stats.writer_order_ok},
            "determinism": context.determinism_receipt if context else None,
            "warnings": warnings,
            "errors": errors,
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return report_path

    def _resolve_assets(
        self,
        *,
        data_root: Path,
        seed: int,
        manifest_fingerprint: str,
        upstream_manifest_fingerprint: str,
        dictionary: Mapping[str, object],
        receipt: GateReceiptSummary,
        sealed_assets: Mapping[str, SealedInputRecord],
    ) -> OverridesAssets:
        template_args = {"seed": str(seed), "manifest_fingerprint": manifest_fingerprint}
        s1_lookup = resolve_dataset_path(
            "s1_tz_lookup",
            base_path=data_root,
            template_args=template_args,
            dictionary=dictionary,
        )
        tz_overrides_rel = render_dataset_path(
            "tz_overrides",
            template_args={},
            dictionary=dictionary,
        )
        tz_overrides_record = require_sealed_asset(
            asset_id="tz_overrides",
            sealed_assets=sealed_assets,
            code="2A-S2-010",
        )
        ensure_catalog_path(
            asset_id="tz_overrides",
            record=tz_overrides_record,
            expected_relative_path=tz_overrides_rel,
            code="2A-S2-010",
        )
        tz_overrides = resolve_sealed_path(
            base_path=data_root,
            record=tz_overrides_record,
            code="2A-S2-010",
        )
        verify_sealed_digest(
            asset_id="tz_overrides",
            path=tz_overrides,
            expected_hex=tz_overrides_record.sha256_hex,
            code="2A-S2-010",
        )
        tz_world_rel = render_dataset_path(
            "tz_world_2025a",
            template_args={},
            dictionary=dictionary,
        )
        tz_world_record = require_sealed_asset(
            asset_id="tz_world_2025a",
            sealed_assets=sealed_assets,
            code="2A-S2-010",
        )
        ensure_catalog_path(
            asset_id="tz_world_2025a",
            record=tz_world_record,
            expected_relative_path=tz_world_rel,
            code="2A-S2-010",
        )
        tz_world = resolve_sealed_path(
            base_path=data_root,
            record=tz_world_record,
            code="2A-S2-010",
        )
        verify_sealed_digest(
            asset_id="tz_world_2025a",
            path=tz_world,
            expected_hex=tz_world_record.sha256_hex,
            code="2A-S2-010",
        )
        merchant_mcc_map = None
        merchant_rel: str | None = None
        merchant_record = sealed_assets.get("merchant_mcc_map")
        if merchant_record:
            merchant_rel = render_dataset_path(
                "merchant_mcc_map",
                template_args={
                    "seed": seed,
                    "manifest_fingerprint": upstream_manifest_fingerprint,
                },
                dictionary=dictionary,
            )
            ensure_catalog_path(
                asset_id="merchant_mcc_map",
                record=merchant_record,
                expected_relative_path=merchant_rel,
                code="2A-S2-010",
            )
            merchant_mcc_map = resolve_sealed_path(
                base_path=data_root,
                record=merchant_record,
                code="2A-S2-010",
            )
            verify_sealed_digest(
                asset_id="merchant_mcc_map",
                path=merchant_mcc_map,
                expected_hex=merchant_record.sha256_hex,
                code="2A-S2-010",
            )
        return OverridesAssets(
            s1_tz_lookup=s1_lookup,
            tz_overrides=tz_overrides,
            tz_world=tz_world,
            merchant_mcc_map=merchant_mcc_map,
        )

    @staticmethod
    def _ensure_receipt_asset(receipt: GateReceiptSummary, asset_id: str) -> None:
        if not any(asset.asset_id == asset_id for asset in receipt.assets):
            raise err(
                "E_S2_RECEIPT_MISSING_ASSET",
                f"sealed asset '{asset_id}' not present in gate receipt '{receipt.path}'",
            )

    def _load_override_policy(
        self,
        *,
        policy_path: Path,
        cutoff_date: date,
        tzid_whitelist: set[str],
        has_mcc_map: bool,
    ) -> tuple["OverrideIndex", OverridePolicyMetadata]:
        if not policy_path.exists():
            raise err(
                "E_S2_OVERRIDES_MISSING",
                f"tz_overrides policy missing at '{policy_path}'",
            )
        payload = yaml.safe_load(policy_path.read_text(encoding="utf-8")) or {}
        overrides = payload.get("overrides") or []
        if not isinstance(overrides, list):
            raise err("E_S2_OVERRIDES_INVALID", "overrides must be an array")

        semver = str(payload.get("semver") or "unknown")
        sha256_declared = str(payload.get("sha256_digest") or "")
        sha256_computed = _sha256_file(policy_path)
        meta = OverridePolicyMetadata(
            semver=semver,
            sha256_digest=sha256_computed or sha256_declared,
        )

        index = OverrideIndex()
        for entry in overrides:
            if not isinstance(entry, Mapping):
                raise err("E_S2_OVERRIDES_INVALID", "override entries must be objects")
            scope = entry.get("scope")
            target = entry.get("target")
            tzid = entry.get("tzid")
            expiry = entry.get("expiry_yyyy_mm_dd")
            if not isinstance(scope, str) or scope not in {"site", "mcc", "country"}:
                raise err("E_S2_OVERRIDES_INVALID", "override scope must be site, mcc, or country")
            if not isinstance(target, str) or not target:
                raise err("E_S2_OVERRIDES_INVALID", "override target must be a non-empty string")
            if not isinstance(tzid, str) or not tzid:
                raise err("E_S2_OVERRIDES_INVALID", "override tzid must be a non-empty string")
            if tzid not in tzid_whitelist:
                raise err(
                    "E_S2_UNKNOWN_TZID",
                    f"override tzid '{tzid}' not present in sealed tz_world release",
                )
            expiry_date = None
            if isinstance(expiry, str) and expiry:
                try:
                    expiry_date = datetime.strptime(expiry, "%Y-%m-%d").date()
                except ValueError as exc:
                    raise err(
                        "E_S2_OVERRIDES_INVALID",
                        f"override expiry '{expiry}' is not YYYY-MM-DD",
                    ) from exc
                if expiry_date < cutoff_date:
                    meta.expired_skipped += 1
                    continue
            bucket = {"site": index.site, "mcc": index.mcc, "country": index.country}[scope]
            if target in bucket:
                meta.dup_scope_target += 1
                raise err(
                    "E_S2_OVERRIDES_DUPLICATE_SCOPE_TARGET",
                    f"scope '{scope}' contains duplicate target '{target}'",
                )
            bucket[target] = OverrideRecord(tzid=tzid, scope=scope)
        if meta.expired_skipped:
            logger.info(
                "Segment2A S2 skipped %s expired overrides (cutoff=%s)",
                meta.expired_skipped,
                cutoff_date.isoformat(),
            )
        index.mcc_present = bool(index.mcc)
        if index.mcc_present and not has_mcc_map:
            logger.info("Segment2A S2 detected MCC overrides but no mapping is sealed.")
        return index, meta

    def _load_mcc_mapping(self, mapping_path: Path | None) -> tuple[Mapping[str, str], str | None]:
        if mapping_path is None or not mapping_path.exists():
            return {}, None
        try:
            table = pq.read_table(mapping_path)
        except Exception as exc:  # pragma: no cover - defensive
            raise err(
                "E_S2_MCC_MAP_INVALID",
                f"failed to read MCC mapping at '{mapping_path}': {exc}",
            ) from exc
        required = {"merchant_id", "mcc"}
        missing = required.difference(table.column_names)
        if missing:
            raise err(
                "E_S2_MCC_MAP_INVALID",
                f"MCC mapping missing required columns {sorted(missing)}",
            )
        merchant_col = table["merchant_id"].to_pandas()
        mcc_col = table["mcc"].to_pandas()
        mapping: dict[str, str] = {}
        for merchant_id, mcc in zip(merchant_col, mcc_col, strict=False):
            key = str(merchant_id)
            mapping[key] = str(mcc)
        return mapping, _sha256_file(mapping_path)

    def _load_tzid_whitelist(self, tz_world_path: Path) -> set[str]:
        if not tz_world_path.exists():
            raise err(
                "E_S2_TZ_WORLD_MISSING",
                f"tz_world release missing at '{tz_world_path}'",
            )
        table = pq.read_table(tz_world_path, columns=["tzid"])
        tzid_column = table.column("tzid")
        tzids = {str(value) for value in tzid_column.unique().to_pylist()}
        if not tzids:
            raise err("E_S2_TZ_WORLD_EMPTY", "tz_world release contained no tzids")
        return tzids

    def _process_lookup(
        self,
        *,
        context: OverridesContext,
        output_dir: Path,
        override_index: "OverrideIndex",
        mcc_mapping: Mapping[str, str],
        tzid_whitelist: set[str],
        chunk_size: int,
        stats: ProcessingStats,
    ) -> ProcessingStats:
        data_path = context.assets.s1_tz_lookup
        dataset = pa_ds.dataset(
            data_path,
            format="parquet",
            partitioning="hive",
        )
        scanner = dataset.scanner(columns=_S1_COLUMNS, batch_size=chunk_size, use_threads=True)
        part_counter = 0
        resolver = OverrideResolver(
            index=override_index,
            merchant_mcc_map=mcc_mapping,
        )
        seen_keys: set[tuple[str, str, int]] = set()
        last_key: tuple[str, str, int] | None = None

        for batch in scanner.to_batches():
            if batch.num_rows == 0:
                continue
            df = pl.from_arrow(batch)
            result_rows = []
            for row in df.iter_rows(named=True):
                record = self._apply_row(
                    row=row,
                    resolver=resolver,
                    context=context,
                    tzid_whitelist=tzid_whitelist,
                    stats=stats,
                )
                key = (str(record["merchant_id"]), str(record["legal_country_iso"]), int(record["site_order"]))
                if key in seen_keys:
                    stats.pk_duplicates += 1
                    raise err(
                        "E_S2_PK_DUPLICATE",
                        f"duplicate site key detected for ({key[0]}, {key[1]}, {key[2]})",
                    )
                seen_keys.add(key)
                if last_key is not None and key < last_key:
                    stats.writer_order_ok = False
                last_key = key
                stats.distinct_tzids.add(str(record["tzid"]))
                result_rows.append(record)
            result_df = pl.DataFrame(result_rows)
            part_path = output_dir / f"part-{part_counter:05d}.parquet"
            result_df.write_parquet(part_path)
            part_counter += 1
            stats.total_rows += batch.num_rows
            stats.rows_emitted += len(result_rows)
        if stats.total_rows == 0:
            raise err(
                "E_S2_NO_INPUT_ROWS",
                f"s1_tz_lookup at '{data_path}' contained no rows to process",
            )
        stats.coverage_mismatch = abs(stats.rows_emitted - stats.total_rows)
        if stats.coverage_mismatch:
            raise err(
                "E_S2_COVERAGE_MISMATCH",
                f"coverage mismatch detected (rows={stats.total_rows}, emitted={stats.rows_emitted})",
            )
        return stats

    def _apply_row(
        self,
        *,
        row: Mapping[str, object],
        resolver: "OverrideResolver",
        context: OverridesContext,
        tzid_whitelist: set[str],
        stats: "ProcessingStats",
    ) -> Mapping[str, object]:
        original_merchant = row["merchant_id"]
        merchant = str(original_merchant)
        country = str(row["legal_country_iso"])
        site_order = int(row["site_order"])
        tzid_provisional = row.get("tzid_provisional")
        if tzid_provisional is None or str(tzid_provisional) == "":
            stats.null_tzid += 1
            raise err(
                "E_S2_NULL_TZID",
                f"s1_tz_lookup row ({merchant}, {country}, {site_order}) missing tzid_provisional",
            )
        tzid_provisional = str(tzid_provisional)
        if resolver.has_mcc_scope and not resolver.has_mapping_for(merchant):
            stats.mcc_targets_missing += 1
        result = resolver.resolve(
            merchant_id=merchant,
            legal_country_iso=country,
            site_order=site_order,
        )
        tzid = tzid_provisional
        tzid_source = "polygon"
        override_scope: str | None = None
        if result is not None:
            tzid = result.tzid
            override_scope = result.scope
            if tzid == tzid_provisional:
                stats.override_no_effect += 1
                raise err(
                    "E_S2_OVERRIDE_NO_EFFECT",
                    f"override for ({merchant}, {country}, {site_order})"
                    " did not change the tzid",
                )
            tzid_source = "override"
            stats.overrides_by_scope[result.scope] += 1
        if tzid not in tzid_whitelist:
            stats.tzid_not_in_tz_world += 1
            raise err(
                "E_S2_TZID_NOT_IN_TZ_WORLD",
                f"final tzid '{tzid}' not present in sealed tz_world release",
            )
        nudge_lat = row.get("nudge_lat_deg")
        nudge_lon = row.get("nudge_lon_deg")
        if (nudge_lat is None) ^ (nudge_lon is None):
            raise err(
                "E_S2_NUDGE_PAIR_VIOLATION",
                f"s1_tz_lookup row ({merchant}, {country}, {site_order}) "
                "must have both nudge coordinates set or both null",
            )
        return {
            "merchant_id": merchant,
            "legal_country_iso": country,
            "site_order": site_order,
            "tzid": tzid,
            "tzid_source": tzid_source,
            "override_scope": override_scope,
            "nudge_lat_deg": nudge_lat,
            "nudge_lon_deg": nudge_lon,
            "created_utc": context.verified_at_utc,
        }


@dataclass
class OverrideRecord:
    tzid: str
    scope: str


class OverrideIndex:
    """Index of overrides bucketed by scope."""

    def __init__(self) -> None:
        self.site: dict[str, OverrideRecord] = {}
        self.mcc: dict[str, OverrideRecord] = {}
        self.country: dict[str, OverrideRecord] = {}
        self.mcc_present: bool = False


@dataclass
class OverrideDecision:
    tzid: str
    scope: str


class OverrideResolver:
    """Apply precedence rules for overrides."""

    def __init__(
        self,
        *,
        index: OverrideIndex,
        merchant_mcc_map: Mapping[str, str],
    ) -> None:
        self._index = index
        self._merchant_mcc_map = merchant_mcc_map
        self._has_mcc_scope = bool(index.mcc)

    @property
    def has_mcc_scope(self) -> bool:
        return self._has_mcc_scope

    def has_mapping_for(self, merchant_id: str) -> bool:
        return merchant_id in self._merchant_mcc_map

    def resolve(
        self,
        *,
        merchant_id: str,
        legal_country_iso: str,
        site_order: int,
    ) -> OverrideDecision | None:
        site_key = _site_target(merchant_id, legal_country_iso, site_order)
        record = self._index.site.get(site_key)
        if record:
            return OverrideDecision(tzid=record.tzid, scope="site")

        if self._index.mcc and self._merchant_mcc_map:
            merchant_mcc = self._merchant_mcc_map.get(merchant_id)
            if merchant_mcc:
                record = self._index.mcc.get(merchant_mcc)
                if record:
                    return OverrideDecision(tzid=record.tzid, scope="mcc")

        record = self._index.country.get(legal_country_iso)
        if record:
            return OverrideDecision(tzid=record.tzid, scope="country")
        return None


@dataclass
class ProcessingStats:
    total_rows: int = 0
    rows_emitted: int = 0
    overrides_by_scope: Counter[str] = field(
        default_factory=lambda: Counter({"site": 0, "mcc": 0, "country": 0})
    )
    override_no_effect: int = 0
    expired_skipped: int = 0
    dup_scope_target: int = 0
    mcc_targets_missing: int = 0
    distinct_tzids: set[str] = field(default_factory=set)
    pk_duplicates: int = 0
    coverage_mismatch: int = 0
    null_tzid: int = 0
    unknown_tzid: int = 0
    tzid_not_in_tz_world: int = 0
    writer_order_ok: bool = True
    warnings: set[str] = field(default_factory=set)


def _site_target(merchant_id: str, country_iso: str, site_order: int) -> str:
    return f"{merchant_id}:{country_iso}:{site_order}"


def _to_date(value: str) -> date:
    text = value
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    dt = dt.astimezone(UTC)
    return dt.date()


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _format_ts(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(8192), b""):
                digest.update(chunk)
    except FileNotFoundError:  # pragma: no cover - defensive guard
        return ""
    return digest.hexdigest()


__all__ = ["OverridesInputs", "OverridesResult", "OverridesRunner"]
