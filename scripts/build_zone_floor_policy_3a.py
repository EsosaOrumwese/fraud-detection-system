"""Build zone_floor_policy_3A deterministically from tz_world_2025a."""
from __future__ import annotations

import math
from pathlib import Path

import geopandas as gpd


ROOT = Path(__file__).resolve().parents[1]
TZ_WORLD_PATH = ROOT / "reference/spatial/tz_world/2025a/tz_world_2025a.parquet"
OUT_PATH = ROOT / "config/allocation/zone_floor_policy.yaml"

VERSION = "v1.0.0"
PHI_MIN = 0.01
PHI_MAX = 0.12
DOMINANT_BUMP_THRESHOLD = 0.60
DOMINANT_S_THRESHOLD = 0.60
DOMINANT_BOOST = 1.25
MAX_FLOOR_VALUE = 0.25


def format_float(value: float) -> str:
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return text if text else "0"


def main() -> None:
    if not TZ_WORLD_PATH.exists():
        raise FileNotFoundError(f"Missing tz_world_2025a: {TZ_WORLD_PATH}")

    tz_world = gpd.read_parquet(TZ_WORLD_PATH)
    tz_world["tzid"] = tz_world["tzid"].astype(str)
    tz_world["country_iso"] = tz_world["country_iso"].astype(str).str.upper()

    tz_country_counts = (
        tz_world.groupby("tzid")["country_iso"].nunique().sort_index()
    )
    if tz_country_counts.empty:
        raise ValueError("tz_world_2025a produced no tzid rows")

    k_max = int(tz_country_counts.max())
    if k_max <= 0:
        raise ValueError("tz_world_2025a has non-positive country counts")

    floors = []
    for tzid, k_val in tz_country_counts.items():
        s_val = math.log1p(k_val) / math.log1p(k_max)
        bump_threshold = DOMINANT_BUMP_THRESHOLD if s_val >= DOMINANT_S_THRESHOLD else 0.0
        floor_value = PHI_MIN + (PHI_MAX - PHI_MIN) * math.sqrt(s_val)
        if bump_threshold == DOMINANT_BUMP_THRESHOLD:
            floor_value *= DOMINANT_BOOST
        floor_value = min(max(floor_value, 0.0), MAX_FLOOR_VALUE)
        floors.append(
            {
                "tzid": tzid,
                "floor_value": floor_value,
                "bump_threshold": bump_threshold,
            }
        )

    floors_sorted = sorted(floors, key=lambda row: row["tzid"])
    tzid_set = {row["tzid"] for row in floors_sorted}

    if len(floors_sorted) != len(tz_country_counts):
        raise ValueError("tzid coverage mismatch for zone floor policy")
    if len(tzid_set) != len(floors_sorted):
        raise ValueError("Duplicate tzid in zone floor policy")

    floor_values = [row["floor_value"] for row in floors_sorted]
    bump_values = [row["bump_threshold"] for row in floors_sorted]
    count_ge_005 = sum(1 for value in floor_values if value >= 0.05)
    count_gt_0 = sum(1 for value in floor_values if value > 0.0)
    bump_060 = sum(1 for value in bump_values if value == DOMINANT_BUMP_THRESHOLD)
    bump_000 = sum(1 for value in bump_values if value == 0.0)

    if count_ge_005 < 50:
        raise ValueError("Too few tzids with floor_value >= 0.05")
    if count_gt_0 < 200:
        raise ValueError("Too few tzids with floor_value > 0.0")
    if bump_060 < 0.10 * len(floors_sorted):
        raise ValueError("Too few tzids with bump_threshold=0.60")
    if bump_000 < 0.50 * len(floors_sorted):
        raise ValueError("Too few tzids with bump_threshold=0.00")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"version: {VERSION}", "floors:"]
    for row in floors_sorted:
        lines.append(f"  - tzid: {row['tzid']}")
        lines.append(f"    floor_value: {format_float(row['floor_value'])}")
        lines.append(f"    bump_threshold: {format_float(row['bump_threshold'])}")
    OUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
