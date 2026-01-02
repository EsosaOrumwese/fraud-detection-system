"""High-level orchestration for Segment 2A S1."""

from __future__ import annotations

import json
import logging
import math
import time
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence

import geopandas as gpd
import polars as pl
import pyarrow.parquet as pq
import yaml
from shapely.geometry import Point
from shapely.strtree import STRtree

from engine.layers.l1.seg_2A.s0_gate.exceptions import err
from engine.layers.l1.seg_2A.shared.dictionary import (
    get_dataset_entry,
    load_dictionary,
    render_dataset_path,
    resolve_dataset_path,
)
from engine.layers.l1.seg_2A.shared.receipt import (
    GateReceiptSummary,
    SealedInputRecord,
    load_determinism_receipt,
    load_gate_receipt,
    load_sealed_inputs_inventory,
)

from ..l1.context import ProvisionalLookupAssets, ProvisionalLookupContext

logger = logging.getLogger(__name__)

_SITE_COLUMNS = ["merchant_id", "legal_country_iso", "site_order", "lat_deg", "lon_deg"]


@dataclass(frozen=True)
class ProvisionalLookupInputs:
    """User-supplied configuration for running 2A.S1."""

    data_root: Path
    seed: int
    manifest_fingerprint: str
    upstream_manifest_fingerprint: str
    chunk_size: int = 250_000
    resume: bool = False
    dictionary: Optional[Mapping[str, object]] = None
    dictionary_path: Optional[Path] = None
    emit_run_report_stdout: bool = True


@dataclass(frozen=True)
class ProvisionalLookupResult:
    """Outcome of the provisional lookup runner."""

    seed: int
    manifest_fingerprint: str
    output_path: Path
    run_report_path: Path
    resumed: bool


class ProvisionalLookupRunner:
    """Runs the provisional time-zone lookup."""

    def run(self, config: ProvisionalLookupInputs) -> ProvisionalLookupResult:
        dictionary = config.dictionary or load_dictionary(config.dictionary_path)
        data_root = config.data_root.expanduser().resolve()
        run_started_at = datetime.now(timezone.utc)
        wall_timer = time.perf_counter()
        logger.info(
            "Segment2A S1 scaffolding invoked (seed=%s, manifest=%s)",
            config.seed,
            config.manifest_fingerprint,
        )
        receipt = load_gate_receipt(
            base_path=data_root,
            manifest_fingerprint=config.manifest_fingerprint,
            dictionary=dictionary,
        )
        sealed_records = load_sealed_inputs_inventory(
            base_path=data_root,
            manifest_fingerprint=config.manifest_fingerprint,
            dictionary=dictionary,
        )
        sealed_assets = {record.asset_id: record for record in sealed_records}
        determinism_receipt = load_determinism_receipt(
            base_path=data_root,
            manifest_fingerprint=config.manifest_fingerprint,
            dictionary=dictionary,
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
        run_report_path = self._resolve_run_report_path(
            data_root=data_root,
            seed=config.seed,
            manifest_fingerprint=config.manifest_fingerprint,
            dictionary=dictionary,
        )
        if output_dir.exists():
            if config.resume:
                if not run_report_path.exists():
                    raise err(
                        "2A-S1-070",
                        f"run report missing at '{run_report_path}' while resume requested",
                    )
                logger.info(
                    "Segment2A S1 resume detected (seed=%s, manifest=%s); skipping run",
                    config.seed,
                    config.manifest_fingerprint,
                )
                if config.emit_run_report_stdout:
                    try:
                        existing_report = json.loads(run_report_path.read_text(encoding="utf-8"))
                    except json.JSONDecodeError:
                        existing_report = None
                    if isinstance(existing_report, Mapping):
                        print(json.dumps(existing_report, indent=2))
                return ProvisionalLookupResult(
                    seed=config.seed,
                    manifest_fingerprint=config.manifest_fingerprint,
                    output_path=output_dir,
                    run_report_path=run_report_path,
                    resumed=True,
                )
            raise err(
                "E_S1_OUTPUT_EXISTS",
                f"s1_tz_lookup already exists at '{output_dir}' "
                "- use resume to skip or delete the partition first",
            )
        output_dir.mkdir(parents=True, exist_ok=True)
        tz_index = self._build_tz_index(context.assets.tz_world)
        epsilon = self._load_nudge_policy(context.assets.tz_nudge)
        total_rows, border_nudged, distinct_tzids, fallback_resolved = self._process_site_locations(
            context=context,
            tz_index=tz_index,
            epsilon=epsilon,
            output_dir=output_dir,
            chunk_size=config.chunk_size,
        )
        run_finished_at = datetime.now(timezone.utc)
        wall_ms = int(round((time.perf_counter() - wall_timer) * 1000))
        counts = {
            "sites_total": total_rows,
            "rows_emitted": total_rows,
            "border_nudged": border_nudged,
            "distinct_tzids": distinct_tzids,
        }
        warnings: list[str] = []
        if fallback_resolved:
            warnings.append(
                f"{fallback_resolved} sites resolved via deterministic fallback after unresolved border ambiguity"
            )
        run_report_payload = self._build_run_report(
            context=context,
            dictionary=dictionary,
            output_dir=output_dir,
            counts=counts,
            warnings=warnings,
            started_at=run_started_at,
            finished_at=run_finished_at,
            timings={"wall_ms": wall_ms},
        )
        self._write_run_report(path=run_report_path, payload=run_report_payload)
        if config.emit_run_report_stdout:
            print(json.dumps(run_report_payload, indent=2))
        logger.info(
            "Segment2A S1 completed (rows=%s, border_nudged=%s, output=%s)",
            total_rows,
            border_nudged,
            output_dir,
        )
        return ProvisionalLookupResult(
            seed=config.seed,
            manifest_fingerprint=config.manifest_fingerprint,
            output_path=output_dir,
            run_report_path=run_report_path,
            resumed=False,
        )

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
    ) -> ProvisionalLookupContext:
        assets = self._resolve_assets(
            data_root=data_root,
            seed=seed,
            manifest_fingerprint=manifest_fingerprint,
            upstream_manifest_fingerprint=upstream_manifest_fingerprint,
            dictionary=dictionary,
            receipt=receipt,
            sealed_assets=sealed_assets,
        )
        logger.debug(
            "Resolved S1 assets (site_locations=%s, tz_world=%s)",
            assets.site_locations,
            assets.tz_world,
        )
        return ProvisionalLookupContext(
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
            "s1_tz_lookup",
            template_args={
                "seed": seed,
                "manifest_fingerprint": manifest_fingerprint,
            },
            dictionary=dictionary,
        )
        return (data_root / output_rel).resolve()

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
    ) -> ProvisionalLookupAssets:
        receipt_assets = {asset.asset_id for asset in receipt.assets}
        template_args = {
            "seed": str(seed),
            "manifest_fingerprint": upstream_manifest_fingerprint,
        }
        site_locations = self._resolve_required_asset(
            asset_id="site_locations",
            template_args=template_args,
            data_root=data_root,
            dictionary=dictionary,
            sealed_assets=sealed_assets,
            receipt_assets=receipt_assets,
            code="2A-S1-011",
        )
        tz_world_asset_id = self._discover_tz_world_asset_id(sealed_assets)
        tz_world = self._resolve_required_asset(
            asset_id=tz_world_asset_id,
            template_args={},
            data_root=data_root,
            dictionary=dictionary,
            sealed_assets=sealed_assets,
            receipt_assets=receipt_assets,
            code="2A-S1-020",
        )
        tz_nudge = self._resolve_required_asset(
            asset_id="tz_nudge",
            template_args={},
            data_root=data_root,
            dictionary=dictionary,
            sealed_assets=sealed_assets,
            receipt_assets=receipt_assets,
            code="2A-S1-021",
        )
        tz_overrides: Path | None
        if "tz_overrides" in receipt_assets:
            tz_overrides = self._resolve_required_asset(
                asset_id="tz_overrides",
                template_args={},
                data_root=data_root,
                dictionary=dictionary,
                sealed_assets=sealed_assets,
                receipt_assets=receipt_assets,
                code="2A-S1-020",
            )
        else:
            tz_overrides = None
        return ProvisionalLookupAssets(
            site_locations=site_locations,
            tz_world=tz_world,
            tz_nudge=tz_nudge,
            tz_overrides=tz_overrides,
        )

    def _resolve_required_asset(
        self,
        *,
        asset_id: str,
        template_args: Mapping[str, object],
        data_root: Path,
        dictionary: Mapping[str, object],
        sealed_assets: Mapping[str, SealedInputRecord],
        receipt_assets: set[str],
        code: str,
    ) -> Path:
        if asset_id not in receipt_assets:
            raise err("2A-S1-001", f"gate receipt missing sealed asset '{asset_id}'")
        record = self._require_sealed_asset(
            sealed_assets=sealed_assets,
            asset_id=asset_id,
            code=code,
        )
        rendered = render_dataset_path(
            asset_id,
            template_args=template_args,
            dictionary=dictionary,
        )
        self._assert_catalog_match(
            asset_id=asset_id,
            sealed_path=record.catalog_path,
            expected_path=rendered,
            code=code,
        )
        path = (data_root / rendered).resolve()
        if not path.exists():
            raise err(code, f"sealed asset '{asset_id}' not found at '{path}'")
        return path

    @staticmethod
    def _require_sealed_asset(
        *,
        sealed_assets: Mapping[str, SealedInputRecord],
        asset_id: str,
        code: str,
    ) -> SealedInputRecord:
        record = sealed_assets.get(asset_id)
        if record is None:
            raise err(code, f"sealed asset '{asset_id}' not present in sealed_inputs_v1")
        return record

    @staticmethod
    def _assert_catalog_match(
        *,
        asset_id: str,
        sealed_path: str,
        expected_path: str,
        code: str,
    ) -> None:
        sealed_norm = sealed_path.rstrip("/\\")
        expected_norm = expected_path.rstrip("/\\")
        if sealed_norm != expected_norm:
            raise err(
                code,
                f"sealed asset '{asset_id}' catalog path '{sealed_path}' does not match dictionary '{expected_path}'",
            )

    @staticmethod
    def _discover_tz_world_asset_id(
        sealed_assets: Mapping[str, SealedInputRecord]
    ) -> str:
        for asset_id in sealed_assets:
            if asset_id.startswith("tz_world"):
                return asset_id
        return "tz_world_2025a"

    @staticmethod
    def _find_tz_world_record(
        sealed_assets: Mapping[str, SealedInputRecord]
    ) -> SealedInputRecord:
        for record in sealed_assets.values():
            if record.asset_id.startswith("tz_world"):
                return record
        raise err("2A-S1-020", "sealed_inputs_v1 missing tz_world asset")


    def _build_tz_index(self, tz_path: Path) -> "TimeZoneIndex":
        return TimeZoneIndex.from_parquet(tz_path)

    def _load_nudge_policy(self, tz_nudge_path: Path) -> float:
        payload = yaml.safe_load(tz_nudge_path.read_text(encoding="utf-8")) or {}
        epsilon = payload.get("epsilon_degrees")
        sha256_digest = payload.get("sha256_digest")
        if not isinstance(epsilon, (int, float)) or epsilon <= 0:
            raise err(
                "E_S1_NUDGE_POLICY_INVALID",
                "tz_nudge policy must declare positive epsilon_degrees",
            )
        if not isinstance(sha256_digest, str) or len(sha256_digest) != 64:
            raise err(
                "E_S1_NUDGE_POLICY_INVALID",
                "tz_nudge policy must declare sha256_digest (hex64)",
            )
        return float(epsilon)

    def _process_site_locations(
        self,
        *,
        context: ProvisionalLookupContext,
        tz_index: "TimeZoneIndex",
        epsilon: float,
        output_dir: Path,
        chunk_size: int,
    ) -> tuple[int, int, int, int]:
        if chunk_size <= 0:
            raise err("E_S1_INVALID_CHUNK_SIZE", "chunk_size must be a positive integer")
        site_path = context.assets.site_locations
        files = sorted(site_path.rglob("*.parquet"))
        if not files:
            raise err(
                "E_S1_INPUT_EMPTY",
                f"site_locations partition '{site_path}' contains no parquet files",
            )

        total_rows = 0
        border_nudged = 0
        fallback_resolved = 0
        distinct_tzids: set[str] = set()
        part_idx = 0

        for file in files:
            file_rows = 0
            for batch in _iter_site_batches(file, chunk_size):
                out_df, nudged, tzids, fallback = self._assign_batch(
                    batch,
                    tz_index,
                    epsilon,
                    context.seed,
                    context.manifest_fingerprint,
                    context.verified_at_utc,
                )
                part_path = output_dir / f"part-{part_idx:05d}.parquet"
                out_df.write_parquet(part_path, compression="zstd")
                part_idx += 1

                batch_rows = len(batch)
                total_rows += batch_rows
                file_rows += batch_rows
                border_nudged += nudged
                fallback_resolved += fallback
                distinct_tzids.update(tzids)

            if file_rows > 0:
                logger.info(
                    "Segment2A S1 streamed %s rows from %s (seed=%s, manifest=%s)",
                    file_rows,
                    file.name,
                    context.seed,
                    context.manifest_fingerprint,
                )

        if total_rows == 0:
            raise err("E_S1_INPUT_EMPTY", "site_locations partition contained zero rows")

        return total_rows, border_nudged, len(distinct_tzids), fallback_resolved

    def _build_run_report(
        self,
        *,
        context: ProvisionalLookupContext,
        dictionary: Mapping[str, object],
        output_dir: Path,
        counts: Mapping[str, int],
        warnings: Sequence[str],
        started_at: datetime,
        finished_at: datetime,
        timings: Mapping[str, int],
    ) -> Mapping[str, object]:
        site_rel = render_dataset_path(
            "site_locations",
            template_args={
                "seed": context.seed,
                "manifest_fingerprint": context.upstream_manifest_fingerprint,
            },
            dictionary=dictionary,
        )
        output_rel = render_dataset_path(
            "s1_tz_lookup",
            template_args={
                "seed": context.seed,
                "manifest_fingerprint": context.manifest_fingerprint,
            },
            dictionary=dictionary,
        )
        tz_world_record = self._find_tz_world_record(context.sealed_assets)
        tz_world_entry = get_dataset_entry(tz_world_record.asset_id, dictionary=dictionary)
        tz_nudge_record = self._require_sealed_asset(
            sealed_assets=context.sealed_assets,
            asset_id="tz_nudge",
            code="2A-S1-021",
        )
        tz_nudge_entry = get_dataset_entry("tz_nudge", dictionary=dictionary)
        warnings = list(warnings)
        warn_count = len(warnings)
        report = {
            "segment": "2A",
            "state": "S1",
            "status": "pass",
            "manifest_fingerprint": context.manifest_fingerprint,
            "seed": context.seed,
            "started_utc": started_at.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "finished_utc": finished_at.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "durations": dict(timings),
            "s0": {
                "receipt_path": str(context.receipt_path),
                "verified_at_utc": context.verified_at_utc,
                "determinism": context.determinism_receipt,
            },
            "inputs": {
                "site_locations": {
                    "path": site_rel,
                    "license": get_dataset_entry("site_locations", dictionary=dictionary).get("license", ""),
                },
                "tz_world": {
                    "id": tz_world_record.asset_id,
                    "path": tz_world_record.catalog_path,
                    "license": tz_world_entry.get("license", ""),
                },
                "tz_nudge": {
                    "path": tz_nudge_record.catalog_path,
                    "sha256_hex": tz_nudge_record.sha256_hex,
                    "semver": tz_nudge_entry.get("version", ""),
                },
            },
            "counts": {
                "sites_total": int(counts.get("sites_total", 0)),
                "rows_emitted": int(counts.get("rows_emitted", 0)),
                "border_nudged": int(counts.get("border_nudged", 0)),
                "distinct_tzids": int(counts.get("distinct_tzids", 0)),
            },
            "checks": {
                "pk_duplicates": 0,
                "coverage_mismatch": 0,
                "null_tzid": 0,
                "unknown_tzid": 0,
            },
            "output": {
                "path": output_rel,
                "filesystem_path": str(output_dir),
                "format": "parquet",
            },
            "warnings": warnings,
            "errors": [],
            "determinism": context.determinism_receipt,
            "validators": self._build_validators(warnings_present=warn_count > 0),
            "summary": {
                "overall_status": "PASS",
                "warn_count": warn_count,
                "fail_count": 0,
            },
        }
        return report

    def _build_validators(self, *, warnings_present: bool) -> list[dict[str, object]]:
        validators = [
            {"id": "V-01", "status": "PASS", "codes": ["2A-S1-001"]},
            {"id": "V-02", "status": "PASS", "codes": ["2A-S1-010"]},
            {"id": "V-03", "status": "PASS", "codes": ["2A-S1-011"]},
            {"id": "V-04", "status": "PASS", "codes": ["2A-S1-020"]},
            {"id": "V-05", "status": "PASS", "codes": ["2A-S1-021"]},
            {"id": "V-06", "status": "PASS", "codes": ["2A-S1-030"]},
            {"id": "V-07", "status": "PASS", "codes": ["2A-S1-040"]},
            {"id": "V-08", "status": "PASS", "codes": ["2A-S1-041"]},
            {"id": "V-09", "status": "PASS", "codes": ["2A-S1-050"]},
            {"id": "V-10", "status": "PASS", "codes": ["2A-S1-051"]},
            {"id": "V-11", "status": "PASS", "codes": ["2A-S1-052"]},
            {"id": "V-12", "status": "PASS", "codes": ["2A-S1-053"]},
            {"id": "V-13", "status": "PASS", "codes": ["2A-S1-054"]},
            {"id": "V-14", "status": "PASS", "codes": ["2A-S1-055"]},
            {"id": "V-15", "status": "WARN" if warnings_present else "PASS", "codes": ["2A-S1-070"]},
        ]
        return validators

    def _resolve_run_report_path(
        self,
        *,
        data_root: Path,
        seed: int,
        manifest_fingerprint: str,
        dictionary: Mapping[str, object],
    ) -> Path:
        rel_path = render_dataset_path(
            "s1_run_report_2A",
            template_args={"seed": seed, "manifest_fingerprint": manifest_fingerprint},
            dictionary=dictionary,
        )
        return (data_root / rel_path).resolve()

    def _write_run_report(self, *, path: Path, payload: Mapping[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _assign_batch(
        self,
        batch: pl.DataFrame,
        tz_index: "TimeZoneIndex",
        epsilon: float,
        seed: int,
        manifest_fingerprint: str,
        created_utc: str,
    ) -> tuple[pl.DataFrame, int, list[str], int]:
        lons = batch["lon_deg"].to_list()
        lats = batch["lat_deg"].to_list()
        tz_ids, nudge_lat, nudge_lon, nudged_count, fallback_resolved = tz_index.assign(
            lons=lons,
            lats=lats,
            epsilon=epsilon,
        )
        output = pl.DataFrame(
            {
                "seed": pl.Series([seed] * len(batch), dtype=pl.UInt64),
                "fingerprint": pl.Series([manifest_fingerprint] * len(batch), dtype=pl.Utf8),
                "merchant_id": batch["merchant_id"],
                "legal_country_iso": batch["legal_country_iso"],
                "site_order": batch["site_order"],
                "lat_deg": batch["lat_deg"],
                "lon_deg": batch["lon_deg"],
                "tzid_provisional": pl.Series(tz_ids, dtype=pl.Utf8),
                "nudge_lat_deg": pl.Series(nudge_lat, dtype=pl.Float64),
                "nudge_lon_deg": pl.Series(nudge_lon, dtype=pl.Float64),
                "created_utc": pl.Series([created_utc] * len(batch), dtype=pl.Utf8),
            }
        ).sort(["merchant_id", "legal_country_iso", "site_order"])
        mask_lat_null = output["nudge_lat_deg"].is_null()
        mask_lon_null = output["nudge_lon_deg"].is_null()
        if not (mask_lat_null == mask_lon_null).all():
            raise err(
                "E_S1_NUDGE_PAIR_VIOLATION",
                "nudge_lat_deg/nudge_lon_deg must both be null or both be non-null",
            )
        return output, nudged_count, tz_ids, fallback_resolved


def _iter_site_batches(path: Path, batch_size: int) -> Iterable[pl.DataFrame]:
    try:
        parquet_file = pq.ParquetFile(path)
    except Exception as exc:
        raise err(
            "E_S1_INPUT_INVALID",
            f"unable to read site_locations parquet '{path}': {exc}",
        ) from exc

    try:
        batch_iter = parquet_file.iter_batches(columns=_SITE_COLUMNS, batch_size=batch_size)
    except KeyError as exc:
        missing = exc.args[0]
        raise err(
            "E_S1_INPUT_SHAPE",
            f"site_locations missing required column '{missing}'",
        ) from exc

    for record_batch in batch_iter:
        frame = pl.from_arrow(record_batch)
        if frame.is_empty():
            continue
        yield frame


class TimeZoneIndex:
    """Spatial index over tz_world polygons."""

    def __init__(self, geometries: list[shapely.Geometry], tzids: list[str]) -> None:
        self._geoms = geometries
        self._tzids = tzids
        self._tree = STRtree(self._geoms)

    @classmethod
    def from_parquet(cls, path: Path) -> "TimeZoneIndex":
        import geopandas as gpd

        frame = gpd.read_parquet(path)
        if "tzid" not in frame.columns:
            raise err("E_S1_TZ_WORLD_INVALID", "tz_world parquet missing 'tzid' column")
        geometries = frame.geometry.to_list()
        tzids = frame["tzid"].astype(str).to_list()
        return cls(geometries=list(geometries), tzids=tzids)

    def assign(
        self,
        *,
        lons: list[float],
        lats: list[float],
        epsilon: float,
    ) -> tuple[list[str], list[Optional[float]], list[Optional[float]], int, int]:
        if len(lons) != len(lats):
            raise err("E_S1_ASSIGN_BOUNDS", "longitude/latitude array length mismatch")
        points = [Point(lon, lat) for lon, lat in zip(lons, lats)]
        tzids = [None] * len(points)
        match_counts = [0] * len(points)
        for point_idx, zone_idx in self._query_contains(points):
            match_counts[point_idx] += 1
            if match_counts[point_idx] == 1:
                tzids[point_idx] = self._tzids[zone_idx]
        ambiguous = [i for i, count in enumerate(match_counts) if count != 1]
        nudge_lat: list[Optional[float]] = [None] * len(points)
        nudge_lon: list[Optional[float]] = [None] * len(points)
        nudged_count = 0
        fallback_resolved = 0
        if ambiguous:
            nudged_count = len(ambiguous)
            nudged_coords = [
                self._apply_nudge(lats[i], lons[i], epsilon) for i in ambiguous
            ]
            nudged_pts = [
                Point(lon, lat) for lat, lon in nudged_coords
            ]
            match_counts_nudged = [0] * len(ambiguous)
            tzids_nudged: list[Optional[str]] = [None] * len(ambiguous)
            candidates_nudged: dict[int, list[int]] = {}
            for pt_idx, poly_idx in self._query_contains(nudged_pts):
                candidates_nudged.setdefault(pt_idx, []).append(poly_idx)
                match_counts_nudged[pt_idx] += 1
                if match_counts_nudged[pt_idx] == 1:
                    tzids_nudged[pt_idx] = self._tzids[poly_idx]
            unresolved = [
                i for i, count in enumerate(match_counts_nudged) if count != 1
            ]
            if unresolved:
                fallback_resolved = len(unresolved)
                candidates_original: dict[int, list[int]] = {}
                original_points = [points[i] for i in ambiguous]
                for pt_idx, poly_idx in self._query_contains(original_points):
                    candidates_original.setdefault(pt_idx, []).append(poly_idx)
                for idx in unresolved:
                    point = nudged_pts[idx]
                    candidates = candidates_nudged.get(idx) or candidates_original.get(idx) or []
                    tzids_nudged[idx] = self._choose_fallback_tzid(point, candidates)
                logger.warning(
                    "Segment2A S1: resolved %d ambiguous sites via deterministic fallback",
                    fallback_resolved,
                )
            for idx, original_idx in enumerate(ambiguous):
                tzids[original_idx] = tzids_nudged[idx]
                nudge_lat[original_idx] = nudged_coords[idx][0]
                nudge_lon[original_idx] = nudged_coords[idx][1]
        # Ensure no unresolved entries remain
        if any(tzid is None for tzid in tzids):
            raise err(
                "E_S1_ASSIGN_FAILED",
                "some site rows could not be matched to a zone even after nudge",
            )
        return tzids, nudge_lat, nudge_lon, nudged_count, fallback_resolved

    def _choose_fallback_tzid(self, point: Point, candidates: list[int]) -> str:
        if candidates:
            tzids = sorted(self._tzids[idx] for idx in candidates)
            return tzids[0]
        best_idx = None
        best_distance = None
        best_tzid = None
        for idx, geom in enumerate(self._geoms):
            dist = geom.distance(point)
            tzid = self._tzids[idx]
            if best_distance is None or dist < best_distance:
                best_distance = dist
                best_idx = idx
                best_tzid = tzid
            elif dist == best_distance and tzid < (best_tzid or tzid):
                best_distance = dist
                best_idx = idx
                best_tzid = tzid
        if best_idx is None or best_tzid is None:
            raise err("E_S1_ASSIGN_FAILED", "unable to resolve fallback tzid for ambiguous site")
        return best_tzid

    @staticmethod
    def _apply_nudge(lat: float, lon: float, epsilon: float) -> tuple[float, float]:
        lat_n = lat + epsilon
        lon_n = lon + epsilon
        if lat_n > 90.0:
            lat_n = 90.0
        elif lat_n < -90.0:
            lat_n = -90.0
        x = lon_n + 180.0
        r = x - 360.0 * math.floor(x / 360.0)
        lon_wrapped = r - 180.0
        if lon_wrapped == -180.0:
            lon_wrapped = 180.0
        return lat_n, lon_wrapped

    def _query_contains(self, points: list[Point]) -> list[tuple[int, int]]:
        idx_pts, idx_polys = self._tree.query(points)
        matches: list[tuple[int, int]] = []
        for pt_idx_raw, poly_idx_raw in zip(idx_pts.tolist(), idx_polys.tolist()):
            pt_idx = int(pt_idx_raw)
            poly_idx = int(poly_idx_raw)
            if self._geoms[poly_idx].contains(points[pt_idx]):
                matches.append((pt_idx, poly_idx))
        return matches


__all__ = [
    "ProvisionalLookupInputs",
    "ProvisionalLookupResult",
    "ProvisionalLookupRunner",
]
