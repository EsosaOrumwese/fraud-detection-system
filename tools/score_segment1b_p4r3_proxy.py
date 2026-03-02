#!/usr/bin/env python3
"""Score Segment 1B P4.R3 proxy lane from S4 concentration/coverage metrics."""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import polars as pl


B_THRESHOLDS = {
    "country_gini_max": 0.68,
    "top10_share_max": 0.50,
    "top5_share_max": 0.33,
    "top1_share_max": 0.10,
}


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _gini(values: list[int]) -> float:
    if not values:
        return 0.0
    vals = sorted(v for v in values if v >= 0)
    total = float(sum(vals))
    n = len(vals)
    if n == 0 or total <= 0.0:
        return 0.0
    weighted = sum((2 * (idx + 1) - n - 1) * value for idx, value in enumerate(vals))
    return float(weighted / (n * total))


def _top_share(sorted_desc: list[int], k: int) -> float:
    if not sorted_desc:
        return 0.0
    total = float(sum(sorted_desc))
    if total <= 0.0:
        return 0.0
    return float(sum(sorted_desc[: max(1, k)]) / total)


def _run_receipt(run_root: Path) -> dict[str, Any]:
    return json.loads((run_root / "run_receipt.json").read_text(encoding="utf-8"))


def _resolve_s4_paths(run_root: Path, seed: int, parameter_hash: str, manifest_fingerprint: str) -> list[Path]:
    base = (
        run_root
        / "data"
        / "layer1"
        / "1B"
        / "s4_alloc_plan"
        / f"seed={seed}"
        / f"parameter_hash={parameter_hash}"
        / f"manifest_fingerprint={manifest_fingerprint}"
    )
    return sorted(base.glob("part-*.parquet"))


def _s4_metrics(run_root: Path) -> dict[str, Any]:
    receipt = _run_receipt(run_root)
    seed = int(receipt["seed"])
    parameter_hash = str(receipt["parameter_hash"])
    manifest_fingerprint = str(receipt["manifest_fingerprint"])
    paths = _resolve_s4_paths(run_root, seed, parameter_hash, manifest_fingerprint)
    if not paths:
        raise FileNotFoundError(f"s4_alloc_plan parquet not found under {run_root}")

    by_country = (
        pl.scan_parquet(str(paths[0].parent / "part-*.parquet"))
        .group_by("legal_country_iso")
        .agg(pl.col("n_sites_tile").sum().cast(pl.Int64).alias("sites"))
        .collect()
        .sort("sites", descending=True)
    )
    country_sites = [int(v) for v in by_country["sites"].to_list()]
    total_sites = int(sum(country_sites))
    nonzero_country_count = int(sum(1 for v in country_sites if v > 0))
    metrics = {
        "country_gini_s4": _gini(country_sites),
        "top1_share_s4": _top_share(country_sites, 1),
        "top5_share_s4": _top_share(country_sites, 5),
        "top10_share_s4": _top_share(country_sites, 10),
        "nonzero_country_count_s4": nonzero_country_count,
        "country_count_s4": int(by_country.height),
        "total_sites_s4": total_sites,
    }
    return {
        "run": {
            "run_id": str(receipt["run_id"]),
            "seed": seed,
            "parameter_hash": parameter_hash,
            "manifest_fingerprint": manifest_fingerprint,
        },
        "metrics": metrics,
    }


def _distance_to_b(metrics: dict[str, float]) -> float:
    g = max(0.0, float(metrics["country_gini_s4"]) - B_THRESHOLDS["country_gini_max"]) / B_THRESHOLDS["country_gini_max"]
    t10 = max(0.0, float(metrics["top10_share_s4"]) - B_THRESHOLDS["top10_share_max"]) / B_THRESHOLDS["top10_share_max"]
    t5 = max(0.0, float(metrics["top5_share_s4"]) - B_THRESHOLDS["top5_share_max"]) / B_THRESHOLDS["top5_share_max"]
    t1 = max(0.0, float(metrics["top1_share_s4"]) - B_THRESHOLDS["top1_share_max"]) / B_THRESHOLDS["top1_share_max"]
    return float(g + t10 + t5 + t1)


def _match_1b_run_for_1a_candidate(runs_root_1a: Path, runs_root_1b: Path, candidate_1a_run_id: str) -> Path:
    candidate_1a = _run_receipt(runs_root_1a / candidate_1a_run_id)
    seed = int(candidate_1a["seed"])
    parameter_hash = str(candidate_1a["parameter_hash"])
    manifest_fingerprint = str(candidate_1a["manifest_fingerprint"])

    matches: list[tuple[float, Path]] = []
    for run_dir in sorted([p for p in runs_root_1b.iterdir() if p.is_dir()]):
        receipt_path = run_dir / "run_receipt.json"
        if not receipt_path.exists():
            continue
        try:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if int(receipt.get("seed", -1)) != seed:
            continue
        if str(receipt.get("parameter_hash", "")) != parameter_hash:
            continue
        if str(receipt.get("manifest_fingerprint", "")) != manifest_fingerprint:
            continue
        try:
            if _resolve_s4_paths(run_dir, seed, parameter_hash, manifest_fingerprint):
                matches.append((receipt_path.stat().st_mtime, run_dir))
        except Exception:
            continue

    if not matches:
        raise FileNotFoundError(
            f"no 1B run with S4 outputs found for 1A candidate {candidate_1a_run_id} "
            f"(seed={seed}, parameter_hash={parameter_hash}, manifest_fingerprint={manifest_fingerprint})"
        )
    matches.sort(key=lambda x: x[0], reverse=True)
    return matches[0][1]


def score_proxy(
    runs_root_1a: Path,
    runs_root_1b: Path,
    r2_summary_json: Path,
    reference_run_id: str,
    max_shortlist: int,
    output_dir: Path,
) -> dict[str, Any]:
    r2_payload = json.loads(r2_summary_json.read_text(encoding="utf-8"))
    promoted_1a = [str(v) for v in r2_payload.get("promoted_candidates", [])]
    wave = str(r2_payload.get("wave", "wave_1"))

    reference = _s4_metrics(runs_root_1b / reference_run_id)
    ref_metrics = reference["metrics"]

    candidates: list[dict[str, Any]] = []
    for candidate_1a_run_id in promoted_1a:
        artifact_path = output_dir / f"segment1b_p4r3_proxy_{candidate_1a_run_id}.json"
        try:
            matched_1b = _match_1b_run_for_1a_candidate(runs_root_1a, runs_root_1b, candidate_1a_run_id)
            snap = _s4_metrics(matched_1b)
            m = snap["metrics"]
            deltas = {
                "country_gini_s4": float(m["country_gini_s4"] - ref_metrics["country_gini_s4"]),
                "top1_share_s4": float(m["top1_share_s4"] - ref_metrics["top1_share_s4"]),
                "top5_share_s4": float(m["top5_share_s4"] - ref_metrics["top5_share_s4"]),
                "top10_share_s4": float(m["top10_share_s4"] - ref_metrics["top10_share_s4"]),
                "nonzero_country_count_s4": int(m["nonzero_country_count_s4"] - ref_metrics["nonzero_country_count_s4"]),
            }
            checks = {
                "concentration_direction_non_regression": bool(
                    deltas["country_gini_s4"] <= 1.0e-12
                    and deltas["top1_share_s4"] <= 1.0e-12
                    and deltas["top5_share_s4"] <= 1.0e-12
                    and deltas["top10_share_s4"] <= 1.0e-12
                ),
                "coverage_direction_non_regression": bool(deltas["nonzero_country_count_s4"] >= 0),
            }
            checks["proxy_competitive"] = bool(
                checks["concentration_direction_non_regression"] and checks["coverage_direction_non_regression"]
            )
            dist = _distance_to_b(m)
            coverage_bonus = float(max(0, deltas["nonzero_country_count_s4"]) / max(1, ref_metrics["nonzero_country_count_s4"]))
            rank_score = float(dist - 0.25 * coverage_bonus)
            payload = {
                "generated_utc": _now_utc(),
                "phase": "P4.R3",
                "segment": "1B",
                "candidate_1a_run_id": candidate_1a_run_id,
                "matched_1b_run_id": snap["run"]["run_id"],
                "reference_run_id": reference_run_id,
                "reference_metrics": ref_metrics,
                "candidate_metrics": m,
                "delta_vs_reference": deltas,
                "proxy_checks": checks,
                "distance_to_B_proxy": dist,
                "proxy_rank_score": rank_score,
            }
        except Exception as exc:
            payload = {
                "generated_utc": _now_utc(),
                "phase": "P4.R3",
                "segment": "1B",
                "candidate_1a_run_id": candidate_1a_run_id,
                "matched_1b_run_id": None,
                "reference_run_id": reference_run_id,
                "reference_metrics": ref_metrics,
                "proxy_checks": {
                    "concentration_direction_non_regression": False,
                    "coverage_direction_non_regression": False,
                    "proxy_competitive": False,
                },
                "distance_to_B_proxy": math.inf,
                "proxy_rank_score": math.inf,
                "error": {"type": type(exc).__name__, "message": str(exc)},
            }

        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True), encoding="utf-8")
        candidates.append(payload)

    competitive = [c for c in candidates if bool((c.get("proxy_checks") or {}).get("proxy_competitive", False))]
    competitive_sorted = sorted(competitive, key=lambda c: float(c.get("proxy_rank_score", math.inf)))
    shortlisted = competitive_sorted[: max_shortlist]
    shortlisted_1a = [str(c["candidate_1a_run_id"]) for c in shortlisted]
    shortlisted_1b = [str(c["matched_1b_run_id"]) for c in shortlisted]

    dropped: list[dict[str, Any]] = []
    shortlist_set = {str(c["candidate_1a_run_id"]) for c in shortlisted}
    for c in candidates:
        cid = str(c["candidate_1a_run_id"])
        if cid in shortlist_set:
            continue
        reason = "proxy_gate_fail"
        if bool((c.get("proxy_checks") or {}).get("proxy_competitive", False)):
            reason = "rank_below_shortlist_cut"
        dropped.append(
            {
                "candidate_1a_run_id": cid,
                "matched_1b_run_id": c.get("matched_1b_run_id"),
                "reason": reason,
                "proxy_rank_score": c.get("proxy_rank_score"),
            }
        )

    non_competitive_ids = {
        str(c["candidate_1a_run_id"])
        for c in candidates
        if not bool((c.get("proxy_checks") or {}).get("proxy_competitive", False))
    }
    dropped_ids = {str(item["candidate_1a_run_id"]) for item in dropped}

    summary = {
        "generated_utc": _now_utc(),
        "phase": "P4.R3",
        "segment": "1B",
        "wave": wave,
        "reference_run_id": reference_run_id,
        "reference_metrics": ref_metrics,
        "candidate_count": len(candidates),
        "max_shortlist": max_shortlist,
        "candidate_artifacts": [
            str((output_dir / f"segment1b_p4r3_proxy_{c['candidate_1a_run_id']}.json").as_posix())
            for c in candidates
        ],
        "shortlisted_candidates_1a": shortlisted_1a,
        "shortlisted_candidates_1b": shortlisted_1b,
        "dropped_candidates": dropped,
        "summary_checks": {
            "all_candidates_have_artifacts": bool(len(candidates) == len(promoted_1a)),
            "non_competitive_filtered_before_expensive_runs": bool(non_competitive_ids.issubset(dropped_ids)),
            "shortlist_bounded": bool(len(shortlisted) <= max_shortlist),
        },
    }
    out_summary = output_dir / f"segment1b_p4r3_proxy_{wave}.json"
    out_summary.write_text(json.dumps(summary, ensure_ascii=True, indent=2, sort_keys=True), encoding="utf-8")
    return {"summary_path": out_summary, "summary": summary}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runs-root-1a",
        default="runs/fix-data-engine/segment_1A",
        help="Segment 1A runs root used to resolve promoted candidate lineage.",
    )
    parser.add_argument(
        "--runs-root-1b",
        default="runs/fix-data-engine/segment_1B",
        help="Segment 1B runs root used for S4 proxy snapshots.",
    )
    parser.add_argument(
        "--r2-summary-json",
        default="runs/fix-data-engine/segment_1B/reports/segment1b_p4r2_wave1_guard_summary.json",
        help="P4.R2 promoted/rejected summary artifact.",
    )
    parser.add_argument(
        "--reference-run-id",
        default="625644d528a44f148bbf44339a41a044",
        help="Reference RED run-id used for movement direction gates.",
    )
    parser.add_argument(
        "--max-shortlist",
        type=int,
        default=2,
        help="Maximum candidates to keep for downstream closure lane.",
    )
    parser.add_argument(
        "--output-dir",
        default="runs/fix-data-engine/segment_1B/reports",
        help="Directory for proxy artifacts.",
    )
    args = parser.parse_args()

    result = score_proxy(
        runs_root_1a=Path(args.runs_root_1a),
        runs_root_1b=Path(args.runs_root_1b),
        r2_summary_json=Path(args.r2_summary_json),
        reference_run_id=str(args.reference_run_id),
        max_shortlist=int(args.max_shortlist),
        output_dir=Path(args.output_dir),
    )
    print(str(result["summary_path"]))
    print(
        json.dumps(
            {
                "candidate_count": result["summary"]["candidate_count"],
                "shortlisted_candidates_1a": result["summary"]["shortlisted_candidates_1a"],
                "shortlisted_candidates_1b": result["summary"]["shortlisted_candidates_1b"],
                "dropped_count": len(result["summary"]["dropped_candidates"]),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
