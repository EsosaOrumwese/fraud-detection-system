"""Deterministic assignment kernels for Segment 1B state-5."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Tuple

import numpy as np
import polars as pl

from engine.layers.l1.seg_1A.s0_foundations.l1.rng import PhiloxEngine, PhiloxState

from ..exceptions import err
from .rng import MODULE_NAME, SUBSTREAM_LABEL, derive_site_tile_substream


@dataclass(frozen=True)
class PairKey:
    """Convenience key grouping merchant and country."""

    merchant_id: int
    legal_country_iso: str


@dataclass(frozen=True)
class AssignmentResult:
    """Container for assignment outputs used by later materialisation."""

    assignments: pl.DataFrame
    rng_events: List[dict]
    rows_emitted: int
    rng_events_emitted: int
    pairs_total: int
    ties_broken_total: int
    run_id: str


def _utc_timestamp() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(tzinfo=timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    )


def _expand_tile_multiset(frame: pl.DataFrame) -> Dict[PairKey, List[int]]:
    multiset: Dict[PairKey, List[int]] = {}
    for row in frame.iter_rows(named=True):
        merchant_id = int(row["merchant_id"])
        country = str(row["legal_country_iso"])
        tile_id = int(row["tile_id"])
        count = int(row["n_sites_tile"])
        if count <= 0:
            raise err(
                "E414_WEIGHT_TAMPER",
                f"non-positive n_sites_tile={count} for merchant {merchant_id} country {country}",
            )
        key = PairKey(merchant_id, country)
        tiles = multiset.setdefault(key, [])
        tiles.extend([tile_id] * count)
    return multiset


def _validate_tile_universe(
    *,
    multiset: Dict[PairKey, List[int]],
    tile_lookup: Dict[str, np.ndarray],
) -> None:
    missing: List[Tuple[int, str, int]] = []
    for key, tiles in multiset.items():
        allowed = tile_lookup.get(key.legal_country_iso)
        if allowed is None:
            missing.extend((key.merchant_id, key.legal_country_iso, tile_id) for tile_id in tiles)
            continue
        allowed_arr = allowed
        tile_array = np.asarray(tiles, dtype=np.uint64)
        positions = np.searchsorted(allowed_arr, tile_array)
        mask = (positions >= allowed_arr.size) | (allowed_arr[positions] != tile_array)
        if mask.any():
            for tile_id in tile_array[mask]:
                missing.append((key.merchant_id, key.legal_country_iso, int(tile_id)))
    if missing:
        sample = missing[:3]
        raise err(
            "E505_TILE_NOT_IN_INDEX",
            f"tiles not present in tile_index: {sample}",
        )


def _validate_iso_codes(
    *,
    multiset: Dict[PairKey, List[int]],
    iso_codes: frozenset[str],
) -> None:
    invalid = {
        key.legal_country_iso
        for key in multiset
        if key.legal_country_iso not in iso_codes
    }
    if invalid:
        raise err(
            "E408_COVERAGE_MISSING",
            f"iso3166_canonical_2024 missing codes: {sorted(invalid)}",
        )


def build_assignments(
    *,
    allocations: pl.DataFrame,
    iso_codes: frozenset[str],
    allowed_tiles: Dict[str, np.ndarray],
    engine: PhiloxEngine,
    parameter_hash: str,
    manifest_fingerprint: str,
    seed_int: int,
    run_id: str,
) -> AssignmentResult:
    """Compute site assignments and RNG events."""

    multiset = _expand_tile_multiset(allocations)
    _validate_iso_codes(multiset=multiset, iso_codes=iso_codes)
    _validate_tile_universe(multiset=multiset, tile_lookup=allowed_tiles)

    assignments: List[dict] = []
    rng_events: List[dict] = []
    ties_broken_total = 0

    for key, tiles in multiset.items():
        tiles_sorted = sorted(tiles)
        n_sites = len(tiles_sorted)
        site_orders = list(range(1, n_sites + 1))

        substream = derive_site_tile_substream(
            engine,
            merchant_id=key.merchant_id,
            legal_country_iso=key.legal_country_iso,
            parameter_hash=parameter_hash,
        )

        draws: List[Tuple[int, float, PhiloxState, PhiloxState]] = []
        duplicates: Dict[float, int] = {}

        for site_order in site_orders:
            before_state = substream.snapshot()
            prior_blocks = substream.blocks
            prior_draws = substream.draws
            u = substream.uniform()
            after_state = substream.snapshot()
            blocks_used = substream.blocks - prior_blocks
            draws_used = substream.draws - prior_draws
            if blocks_used != 1 or draws_used != 1:
                raise err(
                    "E507_RNG_EVENT_MISMATCH",
                    "assignment event must consume exactly one block and one draw",
                )
            draws.append((site_order, u, before_state, after_state))
            duplicates[u] = duplicates.get(u, 0) + 1

        ties_broken_total += sum(count - 1 for count in duplicates.values() if count > 1)

        permutation = sorted(draws, key=lambda value: (value[1], value[0]))
        if len(permutation) != len(tiles_sorted):
            raise err(
                "E504_SUM_TO_N_MISMATCH",
                f"site count mismatch for merchant {key.merchant_id} country {key.legal_country_iso}",
            )

        for tile_id, (site_order, u, before_state, after_state) in zip(
            tiles_sorted, permutation, strict=True
        ):
            assignments.append(
                {
                    "merchant_id": key.merchant_id,
                    "legal_country_iso": key.legal_country_iso,
                    "site_order": site_order,
                    "tile_id": tile_id,
                }
            )
            rng_events.append(
                {
                    "ts_utc": _utc_timestamp(),
                    "module": MODULE_NAME,
                    "substream_label": SUBSTREAM_LABEL,
                    "seed": seed_int,
                    "run_id": run_id,
                    "parameter_hash": parameter_hash,
                    "manifest_fingerprint": manifest_fingerprint,
                    "rng_counter_before_hi": int(before_state.counter_hi),
                    "rng_counter_before_lo": int(before_state.counter_lo),
                    "rng_counter_after_hi": int(after_state.counter_hi),
                    "rng_counter_after_lo": int(after_state.counter_lo),
                    "blocks": 1,
                    "draws": "1",
                    "merchant_id": key.merchant_id,
                    "legal_country_iso": key.legal_country_iso,
                    "site_order": site_order,
                    "tile_id": tile_id,
                    "u": u,
                }
            )

    assignments_frame = (
        pl.DataFrame(assignments)
        .with_columns(
            [
                pl.col("merchant_id").cast(pl.UInt64),
                pl.col("legal_country_iso").cast(pl.Utf8).str.to_uppercase(),
                pl.col("site_order").cast(pl.Int64),
                pl.col("tile_id").cast(pl.UInt64),
            ]
        )
        .sort(["merchant_id", "legal_country_iso", "site_order"])
    )

    rows_emitted = assignments_frame.height
    rng_events_emitted = len(rng_events)
    if rows_emitted != rng_events_emitted:
        raise err(
            "E507_RNG_EVENT_MISMATCH",
            f"dataset rows ({rows_emitted}) != RNG events ({rng_events_emitted})",
        )

    pairs_total = len(multiset)

    return AssignmentResult(
        assignments=assignments_frame,
        rng_events=rng_events,
        rows_emitted=rows_emitted,
        rng_events_emitted=rng_events_emitted,
        pairs_total=pairs_total,
        ties_broken_total=ties_broken_total,
        run_id=run_id,
    )


__all__ = ["AssignmentResult", "build_assignments"]
