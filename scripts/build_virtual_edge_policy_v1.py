"""Build the 2B virtual_edge_policy_v1 catalogue deterministically."""
from __future__ import annotations

import json
import math
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from pyproj import Geod
from rasterio import features
from rasterio.enums import Resampling
from shapely.geometry import Point
from shapely.ops import nearest_points


ROOT = Path(__file__).resolve().parents[1]
ISO_PATH = ROOT / "reference/iso/iso3166_canonical/2024-12-31/iso3166.parquet"
WORLD_PATH = ROOT / "reference/spatial/world_countries/2024/world_countries.parquet"
POP_PATH = ROOT / "reference/spatial/population/2025/population.tif"
OUT_PATH = ROOT / "contracts/policy/2B/virtual_edge_policy_v1.json"

POLICY_ID = "virtual_edge_policy_v1"
VERSION_TAG = "v1.0.0"
TARGET_EDGES = 2000
MIN_TARGET_EDGES = 800
MAX_TARGET_EDGES = 5000
POP_EXP = 0.90
EDGE_EXP = 0.85
EDGE_ALLOC_EXP = 0.30
ADD_TERM_DIVISOR = 10.0
WEIGHT_FLOOR = 1e-12
MAX_EDGES_PER_COUNTRY = 80
MIN_SEP_KM = 50.0
MIN_SEP_TINY_KM = 15.0
TINY_COUNTRY_AREA_KM2 = 10000.0
POP_FALLBACK_MAX_FRACTION = 0.10
MISSING_POLYGON_MAX_FRACTION = 0.05
SEP_RELAX_MAX_FRACTION = 0.05
EDGE_LON_EPS = 1e-6
POP_OVERVIEW_FACTOR = 4


def canonical_json(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def load_iso_set(path: Path) -> set[str]:
    df = pd.read_parquet(path)
    return set(df["country_iso"].dropna().astype(str).str.upper())


def clean_float(value: float) -> float:
    if value == 0 or value == -0.0:
        return 0.0
    return float(value)


def build_population_surface(
    pop_path: Path,
    world: gpd.GeoDataFrame,
) -> tuple[np.ndarray, np.ndarray, rasterio.Affine]:
    with rasterio.open(pop_path) as src:
        out_height = int(math.ceil(src.height / POP_OVERVIEW_FACTOR))
        out_width = int(math.ceil(src.width / POP_OVERVIEW_FACTOR))
        scale_x = src.width / out_width
        scale_y = src.height / out_height
        out_transform = src.transform * rasterio.Affine.scale(scale_x, scale_y)
        pop = src.read(
            1,
            out_shape=(out_height, out_width),
            resampling=Resampling.average,
        ).astype("float64", copy=False)
        pop *= (scale_x * scale_y)
        if src.nodata is not None:
            pop[pop == src.nodata] = 0.0
    pop[~np.isfinite(pop)] = 0.0
    pop[pop < 0] = 0.0

    shapes = [(geom, idx) for idx, geom in enumerate(world.geometry, start=1)]
    country_id = features.rasterize(
        shapes=shapes,
        out_shape=pop.shape,
        transform=out_transform,
        fill=0,
        dtype="int32",
        all_touched=False,
    )
    return pop, country_id, out_transform


def allocate_edges_per_country(
    q_values: np.ndarray,
    iso_codes: list[str],
) -> tuple[np.ndarray, int]:
    if not (MIN_TARGET_EDGES <= TARGET_EDGES <= MAX_TARGET_EDGES):
        raise ValueError("TARGET_EDGES out of bounds")
    alloc_weights = np.power(q_values, EDGE_ALLOC_EXP)
    total_q = float(alloc_weights.sum())
    if total_q <= 0:
        raise ValueError("Total demand weight is non-positive")
    k_raw = TARGET_EDGES * (alloc_weights / total_q)
    k = np.floor(k_raw).astype(int)
    k = np.maximum(k, 1)

    remainder = TARGET_EDGES - int(k.sum())
    frac = k_raw - np.floor(k_raw)

    def apply_remainder(
        remainder_value: int,
        order: np.ndarray,
        min_value: int = 1,
        max_value: int | None = None,
    ) -> int:
        while remainder_value != 0:
            progressed = False
            for idx in order:
                if remainder_value == 0:
                    break
                if remainder_value > 0:
                    if max_value is None or k[idx] < max_value:
                        k[idx] += 1
                        remainder_value -= 1
                        progressed = True
                else:
                    if k[idx] > min_value:
                        k[idx] -= 1
                        remainder_value += 1
                        progressed = True
            if not progressed:
                break
        return remainder_value

    if remainder > 0:
        order = np.lexsort((np.array(iso_codes), -frac))
        remainder = apply_remainder(remainder, order, min_value=1, max_value=None)
    elif remainder < 0:
        order = np.lexsort((np.array(iso_codes), frac))
        remainder = apply_remainder(remainder, order, min_value=1, max_value=None)
        if remainder < 0:
            raise ValueError("Unable to resolve edge allocation with min=1")

    capped = k > MAX_EDGES_PER_COUNTRY
    if capped.any():
        k[capped] = MAX_EDGES_PER_COUNTRY
        remainder = TARGET_EDGES - int(k.sum())
        if remainder != 0:
            order = np.lexsort((np.array(iso_codes), -frac))
            remainder = apply_remainder(
                remainder,
                order,
                min_value=1,
                max_value=MAX_EDGES_PER_COUNTRY,
            )
        if remainder != 0:
            raise ValueError("Unable to resolve edge allocation after capping")

    return k, int(remainder)


def select_edges_for_country(
    rows: np.ndarray,
    cols: np.ndarray,
    pops: np.ndarray,
    k: int,
    min_sep_km: float,
    transform: rasterio.Affine,
    geod: Geod,
) -> tuple[list[tuple[float, float, float]], int]:
    order = np.lexsort((cols, rows, -pops))
    selected: list[tuple[float, float, float]] = []
    selected_rc: set[tuple[int, int]] = set()

    def accept_candidate(row: int, col: int, pop_val: float) -> None:
        lon, lat = rasterio.transform.xy(transform, row, col, offset="center")
        if lon <= -180.0:
            lon = -180.0 + EDGE_LON_EPS
        if lon > 180.0:
            lon = 180.0
        lat = max(-90.0, min(90.0, lat))
        selected.append((float(lat), float(lon), float(pop_val)))
        selected_rc.add((row, col))

    for idx in order:
        if len(selected) >= k:
            break
        row = int(rows[idx])
        col = int(cols[idx])
        pop_val = float(pops[idx])
        lon, lat = rasterio.transform.xy(transform, row, col, offset="center")
        if lon <= -180.0:
            lon = -180.0 + EDGE_LON_EPS
        if lon > 180.0:
            lon = 180.0
        lat = max(-90.0, min(90.0, lat))
        ok = True
        for existing in selected:
            _, _, dist_m = geod.inv(lon, lat, existing[1], existing[0])
            if dist_m < min_sep_km * 1000.0:
                ok = False
                break
        if ok:
            selected.append((float(lat), float(lon), pop_val))
            selected_rc.add((row, col))

    sep_relaxed = 0
    if len(selected) < k:
        for idx in order:
            if len(selected) >= k:
                break
            row = int(rows[idx])
            col = int(cols[idx])
            if (row, col) in selected_rc:
                continue
            pop_val = float(pops[idx])
            accept_candidate(row, col, pop_val)
            sep_relaxed += 1
    return selected, sep_relaxed


def synthetic_candidates_from_geometry(
    geom,
    k: int,
) -> list[tuple[float, float, float]]:
    minx, miny, maxx, maxy = geom.bounds
    target = max(k * 8, 64)
    grid_size = int(math.ceil(math.sqrt(target)))
    lons = np.linspace(minx, maxx, grid_size, dtype="float64")
    lats = np.linspace(miny, maxy, grid_size, dtype="float64")
    candidates: list[tuple[float, float, float]] = []
    for lat in lats[::-1]:
        for lon in lons:
            point = Point(float(lon), float(lat))
            if geom.contains(point):
                candidates.append((float(lat), float(lon), 0.0))
    if not candidates:
        point = geom.representative_point()
        candidates.append((float(point.y), float(point.x), 0.0))
    return candidates


def select_edges_from_candidates(
    candidates: list[tuple[float, float, float]],
    k: int,
    min_sep_km: float,
    geod: Geod,
) -> tuple[list[tuple[float, float, float]], int]:
    selected: list[tuple[float, float, float]] = []
    sep_relaxed = 0
    for lat, lon, pop_val in candidates:
        if len(selected) >= k:
            break
        ok = True
        for existing in selected:
            _, _, dist_m = geod.inv(lon, lat, existing[1], existing[0])
            if dist_m < min_sep_km * 1000.0:
                ok = False
                break
        if ok:
            selected.append((lat, lon, pop_val))
    if len(selected) < k:
        for lat, lon, pop_val in candidates:
            if len(selected) >= k:
                break
            if (lat, lon, pop_val) in selected:
                continue
            selected.append((lat, lon, pop_val))
            sep_relaxed += 1
    return selected, sep_relaxed


def fill_with_synthetic(
    selected: list[tuple[float, float, float]],
    candidates: list[tuple[float, float, float]],
    k: int,
    min_sep_km: float,
    geod: Geod,
) -> tuple[list[tuple[float, float, float]], int]:
    selected_set = {(lat, lon) for lat, lon, _ in selected}
    sep_relaxed = 0
    for lat, lon, pop_val in candidates:
        if len(selected) >= k:
            break
        if (lat, lon) in selected_set:
            continue
        ok = True
        for existing in selected:
            _, _, dist_m = geod.inv(lon, lat, existing[1], existing[0])
            if dist_m < min_sep_km * 1000.0:
                ok = False
                break
        if ok:
            selected.append((lat, lon, pop_val))
            selected_set.add((lat, lon))
    if len(selected) < k:
        for lat, lon, pop_val in candidates:
            if len(selected) >= k:
                break
            if (lat, lon) in selected_set:
                continue
            selected.append((lat, lon, pop_val))
            selected_set.add((lat, lon))
            sep_relaxed += 1
    return selected, sep_relaxed


def main() -> None:
    iso_set = load_iso_set(ISO_PATH)
    world = gpd.read_parquet(WORLD_PATH).copy()
    if "geom" in world.columns:
        world = world.set_geometry("geom")
    if world.crs is None:
        world = world.set_crs("EPSG:4326")
    world["country_iso"] = world["country_iso"].astype(str).str.upper()
    world = world[world["country_iso"].isin(iso_set)].copy()
    world.sort_values("country_iso", inplace=True)
    world.reset_index(drop=True, inplace=True)

    world_set = set(world["country_iso"].tolist())
    missing_iso = sorted(iso_set - world_set)
    missing_fraction = len(missing_iso) / max(len(iso_set), 1)
    if missing_fraction > MISSING_POLYGON_MAX_FRACTION:
        missing_note = f"missing_polygons={len(missing_iso)}/{len(iso_set)}"
    else:
        missing_note = f"missing_polygons={len(missing_iso)}/{len(iso_set)}"

    pop, country_id, transform = build_population_surface(POP_PATH, world)
    flat_id = country_id.ravel()
    flat_pop = pop.ravel()
    order = np.argsort(flat_id, kind="stable")
    sorted_ids = flat_id[order]

    world_area = world.to_crs("EPSG:6933")
    area_km2 = (world_area.geometry.area / 1_000_000.0).to_numpy()

    iso_codes = world["country_iso"].tolist()
    pop_values = np.zeros(len(iso_codes), dtype="float64")
    pop_fallback = 0
    for idx in range(1, len(iso_codes) + 1):
        start = np.searchsorted(sorted_ids, idx, side="left")
        end = np.searchsorted(sorted_ids, idx, side="right")
        if start == end:
            pop_val = 0.0
        else:
            pop_val = float(flat_pop[order[start:end]].sum())
        if not math.isfinite(pop_val) or pop_val <= 0.0:
            pop_val = float(area_km2[idx - 1])
            pop_fallback += 1
        pop_values[idx - 1] = pop_val

    if pop_fallback / max(len(iso_codes), 1) > POP_FALLBACK_MAX_FRACTION:
        raise ValueError("Population fallback exceeds threshold")

    q_values = np.power(pop_values, POP_EXP)
    if not np.all(np.isfinite(q_values)):
        raise ValueError("Non-finite demand weights")

    k_alloc, _ = allocate_edges_per_country(q_values, iso_codes)

    geod = Geod(ellps="WGS84")
    edges: list[dict[str, object]] = []
    weights: list[float] = []
    sep_relaxed_total = 0
    synthetic_countries: list[str] = []

    for idx, iso in enumerate(iso_codes):
        start = np.searchsorted(sorted_ids, idx + 1, side="left")
        end = np.searchsorted(sorted_ids, idx + 1, side="right")
        flat_idx = order[start:end]
        min_sep = MIN_SEP_TINY_KM if area_km2[idx] < TINY_COUNTRY_AREA_KM2 else MIN_SEP_KM
        if flat_idx.size == 0:
            synthetic_countries.append(iso)
            candidates = synthetic_candidates_from_geometry(world.geometry.iloc[idx], int(k_alloc[idx]))
            selected, sep_relaxed = select_edges_from_candidates(
                candidates=candidates,
                k=int(k_alloc[idx]),
                min_sep_km=min_sep,
                geod=geod,
            )
        else:
            rows = (flat_idx // pop.shape[1]).astype("int32")
            cols = (flat_idx % pop.shape[1]).astype("int32")
            pops = flat_pop[flat_idx].astype("float64")
            selected, sep_relaxed = select_edges_for_country(
                rows=rows,
                cols=cols,
                pops=pops,
                k=int(k_alloc[idx]),
                min_sep_km=min_sep,
                transform=transform,
                geod=geod,
            )
            if len(selected) < int(k_alloc[idx]):
                synthetic_countries.append(iso)
                candidates = synthetic_candidates_from_geometry(world.geometry.iloc[idx], int(k_alloc[idx]))
                selected, extra_relaxed = fill_with_synthetic(
                    selected=selected,
                    candidates=candidates,
                    k=int(k_alloc[idx]),
                    min_sep_km=min_sep,
                    geod=geod,
                )
                sep_relaxed += extra_relaxed
        sep_relaxed_total += sep_relaxed

        if len(selected) != int(k_alloc[idx]):
            raise ValueError(f"Edge selection count mismatch for {iso}")

        edge_pops = np.array([item[2] for item in selected], dtype="float64")
        add_term = pop_values[idx] / (ADD_TERM_DIVISOR * max(k_alloc[idx], 1))
        w_raw = np.power(edge_pops + add_term, EDGE_EXP)
        if w_raw.sum() <= 0:
            raise ValueError(f"Non-positive weights for {iso}")
        w_country = w_raw / w_raw.sum() * q_values[idx]

        for j, (lat, lon, _pop_val) in enumerate(selected, start=1):
            edge_id = f"{iso}-EDGE-{j:03d}"
            edges.append(
                {
                    "edge_id": edge_id,
                    "ip_country": iso,
                    "edge_lat": clean_float(lat),
                    "edge_lon": clean_float(lon),
                }
            )
        weights.extend(w_country.tolist())

    if sep_relaxed_total / max(len(edges), 1) > SEP_RELAX_MAX_FRACTION:
        raise ValueError("Separation relaxation exceeds threshold")

    weights_arr = np.array(weights, dtype="float64")
    weights_arr = weights_arr / weights_arr.sum()
    weights_arr = np.maximum(weights_arr, WEIGHT_FLOOR)
    weights_arr = weights_arr / weights_arr.sum()

    for edge, weight in zip(edges, weights_arr):
        edge["weight"] = clean_float(weight)

    edges.sort(key=lambda item: (item["ip_country"], item["edge_id"]))

    if len(edges) != TARGET_EDGES:
        raise ValueError("Target edge count mismatch")
    if len({edge["edge_id"] for edge in edges}) != len(edges):
        raise ValueError("Duplicate edge_id detected")

    coverage = len({edge["ip_country"] for edge in edges})
    if coverage < max(200, math.ceil(0.85 * len(iso_codes))):
        raise ValueError("Coverage threshold not met")

    weights_sorted = np.sort(weights_arr)[::-1]
    top1 = weights_sorted[: max(1, int(round(0.01 * len(weights_sorted))))].sum()
    top5 = weights_sorted[: max(1, int(round(0.05 * len(weights_sorted))))].sum()
    if not (top1 >= 0.10 or top5 >= 0.30):
        raise ValueError("Heavy-tail check failed")
    if abs(weights_arr.sum() - 1.0) > 1e-9:
        raise ValueError("Weight sum check failed")

    outside = 0
    outside_far = 0
    for edge in edges:
        iso = edge["ip_country"]
        geom = world.loc[world["country_iso"] == iso, world.geometry.name].iloc[0]
        point = Point(edge["edge_lon"], edge["edge_lat"])
        if not geom.covers(point):
            outside += 1
            nearest = nearest_points(geom, point)[0]
            _, _, dist_m = geod.inv(
                edge["edge_lon"],
                edge["edge_lat"],
                nearest.x,
                nearest.y,
            )
            if dist_m > 5_000:
                outside_far += 1
    if outside_far > 0:
        raise ValueError("Point-in-polygon failure beyond tolerance")
    if outside / max(len(edges), 1) > 0.005:
        raise ValueError("Point-in-polygon failure rate exceeded")

    missing_list = ",".join(missing_iso) if missing_iso else "none"
    synthetic_list = ",".join(sorted(set(synthetic_countries))) if synthetic_countries else "none"
    notes = (
        "Generated deterministically from iso3166_canonical_2024 + world_countries + "
        "population_raster_2025; TARGET_EDGES=2000; Q=POP^0.90; "
        "k_alloc=Q^0.30; w=(p+POP/(10k))^0.85; "
        f"{missing_note} (excluded={missing_list}); "
        f"pop_fallback={pop_fallback}/{len(iso_codes)}; "
        f"sep_relaxed={sep_relaxed_total}/{len(edges)}; "
        f"synthetic_candidates={synthetic_list}."
    )

    policy = {
        "policy_id": POLICY_ID,
        "version_tag": VERSION_TAG,
        "edges": edges,
        "notes": notes,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(canonical_json(policy) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
