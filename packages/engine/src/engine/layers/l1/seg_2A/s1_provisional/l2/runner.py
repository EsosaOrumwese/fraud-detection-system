"""High-level orchestration for Segment 2A S1."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Optional

import geopandas as gpd
import polars as pl
import yaml
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry
from shapely.strtree import STRtree

from engine.layers.l1.seg_2A.s0_gate.exceptions import err
from engine.layers.l1.seg_2A.shared.dictionary import (
    load_dictionary,
    render_dataset_path,
    resolve_dataset_path,
)
from engine.layers.l1.seg_2A.shared.receipt import GateReceiptSummary, load_gate_receipt

from ..l1.context import ProvisionalLookupAssets, ProvisionalLookupContext

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProvisionalLookupInputs:
    """User-supplied configuration for running 2A.S1."""

    data_root: Path
    seed: int
    manifest_fingerprint: str
    chunk_size: int = 250_000
    resume: bool = False
    dictionary: Optional[Mapping[str, object]] = None
    dictionary_path: Optional[Path] = None


@dataclass(frozen=True)
class ProvisionalLookupResult:
    """Outcome of the provisional lookup runner."""

    seed: int
    manifest_fingerprint: str
    output_path: Path
    resumed: bool


class ProvisionalLookupRunner:
    """Runs the provisional time-zone lookup."""

    def run(self, config: ProvisionalLookupInputs) -> ProvisionalLookupResult:
        dictionary = config.dictionary or load_dictionary(config.dictionary_path)
        data_root = config.data_root.expanduser().resolve()
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
        context = self._prepare_context(
            data_root=data_root,
            seed=config.seed,
            manifest_fingerprint=config.manifest_fingerprint,
            dictionary=dictionary,
            receipt=receipt,
        )
        output_dir = self._resolve_output_dir(
            data_root=data_root,
            seed=config.seed,
            manifest_fingerprint=config.manifest_fingerprint,
            dictionary=dictionary,
        )
        if output_dir.exists():
            if config.resume:
                logger.info(
                    "Segment2A S1 resume detected (seed=%s, manifest=%s); skipping run",
                    config.seed,
                    config.manifest_fingerprint,
                )
                return ProvisionalLookupResult(
                    seed=config.seed,
                    manifest_fingerprint=config.manifest_fingerprint,
                    output_path=output_dir,
                    resumed=True,
                )
            raise err(
                "E_S1_OUTPUT_EXISTS",
                f"s1_tz_lookup already exists at '{output_dir}' "
                "— use resume to skip or delete the partition first",
            )
        output_dir.mkdir(parents=True, exist_ok=True)
        tz_index = self._build_tz_index(context.assets.tz_world)
        epsilon = self._load_nudge_policy(context.assets.tz_nudge)
        total_rows, border_nudged = self._process_site_locations(
            context=context,
            tz_index=tz_index,
            epsilon=epsilon,
            output_dir=output_dir,
            chunk_size=config.chunk_size,
        )
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
            resumed=False,
        )

    def _prepare_context(
        self,
        *,
        data_root: Path,
        seed: int,
        manifest_fingerprint: str,
        dictionary: Mapping[str, object],
        receipt: GateReceiptSummary,
    ) -> ProvisionalLookupContext:
        assets = self._resolve_assets(
            data_root=data_root,
            seed=seed,
            manifest_fingerprint=manifest_fingerprint,
            dictionary=dictionary,
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
            receipt_path=receipt.path,
            assets=assets,
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
        dictionary: Mapping[str, object],
    ) -> ProvisionalLookupAssets:
        template_args = {"seed": seed, "manifest_fingerprint": manifest_fingerprint}
        site_locations = resolve_dataset_path(
            "site_locations",
            base_path=data_root,
            template_args=template_args,
            dictionary=dictionary,
        )
        tz_world = resolve_dataset_path(
            "tz_world_2025a",
            base_path=data_root,
            template_args={},
            dictionary=dictionary,
        )
        tz_nudge = resolve_dataset_path(
            "tz_nudge",
            base_path=data_root,
            template_args={},
            dictionary=dictionary,
        )
        tz_overrides: Path | None
        try:
            tz_overrides = resolve_dataset_path(
                "tz_overrides",
                base_path=data_root,
                template_args={},
                dictionary=dictionary,
            )
        except Exception:
            tz_overrides = None
        return ProvisionalLookupAssets(
            site_locations=site_locations,
            tz_world=tz_world,
            tz_nudge=tz_nudge,
            tz_overrides=tz_overrides,
        )


    def _build_tz_index(self, tz_path: Path) -> "TimeZoneIndex":
        return TimeZoneIndex.from_parquet(tz_path)

    def _load_nudge_policy(self, tz_nudge_path: Path) -> float:
        payload = yaml.safe_load(tz_nudge_path.read_text(encoding="utf-8")) or {}
        epsilon = payload.get("nudge_distance_degrees")
        if not isinstance(epsilon, (int, float)) or epsilon <= 0:
            raise err(
                "E_S1_NUDGE_POLICY_INVALID",
                "tz_nudge policy must declare positive nudge_distance_degrees",
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
    ) -> tuple[int, int]:
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
        part_idx = 0
        for file in files:
            df = pl.read_parquet(
                file,
                columns=["merchant_id", "legal_country_iso", "site_order", "lat_deg", "lon_deg"],
            )
            if df.is_empty():
                continue
            batches = _yield_batches(df, chunk_size)
            for batch in batches:
                out_df, nudged = self._assign_batch(batch, tz_index, epsilon)
                part_path = output_dir / f"part-{part_idx:05d}.parquet"
                out_df.write_parquet(part_path, compression="zstd")
                part_idx += 1
                total_rows += len(batch)
                border_nudged += nudged
        if total_rows == 0:
            raise err("E_S1_INPUT_EMPTY", "site_locations partition contained zero rows")
        return total_rows, border_nudged

    def _assign_batch(
        self,
        batch: pl.DataFrame,
        tz_index: "TimeZoneIndex",
        epsilon: float,
    ) -> tuple[pl.DataFrame, int]:
        lons = batch["lon_deg"].to_list()
        lats = batch["lat_deg"].to_list()
        tz_ids, nudge_lat, nudge_lon, nudged_count = tz_index.assign(
            lons=lons,
            lats=lats,
            epsilon=epsilon,
        )
        created = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        output = pl.DataFrame(
            {
                "merchant_id": batch["merchant_id"],
                "legal_country_iso": batch["legal_country_iso"],
                "site_order": batch["site_order"],
                "lat_deg": batch["lat_deg"],
                "lon_deg": batch["lon_deg"],
                "tzid_provisional": pl.Series(tz_ids, dtype=pl.Utf8),
                "nudge_lat_deg": pl.Series(nudge_lat, dtype=pl.Float64),
                "nudge_lon_deg": pl.Series(nudge_lon, dtype=pl.Float64),
                "created_utc": pl.Series([created] * len(batch), dtype=pl.Utf8),
            }
        ).sort(["merchant_id", "legal_country_iso", "site_order"])
        return output, nudged_count


def _yield_batches(df: pl.DataFrame, batch_size: int) -> Iterable[pl.DataFrame]:
    if len(df) <= batch_size:
        yield df
        return
    for offset in range(0, len(df), batch_size):
        yield df.slice(offset, batch_size)


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
    ) -> tuple[list[str], list[Optional[float]], list[Optional[float]], int]:
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
        if ambiguous:
            nudged_count = len(ambiguous)
            nudged_pts = [
                Point(lons[i] + epsilon, lats[i] + epsilon) for i in ambiguous
            ]
            match_counts_nudged = [0] * len(ambiguous)
            tzids_nudged: list[Optional[str]] = [None] * len(ambiguous)
            for pt_idx, poly_idx in self._query_contains(nudged_pts):
                match_counts_nudged[pt_idx] += 1
                if match_counts_nudged[pt_idx] == 1:
                    tzids_nudged[pt_idx] = self._tzids[poly_idx]
            unresolved = [
                i for i, count in enumerate(match_counts_nudged) if count != 1
            ]
            if unresolved:
                raise err(
                    "E_S1_BORDER_AMBIGUITY",
                    f"border ambiguity remained unresolved for {len(unresolved)} sites",
                )
            for idx, original_idx in enumerate(ambiguous):
                tzids[original_idx] = tzids_nudged[idx]
                nudge_lat[original_idx] = lats[original_idx] + epsilon
                nudge_lon[original_idx] = lons[original_idx] + epsilon
        # Ensure no unresolved entries remain
        if any(tzid is None for tzid in tzids):
            raise err(
                "E_S1_ASSIGN_FAILED",
                "some site rows could not be matched to a zone even after nudge",
            )
        return tzids, nudge_lat, nudge_lon, nudged_count

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
