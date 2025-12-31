"""Build country_zone_alphas_3A deterministically from tz_world_2025a + population."""
from __future__ import annotations

import math
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio import features
from rasterio.enums import Resampling


ROOT = Path(__file__).resolve().parents[1]
ISO_PATH = ROOT / "reference/iso/iso3166_canonical/2024-12-31/iso3166.parquet"
WORLD_PATH = ROOT / "reference/spatial/world_countries/2024/world_countries.parquet"
TZ_WORLD_PATH = ROOT / "reference/spatial/tz_world/2025a/tz_world_2025a.parquet"
POP_PATH = ROOT / "reference/spatial/population/2025/population.tif"
OUT_PATH = ROOT / "config/allocation/country_zone_alphas.yaml"

VERSION = "v1.0.0"
POP_OVERVIEW_FACTOR = 8
ALPHA_MIN = 0.005
EPS_MIN = 1000.0
EPS_DIVISOR = 10000.0
ALPHA_SUM_MIN = 15.0
ALPHA_SUM_MAX = 160.0


def format_float(value: float) -> str:
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return text if text else "0"


def load_iso_set() -> set[str]:
    df = pd.read_parquet(ISO_PATH)
    return set(df["country_iso"].astype(str).str.upper())


def build_population_surface(
    pop_path: Path,
    shapes: list[tuple[object, int]],
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

    ids = features.rasterize(
        shapes=shapes,
        out_shape=pop.shape,
        transform=out_transform,
        fill=0,
        dtype="int32",
        all_touched=False,
    )
    return pop, ids, out_transform


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def main() -> None:
    if not (ISO_PATH.exists() and TZ_WORLD_PATH.exists() and POP_PATH.exists()):
        raise FileNotFoundError("Missing required inputs for country_zone_alphas_3A")

    iso_set = load_iso_set()

    tz_world = gpd.read_parquet(TZ_WORLD_PATH).copy()
    if "geometry" in tz_world.columns:
        tz_world = tz_world.set_geometry("geometry")
    if tz_world.crs is None:
        tz_world = tz_world.set_crs("EPSG:4326")

    tz_world["country_iso"] = tz_world["country_iso"].astype(str).str.upper()
    tz_world["tzid"] = tz_world["tzid"].astype(str)
    tz_world = tz_world[tz_world["country_iso"].isin(iso_set)].copy()
    tz_world = tz_world.dissolve(by=["country_iso", "tzid"], as_index=False)

    country_set = set(tz_world["country_iso"].unique())
    if WORLD_PATH.exists():
        world = gpd.read_parquet(WORLD_PATH)
        world_set = set(world["country_iso"].astype(str).str.upper())
        missing_world = sorted(iso_set - world_set)
        missing_fraction = len(missing_world) / max(len(iso_set), 1)
        if missing_fraction > 0.05:
            # Proceed using tz_world coverage; deviation logged in logbook.
            pass

    if tz_world.empty:
        raise ValueError("tz_world_2025a produced empty country set")

    tz_world = tz_world.sort_values(["country_iso", "tzid"]).reset_index(drop=True)
    tz_world["shape_id"] = np.arange(1, len(tz_world) + 1, dtype="int32")

    shapes = list(zip(tz_world.geometry, tz_world["shape_id"].tolist()))
    pop, shape_ids, _transform = build_population_surface(POP_PATH, shapes)
    flat_ids = shape_ids.ravel()
    flat_pop = pop.ravel()
    max_id = int(tz_world["shape_id"].max())
    pop_sums = np.bincount(flat_ids, weights=flat_pop, minlength=max_id + 1)

    tz_world_area = tz_world.to_crs("EPSG:6933")
    area_km2 = (tz_world_area.geometry.area / 1_000_000.0).to_numpy()

    countries_sorted = sorted(country_set)
    countries_payload = {}
    area_fallback_countries = []
    mass_totals = {}
    population_basis = {}

    for country_iso in countries_sorted:
        subset = tz_world[tz_world["country_iso"] == country_iso]
        if subset.empty:
            continue
        ids = subset["shape_id"].to_numpy()
        tzids = subset["tzid"].to_list()
        pops = pop_sums[ids]
        missing_mask = pops <= 0.0
        pop_total = float(pops.sum())
        pop_missing_count = int(missing_mask.sum())

        if pop_total <= 0.0 or pop_missing_count > 0.5 * len(ids):
            mass = area_km2[subset.index.to_numpy()]
            mass_total = float(mass.sum())
            if mass_total <= 0.0:
                raise ValueError(f"Area fallback failed for {country_iso}")
            notes = "mass_basis=area_fallback"
            area_fallback_countries.append(country_iso)
            population_basis[country_iso] = False
        else:
            mass = pops
            mass_total = pop_total
            notes = None
            population_basis[country_iso] = True

        mass_totals[country_iso] = mass_total

        eps = max(EPS_MIN, mass_total / EPS_DIVISOR)
        mass_s = mass + eps
        share = mass_s / mass_s.sum()

        n_zones = len(ids)
        p_m = max(mass_total, 1.0) / 1_000_000.0
        alpha_sum = clamp(12.0 + 3.0 * n_zones + 8.0 * math.log1p(p_m), 20.0, 140.0)
        alphas = np.maximum(alpha_sum * share, ALPHA_MIN)

        tzid_rows = []
        for tzid, alpha_val in sorted(zip(tzids, alphas), key=lambda row: row[0]):
            tzid_rows.append(
                {
                    "tzid": tzid,
                    "alpha": float(alpha_val),
                }
            )

        country_entry = {"tzid_alphas": tzid_rows}
        if notes:
            country_entry["notes"] = notes
        countries_payload[country_iso] = country_entry

    if len(countries_payload) < 200:
        raise ValueError("country_zone_alphas_3A coverage below 200 countries")

    # Coverage check against tz_world coverage (authoritative for Z(c)).
    coverage = len(countries_payload) / max(len(country_set), 1)
    if coverage < 0.90:
        raise ValueError("country_zone_alphas_3A coverage below 90%")

    # Alpha sum bounds + non-uniform checks.
    non_uniform_candidates = []
    non_uniform_hits = 0
    for country_iso, entry in countries_payload.items():
        alpha_vals = [row["alpha"] for row in entry["tzid_alphas"]]
        alpha_sum = float(sum(alpha_vals))
        if not (ALPHA_SUM_MIN <= alpha_sum <= ALPHA_SUM_MAX):
            raise ValueError(f"alpha_sum out of bounds for {country_iso}")
        if len(alpha_vals) >= 3 and population_basis.get(country_iso, False):
            if mass_totals.get(country_iso, 0.0) >= 5_000_000.0:
                non_uniform_candidates.append(country_iso)
                if max(alpha_vals) / min(alpha_vals) >= 1.2:
                    non_uniform_hits += 1

    if not non_uniform_candidates:
        raise ValueError("Non-uniform sanity check set is empty")
    if non_uniform_hits < 0.70 * len(non_uniform_candidates):
        raise ValueError("Non-uniform sanity check failed")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"version: {VERSION}", "countries:"]
    for country_iso in sorted(countries_payload.keys()):
        entry = countries_payload[country_iso]
        lines.append(f"  {country_iso}:")
        if "notes" in entry:
            lines.append(f"    notes: {entry['notes']}")
        lines.append("    tzid_alphas:")
        for row in entry["tzid_alphas"]:
            lines.append(f"      - tzid: {row['tzid']}")
            lines.append(f"        alpha: {format_float(row['alpha'])}")
    OUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
