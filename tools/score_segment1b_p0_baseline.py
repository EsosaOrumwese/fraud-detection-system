"""Build Segment 1B P0 baseline scorecard and companion tables.

This tool materializes the P0 authority baseline artifact set from one completed
run-id:
- baseline scorecard JSON,
- country-share CSV,
- region-share CSV,
- nearest-neighbor quantile CSV.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl
from scipy.spatial import cKDTree


EARTH_RADIUS_M = 6_371_008.8


@dataclass(frozen=True)
class RunContext:
    run_root: Path
    run_id: str
    seed: int
    manifest_fingerprint: str
    parameter_hash: str


def _now_utc() -> str:
    return (
        datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )


def _gini(values: list[int]) -> float:
    if not values:
        return 0.0
    vals = sorted(v for v in values if v >= 0)
    total = float(sum(vals))
    n = len(vals)
    if n == 0 or total <= 0:
        return 0.0
    weighted = sum((2 * (idx + 1) - n - 1) * value for idx, value in enumerate(vals))
    return float(weighted / (n * total))


def _top_share(values_desc: list[int], fraction: float) -> float:
    if not values_desc:
        return 0.0
    total = float(sum(values_desc))
    if total <= 0:
        return 0.0
    k = max(1, math.ceil(fraction * len(values_desc)))
    return float(sum(values_desc[:k]) / total)


def _nn_distances_m(lat_deg: np.ndarray, lon_deg: np.ndarray) -> np.ndarray:
    if lat_deg.size < 2:
        return np.array([], dtype=np.float64)
    lat_rad = np.radians(lat_deg.astype(np.float64))
    lon_rad = np.radians(lon_deg.astype(np.float64))
    cos_lat = np.cos(lat_rad)
    xyz = np.column_stack(
        (
            cos_lat * np.cos(lon_rad),
            cos_lat * np.sin(lon_rad),
            np.sin(lat_rad),
        )
    )
    tree = cKDTree(xyz)
    distances, _ = tree.query(xyz, k=2)
    chord = np.clip(distances[:, 1], 0.0, 2.0)
    arc = 2.0 * np.arcsin(np.clip(chord / 2.0, 0.0, 1.0))
    return arc * EARTH_RADIUS_M


def _quantile_map(values: np.ndarray, qs: list[float]) -> dict[str, float]:
    if values.size == 0:
        return {f"q{int(q * 100):02d}": 0.0 for q in qs}
    out: dict[str, float] = {}
    for q in qs:
        out[f"q{int(q * 100):02d}"] = float(np.quantile(values, q))
    return out


def _load_run_context(runs_root: Path, run_id: str) -> RunContext:
    run_root = runs_root / run_id
    receipt_path = run_root / "run_receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    return RunContext(
        run_root=run_root,
        run_id=run_id,
        seed=int(receipt["seed"]),
        manifest_fingerprint=str(receipt["manifest_fingerprint"]),
        parameter_hash=str(receipt["parameter_hash"]),
    )


def _resolve_site_locations(ctx: RunContext) -> Path:
    root = (
        ctx.run_root
        / "data"
        / "layer1"
        / "1B"
        / "site_locations"
        / f"seed={ctx.seed}"
        / f"manifest_fingerprint={ctx.manifest_fingerprint}"
    )
    return next(root.glob("*.parquet"))


def _resolve_s4_alloc_plan(ctx: RunContext) -> Path:
    root = (
        ctx.run_root
        / "data"
        / "layer1"
        / "1B"
        / "s4_alloc_plan"
        / f"seed={ctx.seed}"
        / f"parameter_hash={ctx.parameter_hash}"
        / f"manifest_fingerprint={ctx.manifest_fingerprint}"
    )
    return next(root.glob("*.parquet"))


def _resolve_report(ctx: RunContext, state: str, filename: str) -> Path:
    reports_root = ctx.run_root / "reports" / "layer1" / "1B"
    if state == "S2":
        path = reports_root / "state=S2" / f"parameter_hash={ctx.parameter_hash}" / filename
    elif state == "S4":
        path = (
            reports_root
            / "state=S4"
            / f"seed={ctx.seed}"
            / f"parameter_hash={ctx.parameter_hash}"
            / f"manifest_fingerprint={ctx.manifest_fingerprint}"
            / filename
        )
    elif state == "S6":
        path = (
            reports_root
            / "state=S6"
            / f"seed={ctx.seed}"
            / f"parameter_hash={ctx.parameter_hash}"
            / f"manifest_fingerprint={ctx.manifest_fingerprint}"
            / filename
        )
    elif state == "S8":
        path = (
            reports_root
            / "state=S8"
            / f"seed={ctx.seed}"
            / f"manifest_fingerprint={ctx.manifest_fingerprint}"
            / filename
        )
    else:
        raise ValueError(f"Unsupported state: {state}")
    return path


def _load_region_lookup(repo_root: Path) -> dict[str, str]:
    candidates = [
        repo_root
        / "reference"
        / "_untracked"
        / "reference"
        / "layer1"
        / "iso_canonical"
        / "v2025-10-09"
        / "iso_canonical.csv",
        repo_root
        / "reference"
        / "_untracked"
        / "reference"
        / "layer1"
        / "iso_canonical"
        / "v2025-10-08"
        / "iso_canonical.csv",
    ]
    for path in candidates:
        if path.exists():
            mapping: dict[str, str] = {}
            with path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    iso = (row.get("country_iso") or "").strip().upper()
                    region = (row.get("region") or "").strip() or "Unknown"
                    if iso:
                        mapping[iso] = region
            if mapping:
                return mapping

    fallback_parquet = (
        repo_root / "reference" / "iso" / "iso3166_canonical" / "2024-12-31" / "iso3166.parquet"
    )
    if fallback_parquet.exists():
        frame = pl.read_parquet(fallback_parquet)
        mapping = {}
        for row in frame.select(["country_iso", "region"]).to_dicts():
            iso = str(row["country_iso"]).upper()
            region = "Unknown" if row["region"] in (None, "") else str(row["region"])
            mapping[iso] = region
        return mapping

    return {}


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def build_baseline(ctx: RunContext, repo_root: Path, output_root: Path) -> dict[str, Any]:
    site_path = _resolve_site_locations(ctx)
    s4_path = _resolve_s4_alloc_plan(ctx)
    s2_report_path = _resolve_report(ctx, "S2", "s2_run_report.json")
    s4_report_path = _resolve_report(ctx, "S4", "s4_run_report.json")
    s6_report_path = _resolve_report(ctx, "S6", "s6_run_report.json")
    s8_report_path = _resolve_report(ctx, "S8", "s8_run_summary.json")

    s2_report = json.loads(s2_report_path.read_text(encoding="utf-8"))
    s4_report = json.loads(s4_report_path.read_text(encoding="utf-8"))
    s6_report = json.loads(s6_report_path.read_text(encoding="utf-8"))
    s8_report = json.loads(s8_report_path.read_text(encoding="utf-8"))

    site_df = pl.read_parquet(site_path).select(
        ["legal_country_iso", "lat_deg", "lon_deg", "merchant_id", "site_order"]
    )
    s4_df = pl.read_parquet(s4_path).select(["legal_country_iso", "n_sites_tile"])

    country_counts_df = (
        site_df.group_by("legal_country_iso")
        .len()
        .rename({"legal_country_iso": "country_iso", "len": "site_count"})
        .sort("site_count", descending=True)
    )
    country_counts_rows = country_counts_df.to_dicts()
    active_country_count = int(country_counts_df.height)
    total_sites = int(site_df.height)
    site_counts_desc = [int(row["site_count"]) for row in country_counts_rows]

    country_gini = _gini(site_counts_desc)
    top1_share = _top_share(site_counts_desc, 0.01)
    top5_share = _top_share(site_counts_desc, 0.05)
    top10_share = _top_share(site_counts_desc, 0.10)

    eligible_countries_total = int(s2_report.get("countries_total", 0))
    eligible_country_nonzero_share = (
        float(active_country_count / eligible_countries_total)
        if eligible_countries_total > 0
        else 0.0
    )
    southern_hemisphere_share = float((site_df["lat_deg"] < 0.0).sum() / total_sites) if total_sites else 0.0

    nn_distances = _nn_distances_m(
        site_df["lat_deg"].to_numpy(), site_df["lon_deg"].to_numpy()
    )
    nn_quantiles = _quantile_map(nn_distances, [0.50, 0.75, 0.90, 0.95, 0.99])
    nn_ratio_p99_p50 = (
        float(nn_quantiles["q99"] / nn_quantiles["q50"]) if nn_quantiles["q50"] > 0 else 0.0
    )

    region_lookup = _load_region_lookup(repo_root)
    country_share_rows: list[dict[str, Any]] = []
    cumulative = 0.0
    for rank, row in enumerate(country_counts_rows, start=1):
        count = int(row["site_count"])
        share = float(count / total_sites) if total_sites else 0.0
        cumulative += share
        iso = str(row["country_iso"])
        country_share_rows.append(
            {
                "rank": rank,
                "country_iso": iso,
                "region": region_lookup.get(iso, "Unknown"),
                "site_count": count,
                "share": share,
                "cumulative_share": cumulative,
            }
        )

    region_rollup: dict[str, dict[str, Any]] = {}
    for row in country_share_rows:
        region = str(row["region"])
        bucket = region_rollup.setdefault(
            region,
            {"region": region, "site_count": 0, "active_countries": 0},
        )
        bucket["site_count"] += int(row["site_count"])
        bucket["active_countries"] += 1

    region_share_rows = []
    for bucket in region_rollup.values():
        site_count = int(bucket["site_count"])
        region_share_rows.append(
            {
                "region": bucket["region"],
                "site_count": site_count,
                "active_countries": int(bucket["active_countries"]),
                "share": float(site_count / total_sites) if total_sites else 0.0,
            }
        )
    region_share_rows.sort(key=lambda row: row["share"], reverse=True)

    nn_rows = []
    for q_label, value in nn_quantiles.items():
        nn_rows.append({"scope": "global", "quantile": q_label, "distance_m": value})

    top_country_for_nn = [row["country_iso"] for row in country_share_rows[:20]]
    for iso in top_country_for_nn:
        subset = site_df.filter(pl.col("legal_country_iso") == iso)
        if subset.height < 2:
            continue
        d = _nn_distances_m(subset["lat_deg"].to_numpy(), subset["lon_deg"].to_numpy())
        q = _quantile_map(d, [0.50, 0.95, 0.99])
        for q_label, value in q.items():
            nn_rows.append({"scope": f"country:{iso}", "quantile": q_label, "distance_m": value})

    s4_country_df = (
        s4_df.group_by("legal_country_iso")
        .agg(pl.col("n_sites_tile").sum().alias("assigned_sites"))
        .sort("assigned_sites", descending=True)
    )
    s4_country_rows = s4_country_df.to_dicts()
    s4_counts_desc = [int(row["assigned_sites"]) for row in s4_country_rows]
    s4_total = int(sum(s4_counts_desc))
    s4_metrics = {
        "countries_active": int(s4_country_df.height),
        "assigned_sites_total": s4_total,
        "country_gini": _gini(s4_counts_desc),
        "top1_share": _top_share(s4_counts_desc, 0.01),
        "top5_share": _top_share(s4_counts_desc, 0.05),
        "top10_share": _top_share(s4_counts_desc, 0.10),
    }

    b_thresholds = {
        "country_gini_max": 0.68,
        "top10_share_max": 0.50,
        "top5_share_max": 0.33,
        "top1_share_max": 0.10,
        "eligible_country_nonzero_share_min": 0.85,
        "southern_hemisphere_share_min": 0.12,
    }
    bplus_thresholds = {
        "country_gini_max": 0.60,
        "top10_share_max": 0.42,
        "top5_share_max": 0.27,
        "top1_share_max": 0.08,
        "eligible_country_nonzero_share_min": 0.92,
        "southern_hemisphere_share_min": 0.18,
    }

    metrics = {
        "country_gini": country_gini,
        "top1_share": top1_share,
        "top5_share": top5_share,
        "top10_share": top10_share,
        "eligible_country_nonzero_share": eligible_country_nonzero_share,
        "southern_hemisphere_share": southern_hemisphere_share,
        "nn_p99_p50_ratio": nn_ratio_p99_p50,
        "active_country_count": active_country_count,
        "eligible_country_total": eligible_countries_total,
        "site_count_total": total_sites,
    }

    b_eval = {
        "country_gini": metrics["country_gini"] <= b_thresholds["country_gini_max"],
        "top10_share": metrics["top10_share"] <= b_thresholds["top10_share_max"],
        "top5_share": metrics["top5_share"] <= b_thresholds["top5_share_max"],
        "top1_share": metrics["top1_share"] <= b_thresholds["top1_share_max"],
        "eligible_country_nonzero_share": metrics["eligible_country_nonzero_share"]
        >= b_thresholds["eligible_country_nonzero_share_min"],
        "southern_hemisphere_share": metrics["southern_hemisphere_share"]
        >= b_thresholds["southern_hemisphere_share_min"],
    }
    bplus_eval = {
        "country_gini": metrics["country_gini"] <= bplus_thresholds["country_gini_max"],
        "top10_share": metrics["top10_share"] <= bplus_thresholds["top10_share_max"],
        "top5_share": metrics["top5_share"] <= bplus_thresholds["top5_share_max"],
        "top1_share": metrics["top1_share"] <= bplus_thresholds["top1_share_max"],
        "eligible_country_nonzero_share": metrics["eligible_country_nonzero_share"]
        >= bplus_thresholds["eligible_country_nonzero_share_min"],
        "southern_hemisphere_share": metrics["southern_hemisphere_share"]
        >= bplus_thresholds["southern_hemisphere_share_min"],
    }

    prefix = f"segment1b_p0_baseline_{ctx.run_id}"
    output_root.mkdir(parents=True, exist_ok=True)
    country_csv = output_root / f"{prefix}_country_share.csv"
    region_csv = output_root / f"{prefix}_region_share.csv"
    nn_csv = output_root / f"{prefix}_nn_quantiles.csv"
    score_json = output_root / f"{prefix}.json"

    _write_csv(
        country_csv,
        country_share_rows,
        ["rank", "country_iso", "region", "site_count", "share", "cumulative_share"],
    )
    _write_csv(region_csv, region_share_rows, ["region", "site_count", "active_countries", "share"])
    _write_csv(nn_csv, nn_rows, ["scope", "quantile", "distance_m"])

    payload = {
        "generated_utc": _now_utc(),
        "phase": "P0",
        "segment": "1B",
        "baseline_authority": {
            "run_id": ctx.run_id,
            "seed": ctx.seed,
            "manifest_fingerprint": ctx.manifest_fingerprint,
            "parameter_hash": ctx.parameter_hash,
            "run_root": str(ctx.run_root.as_posix()),
        },
        "artifacts": {
            "scorecard_json": str(score_json.as_posix()),
            "country_share_csv": str(country_csv.as_posix()),
            "region_share_csv": str(region_csv.as_posix()),
            "nn_quantiles_csv": str(nn_csv.as_posix()),
        },
        "metrics": metrics,
        "nn_quantiles_global_m": nn_quantiles,
        "thresholds": {"B": b_thresholds, "Bplus": bplus_thresholds},
        "threshold_eval": {
            "B": {"all_pass": all(b_eval.values()), "checks": b_eval},
            "Bplus": {"all_pass": all(bplus_eval.values()), "checks": bplus_eval},
        },
        "checkpoints": {
            "S2": {
                "basis": s2_report.get("basis"),
                "dp": s2_report.get("dp"),
                "countries_total": s2_report.get("countries_total"),
                "rows_emitted": s2_report.get("rows_emitted"),
                "tile_count_quantiles": _quantile_map(
                    np.array([float(row["tiles"]) for row in s2_report.get("country_summaries", [])]),
                    [0.50, 0.95, 0.99],
                ),
                "mass_sum_quantiles": _quantile_map(
                    np.array([float(row["mass_sum"]) for row in s2_report.get("country_summaries", [])]),
                    [0.50, 0.95, 0.99],
                ),
            },
            "S4": {
                "run_report_rows_emitted": s4_report.get("rows_emitted"),
                "run_report_pairs_total": s4_report.get("pairs_total"),
                "run_report_merchants_total": s4_report.get("merchants_total"),
                "alloc_sum_equals_requirements": s4_report.get("alloc_sum_equals_requirements"),
                "country_allocation_profile": s4_metrics,
            },
            "S6": {
                "sites_total": s6_report.get("counts", {}).get("sites_total"),
                "resamples_total": s6_report.get("counts", {}).get("resamples_total"),
                "attempt_histogram": s6_report.get("attempt_histogram", {}),
                "resample_rate": (
                    float(s6_report.get("counts", {}).get("resamples_total", 0))
                    / float(max(1, s6_report.get("counts", {}).get("sites_total", 0)))
                ),
            },
            "S8": {
                "rows_s7": s8_report.get("sizes", {}).get("rows_s7"),
                "rows_s8": s8_report.get("sizes", {}).get("rows_s8"),
                "parity_ok": s8_report.get("sizes", {}).get("parity_ok"),
                "validation_counters": s8_report.get("validation_counters", {}),
            },
            "S6_S8_geometry": {
                "nn_p99_p50_ratio": nn_ratio_p99_p50,
                "southern_hemisphere_share": southern_hemisphere_share,
                "north_hemisphere_share": float(1.0 - southern_hemisphere_share),
                "top_country_count_used_for_nn": len(top_country_for_nn),
            },
        },
        "companion_tables": {
            "country_share_top10": country_share_rows[:10],
            "region_share_all": region_share_rows,
        },
        "p0_readiness": {
            "baseline_scorecard_materialized": True,
            "state_checkpoints_materialized": True,
            "companion_tables_materialized": True,
        },
    }

    score_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-root", required=True, help="Root containing run-id folders.")
    parser.add_argument("--run-id", required=True, help="Baseline authority run-id.")
    parser.add_argument(
        "--output-root",
        default="runs/fix-data-engine/segment_1B/reports",
        help="Where to write baseline artifacts.",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root used for optional region lookup references.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    runs_root = Path(args.runs_root).resolve()
    output_root = Path(args.output_root).resolve()
    repo_root = Path(args.repo_root).resolve()

    ctx = _load_run_context(runs_root, str(args.run_id))
    payload = build_baseline(ctx, repo_root=repo_root, output_root=output_root)

    print(
        json.dumps(
            {
                "scorecard_json": payload["artifacts"]["scorecard_json"],
                "country_share_csv": payload["artifacts"]["country_share_csv"],
                "region_share_csv": payload["artifacts"]["region_share_csv"],
                "nn_quantiles_csv": payload["artifacts"]["nn_quantiles_csv"],
                "baseline_run_id": payload["baseline_authority"]["run_id"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
