"""Score Segment 1B P2 candidate against locked P1 baseline."""

from __future__ import annotations

import argparse
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
TOP_FRACTIONS = {"top1": 0.01, "top5": 0.05, "top10": 0.10}


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


def _load_run_context(runs_root: Path, run_id: str) -> RunContext:
    run_root = runs_root / run_id
    receipt = json.loads((run_root / "run_receipt.json").read_text(encoding="utf-8"))
    return RunContext(
        run_root=run_root,
        run_id=run_id,
        seed=int(receipt["seed"]),
        manifest_fingerprint=str(receipt["manifest_fingerprint"]),
        parameter_hash=str(receipt["parameter_hash"]),
    )


def _resolve_report(ctx: RunContext, state: str, filename: str) -> Path:
    reports_root = ctx.run_root / "reports" / "layer1" / "1B"
    if state == "S4":
        return (
            reports_root
            / "state=S4"
            / f"seed={ctx.seed}"
            / f"parameter_hash={ctx.parameter_hash}"
            / f"manifest_fingerprint={ctx.manifest_fingerprint}"
            / filename
        )
    if state == "S8":
        return (
            reports_root
            / "state=S8"
            / f"seed={ctx.seed}"
            / f"manifest_fingerprint={ctx.manifest_fingerprint}"
            / filename
        )
    raise ValueError(f"Unsupported state: {state}")


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


def _resolve_tile_weights_dir(ctx: RunContext) -> Path:
    return (
        ctx.run_root
        / "data"
        / "layer1"
        / "1B"
        / "tile_weights"
        / f"parameter_hash={ctx.parameter_hash}"
    )


def _gini(values: list[float]) -> float:
    if not values:
        return 0.0
    vals = sorted(v for v in values if v >= 0.0)
    total = float(sum(vals))
    n = len(vals)
    if n == 0 or total <= 0:
        return 0.0
    weighted = sum((2 * (idx + 1) - n - 1) * value for idx, value in enumerate(vals))
    return float(weighted / (n * total))


def _top_share(values_desc: list[float], fraction: float) -> float:
    if not values_desc:
        return 0.0
    total = float(sum(values_desc))
    if total <= 0:
        return 0.0
    k = max(1, math.ceil(fraction * len(values_desc)))
    return float(sum(values_desc[:k]) / total)


def _summary(values: np.ndarray) -> dict[str, float]:
    if values.size == 0:
        return {"p50": 0.0, "p90": 0.0, "p99": 0.0, "mean": 0.0}
    return {
        "p50": float(np.quantile(values, 0.50)),
        "p90": float(np.quantile(values, 0.90)),
        "p99": float(np.quantile(values, 0.99)),
        "mean": float(values.mean()),
    }


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


def _quantile(values: np.ndarray, q: float) -> float:
    if values.size == 0:
        return 0.0
    return float(np.quantile(values, q))


def _country_tile_capacity_map(
    tile_weights_dir: Path,
    countries: list[str],
) -> dict[str, int]:
    capacities: dict[str, int] = {}
    for country_iso in countries:
        path = tile_weights_dir / f"part-{country_iso}.parquet"
        if not path.exists():
            capacities[country_iso] = 0
            continue
        cap = (
            pl.read_parquet(path)
            .select(pl.col("tile_id").n_unique().alias("tile_capacity"))
            .item()
        )
        capacities[country_iso] = int(cap)
    return capacities


def _s4_pair_metrics(ctx: RunContext, s4_alloc_path: Path) -> dict[str, Any]:
    s4 = pl.read_parquet(s4_alloc_path).select(
        ["merchant_id", "legal_country_iso", "tile_id", "n_sites_tile"]
    )
    if s4.height == 0:
        return {
            "pairs_total": 0,
            "rows_total": 0,
            "pair_top1_share": {"p50": 0.0, "p90": 0.0, "p99": 0.0, "mean": 0.0},
            "pair_hhi": {"p50": 0.0, "p90": 0.0, "p99": 0.0, "mean": 0.0},
            "pair_active_tiles": {"p50": 0.0, "p90": 0.0, "p99": 0.0, "mean": 0.0},
            "theoretical_floor": {"pair_top1_share_mean": 0.0, "pair_hhi_mean": 0.0},
            "theoretical_headroom": {
                "pair_top1_share_mean": 0.0,
                "pair_hhi_mean": 0.0,
                "pairs_with_top1_headroom": 0,
                "pairs_with_hhi_headroom": 0,
            },
        }

    countries = sorted(set(s4["legal_country_iso"].to_list()))
    tile_capacity = _country_tile_capacity_map(_resolve_tile_weights_dir(ctx), countries)

    pair = s4.group_by(["merchant_id", "legal_country_iso"]).agg(
        [
            pl.col("n_sites_tile").sum().alias("pair_total"),
            pl.col("n_sites_tile").max().alias("pair_max"),
            pl.len().alias("active_tiles"),
            (pl.col("n_sites_tile") * pl.col("n_sites_tile")).sum().alias("sum_sq"),
        ]
    )

    pair_rows = pair.to_dicts()
    top1_values: list[float] = []
    hhi_values: list[float] = []
    active_values: list[float] = []
    top1_floor_values: list[float] = []
    hhi_floor_values: list[float] = []
    top1_headroom_values: list[float] = []
    hhi_headroom_values: list[float] = []

    for row in pair_rows:
        n = int(row["pair_total"])
        cmax = int(row["pair_max"])
        sum_sq = int(row["sum_sq"])
        active = int(row["active_tiles"])
        country_iso = str(row["legal_country_iso"])
        m = max(1, int(tile_capacity.get(country_iso, 0)))

        top1_obs = float(cmax / n) if n > 0 else 0.0
        hhi_obs = float(sum_sq / (n * n)) if n > 0 else 0.0

        q, rem = divmod(n, m)
        top1_floor = float((q + 1) / n) if rem > 0 and n > 0 else float(q / n) if n > 0 else 0.0
        hhi_floor = (
            float((rem * (q + 1) * (q + 1) + (m - rem) * q * q) / (n * n))
            if n > 0
            else 0.0
        )

        top1_values.append(top1_obs)
        hhi_values.append(hhi_obs)
        active_values.append(float(active))
        top1_floor_values.append(top1_floor)
        hhi_floor_values.append(hhi_floor)
        top1_headroom_values.append(top1_obs - top1_floor)
        hhi_headroom_values.append(hhi_obs - hhi_floor)

    top1 = np.asarray(top1_values, dtype=np.float64)
    hhi = np.asarray(hhi_values, dtype=np.float64)
    active = np.asarray(active_values, dtype=np.float64)
    top1_floor = np.asarray(top1_floor_values, dtype=np.float64)
    hhi_floor = np.asarray(hhi_floor_values, dtype=np.float64)
    top1_headroom = np.asarray(top1_headroom_values, dtype=np.float64)
    hhi_headroom = np.asarray(hhi_headroom_values, dtype=np.float64)
    return {
        "pairs_total": int(pair.height),
        "rows_total": int(s4.height),
        "pair_top1_share": _summary(top1),
        "pair_hhi": _summary(hhi),
        "pair_active_tiles": _summary(active),
        "theoretical_floor": {
            "pair_top1_share_mean": float(top1_floor.mean()),
            "pair_hhi_mean": float(hhi_floor.mean()),
        },
        "theoretical_headroom": {
            "pair_top1_share_mean": float(top1_headroom.mean()),
            "pair_hhi_mean": float(hhi_headroom.mean()),
            "pairs_with_top1_headroom": int(np.sum(top1_headroom > 1.0e-12)),
            "pairs_with_hhi_headroom": int(np.sum(hhi_headroom > 1.0e-12)),
        },
    }


def _s8_metrics(ctx: RunContext) -> dict[str, float]:
    site_path = _resolve_site_locations(ctx)
    site_df = pl.read_parquet(site_path).select(["legal_country_iso", "lat_deg", "lon_deg"])
    country_counts_df = (
        site_df.group_by("legal_country_iso")
        .len()
        .rename({"legal_country_iso": "country_iso", "len": "site_count"})
        .sort("site_count", descending=True)
    )
    counts = [float(v) for v in country_counts_df["site_count"].to_list()]
    nn = _nn_distances_m(site_df["lat_deg"].to_numpy(), site_df["lon_deg"].to_numpy())
    q50 = _quantile(nn, 0.50)
    q99 = _quantile(nn, 0.99)
    total_sites = int(site_df.height)
    return {
        "country_gini": _gini(counts),
        "top1_share": _top_share(counts, TOP_FRACTIONS["top1"]),
        "top5_share": _top_share(counts, TOP_FRACTIONS["top5"]),
        "top10_share": _top_share(counts, TOP_FRACTIONS["top10"]),
        "nn_p99_p50_ratio": float(q99 / q50) if q50 > 0 else 0.0,
        "site_count_total": float(total_sites),
    }


def _snapshot(ctx: RunContext) -> dict[str, Any]:
    s4_report_path = _resolve_report(ctx, "S4", "s4_run_report.json")
    s8_report_path = _resolve_report(ctx, "S8", "s8_run_summary.json")
    s4_report = json.loads(s4_report_path.read_text(encoding="utf-8"))
    s8_report = json.loads(s8_report_path.read_text(encoding="utf-8"))
    s4_pair = _s4_pair_metrics(ctx, _resolve_s4_alloc_plan(ctx))
    s8_metrics = _s8_metrics(ctx)
    return {
        "run": {
            "run_id": ctx.run_id,
            "seed": ctx.seed,
            "manifest_fingerprint": ctx.manifest_fingerprint,
            "parameter_hash": ctx.parameter_hash,
            "run_root": str(ctx.run_root.resolve()),
        },
        "artifacts": {
            "s4_report": str(s4_report_path.resolve()),
            "s8_report": str(s8_report_path.resolve()),
            "s4_alloc_plan": str(_resolve_s4_alloc_plan(ctx).resolve()),
            "site_locations": str(_resolve_site_locations(ctx).resolve()),
        },
        "s4_report": s4_report,
        "s8_report": s8_report,
        "s4_pair_metrics": s4_pair,
        "s8_metrics": s8_metrics,
    }


def score_p2(
    runs_root: Path,
    baseline_run_id: str,
    candidate_run_id: str,
    output_dir: Path,
) -> dict[str, Any]:
    baseline_ctx = _load_run_context(runs_root, baseline_run_id)
    candidate_ctx = _load_run_context(runs_root, candidate_run_id)
    baseline = _snapshot(baseline_ctx)
    candidate = _snapshot(candidate_ctx)

    baseline_s4 = baseline["s4_pair_metrics"]
    candidate_s4 = candidate["s4_pair_metrics"]
    baseline_s8 = baseline["s8_metrics"]
    candidate_s8 = candidate["s8_metrics"]
    baseline_top1_headroom = float(
        baseline_s4["theoretical_headroom"]["pair_top1_share_mean"]
    )
    baseline_hhi_headroom = float(baseline_s4["theoretical_headroom"]["pair_hhi_mean"])
    candidate_top1_headroom = float(
        candidate_s4["theoretical_headroom"]["pair_top1_share_mean"]
    )
    candidate_hhi_headroom = float(
        candidate_s4["theoretical_headroom"]["pair_hhi_mean"]
    )
    eps = 1.0e-12
    top1_improvement_feasible = baseline_top1_headroom > eps
    hhi_improvement_feasible = baseline_hhi_headroom > eps

    candidate_s4_report = candidate["s4_report"]
    candidate_s8_report = candidate["s8_report"]
    checks = {
        "s4_diagnostics_present": bool(
            "anti_collapse_policy" in candidate_s4_report
            and "anti_collapse_diagnostics" in candidate_s4_report
        ),
        "s4_alloc_sum_equals_requirements": bool(
            candidate_s4_report.get("alloc_sum_equals_requirements", False)
        ),
        "s4_pair_top1_mean_improved": (
            float(candidate_s4["pair_top1_share"]["mean"])
            < float(baseline_s4["pair_top1_share"]["mean"]) - eps
            if top1_improvement_feasible
            else (
                float(candidate_s4["pair_top1_share"]["mean"])
                <= float(baseline_s4["pair_top1_share"]["mean"]) + eps
                and candidate_top1_headroom <= eps
            )
        ),
        "s4_pair_hhi_mean_improved": (
            float(candidate_s4["pair_hhi"]["mean"])
            < float(baseline_s4["pair_hhi"]["mean"]) - eps
            if hhi_improvement_feasible
            else (
                float(candidate_s4["pair_hhi"]["mean"])
                <= float(baseline_s4["pair_hhi"]["mean"]) + eps
                and candidate_hhi_headroom <= eps
            )
        ),
        "s4_pair_active_tiles_mean_not_worse": float(candidate_s4["pair_active_tiles"]["mean"])
        >= float(baseline_s4["pair_active_tiles"]["mean"]) - 1.0e-12,
        "s8_concentration_not_worse_than_baseline": (
            candidate_s8["country_gini"] <= baseline_s8["country_gini"] + 1.0e-12
            and candidate_s8["top10_share"] <= baseline_s8["top10_share"] + 1.0e-12
            and candidate_s8["top5_share"] <= baseline_s8["top5_share"] + 1.0e-12
            and candidate_s8["top1_share"] <= baseline_s8["top1_share"] + 1.0e-12
        ),
        "s8_nn_p99_p50_not_worse_than_baseline": (
            candidate_s8["nn_p99_p50_ratio"] <= baseline_s8["nn_p99_p50_ratio"] + 1.0e-12
        ),
        "s8_parity_ok": bool(
            candidate_s8_report.get("parity_ok", False)
            or (candidate_s8_report.get("sizes") or {}).get("parity_ok", False)
        ),
    }

    payload = {
        "generated_utc": _now_utc(),
        "phase": "P2",
        "segment": "1B",
        "baseline": baseline,
        "candidate": candidate,
        "delta": {
            "s4_pair_top1_mean": float(candidate_s4["pair_top1_share"]["mean"])
            - float(baseline_s4["pair_top1_share"]["mean"]),
            "s4_pair_hhi_mean": float(candidate_s4["pair_hhi"]["mean"])
            - float(baseline_s4["pair_hhi"]["mean"]),
            "s4_pair_active_tiles_mean": float(candidate_s4["pair_active_tiles"]["mean"])
            - float(baseline_s4["pair_active_tiles"]["mean"]),
            "s8_country_gini": float(candidate_s8["country_gini"])
            - float(baseline_s8["country_gini"]),
            "s8_top10_share": float(candidate_s8["top10_share"])
            - float(baseline_s8["top10_share"]),
            "s8_top5_share": float(candidate_s8["top5_share"])
            - float(baseline_s8["top5_share"]),
            "s8_top1_share": float(candidate_s8["top1_share"])
            - float(baseline_s8["top1_share"]),
            "s8_nn_p99_p50_ratio": float(candidate_s8["nn_p99_p50_ratio"])
            - float(baseline_s8["nn_p99_p50_ratio"]),
        },
        "feasibility": {
            "s4_pair_top1_mean_headroom_baseline": baseline_top1_headroom,
            "s4_pair_top1_mean_headroom_candidate": candidate_top1_headroom,
            "s4_pair_hhi_mean_headroom_baseline": baseline_hhi_headroom,
            "s4_pair_hhi_mean_headroom_candidate": candidate_hhi_headroom,
            "s4_pair_top1_improvement_feasible": top1_improvement_feasible,
            "s4_pair_hhi_improvement_feasible": hhi_improvement_feasible,
        },
        "checks": checks,
        "checks_all_pass": all(checks.values()),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    baseline_path = output_dir / f"segment1b_p2_baseline_{baseline_run_id}.json"
    candidate_path = output_dir / f"segment1b_p2_candidate_{candidate_run_id}.json"
    baseline_path.write_text(
        json.dumps(
            {
                "generated_utc": _now_utc(),
                "phase": "P2",
                "segment": "1B",
                "baseline": baseline,
            },
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    candidate_path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True), encoding="utf-8"
    )
    return {
        "baseline_path": baseline_path,
        "candidate_path": candidate_path,
        "payload": payload,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Score Segment 1B P2 candidate.")
    parser.add_argument(
        "--runs-root",
        default="runs/fix-data-engine/segment_1B",
        help="Runs root containing baseline/candidate run-id folders.",
    )
    parser.add_argument("--baseline-run-id", required=True, help="Locked P1 baseline run_id.")
    parser.add_argument("--candidate-run-id", required=True, help="P2 candidate run_id.")
    parser.add_argument(
        "--output-dir",
        default="runs/fix-data-engine/segment_1B/reports",
        help="Output directory for P2 score artifacts.",
    )
    args = parser.parse_args()
    result = score_p2(
        runs_root=Path(args.runs_root),
        baseline_run_id=args.baseline_run_id,
        candidate_run_id=args.candidate_run_id,
        output_dir=Path(args.output_dir),
    )
    print(str(result["candidate_path"]))


if __name__ == "__main__":
    main()
