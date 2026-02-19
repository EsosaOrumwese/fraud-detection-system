#!/usr/bin/env python3
"""Score Segment 3B P0 baseline realism surfaces across required seeds."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import polars as pl


REQUIRED_REALISM_TEST_TYPES = {
    "EDGE_HETEROGENEITY",
    "SETTLEMENT_COHERENCE",
    "CLASSIFICATION_EXPLAINABILITY",
    "ALIAS_FIDELITY",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _parse_seed_list(raw: str) -> list[int]:
    out: list[int] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        out.append(int(token))
    if not out:
        raise ValueError("required seeds list is empty")
    return out


def _parse_seed_run_overrides(raw_items: list[str]) -> dict[int, str]:
    overrides: dict[int, str] = {}
    for item in raw_items:
        if ":" not in item:
            raise ValueError(f"Invalid --seed-run value: {item} (expected seed:run_id)")
        seed_raw, run_id = item.split(":", 1)
        overrides[int(seed_raw.strip())] = run_id.strip()
    return overrides


def _cv(values: list[float]) -> float:
    if not values:
        return float("nan")
    mean = float(sum(values)) / float(len(values))
    if abs(mean) < 1e-12:
        if max(abs(v) for v in values) < 1e-12:
            return 0.0
        return float("inf")
    std = statistics.pstdev(values)
    return float(std / mean)


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


def _resolve_latest_seed_run(runs_root: Path, seed: int) -> str:
    candidates: list[tuple[float, str]] = []
    for receipt_path in runs_root.glob("*/run_receipt.json"):
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
        if int(payload.get("seed", -1)) != int(seed):
            continue
        run_id = str(payload.get("run_id") or "")
        if not run_id:
            continue
        candidates.append((receipt_path.stat().st_mtime, run_id))
    if not candidates:
        raise FileNotFoundError(f"No run_receipt.json with seed={seed} under {runs_root}")
    return sorted(candidates, key=lambda item: item[0])[-1][1]


@dataclass(frozen=True)
class SeedContext:
    seed: int
    run_id: str
    run_root: Path
    manifest_fingerprint: str
    parameter_hash: str
    receipt_path: Path
    s3_report_path: Path
    vc_glob: str
    vs_glob: str
    ec_glob: str
    vv_path: Path


def _resolve_seed_context(runs_root: Path, seed: int, run_id: str) -> SeedContext:
    run_root = runs_root / run_id
    if not run_root.exists():
        raise FileNotFoundError(f"Run root not found for seed={seed}: {run_root}")
    receipt_path = run_root / "run_receipt.json"
    if not receipt_path.exists():
        raise FileNotFoundError(f"run_receipt.json missing for seed={seed}: {receipt_path}")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    manifest = str(receipt.get("manifest_fingerprint") or "")
    parameter_hash = str(receipt.get("parameter_hash") or "")
    receipt_seed = int(receipt.get("seed", -1))
    if receipt_seed != int(seed):
        raise ValueError(f"Seed mismatch for run {run_id}: receipt.seed={receipt_seed}, expected={seed}")
    if not manifest or not parameter_hash:
        raise ValueError(f"Run {run_id} missing manifest_fingerprint/parameter_hash")

    s3_report_path = (
        run_root
        / "reports/layer1/3B/state=S3"
        / f"seed={seed}"
        / f"manifest_fingerprint={manifest}"
        / "run_report.json"
    )
    if not s3_report_path.exists():
        raise FileNotFoundError(f"S3 run_report missing for run {run_id}: {s3_report_path}")

    vc_glob = str(
        run_root
        / "data/layer1/3B/virtual_classification"
        / f"seed={seed}"
        / f"manifest_fingerprint={manifest}"
        / "part-*.parquet"
    )
    vs_glob = str(
        run_root
        / "data/layer1/3B/virtual_settlement"
        / f"seed={seed}"
        / f"manifest_fingerprint={manifest}"
        / "part-*.parquet"
    )
    ec_glob = str(
        run_root
        / "data/layer1/3B/edge_catalogue"
        / f"seed={seed}"
        / f"manifest_fingerprint={manifest}"
        / "part-*.parquet"
    )
    vv_path = (
        run_root
        / "data/layer1/3B/virtual_validation_contract"
        / f"manifest_fingerprint={manifest}"
        / "virtual_validation_contract_3B.parquet"
    )
    if not vv_path.exists():
        raise FileNotFoundError(f"virtual_validation_contract_3B missing for run {run_id}: {vv_path}")

    return SeedContext(
        seed=seed,
        run_id=run_id,
        run_root=run_root,
        manifest_fingerprint=manifest,
        parameter_hash=parameter_hash,
        receipt_path=receipt_path,
        s3_report_path=s3_report_path,
        vc_glob=vc_glob,
        vs_glob=vs_glob,
        ec_glob=ec_glob,
        vv_path=vv_path,
    )


def _settlement_country_map(vs_df: pl.DataFrame, countries: gpd.GeoDataFrame) -> dict[int, str]:
    points = gpd.GeoDataFrame(
        {
            "merchant_id": vs_df.get_column("merchant_id").to_list(),
        },
        geometry=gpd.points_from_xy(
            vs_df.get_column("lon_deg").to_list(),
            vs_df.get_column("lat_deg").to_list(),
        ),
        crs="EPSG:4326",
    )
    joined = gpd.sjoin(
        points,
        countries[["country_iso", "geometry"]],
        how="left",
        predicate="within",
    )
    out: dict[int, str] = {}
    for row in joined[["merchant_id", "country_iso"]].itertuples(index=False):
        merchant_id = int(row.merchant_id)
        iso = str(row.country_iso) if row.country_iso is not None else "UNK"
        if iso == "nan":
            iso = "UNK"
        out[merchant_id] = iso
    return out


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
    eps = 1e-12
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
        js = 0.5 * (kl_p + kl_q)
        js_vals.append(js)
    if not js_vals:
        return 0.0
    return float(np.median(np.concatenate(js_vals)))


def _seed_metrics(ctx: SeedContext, countries: gpd.GeoDataFrame) -> dict[str, Any]:
    vc_df = pl.read_parquet(ctx.vc_glob)
    vs_df = pl.read_parquet(ctx.vs_glob)
    ec_df = pl.read_parquet(ctx.ec_glob)
    vv_df = pl.read_parquet(ctx.vv_path)
    s3_report = json.loads(ctx.s3_report_path.read_text(encoding="utf-8"))

    edges_per = ec_df.group_by("merchant_id").len().rename({"len": "edges_per_merchant"})
    countries_per = (
        ec_df.group_by("merchant_id")
        .agg(pl.col("country_iso").n_unique().alias("countries_per_merchant"))
    )
    top1 = (
        ec_df.group_by("merchant_id")
        .agg(pl.col("edge_weight").max().alias("top1_share"))
    )
    country_weight_df = (
        ec_df.group_by(["merchant_id", "country_iso"])
        .agg(pl.col("edge_weight").sum().alias("country_weight"))
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
            "tzid_settlement",
        ]
    )
    dist_join = (
        ec_df.select(["merchant_id", "lat_deg", "lon_deg"])
        .join(settle_coords, on="merchant_id", how="inner")
    )
    d = _haversine_km(
        dist_join.get_column("lat_deg").to_numpy(),
        dist_join.get_column("lon_deg").to_numpy(),
        dist_join.get_column("lat_deg_settlement").to_numpy(),
        dist_join.get_column("lon_deg_settlement").to_numpy(),
    )

    rule_id_values = [str(v).strip() for v in vc_df.get_column("rule_id").to_list() if v is not None]
    rule_version_values = [str(v).strip() for v in vc_df.get_column("rule_version").to_list() if v is not None]
    non_empty_rule_id = [v for v in rule_id_values if v]
    non_empty_rule_version = [v for v in rule_version_values if v]
    total_rows = int(vc_df.height)

    tz_counts = (
        vs_df.group_by("tzid_settlement")
        .len()
        .sort("len", descending=True)
    )
    tz_top1_share = float(tz_counts.get_column("len")[0] / max(1, vs_df.height)) if tz_counts.height else 0.0

    test_types = set(str(v) for v in vv_df.get_column("test_type").to_list() if v is not None)
    realism_block_active = REQUIRED_REALISM_TEST_TYPES.issubset(test_types)
    decode = s3_report.get("decode") or {}

    metrics = {
        "virtual_rate": float(vc_df.get_column("is_virtual").cast(pl.Float64).mean()),
        "virtual_rows_total": int(total_rows),
        "virtual_rows_marked": int(vc_df.get_column("is_virtual").sum()),
        "edges_per_merchant_cv": _cv([float(v) for v in edges_per.get_column("edges_per_merchant").to_list()]),
        "countries_per_merchant_cv": _cv([float(v) for v in countries_per.get_column("countries_per_merchant").to_list()]),
        "top1_share_p50": float(top1.get_column("top1_share").median()),
        "top1_share_p10": float(top1.get_column("top1_share").quantile(0.10)),
        "top1_share_p90": float(top1.get_column("top1_share").quantile(0.90)),
        "median_pairwise_js": _median_pairwise_js(country_weight_df),
        "settlement_overlap_median": float(overlap_series.median()),
        "settlement_overlap_p75": float(overlap_series.quantile(0.75)),
        "settlement_distance_median_km": float(np.median(d)),
        "rule_id_non_null_rate": float(len(non_empty_rule_id) / max(1, total_rows)),
        "rule_version_non_null_rate": float(len(non_empty_rule_version) / max(1, total_rows)),
        "active_rule_id_count": int(len(set(non_empty_rule_id))),
        "alias_max_abs_delta": float(decode.get("max_abs_delta") or float("inf")),
        "realism_block_active_enforced": bool(realism_block_active),
        "settlement_tzid_top1_share": tz_top1_share,
        "virtual_validation_test_count": int(vv_df.height),
        "virtual_validation_test_types": sorted(test_types),
    }
    return metrics


def _gate_specs() -> dict[str, dict[str, Any]]:
    return {
        "3B-V01": {"metric": "edges_per_merchant_cv", "op": ">=", "value": 0.25, "state": "S2"},
        "3B-V02": {"metric": "countries_per_merchant_cv", "op": ">=", "value": 0.20, "state": "S2"},
        "3B-V03": {"metric": "top1_share_p50", "op": "range", "value": [0.03, 0.20], "state": "S2"},
        "3B-V04": {"metric": "median_pairwise_js", "op": ">=", "value": 0.05, "state": "S2"},
        "3B-V05": {"metric": "settlement_overlap_median", "op": ">=", "value": 0.03, "state": "S2"},
        "3B-V06": {"metric": "settlement_overlap_p75", "op": ">=", "value": 0.06, "state": "S2"},
        "3B-V07": {"metric": "settlement_distance_median_km", "op": "<=", "value": 6000.0, "state": "S2"},
        "3B-V08": {"metric": "rule_id_non_null_rate", "op": ">=", "value": 0.99, "state": "S1"},
        "3B-V09": {"metric": "rule_version_non_null_rate", "op": ">=", "value": 0.99, "state": "S1"},
        "3B-V10": {"metric": "active_rule_id_count", "op": ">=", "value": 3, "state": "S1"},
        "3B-V11": {"metric": "alias_max_abs_delta", "op": "<=", "value": 1e-6, "state": "S3"},
        "3B-V12": {"metric": "realism_block_active_enforced", "op": "bool_true", "value": True, "state": "S4"},
    }


def _stretch_specs() -> dict[str, dict[str, Any]]:
    return {
        "3B-S01": {"metric": "edges_per_merchant_cv", "op": ">=", "value": 0.40, "state": "S2"},
        "3B-S02": {"metric": "countries_per_merchant_cv", "op": ">=", "value": 0.35, "state": "S2"},
        "3B-S03": {"metric": "top1_share_p50", "op": "range", "value": [0.05, 0.30], "state": "S2"},
        "3B-S04": {"metric": "median_pairwise_js", "op": ">=", "value": 0.10, "state": "S2"},
        "3B-S05": {"metric": "settlement_overlap_median", "op": ">=", "value": 0.07, "state": "S2"},
        "3B-S06": {"metric": "settlement_overlap_p75", "op": ">=", "value": 0.12, "state": "S2"},
        "3B-S07": {"metric": "settlement_distance_median_km", "op": "<=", "value": 4500.0, "state": "S2"},
        "3B-S08A": {"metric": "rule_id_non_null_rate", "op": ">=", "value": 0.998, "state": "S1"},
        "3B-S08B": {"metric": "rule_version_non_null_rate", "op": ">=", "value": 0.998, "state": "S1"},
        "3B-S09": {"metric": "active_rule_id_count", "op": ">=", "value": 5, "state": "S1"},
        "3B-S10": {"metric": "settlement_tzid_top1_share", "op": "<=", "value": 0.18, "state": "S1"},
    }


def _evaluate_gate(observed: float | bool, op: str, value: Any) -> tuple[bool, float, float | None]:
    if op == ">=":
        threshold = float(value)
        miss = max(0.0, threshold - float(observed))
        pct = (miss / threshold) if threshold != 0.0 else None
        return float(observed) >= threshold, miss, pct
    if op == "<=":
        threshold = float(value)
        miss = max(0.0, float(observed) - threshold)
        pct = (miss / threshold) if threshold != 0.0 else None
        return float(observed) <= threshold, miss, pct
    if op == "range":
        low = float(value[0])
        high = float(value[1])
        if float(observed) < low:
            miss = low - float(observed)
            pct = miss / low if low != 0.0 else None
            return False, miss, pct
        if float(observed) > high:
            miss = float(observed) - high
            pct = miss / high if high != 0.0 else None
            return False, miss, pct
        return True, 0.0, 0.0
    if op == "bool_true":
        ok = bool(observed) is True
        return ok, 0.0 if ok else 1.0, None
    raise ValueError(f"Unsupported gate operator: {op}")


def _evaluate_gates(metrics: dict[str, Any], specs: dict[str, dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], bool]:
    out: dict[str, dict[str, Any]] = {}
    all_pass = True
    for gate_id, spec in specs.items():
        observed = metrics[spec["metric"]]
        passed, miss_abs, miss_pct = _evaluate_gate(observed, spec["op"], spec["value"])
        all_pass = all_pass and passed
        out[gate_id] = {
            "metric": spec["metric"],
            "state": spec["state"],
            "operator": spec["op"],
            "threshold": spec["value"],
            "observed": observed,
            "pass": bool(passed),
            "miss_abs": float(miss_abs),
            "miss_pct": None if miss_pct is None else float(miss_pct),
        }
    return out, all_pass


def _failure_trace_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Segment 3B P0 Failure Trace",
        "",
        f"- generated_utc: `{payload['generated_utc']}`",
        f"- overall_verdict: `{payload['overall_verdict']}`",
        "",
        "## Ranked Failing Gates",
    ]
    failures = payload.get("ranked_failures", [])
    if not failures:
        lines.append("- none")
        return "\n".join(lines) + "\n"
    lines.append("")
    lines.append("| rank | gate_id | seed | state | observed | threshold | miss_abs | miss_pct | lane |")
    lines.append("|---|---|---:|---|---:|---|---:|---:|---|")
    for idx, item in enumerate(failures, start=1):
        miss_pct = item.get("miss_pct")
        miss_pct_txt = "n/a" if miss_pct is None else f"{100.0 * float(miss_pct):.2f}%"
        lines.append(
            f"| {idx} | {item['gate_id']} | {item['seed']} | {item['state']} | "
            f"{float(item['observed']):.6g} | {item['threshold']} | {float(item['miss_abs']):.6g} | "
            f"{miss_pct_txt} | {item['lane']} |"
        )
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Score Segment 3B P0 baseline across required seeds.")
    parser.add_argument("--runs-root", default="runs/fix-data-engine/segment_3B")
    parser.add_argument("--required-seeds", default="42,7,101,202")
    parser.add_argument("--seed-run", action="append", default=[], help="Seed to run-id override, format seed:run_id")
    parser.add_argument("--baseline-seed", type=int, default=42)
    parser.add_argument(
        "--world-countries",
        default="reference/spatial/world_countries/2024/world_countries.parquet",
    )
    parser.add_argument("--out-dir", default="")
    args = parser.parse_args()

    runs_root = Path(args.runs_root)
    out_dir = Path(args.out_dir) if args.out_dir else runs_root / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    required_seeds = _parse_seed_list(args.required_seeds)
    seed_run_overrides = _parse_seed_run_overrides(args.seed_run)

    seed_run_map: dict[int, str] = {}
    for seed in required_seeds:
        seed_run_map[seed] = seed_run_overrides.get(seed) or _resolve_latest_seed_run(runs_root, seed)

    world = gpd.read_parquet(args.world_countries)
    if "geom" in world.columns:
        world = world.set_geometry("geom")
    if world.geometry.name != "geometry":
        world = world.rename_geometry("geometry")
    world = world[["country_iso", "geometry"]].to_crs("EPSG:4326")

    contexts: dict[int, SeedContext] = {
        seed: _resolve_seed_context(runs_root, seed, run_id)
        for seed, run_id in seed_run_map.items()
    }

    hard_specs = _gate_specs()
    stretch_specs = _stretch_specs()

    seed_payloads: dict[int, dict[str, Any]] = {}
    for seed in required_seeds:
        ctx = contexts[seed]
        metrics = _seed_metrics(ctx, world)
        hard_gates, hard_pass = _evaluate_gates(metrics, hard_specs)
        stretch_gates, stretch_pass = _evaluate_gates(metrics, stretch_specs)
        verdict = "PASS_BPLUS" if (hard_pass and stretch_pass) else ("PASS_B" if hard_pass else "FAIL_REALISM")
        seed_payload = {
            "segment": "3B",
            "phase": "P0",
            "seed": int(seed),
            "run_id": ctx.run_id,
            "manifest_fingerprint": ctx.manifest_fingerprint,
            "parameter_hash": ctx.parameter_hash,
            "generated_utc": _utc_now(),
            "metrics": metrics,
            "hard_gates": hard_gates,
            "stretch_gates": stretch_gates,
            "hard_pass": bool(hard_pass),
            "stretch_pass": bool(stretch_pass),
            "verdict": verdict,
            "provenance": {
                "receipt_path": str(ctx.receipt_path).replace("\\", "/"),
                "virtual_classification_glob": ctx.vc_glob.replace("\\", "/"),
                "virtual_settlement_glob": ctx.vs_glob.replace("\\", "/"),
                "edge_catalogue_glob": ctx.ec_glob.replace("\\", "/"),
                "virtual_validation_contract_path": str(ctx.vv_path).replace("\\", "/"),
                "s3_report_path": str(ctx.s3_report_path).replace("\\", "/"),
            },
        }
        seed_payloads[seed] = seed_payload
        _write_json(out_dir / f"3B_validation_metrics_seed_{seed}.json", seed_payload)

    top1_vals = [float(seed_payloads[s]["metrics"]["top1_share_p50"]) for s in required_seeds]
    overlap_vals = [float(seed_payloads[s]["metrics"]["settlement_overlap_median"]) for s in required_seeds]
    distance_vals = [float(seed_payloads[s]["metrics"]["settlement_distance_median_km"]) for s in required_seeds]
    js_vals = [float(seed_payloads[s]["metrics"]["median_pairwise_js"]) for s in required_seeds]
    virtual_rate_vals = [float(seed_payloads[s]["metrics"]["virtual_rate"]) for s in required_seeds]

    x01_key_cv = {
        "top1_share_p50": _cv(top1_vals),
        "settlement_overlap_median": _cv(overlap_vals),
        "settlement_distance_median_km": _cv(distance_vals),
        "median_pairwise_js": _cv(js_vals),
    }
    x01_b_pass = all(float(v) <= 0.25 for v in x01_key_cv.values())
    x01_bplus_pass = all(float(v) <= 0.15 for v in x01_key_cv.values())
    x02_pass = all(0.02 <= v <= 0.08 for v in virtual_rate_vals)
    x03_pass = all(bool(seed_payloads[s]["hard_pass"]) for s in required_seeds)

    ranked_failures: list[dict[str, Any]] = []
    for seed in required_seeds:
        seed_item = seed_payloads[seed]
        for gate_id, gate in seed_item["hard_gates"].items():
            if gate["pass"]:
                continue
            ranked_failures.append(
                {
                    "seed": seed,
                    "gate_id": gate_id,
                    "state": gate["state"],
                    "observed": gate["observed"],
                    "threshold": gate["threshold"],
                    "miss_abs": gate["miss_abs"],
                    "miss_pct": gate["miss_pct"],
                    "lane": "P1" if gate["state"] == "S1" else ("P2" if gate["state"] == "S2" else "P3"),
                    "tier": 0,
                }
            )
        for gate_id, gate in seed_item["stretch_gates"].items():
            if gate["pass"]:
                continue
            ranked_failures.append(
                {
                    "seed": seed,
                    "gate_id": gate_id,
                    "state": gate["state"],
                    "observed": gate["observed"],
                    "threshold": gate["threshold"],
                    "miss_abs": gate["miss_abs"],
                    "miss_pct": gate["miss_pct"],
                    "lane": "P1" if gate["state"] == "S1" else ("P2" if gate["state"] == "S2" else "P3"),
                    "tier": 1,
                }
            )
    ranked_failures = sorted(
        ranked_failures,
        key=lambda row: (
            int(row["tier"]),
            -float(row["miss_pct"] if row["miss_pct"] is not None else 0.0),
            -float(row["miss_abs"]),
            int(row["seed"]),
            str(row["gate_id"]),
        ),
    )

    all_hard = all(seed_payloads[s]["hard_pass"] for s in required_seeds)
    all_stretch = all(seed_payloads[s]["stretch_pass"] for s in required_seeds)
    b_pass = bool(all_hard and x01_b_pass and x02_pass and x03_pass)
    bplus_pass = bool(all_hard and all_stretch and x01_bplus_pass and x02_pass and x03_pass)
    overall_verdict = "PASS_BPLUS" if bplus_pass else ("PASS_B" if b_pass else "FAIL_REALISM")

    baseline_seed = int(args.baseline_seed)
    if baseline_seed not in contexts:
        raise ValueError(f"baseline seed {baseline_seed} is not in selected required seeds")
    baseline_ctx = contexts[baseline_seed]
    baseline_lock = {
        "segment": "3B",
        "phase": "P0",
        "generated_utc": _utc_now(),
        "baseline_seed": baseline_seed,
        "baseline_run_id": baseline_ctx.run_id,
        "baseline_manifest_fingerprint": baseline_ctx.manifest_fingerprint,
        "baseline_parameter_hash": baseline_ctx.parameter_hash,
        "required_seeds": required_seeds,
        "selected_seed_run_map": {int(seed): str(run_id) for seed, run_id in seed_run_map.items()},
        "dataset_surface_map": {
            str(seed): {
                "virtual_classification_glob": contexts[seed].vc_glob.replace("\\", "/"),
                "virtual_settlement_glob": contexts[seed].vs_glob.replace("\\", "/"),
                "edge_catalogue_glob": contexts[seed].ec_glob.replace("\\", "/"),
                "virtual_validation_contract_path": str(contexts[seed].vv_path).replace("\\", "/"),
            }
            for seed in required_seeds
        },
    }

    scorer_contract = {
        "segment": "3B",
        "phase": "P0",
        "generated_utc": _utc_now(),
        "version": "3B-P0-scorer-v1",
        "required_seeds": required_seeds,
        "hard_gates": hard_specs,
        "stretch_gates": stretch_specs,
        "cross_seed_checks": {
            "3B-X01": {
                "description": "cross-seed CV of key medians",
                "metrics": ["top1_share_p50", "settlement_overlap_median", "settlement_distance_median_km", "median_pairwise_js"],
                "threshold_b": 0.25,
                "threshold_bplus": 0.15,
            },
            "3B-X02": {
                "description": "virtual prevalence within policy band on all seeds",
                "virtual_rate_min": 0.02,
                "virtual_rate_max": 0.08,
            },
            "3B-X03": {
                "description": "no hard gate failures on any seed",
            },
        },
        "verdict_rules": {
            "PASS_B": "all hard gates pass on all seeds + X01(B) + X02 + X03",
            "PASS_BPLUS": "PASS_B conditions + all stretch gates pass on all seeds + X01(B+)",
            "FAIL_REALISM": "otherwise",
        },
    }

    cross_seed_summary = {
        "segment": "3B",
        "phase": "P0",
        "generated_utc": _utc_now(),
        "required_seeds": required_seeds,
        "selected_seed_run_map": {int(seed): str(run_id) for seed, run_id in seed_run_map.items()},
        "seed_verdicts": {int(seed): str(seed_payloads[seed]["verdict"]) for seed in required_seeds},
        "cross_seed_checks": {
            "3B-X01": {
                "metric_cvs": x01_key_cv,
                "pass_b": bool(x01_b_pass),
                "pass_bplus": bool(x01_bplus_pass),
            },
            "3B-X02": {
                "virtual_rate_values": virtual_rate_vals,
                "band": [0.02, 0.08],
                "pass": bool(x02_pass),
            },
            "3B-X03": {
                "all_hard_gates_pass": bool(x03_pass),
                "pass": bool(x03_pass),
            },
        },
        "overall": {
            "all_seed_hard_pass": bool(all_hard),
            "all_seed_stretch_pass": bool(all_stretch),
            "pass_b": bool(b_pass),
            "pass_bplus": bool(bplus_pass),
            "overall_verdict": overall_verdict,
        },
        "ranked_failures": ranked_failures,
    }

    handoff_pack = {
        "segment": "3B",
        "phase": "P0",
        "generated_utc": _utc_now(),
        "overall_verdict": overall_verdict,
        "baseline_lock_path": str(out_dir / "segment3b_p0_baseline_lock.json").replace("\\", "/"),
        "scorer_contract_path": str(out_dir / "segment3b_p0_scorer_contract_v1.json").replace("\\", "/"),
        "cross_seed_summary_path": str(out_dir / "3B_validation_cross_seed_summary.json").replace("\\", "/"),
        "seed_metric_paths": {
            str(seed): str(out_dir / f"3B_validation_metrics_seed_{seed}.json").replace("\\", "/")
            for seed in required_seeds
        },
        "p1_entry_targets": {
            "rule_id_non_null_rate_min": 0.99,
            "rule_version_non_null_rate_min": 0.99,
            "active_rule_id_count_min": 3,
            "stretch_rule_id_non_null_rate_min": 0.998,
            "stretch_rule_version_non_null_rate_min": 0.998,
            "stretch_active_rule_id_count_min": 5,
        },
        "ranked_failures": ranked_failures,
    }

    _write_json(out_dir / "segment3b_p0_baseline_lock.json", baseline_lock)
    _write_json(out_dir / "segment3b_p0_scorer_contract_v1.json", scorer_contract)
    _write_json(out_dir / "3B_validation_cross_seed_summary.json", cross_seed_summary)
    _write_json(out_dir / "segment3b_p0_handoff_pack.json", handoff_pack)
    _write_text(out_dir / "3B_validation_failure_trace.md", _failure_trace_md(handoff_pack | {"generated_utc": _utc_now()}))

    print(str(out_dir / "segment3b_p0_baseline_lock.json").replace("\\", "/"))
    print(str(out_dir / "3B_validation_cross_seed_summary.json").replace("\\", "/"))
    print(str(out_dir / "segment3b_p0_handoff_pack.json").replace("\\", "/"))
    print(f"overall_verdict={overall_verdict}")


if __name__ == "__main__":
    main()
