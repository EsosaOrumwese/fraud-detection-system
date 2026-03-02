#!/usr/bin/env python3
"""Run a bounded knob-sensitivity sweep for Segment 2B P2 entropy failure."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import polars as pl


MANIFEST = "c8fd43cd60ce0ede0c63d2ceb4610f167c9b107e1d59b9b8c7d7b8d0028b05c8"
PARAM_HASH = "56d45126eaabedd083a1d8428a763e0278c89efec5023cfd6cf3cab7fc8dd2d7"
SEED = 42


@dataclass(frozen=True)
class Experiment:
    name: str
    sigma_scale: float
    jitter_scale: float
    weekly_scale: float
    tz_spread_scale: float
    clip_width_scale: float
    code_sigma: int
    code_jitter: int
    code_weekly: int
    code_tz: int
    code_clip: int


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _utc_now_micro() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _stage_run(source_run: Path, runs_root: Path, run_id: str) -> Path:
    dst = runs_root / run_id
    (dst / "data" / "layer1").mkdir(parents=True, exist_ok=False)
    (dst / "logs").mkdir(parents=True, exist_ok=True)
    (dst / "reports").mkdir(parents=True, exist_ok=True)
    (dst / "tmp").mkdir(parents=True, exist_ok=True)

    shutil.copytree(source_run / "data" / "layer1" / "1B", dst / "data" / "layer1" / "1B")
    shutil.copytree(source_run / "data" / "layer1" / "2A", dst / "data" / "layer1" / "2A")

    src_receipt = _load_json(source_run / "run_receipt.json")
    receipt = {
        "contracts_layout": src_receipt["contracts_layout"],
        "contracts_root": src_receipt["contracts_root"],
        "created_utc": _utc_now_micro(),
        "external_roots": src_receipt.get("external_roots", []),
        "manifest_fingerprint": src_receipt["manifest_fingerprint"],
        "parameter_hash": src_receipt["parameter_hash"],
        "run_id": run_id,
        "runs_root": str(runs_root).replace("\\", "/"),
        "seed": int(src_receipt["seed"]),
    }
    _write_json(dst / "run_receipt.json", receipt)
    return dst


def _set_policy_variant(base: dict[str, Any], exp: Experiment) -> dict[str, Any]:
    policy = json.loads(json.dumps(base))
    s = policy["sigma_gamma_policy_v2"]

    sigma_min = float(s["sigma_min"])
    sigma_max = float(s["sigma_max"])
    for key, val in list(s["sigma_base_by_segment"].items()):
        scaled = float(val) * exp.sigma_scale
        s["sigma_base_by_segment"][key] = max(sigma_min, min(sigma_max, scaled))

    s["sigma_jitter_by_merchant"]["amplitude"] = max(
        0.0, min(0.35, float(s["sigma_jitter_by_merchant"]["amplitude"]) * exp.jitter_scale)
    )

    for key, val in list(s["weekly_component_amp_by_segment"].items()):
        scaled = float(val) * exp.weekly_scale
        s["weekly_component_amp_by_segment"][key] = max(0.0, min(0.06, scaled))

    for rule in s["sigma_multiplier_by_tz_group"]["prefix_rules"]:
        m = float(rule["multiplier"])
        rule["multiplier"] = max(0.8, min(1.2, 1.0 + (m - 1.0) * exp.tz_spread_scale))
    s["sigma_multiplier_by_tz_group"]["default"] = 1.0

    clip_min = float(s["gamma_clip"]["min"])
    clip_max = float(s["gamma_clip"]["max"])
    center = 0.5 * (clip_min + clip_max)
    width = (clip_max - clip_min) * exp.clip_width_scale
    new_min = max(0.2, center - 0.5 * width)
    new_max = min(2.5, center + 0.5 * width)
    if new_max <= new_min:
        new_max = new_min + 0.05
    s["gamma_clip"]["min"] = round(new_min, 6)
    s["gamma_clip"]["max"] = round(new_max, 6)
    return policy


def _run_states(runs_root: Path, run_id: str) -> None:
    env = dict(**__import__("os").environ)
    env["PYTHONPATH"] = "packages/engine/src"
    cmds = [
        ["python", "-m", "engine.cli.s0_gate_2b", "--runs-root", str(runs_root), "--run-id", run_id],
        ["python", "-m", "engine.cli.s1_site_weights_2b", "--runs-root", str(runs_root), "--run-id", run_id],
        ["python", "-m", "engine.cli.s2_alias_tables_2b", "--runs-root", str(runs_root), "--run-id", run_id],
        ["python", "-m", "engine.cli.s3_day_effects_2b", "--runs-root", str(runs_root), "--run-id", run_id],
        ["python", "-m", "engine.cli.s4_group_weights_2b", "--runs-root", str(runs_root), "--run-id", run_id],
    ]
    for cmd in cmds:
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(
                f"Command failed ({proc.returncode}): {' '.join(cmd)}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
            )


def _parquet_glob(run_root: Path, dataset_id: str) -> str:
    return str(
        run_root
        / "data"
        / "layer1"
        / "2B"
        / dataset_id
        / f"seed={SEED}"
        / f"manifest_fingerprint={MANIFEST}"
        / "*.parquet"
    ).replace("\\", "/")


def _metrics(run_root: Path) -> dict[str, float]:
    s3 = pl.scan_parquet(_parquet_glob(run_root, "s3_day_effects"))
    s4 = pl.scan_parquet(_parquet_glob(run_root, "s4_group_weights"))

    s3_m = s3.group_by("merchant_id").agg(pl.col("gamma").std(ddof=1).fill_null(0.0).alias("gstd")).collect()
    md = (
        s4.group_by(["merchant_id", "utc_day"])
        .agg(
            [
                pl.col("p_group").max().alias("maxp"),
                (
                    -pl.when(pl.col("p_group") > 0.0)
                    .then(pl.col("p_group") * pl.col("p_group").log())
                    .otherwise(0.0)
                )
                .sum()
                .alias("entropy"),
                (
                    -pl.when(pl.col("base_share") > 0.0)
                    .then(pl.col("base_share") * pl.col("base_share").log())
                    .otherwise(0.0)
                )
                .sum()
                .alias("base_entropy"),
                pl.col("gamma").mean().alias("gamma_mean"),
            ]
        )
        .collect()
    )
    delta = md.with_columns((pl.col("entropy") - pl.col("base_entropy")).alias("delta_entropy"))

    return {
        "s3_gamma_std_median": float(s3_m.select(pl.col("gstd").median()).item()),
        "s4_entropy_p50": float(md.select(pl.col("entropy").median()).item()),
        "s4_max_p_group_p50": float(md.select(pl.col("maxp").median()).item()),
        "s4_share_max_ge_095": float(md.select((pl.col("maxp") >= 0.95).mean()).item()),
        "s4_multi_group_share": float(
            s4.group_by(["merchant_id", "utc_day"])
            .agg((pl.col("p_group") >= 0.05).sum().alias("n_ge_005"))
            .collect()
            .select((pl.col("n_ge_005") >= 2).mean())
            .item()
        ),
        "base_entropy_p50": float(md.select(pl.col("base_entropy").median()).item()),
        "delta_entropy_p50": float(delta.select(pl.col("delta_entropy").median()).item()),
    }


def _fit_linear(rows: list[dict[str, Any]], y_key: str) -> dict[str, float]:
    valid = [r for r in rows if r.get("status") == "ok"]
    if not valid:
        return {}
    import numpy as np

    x = np.array(
        [
            [1.0, r["code_sigma"], r["code_jitter"], r["code_weekly"], r["code_tz"], r["code_clip"]]
            for r in valid
        ],
        dtype=float,
    )
    y = np.array([r[y_key] for r in valid], dtype=float)
    beta, *_ = np.linalg.lstsq(x, y, rcond=None)
    return {
        "intercept": float(beta[0]),
        "sigma": float(beta[1]),
        "jitter": float(beta[2]),
        "weekly": float(beta[3]),
        "tz_spread": float(beta[4]),
        "clip_width": float(beta[5]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-root", default="runs/fix-data-engine/segment_2B_sensitivity")
    parser.add_argument("--source-run-root", default="runs/fix-data-engine/segment_2B/c25a2675fbfbacd952b13bb594880e92")
    parser.add_argument("--policy-path", default="config/layer1/2B/policy/day_effect_policy_v1.json")
    parser.add_argument("--reports-root", default="runs/fix-data-engine/segment_2B/reports")
    parser.add_argument("--prune", action="store_true", help="Prune all sweep run-id folders after scoring.")
    args = parser.parse_args()

    runs_root = Path(args.runs_root)
    source_run = Path(args.source_run_root)
    policy_path = Path(args.policy_path)
    reports_root = Path(args.reports_root)
    runs_root.mkdir(parents=True, exist_ok=True)
    reports_root.mkdir(parents=True, exist_ok=True)

    original_policy_text = policy_path.read_text(encoding="utf-8")
    base_policy = json.loads(original_policy_text)

    experiments = [
        Experiment("baseline", 1.0, 1.0, 1.0, 1.0, 1.0, 0, 0, 0, 0, 0),
        Experiment("sigma_low", 0.75, 1.0, 1.0, 1.0, 1.0, -1, 0, 0, 0, 0),
        Experiment("sigma_high", 1.25, 1.0, 1.0, 1.0, 1.0, 1, 0, 0, 0, 0),
        Experiment("jitter_low", 1.0, 0.5, 1.0, 1.0, 1.0, 0, -1, 0, 0, 0),
        Experiment("jitter_high", 1.0, 1.5, 1.0, 1.0, 1.0, 0, 1, 0, 0, 0),
        Experiment("weekly_low", 1.0, 1.0, 0.5, 1.0, 1.0, 0, 0, -1, 0, 0),
        Experiment("weekly_high", 1.0, 1.0, 1.5, 1.0, 1.0, 0, 0, 1, 0, 0),
        Experiment("tz_low", 1.0, 1.0, 1.0, 0.5, 1.0, 0, 0, 0, -1, 0),
        Experiment("tz_high", 1.0, 1.0, 1.0, 1.5, 1.0, 0, 0, 0, 1, 0),
        Experiment("clip_narrow", 1.0, 1.0, 1.0, 1.0, 0.75, 0, 0, 0, 0, -1),
        Experiment("clip_wide", 1.0, 1.0, 1.0, 1.0, 1.25, 0, 0, 0, 0, 1),
    ]

    rows: list[dict[str, Any]] = []
    try:
        for exp in experiments:
            run_id = uuid.uuid4().hex
            policy_variant = _set_policy_variant(base_policy, exp)
            policy_path.write_text(json.dumps(policy_variant, indent=2) + "\n", encoding="utf-8")

            run_root = _stage_run(source_run, runs_root, run_id)
            row: dict[str, Any] = {
                "experiment": exp.name,
                "run_id": run_id,
                "sigma_scale": exp.sigma_scale,
                "jitter_scale": exp.jitter_scale,
                "weekly_scale": exp.weekly_scale,
                "tz_spread_scale": exp.tz_spread_scale,
                "clip_width_scale": exp.clip_width_scale,
                "code_sigma": exp.code_sigma,
                "code_jitter": exp.code_jitter,
                "code_weekly": exp.code_weekly,
                "code_tz": exp.code_tz,
                "code_clip": exp.code_clip,
            }
            try:
                _run_states(runs_root, run_id)
                row.update(_metrics(run_root))
                row["status"] = "ok"
            except Exception as exc:  # noqa: BLE001
                row["status"] = "fail"
                row["error"] = str(exc)
            rows.append(row)
            (run_root / "_FAILED.SENTINEL.json").write_text('{"reason":"sensitivity_sweep"}\n', encoding="utf-8")
    finally:
        policy_path.write_text(original_policy_text, encoding="utf-8")

    baseline = next((r for r in rows if r["experiment"] == "baseline" and r["status"] == "ok"), None)
    effects: list[dict[str, Any]] = []
    if baseline is not None:
        pairs = [
            ("sigma", "sigma_low", "sigma_high"),
            ("jitter", "jitter_low", "jitter_high"),
            ("weekly", "weekly_low", "weekly_high"),
            ("tz_spread", "tz_low", "tz_high"),
            ("clip_width", "clip_narrow", "clip_wide"),
        ]
        by_name = {r["experiment"]: r for r in rows}
        for factor, low_name, high_name in pairs:
            low = by_name.get(low_name)
            high = by_name.get(high_name)
            if not low or not high or low.get("status") != "ok" or high.get("status") != "ok":
                continue
            effects.append(
                {
                    "factor": factor,
                    "delta_entropy_p50_high_minus_low": float(high["s4_entropy_p50"] - low["s4_entropy_p50"]),
                    "delta_maxp_p50_high_minus_low": float(high["s4_max_p_group_p50"] - low["s4_max_p_group_p50"]),
                    "delta_share_max_ge_095_high_minus_low": float(
                        high["s4_share_max_ge_095"] - low["s4_share_max_ge_095"]
                    ),
                    "low_entropy_p50": float(low["s4_entropy_p50"]),
                    "high_entropy_p50": float(high["s4_entropy_p50"]),
                    "baseline_entropy_p50": float(baseline["s4_entropy_p50"]),
                }
            )
        effects.sort(key=lambda item: abs(item["delta_entropy_p50_high_minus_low"]), reverse=True)

    summary = {
        "generated_utc": _utc_now(),
        "segment": "2B",
        "phase": "P2_sensitivity",
        "baseline_guard_target": {"s4_entropy_p50_min": 0.20, "s4_max_p_group_p50_max": 0.97},
        "rows": rows,
        "effects_ranked_by_entropy": effects,
        "linear_fit_entropy_p50": _fit_linear(rows, "s4_entropy_p50"),
        "linear_fit_max_p_group_p50": _fit_linear(rows, "s4_max_p_group_p50"),
    }

    out_json = reports_root / "segment2b_p2_knob_sensitivity.json"
    out_csv = reports_root / "segment2b_p2_knob_sensitivity.csv"
    out_md = reports_root / "segment2b_p2_knob_sensitivity.md"
    _write_json(out_json, summary)

    ok_rows = [r for r in rows if r.get("status") == "ok"]
    csv_cols = [
        "experiment",
        "run_id",
        "status",
        "sigma_scale",
        "jitter_scale",
        "weekly_scale",
        "tz_spread_scale",
        "clip_width_scale",
        "s3_gamma_std_median",
        "s4_entropy_p50",
        "s4_max_p_group_p50",
        "s4_share_max_ge_095",
        "s4_multi_group_share",
        "base_entropy_p50",
        "delta_entropy_p50",
    ]
    if ok_rows:
        pl.DataFrame([{k: r.get(k) for k in csv_cols} for r in rows]).write_csv(out_csv)
    else:
        out_csv.write_text("experiment,status,error\n", encoding="utf-8")

    lines: list[str] = []
    lines.append("# Segment 2B P2 Knob Sensitivity")
    lines.append("")
    lines.append(f"- generated_utc: `{summary['generated_utc']}`")
    if baseline is not None:
        lines.append(f"- baseline entropy_p50: `{baseline['s4_entropy_p50']:.6f}`")
        lines.append(f"- baseline max_p_group_p50: `{baseline['s4_max_p_group_p50']:.6f}`")
        lines.append(f"- baseline s3_gamma_std_median: `{baseline['s3_gamma_std_median']:.6f}`")
    lines.append("")
    lines.append("## Ranked Effects (Entropy)")
    lines.append("")
    if effects:
        for item in effects:
            lines.append(
                f"- `{item['factor']}`: delta_entropy(high-low)=`{item['delta_entropy_p50_high_minus_low']:.6f}`, "
                f"delta_maxp(high-low)=`{item['delta_maxp_p50_high_minus_low']:.6f}`"
            )
    else:
        lines.append("- no valid effect rows")
    lines.append("")
    lines.append("## Linear Fit Coefficients")
    lines.append("")
    lines.append(f"- entropy_p50: `{json.dumps(summary['linear_fit_entropy_p50'], sort_keys=True)}`")
    lines.append(f"- max_p_group_p50: `{json.dumps(summary['linear_fit_max_p_group_p50'], sort_keys=True)}`")
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(str(out_json))
    print(str(out_csv))
    print(str(out_md))

    if args.prune:
        subprocess.run(
            ["python", "tools/prune_failed_runs.py", "--runs-root", str(runs_root)],
            check=False,
        )


if __name__ == "__main__":
    main()

