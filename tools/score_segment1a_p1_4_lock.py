"""Build P1.4 lock scorecard for Segment 1A.

Computes P1.2 + P1.3 metrics for two consecutive S0->S2 pass sets,
checks same-seed replay stability, and records resolved locked bundle paths.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import pathlib
import statistics
from datetime import datetime, timezone
from typing import Any


B_BANDS = {
    "single_share": (0.25, 0.45),
    "median": (6.0, 20.0),
    "top10": (0.35, 0.55),
    "gini": (0.45, 0.62),
    "phi_cv": (0.05, 0.20),
    "phi_ratio": (1.25, 2.0),
}

BPLUS_BANDS = {
    "single_share": (0.35, 0.55),
    "median": (8.0, 18.0),
    "top10": (0.35, 0.55),
    "gini": (0.48, 0.58),
    "phi_cv": (0.10, 0.30),
    "phi_ratio": (1.5, 3.0),
}


def _sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _parse_runs(spec: str) -> dict[str, dict[int, str]]:
    payload = json.loads(spec)
    out: dict[str, dict[int, str]] = {}
    for pass_name, seed_map in payload.items():
        out[pass_name] = {int(seed): str(run_id) for seed, run_id in seed_map.items()}
    return out


def _load_metric_for_run(runs_root: pathlib.Path, run_id: str) -> dict[str, Any]:
    run_root = runs_root / run_id
    receipt_path = run_root / "run_receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

    hurdle_path = next(
        run_root.glob("logs/layer1/1A/rng/events/hurdle_bernoulli/**/part-00000.jsonl")
    )
    nb_path = next(run_root.glob("logs/layer1/1A/rng/events/nb_final/**/part-00000.jsonl"))

    gates: dict[int, bool] = {}
    with hurdle_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            payload = json.loads(line)
            gates[int(payload["merchant_id"])] = bool(payload["is_multi"])

    nb_rows: dict[int, int] = {}
    phis: list[float] = []
    with nb_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            payload = json.loads(line)
            mid = int(payload["merchant_id"])
            nb_rows[mid] = int(payload["n_outlets"])
            phis.append(float(payload["dispersion_k"]))

    outlets = [nb_rows[mid] if is_multi else 1 for mid, is_multi in gates.items()]
    outlets_sorted = sorted(outlets)
    merchant_count = len(outlets_sorted)
    total_outlets = sum(outlets_sorted)
    top_bucket = max(1, math.ceil(0.1 * merchant_count))
    top10_share = (
        sum(sorted(outlets_sorted, reverse=True)[:top_bucket]) / total_outlets
        if total_outlets > 0
        else 0.0
    )
    gini = (
        sum((2 * (idx + 1) - merchant_count - 1) * value for idx, value in enumerate(outlets_sorted))
        / (merchant_count * total_outlets)
        if merchant_count > 0 and total_outlets > 0
        else 0.0
    )
    median = float(statistics.median(outlets_sorted)) if outlets_sorted else 0.0

    phis_sorted = sorted(phis)
    phi_cv = (
        statistics.pstdev(phis) / statistics.mean(phis)
        if phis and statistics.mean(phis) > 0
        else 0.0
    )
    p05 = phis_sorted[max(0, math.ceil(0.05 * len(phis_sorted)) - 1)] if phis_sorted else 0.0
    p95 = phis_sorted[max(0, math.ceil(0.95 * len(phis_sorted)) - 1)] if phis_sorted else 0.0
    phi_ratio = (p95 / p05) if p05 > 0 else 0.0

    single_share = (
        sum(1 for value in gates.values() if not value) / len(gates) if gates else 0.0
    )
    branch_false_with_nb = sum(1 for mid, is_multi in gates.items() if (not is_multi) and mid in nb_rows)
    branch_true_missing_nb = sum(1 for mid, is_multi in gates.items() if is_multi and mid not in nb_rows)

    checks_b = {
        "single_share_B": B_BANDS["single_share"][0] <= single_share <= B_BANDS["single_share"][1],
        "branch_purity_B": branch_false_with_nb == 0 and branch_true_missing_nb == 0,
        "median_B": B_BANDS["median"][0] <= median <= B_BANDS["median"][1],
        "top10_B": B_BANDS["top10"][0] <= top10_share <= B_BANDS["top10"][1],
        "gini_B": B_BANDS["gini"][0] <= gini <= B_BANDS["gini"][1],
        "phi_cv_B": B_BANDS["phi_cv"][0] <= phi_cv <= B_BANDS["phi_cv"][1],
        "phi_ratio_B": B_BANDS["phi_ratio"][0] <= phi_ratio <= B_BANDS["phi_ratio"][1],
    }
    checks_bplus = {
        "single_share_B+": BPLUS_BANDS["single_share"][0]
        <= single_share
        <= BPLUS_BANDS["single_share"][1],
        "branch_purity_B+": branch_false_with_nb == 0 and branch_true_missing_nb == 0,
        "median_B+": BPLUS_BANDS["median"][0] <= median <= BPLUS_BANDS["median"][1],
        "top10_B+": BPLUS_BANDS["top10"][0] <= top10_share <= BPLUS_BANDS["top10"][1],
        "gini_B+": BPLUS_BANDS["gini"][0] <= gini <= BPLUS_BANDS["gini"][1],
        "phi_cv_B+": BPLUS_BANDS["phi_cv"][0] <= phi_cv <= BPLUS_BANDS["phi_cv"][1],
        "phi_ratio_B+": BPLUS_BANDS["phi_ratio"][0] <= phi_ratio <= BPLUS_BANDS["phi_ratio"][1],
    }

    return {
        "run_id": run_id,
        "seed": int(receipt["seed"]),
        "parameter_hash": receipt["parameter_hash"],
        "manifest_fingerprint": receipt["manifest_fingerprint"],
        "single_share": single_share,
        "branch_false_with_nb": branch_false_with_nb,
        "branch_true_missing_nb": branch_true_missing_nb,
        "median_outlets_per_merchant": median,
        "top10_outlet_share": top10_share,
        "gini_outlets_per_merchant": gini,
        "phi_cv": phi_cv,
        "phi_p95_p05_ratio": phi_ratio,
        "checks": {**checks_b, **checks_bplus},
        "all_B_pass": all(checks_b.values()),
        "all_Bplus_pass": all(checks_bplus.values()),
    }


def build_scorecard(
    runs_root: pathlib.Path, runs: dict[str, dict[int, str]], tolerance_abs: float
) -> dict[str, Any]:
    score: dict[str, Any] = {
        "generated_utc": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "wave": "P1.4",
        "definition": "Two-pass S0->S2 replay on locked P1.3 bundle",
        "tolerance_abs": tolerance_abs,
        "passes": {},
    }

    for pass_name, seed_map in runs.items():
        entries = []
        for seed, run_id in sorted(seed_map.items()):
            metric = _load_metric_for_run(runs_root, run_id)
            if metric["seed"] != seed:
                raise ValueError(
                    f"Run {run_id} has seed={metric['seed']} but was mapped as seed={seed}"
                )
            entries.append(metric)
        score["passes"][pass_name] = entries

    replay: list[dict[str, Any]] = []
    pass_names = sorted(score["passes"].keys())
    if len(pass_names) != 2:
        raise ValueError("Expected exactly 2 passes for P1.4 replay check.")
    p1, p2 = pass_names

    metric_keys = [
        "single_share",
        "median_outlets_per_merchant",
        "top10_outlet_share",
        "gini_outlets_per_merchant",
        "phi_cv",
        "phi_p95_p05_ratio",
    ]
    seeds = sorted(runs[p1].keys())
    for seed in seeds:
        a = [row for row in score["passes"][p1] if row["seed"] == seed][0]
        b = [row for row in score["passes"][p2] if row["seed"] == seed][0]
        deltas = {key: abs(a[key] - b[key]) for key in metric_keys}
        replay.append(
            {
                "seed": seed,
                "run_id_pass1": a["run_id"],
                "run_id_pass2": b["run_id"],
                "parameter_hash_match": a["parameter_hash"] == b["parameter_hash"],
                "manifest_fingerprint_match": a["manifest_fingerprint"]
                == b["manifest_fingerprint"],
                "deltas_abs": deltas,
                "within_tolerance": all(value <= tolerance_abs for value in deltas.values()),
            }
        )

    score["same_seed_replay"] = replay
    score["same_seed_replay_all_within_tolerance"] = all(
        row["within_tolerance"] for row in replay
    )
    score["consecutive_passes_all_B"] = all(
        row["all_B_pass"] for pass_rows in score["passes"].values() for row in pass_rows
    )
    score["consecutive_passes_all_Bplus"] = all(
        row["all_Bplus_pass"] for pass_rows in score["passes"].values() for row in pass_rows
    )

    sample_run_id = runs[p1][seeds[0]]
    sample_receipt = json.loads(
        (runs_root / sample_run_id / "run_receipt.json").read_text(encoding="utf-8")
    )
    sealed_inputs_path = (
        runs_root
        / sample_run_id
        / "data"
        / "layer1"
        / "1A"
        / "sealed_inputs"
        / f"manifest_fingerprint={sample_receipt['manifest_fingerprint']}"
        / "sealed_inputs_1A.json"
    )
    sealed_inputs = json.loads(sealed_inputs_path.read_text(encoding="utf-8"))
    assets = {
        row["asset_id"]: row for row in sealed_inputs if isinstance(row, dict) and "asset_id" in row
    }
    hurdle_path = pathlib.Path(assets["hurdle_coefficients.yaml"]["path"])
    dispersion_path = pathlib.Path(assets["nb_dispersion_coefficients.yaml"]["path"])

    score["lock"] = {
        "resolved_from_run_id": sample_run_id,
        "sealed_inputs_path": sealed_inputs_path.as_posix(),
        "hurdle_coefficients": {
            "path": hurdle_path.as_posix(),
            "sha256": _sha256(hurdle_path),
        },
        "nb_dispersion_coefficients": {
            "path": dispersion_path.as_posix(),
            "sha256": _sha256(dispersion_path),
        },
    }
    score["p1_4_dod"] = {
        "two_consecutive_p1_runs_meet_all_p1_metrics": score["consecutive_passes_all_B"],
        "same_seed_replay_preserves_metric_posture": score[
            "same_seed_replay_all_within_tolerance"
        ],
        "locked_bundle_versions_recorded": True,
    }
    return score


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build Segment 1A P1.4 lock scorecard from run IDs."
    )
    parser.add_argument("--runs-root", required=True, help="Runs root, e.g. runs/fix-data-engine/segment_1A")
    parser.add_argument(
        "--runs-json",
        required=True,
        help=(
            "JSON mapping of two passes to seed->run_id, e.g. "
            '\'{"pass1":{"42":"rid1"},"pass2":{"42":"rid2"}}\''
        ),
    )
    parser.add_argument(
        "--out",
        required=True,
        help="Output JSON path for scorecard.",
    )
    parser.add_argument(
        "--tolerance-abs",
        type=float,
        default=1e-12,
        help="Absolute tolerance for same-seed replay deltas.",
    )
    args = parser.parse_args()

    runs_root = pathlib.Path(args.runs_root)
    out_path = pathlib.Path(args.out)
    runs = _parse_runs(args.runs_json)
    scorecard = build_scorecard(
        runs_root=runs_root, runs=runs, tolerance_abs=float(args.tolerance_abs)
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(scorecard, indent=2), encoding="utf-8")
    print(f"Wrote {out_path.as_posix()}")
    print(
        json.dumps(
            {
                "p1_4_dod": scorecard["p1_4_dod"],
                "consecutive_passes_all_B": scorecard["consecutive_passes_all_B"],
                "consecutive_passes_all_Bplus": scorecard["consecutive_passes_all_Bplus"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
