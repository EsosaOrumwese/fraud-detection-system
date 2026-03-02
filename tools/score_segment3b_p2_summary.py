"""
Score Segment 3B P2 witness/shadow closure gates.

P2 core scope:
- V01..V07 on S2 realism surfaces.

Guardrails:
- alias fidelity (V11),
- structural state PASS (S2..S5),
- optional P1 freeze checks (V08..V10) on witness seeds.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import polars as pl


def _parse_seed_list(raw: str) -> list[int]:
    seeds: list[int] = []
    for token in str(raw).split(","):
        token = token.strip()
        if token:
            seeds.append(int(token))
    return seeds


def _parse_seed_run(items: list[str]) -> dict[int, str]:
    out: dict[int, str] = {}
    for item in items:
        raw = str(item).strip()
        if ":" not in raw:
            raise ValueError(f"Invalid --seed-run '{raw}' (expected seed:run_id)")
        seed_s, run_id = raw.split(":", 1)
        seed = int(seed_s.strip())
        run_id = run_id.strip()
        if len(run_id) != 32:
            raise ValueError(f"Invalid run_id in --seed-run '{raw}'")
        out[seed] = run_id
    return out


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_md(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _cv(values: list[float]) -> float:
    if not values:
        return float("nan")
    mean = float(sum(values)) / float(len(values))
    if abs(mean) < 1.0e-12:
        if max(abs(v) for v in values) < 1.0e-12:
            return 0.0
        return float("inf")
    return float(statistics.pstdev(values) / mean)


def _haversine_km(lat1: np.ndarray, lon1: np.ndarray, lat2: np.ndarray, lon2: np.ndarray) -> np.ndarray:
    r = 6371.0088
    lat1r = np.radians(lat1)
    lon1r = np.radians(lon1)
    lat2r = np.radians(lat2)
    lon2r = np.radians(lon2)
    dlat = lat2r - lat1r
    dlon = lon2r - lon1r
    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat1r) * np.cos(lat2r) * np.sin(dlon / 2.0) ** 2
    c = 2.0 * np.arcsin(np.sqrt(a))
    return r * c


def _median_pairwise_js(country_weight_df: pl.DataFrame) -> float:
    pivot = (
        country_weight_df
        .pivot(on="country_iso", index="merchant_id", values="country_weight", aggregate_function="sum")
        .fill_null(0.0)
        .sort("merchant_id")
    )
    cols = [c for c in pivot.columns if c != "merchant_id"]
    matrix = pivot.select(cols).to_numpy().astype(np.float64, copy=False)
    if matrix.shape[0] <= 1:
        return 0.0
    row_sums = matrix.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0.0] = 1.0
    matrix = matrix / row_sums
    eps = 1.0e-12
    js_vals: list[np.ndarray] = []
    for idx in range(matrix.shape[0] - 1):
        p = matrix[idx][None, :]
        q = matrix[idx + 1 :]
        m = 0.5 * (p + q)
        p_safe = np.clip(p, eps, 1.0)
        q_safe = np.clip(q, eps, 1.0)
        m_safe = np.clip(m, eps, 1.0)
        kl_p = np.sum(p_safe * np.log(p_safe / m_safe), axis=1)
        kl_q = np.sum(q_safe * np.log(q_safe / m_safe), axis=1)
        js_vals.append(0.5 * (kl_p + kl_q))
    if not js_vals:
        return 0.0
    return float(np.median(np.concatenate(js_vals)))


def _settlement_country_map(vs_df: pl.DataFrame, countries: gpd.GeoDataFrame) -> dict[int, str]:
    points = gpd.GeoDataFrame(
        {"merchant_id": vs_df.get_column("merchant_id").to_list()},
        geometry=gpd.points_from_xy(vs_df.get_column("lon_deg").to_list(), vs_df.get_column("lat_deg").to_list()),
        crs="EPSG:4326",
    )
    joined = gpd.sjoin(points, countries[["country_iso", "geometry"]], how="left", predicate="within")
    out: dict[int, str] = {}
    for row in joined[["merchant_id", "country_iso"]].itertuples(index=False):
        merchant_id = int(row.merchant_id)
        iso = "UNK" if row.country_iso is None else str(row.country_iso)
        if iso == "nan":
            iso = "UNK"
        out[merchant_id] = iso
    return out


@dataclass(frozen=True)
class SeedContext:
    seed: int
    run_id: str
    run_root: Path
    manifest_fingerprint: str
    vc_glob: str
    vs_glob: str
    ec_glob: str
    s3_report: Path
    state_reports: dict[str, Path]


def _seed_context(runs_root: Path, seed: int, run_id: str) -> SeedContext:
    run_root = runs_root / run_id
    receipt = _load_json(run_root / "run_receipt.json")
    receipt_seed = int(receipt.get("seed", -1))
    if receipt_seed != int(seed):
        raise ValueError(f"Seed mismatch run_id={run_id}: receipt.seed={receipt_seed}, expected={seed}")
    manifest = str(receipt.get("manifest_fingerprint") or "")
    if not manifest:
        raise ValueError(f"Missing manifest_fingerprint in run_receipt for run_id={run_id}")
    state_reports = {}
    for state in ("S1", "S2", "S3", "S4", "S5"):
        p = (
            run_root
            / "reports"
            / "layer1"
            / "3B"
            / f"state={state}"
            / f"seed={seed}"
            / f"manifest_fingerprint={manifest}"
            / "run_report.json"
        )
        if not p.exists():
            raise FileNotFoundError(f"Missing {state} run_report for seed={seed}, run_id={run_id}: {p}")
        state_reports[state] = p
    return SeedContext(
        seed=seed,
        run_id=run_id,
        run_root=run_root,
        manifest_fingerprint=manifest,
        vc_glob=str(
            run_root
            / "data/layer1/3B/virtual_classification"
            / f"seed={seed}"
            / f"manifest_fingerprint={manifest}"
            / "part-*.parquet"
        ),
        vs_glob=str(
            run_root
            / "data/layer1/3B/virtual_settlement"
            / f"seed={seed}"
            / f"manifest_fingerprint={manifest}"
            / "part-*.parquet"
        ),
        ec_glob=str(
            run_root
            / "data/layer1/3B/edge_catalogue"
            / f"seed={seed}"
            / f"manifest_fingerprint={manifest}"
            / "part-*.parquet"
        ),
        s3_report=state_reports["S3"],
        state_reports=state_reports,
    )


def _seed_metrics(ctx: SeedContext, countries: gpd.GeoDataFrame) -> dict[str, Any]:
    vc_df = pl.read_parquet(ctx.vc_glob)
    vs_df = pl.read_parquet(ctx.vs_glob)
    ec_df = pl.read_parquet(ctx.ec_glob)
    s3_report = _load_json(ctx.s3_report)

    edges_per = ec_df.group_by("merchant_id").len().rename({"len": "edges_per_merchant"})
    countries_per = ec_df.group_by("merchant_id").agg(pl.col("country_iso").n_unique().alias("countries_per_merchant"))
    top1 = ec_df.group_by("merchant_id").agg(pl.col("edge_weight").max().alias("top1_share"))
    country_weight_df = ec_df.group_by(["merchant_id", "country_iso"]).agg(
        pl.col("edge_weight").sum().alias("country_weight")
    )

    settlement_country_by_merchant = _settlement_country_map(vs_df, countries)
    settle_country_df = pl.DataFrame(
        {
            "merchant_id": [int(k) for k in settlement_country_by_merchant.keys()],
            "country_iso": [v for v in settlement_country_by_merchant.values()],
        }
    )
    overlap_df = (
        settle_country_df
        .join(country_weight_df, on=["merchant_id", "country_iso"], how="left")
        .with_columns(pl.col("country_weight").fill_null(0.0).alias("settlement_country_overlap"))
    )
    overlap_series = overlap_df.get_column("settlement_country_overlap")

    settle_coords = vs_df.select(
        [
            "merchant_id",
            pl.col("lat_deg").alias("lat_deg_settlement"),
            pl.col("lon_deg").alias("lon_deg_settlement"),
        ]
    )
    dist_join = ec_df.select(["merchant_id", "lat_deg", "lon_deg"]).join(settle_coords, on="merchant_id", how="inner")
    d = _haversine_km(
        dist_join.get_column("lat_deg").to_numpy(),
        dist_join.get_column("lon_deg").to_numpy(),
        dist_join.get_column("lat_deg_settlement").to_numpy(),
        dist_join.get_column("lon_deg_settlement").to_numpy(),
    )

    rule_id_vals = [str(v).strip() for v in vc_df.get_column("rule_id").to_list() if v is not None]
    rule_ver_vals = [str(v).strip() for v in vc_df.get_column("rule_version").to_list() if v is not None]
    non_empty_rule_id = [v for v in rule_id_vals if v]
    non_empty_rule_ver = [v for v in rule_ver_vals if v]

    rows_total = max(int(vc_df.height), 1)
    state_status = {state: str(_load_json(path).get("status") or "UNKNOWN") for state, path in ctx.state_reports.items()}

    metrics = {
        "edges_per_merchant_cv": _cv([float(v) for v in edges_per.get_column("edges_per_merchant").to_list()]),
        "countries_per_merchant_cv": _cv([float(v) for v in countries_per.get_column("countries_per_merchant").to_list()]),
        "top1_share_p50": float(top1.get_column("top1_share").median()),
        "median_pairwise_js": _median_pairwise_js(country_weight_df),
        "settlement_overlap_median": float(overlap_series.median()),
        "settlement_overlap_p75": float(overlap_series.quantile(0.75)),
        "settlement_distance_median_km": float(np.median(d)),
        "rule_id_non_null_rate": float(len(non_empty_rule_id) / rows_total),
        "rule_version_non_null_rate": float(len(non_empty_rule_ver) / rows_total),
        "active_rule_id_count": int(len(set(non_empty_rule_id))),
        "alias_max_abs_delta": float((s3_report.get("decode") or {}).get("max_abs_delta") or float("inf")),
        "state_status": state_status,
    }
    return metrics


def _eval_gate(observed: float | bool, op: str, value: Any) -> bool:
    if op == ">=":
        return float(observed) >= float(value)
    if op == "<=":
        return float(observed) <= float(value)
    if op == "range":
        lo = float(value[0])
        hi = float(value[1])
        return lo <= float(observed) <= hi
    if op == "bool_true":
        return bool(observed) is True
    raise ValueError(f"Unsupported gate op={op}")


def _specs() -> dict[str, dict[str, Any]]:
    return {
        "3B-V01": {"metric": "edges_per_merchant_cv", "op": ">=", "value": 0.25},
        "3B-V02": {"metric": "countries_per_merchant_cv", "op": ">=", "value": 0.20},
        "3B-V03": {"metric": "top1_share_p50", "op": "range", "value": [0.03, 0.20]},
        "3B-V04": {"metric": "median_pairwise_js", "op": ">=", "value": 0.05},
        "3B-V05": {"metric": "settlement_overlap_median", "op": ">=", "value": 0.03},
        "3B-V06": {"metric": "settlement_overlap_p75", "op": ">=", "value": 0.06},
        "3B-V07": {"metric": "settlement_distance_median_km", "op": "<=", "value": 6000.0},
        "3B-V08": {"metric": "rule_id_non_null_rate", "op": ">=", "value": 0.99},
        "3B-V09": {"metric": "rule_version_non_null_rate", "op": ">=", "value": 0.99},
        "3B-V10": {"metric": "active_rule_id_count", "op": ">=", "value": 3},
        "3B-V11": {"metric": "alias_max_abs_delta", "op": "<=", "value": 1.0e-6},
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-root", default="runs/fix-data-engine/segment_3B")
    ap.add_argument("--witness-seeds", default="42,101")
    ap.add_argument("--shadow-seeds", default="7,202")
    ap.add_argument("--seed-run", action="append", required=True, help="seed:run_id (repeatable)")
    ap.add_argument("--world-countries", default="reference/spatial/world_countries/2024/world_countries.parquet")
    ap.add_argument("--tag", default="p2_candidate")
    args = ap.parse_args()

    runs_root = Path(args.runs_root)
    witness_seeds = _parse_seed_list(args.witness_seeds)
    shadow_seeds = _parse_seed_list(args.shadow_seeds)
    all_seeds = witness_seeds + [s for s in shadow_seeds if s not in witness_seeds]
    seed_run_map = _parse_seed_run(args.seed_run or [])
    for seed in all_seeds:
        if seed not in seed_run_map:
            raise ValueError(f"Missing --seed-run mapping for seed={seed}")

    countries = gpd.read_parquet(args.world_countries)
    geom_col = "geometry" if "geometry" in countries.columns else ("geom" if "geom" in countries.columns else "")
    if not geom_col:
        raise ValueError("world_countries parquet must contain 'geometry' or 'geom' column")
    countries = countries[["country_iso", geom_col]].copy()
    if geom_col != "geometry":
        countries = countries.rename(columns={geom_col: "geometry"})
        countries = gpd.GeoDataFrame(countries, geometry="geometry", crs="EPSG:4326")
    countries["country_iso"] = countries["country_iso"].astype(str).str.upper()
    countries = countries.to_crs("EPSG:4326")

    specs = _specs()
    results: dict[int, dict[str, Any]] = {}
    manifests: set[str] = set()
    for seed in all_seeds:
        ctx = _seed_context(runs_root, seed, seed_run_map[seed])
        manifests.add(ctx.manifest_fingerprint)
        metrics = _seed_metrics(ctx, countries)
        checks = {gate: _eval_gate(metrics[spec["metric"]], spec["op"], spec["value"]) for gate, spec in specs.items()}
        structural = all(metrics["state_status"].get(state) == "PASS" for state in ("S2", "S3", "S4", "S5"))
        p2_core_pass = all(checks[g] for g in ("3B-V01", "3B-V02", "3B-V03", "3B-V04", "3B-V05", "3B-V06", "3B-V07"))
        p1_freeze_pass = all(checks[g] for g in ("3B-V08", "3B-V09", "3B-V10"))
        alias_pass = checks["3B-V11"]
        results[seed] = {
            "run_id": seed_run_map[seed],
            "manifest_fingerprint": ctx.manifest_fingerprint,
            "metrics": metrics,
            "checks": checks,
            "p2_core_pass": p2_core_pass,
            "p1_freeze_pass": p1_freeze_pass,
            "alias_pass": alias_pass,
            "structural_pass": structural,
            "seed_pass": p2_core_pass and alias_pass and structural,
        }

    witness_core_pass = all(results[s]["p2_core_pass"] for s in witness_seeds)
    witness_guardrails_pass = all(
        results[s]["alias_pass"] and results[s]["structural_pass"] and results[s]["p1_freeze_pass"]
        for s in witness_seeds
    )
    shadow_pass = all(results[s]["seed_pass"] for s in shadow_seeds) if shadow_seeds else True

    stability_metrics = ["top1_share_p50", "settlement_overlap_median", "settlement_distance_median_km", "median_pairwise_js"]
    stability_cvs: dict[str, float] = {}
    for metric in stability_metrics:
        vals = [float(results[s]["metrics"][metric]) for s in all_seeds]
        stability_cvs[metric] = _cv(vals)
    stability_b_pass = all(v <= 0.25 for v in stability_cvs.values())

    overall_pass = witness_core_pass and witness_guardrails_pass and shadow_pass and stability_b_pass
    decision = "UNLOCK_P3" if overall_pass else "HOLD_P2_REOPEN"

    payload = {
        "phase": "P2",
        "witness_seeds": witness_seeds,
        "shadow_seeds": shadow_seeds,
        "seed_run_map": {str(k): v for k, v in seed_run_map.items()},
        "manifests_observed": sorted(manifests),
        "witness_core_pass": witness_core_pass,
        "witness_guardrails_pass": witness_guardrails_pass,
        "shadow_pass": shadow_pass,
        "stability_b_pass": stability_b_pass,
        "stability_cvs": stability_cvs,
        "overall_pass": overall_pass,
        "decision": decision,
        "seeds": {str(seed): results[seed] for seed in all_seeds},
    }

    out_dir = runs_root / "reports"
    out_json = out_dir / f"segment3b_p2_summary_{args.tag}.json"
    out_md = out_dir / f"segment3b_p2_summary_{args.tag}.md"
    _write_json(out_json, payload)

    lines = [
        "# Segment 3B P2 Summary",
        "",
        f"- decision: `{decision}`",
        f"- witness_core_pass: `{witness_core_pass}`",
        f"- witness_guardrails_pass: `{witness_guardrails_pass}`",
        f"- shadow_pass: `{shadow_pass}`",
        f"- stability_b_pass: `{stability_b_pass}`",
        "",
        "| seed | run_id | V01 | V02 | V03 | V04 | V05 | V06 | V07 | V11 | structural | P1-freeze |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for seed in all_seeds:
        checks = results[seed]["checks"]
        lines.append(
            "| {seed} | {run_id} | {v01} | {v02} | {v03} | {v04} | {v05} | {v06} | {v07} | {v11} | {structural} | {p1} |".format(
                seed=seed,
                run_id=results[seed]["run_id"],
                v01="PASS" if checks["3B-V01"] else "FAIL",
                v02="PASS" if checks["3B-V02"] else "FAIL",
                v03="PASS" if checks["3B-V03"] else "FAIL",
                v04="PASS" if checks["3B-V04"] else "FAIL",
                v05="PASS" if checks["3B-V05"] else "FAIL",
                v06="PASS" if checks["3B-V06"] else "FAIL",
                v07="PASS" if checks["3B-V07"] else "FAIL",
                v11="PASS" if checks["3B-V11"] else "FAIL",
                structural="PASS" if results[seed]["structural_pass"] else "FAIL",
                p1="PASS" if results[seed]["p1_freeze_pass"] else "FAIL",
            )
        )
    lines.extend(
        [
            "",
            "## Stability CVs",
            "",
            "| metric | cv | pass_b (<=0.25) |",
            "|---|---:|---:|",
        ]
    )
    for metric, cv in stability_cvs.items():
        lines.append(f"| {metric} | {cv:.6f} | {'PASS' if cv <= 0.25 else 'FAIL'} |")
    _write_md(out_md, "\n".join(lines) + "\n")

    print(f"[segment3b-p2] summary_json={out_json.as_posix()}")
    print(f"[segment3b-p2] summary_md={out_md.as_posix()}")
    print(f"[segment3b-p2] decision={decision}")


if __name__ == "__main__":
    main()
