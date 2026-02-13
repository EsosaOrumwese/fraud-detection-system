"""Score Segment 1B P3 candidate against P0 baseline and locked P2 posture."""

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
    if state in {"S6", "S7"}:
        return (
            reports_root
            / f"state={state}"
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


def _country_collapse_sentinel(
    site_df: pl.DataFrame,
    top_n: int = 10,
    min_points: int = 50,
) -> dict[str, Any]:
    counts = (
        site_df.group_by("legal_country_iso")
        .len()
        .rename({"len": "site_count"})
        .sort("site_count", descending=True)
    )
    top = counts.head(top_n).to_dicts()
    rows: list[dict[str, Any]] = []
    for row in top:
        iso = str(row["legal_country_iso"])
        n = int(row["site_count"])
        subset = site_df.filter(pl.col("legal_country_iso") == iso).select(["lat_deg", "lon_deg"])
        lat = subset["lat_deg"].to_numpy().astype(np.float64)
        lon = subset["lon_deg"].to_numpy().astype(np.float64)
        if n < min_points:
            rows.append(
                {
                    "country_iso": iso,
                    "site_count": n,
                    "sentinel": False,
                    "reason": "insufficient_points",
                }
            )
            continue
        mat = np.column_stack((lon, lat))
        cov = np.cov(mat, rowvar=False)
        eig = np.linalg.eigvalsh(cov)
        lam_min = float(max(eig[0], 0.0))
        lam_max = float(max(eig[1], 0.0))
        if lam_min <= 1.0e-12:
            anisotropy = float("inf")
            linearity = 1.0
        else:
            anisotropy = float(np.sqrt(lam_max / lam_min))
            linearity = float(lam_max / (lam_max + lam_min)) if (lam_max + lam_min) > 0 else 1.0
        lat_unique_ratio = float(np.unique(np.round(lat, 4)).size / n)
        lon_unique_ratio = float(np.unique(np.round(lon, 4)).size / n)
        sentinel = bool(
            (anisotropy > 12.0 and linearity > 0.98)
            or (lat_unique_ratio < 0.15)
            or (lon_unique_ratio < 0.15)
        )
        rows.append(
            {
                "country_iso": iso,
                "site_count": n,
                "anisotropy": anisotropy,
                "linearity": linearity,
                "lat_unique_ratio_4dp": lat_unique_ratio,
                "lon_unique_ratio_4dp": lon_unique_ratio,
                "sentinel": sentinel,
            }
        )
    flagged = [r for r in rows if bool(r.get("sentinel"))]
    return {
        "top_n": top_n,
        "min_points": min_points,
        "countries_evaluated": rows,
        "flagged_count": int(len(flagged)),
        "flagged_countries": [str(r["country_iso"]) for r in flagged],
        "all_clear": len(flagged) == 0,
    }


def _site_metrics(site_path: Path, eligible_country_total: int) -> dict[str, Any]:
    site_df = pl.read_parquet(site_path).select(["legal_country_iso", "lat_deg", "lon_deg"])
    counts_df = (
        site_df.group_by("legal_country_iso")
        .len()
        .rename({"legal_country_iso": "country_iso", "len": "site_count"})
        .sort("site_count", descending=True)
    )
    counts = [float(v) for v in counts_df["site_count"].to_list()]
    nn = _nn_distances_m(site_df["lat_deg"].to_numpy(), site_df["lon_deg"].to_numpy())
    q50 = _quantile(nn, 0.50)
    q99 = _quantile(nn, 0.99)
    site_count_total = int(site_df.height)
    south_share = (
        float((site_df.filter(pl.col("lat_deg") < 0.0).height) / site_count_total)
        if site_count_total > 0
        else 0.0
    )
    active_country_count = int(counts_df.height)
    collapse = _country_collapse_sentinel(site_df)
    return {
        "country_gini": _gini(counts),
        "top1_share": _top_share(counts, TOP_FRACTIONS["top1"]),
        "top5_share": _top_share(counts, TOP_FRACTIONS["top5"]),
        "top10_share": _top_share(counts, TOP_FRACTIONS["top10"]),
        "nn_p99_p50_ratio": float(q99 / q50) if q50 > 0 else 0.0,
        "nn_q50_m": q50,
        "nn_q99_m": q99,
        "site_count_total": float(site_count_total),
        "active_country_count": float(active_country_count),
        "eligible_country_nonzero_share": (
            float(active_country_count / eligible_country_total) if eligible_country_total > 0 else 0.0
        ),
        "southern_hemisphere_share": south_share,
        "coordinate_bounds_valid": bool(
            site_df.filter(
                (pl.col("lat_deg") < -90.0)
                | (pl.col("lat_deg") > 90.0)
                | (pl.col("lon_deg") < -180.0)
                | (pl.col("lon_deg") > 180.0)
            ).is_empty()
        ),
        "collapse_sentinel": collapse,
    }


def _snapshot(ctx: RunContext, eligible_country_total: int) -> dict[str, Any]:
    s6_report_path = _resolve_report(ctx, "S6", "s6_run_report.json")
    s8_report_path = _resolve_report(ctx, "S8", "s8_run_summary.json")
    s6_report = json.loads(s6_report_path.read_text(encoding="utf-8"))
    s8_report = json.loads(s8_report_path.read_text(encoding="utf-8"))
    site_path = _resolve_site_locations(ctx)
    metrics = _site_metrics(site_path, eligible_country_total)
    return {
        "run": {
            "run_id": ctx.run_id,
            "seed": ctx.seed,
            "manifest_fingerprint": ctx.manifest_fingerprint,
            "parameter_hash": ctx.parameter_hash,
            "run_root": str(ctx.run_root.resolve()),
        },
        "artifacts": {
            "s6_report": str(s6_report_path.resolve()),
            "s8_report": str(s8_report_path.resolve()),
            "site_locations": str(site_path.resolve()),
        },
        "s6_report": s6_report,
        "s8_report": s8_report,
        "metrics": metrics,
    }


def score_p3(
    runs_root: Path,
    baseline_json: Path,
    no_regression_run_id: str,
    candidate_run_id: str,
    output_dir: Path,
) -> dict[str, Any]:
    baseline_payload = json.loads(baseline_json.read_text(encoding="utf-8"))
    baseline_metrics = baseline_payload["metrics"]
    eligible_country_total = int(baseline_metrics["eligible_country_total"])
    baseline_nn_ratio = float(baseline_metrics["nn_p99_p50_ratio"])

    no_reg_ctx = _load_run_context(runs_root, no_regression_run_id)
    candidate_ctx = _load_run_context(runs_root, candidate_run_id)
    no_reg = _snapshot(no_reg_ctx, eligible_country_total)
    candidate = _snapshot(candidate_ctx, eligible_country_total)

    cand = candidate["metrics"]
    p2 = no_reg["metrics"]
    nn_improvement = (
        float((baseline_nn_ratio - cand["nn_p99_p50_ratio"]) / baseline_nn_ratio)
        if baseline_nn_ratio > 0.0
        else 0.0
    )

    checks = {
        "s6_policy_present": bool("jitter_policy" in candidate["s6_report"]),
        "s6_mode_mixture_v2": str(
            (candidate["s6_report"].get("jitter_policy") or {}).get("mode", "")
        )
        == "mixture_v2",
        "s8_parity_ok": bool(
            candidate["s8_report"].get("parity_ok", False)
            or (candidate["s8_report"].get("sizes") or {}).get("parity_ok", False)
        ),
        "coordinate_bounds_valid": bool(cand["coordinate_bounds_valid"]),
        "nn_tail_contraction_b_target": bool(nn_improvement >= 0.20),
        "top_country_no_collapse": bool(cand["collapse_sentinel"]["all_clear"]),
        "s8_concentration_not_worse_than_p2_lock": bool(
            cand["country_gini"] <= p2["country_gini"] + 1.0e-12
            and cand["top10_share"] <= p2["top10_share"] + 1.0e-12
            and cand["top5_share"] <= p2["top5_share"] + 1.0e-12
            and cand["top1_share"] <= p2["top1_share"] + 1.0e-12
        ),
        "coverage_not_worse_than_p2_lock": bool(
            cand["eligible_country_nonzero_share"] >= p2["eligible_country_nonzero_share"] - 1.0e-12
            and cand["southern_hemisphere_share"] >= p2["southern_hemisphere_share"] - 1.0e-12
        ),
    }

    payload = {
        "generated_utc": _now_utc(),
        "phase": "P3",
        "segment": "1B",
        "baseline": {
            "baseline_json": str(baseline_json.resolve()),
            "metrics": baseline_metrics,
        },
        "no_regression_authority": no_reg,
        "candidate": candidate,
        "delta_vs_p2_lock": {
            "country_gini": float(cand["country_gini"] - p2["country_gini"]),
            "top10_share": float(cand["top10_share"] - p2["top10_share"]),
            "top5_share": float(cand["top5_share"] - p2["top5_share"]),
            "top1_share": float(cand["top1_share"] - p2["top1_share"]),
            "eligible_country_nonzero_share": float(
                cand["eligible_country_nonzero_share"] - p2["eligible_country_nonzero_share"]
            ),
            "southern_hemisphere_share": float(
                cand["southern_hemisphere_share"] - p2["southern_hemisphere_share"]
            ),
            "nn_p99_p50_ratio": float(cand["nn_p99_p50_ratio"] - p2["nn_p99_p50_ratio"]),
        },
        "nn_contraction_vs_p0_baseline": {
            "baseline_nn_p99_p50_ratio": baseline_nn_ratio,
            "candidate_nn_p99_p50_ratio": float(cand["nn_p99_p50_ratio"]),
            "improvement_fraction": float(nn_improvement),
            "improvement_percent": float(nn_improvement * 100.0),
            "b_target_fraction": 0.20,
        },
        "checks": checks,
        "checks_all_pass": bool(all(checks.values())),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"segment1b_p3_candidate_{candidate_run_id}.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True), encoding="utf-8")
    return {"candidate_path": out_path, "payload": payload}


def main() -> None:
    parser = argparse.ArgumentParser(description="Score Segment 1B P3 candidate.")
    parser.add_argument(
        "--runs-root",
        default="runs/fix-data-engine/segment_1B",
        help="Runs root containing run-id folders.",
    )
    parser.add_argument(
        "--baseline-json",
        default="runs/fix-data-engine/segment_1B/reports/segment1b_p0_baseline_c25a2675fbfbacd952b13bb594880e92.json",
        help="P0 baseline scorecard JSON used for grade NN contraction baseline.",
    )
    parser.add_argument(
        "--no-regression-run-id",
        default="47ad6781ab9d4d92b311b068f51141f6",
        help="Locked P2 run-id used as no-regression authority.",
    )
    parser.add_argument("--candidate-run-id", required=True, help="P3 candidate run-id.")
    parser.add_argument(
        "--output-dir",
        default="runs/fix-data-engine/segment_1B/reports",
        help="Output directory for P3 score artifacts.",
    )
    args = parser.parse_args()
    result = score_p3(
        runs_root=Path(args.runs_root),
        baseline_json=Path(args.baseline_json),
        no_regression_run_id=args.no_regression_run_id,
        candidate_run_id=args.candidate_run_id,
        output_dir=Path(args.output_dir),
    )
    print(str(result["candidate_path"]))


if __name__ == "__main__":
    main()
