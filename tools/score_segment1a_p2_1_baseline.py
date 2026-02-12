#!/usr/bin/env python3
"""Build Segment 1A P2.1 baseline scorecard (S0->S6 surfaces)."""

from __future__ import annotations

import argparse
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import polars as pl
import yaml
from scipy.stats import spearmanr


RUN_ID_RE = re.compile(r"^[0-9a-f]{32}$")
MEDIAN_C_B_BAND = (5.0, 15.0)
SPEARMAN_MIN_B = 0.30
MEDIAN_RHO_MIN_B = 0.10
SHARE_EXHAUSTED_MAX = 0.02
SHARE_HIGH_REJECT_MAX = 0.10
HIGH_REJECT_THRESHOLD = 16


def _resolve_run_id(runs_root: Path, run_id: str | None) -> str:
    if run_id:
        if not RUN_ID_RE.fullmatch(run_id):
            raise ValueError(f"invalid run_id format: {run_id!r}")
        receipt_path = runs_root / run_id / "run_receipt.json"
        if not receipt_path.exists():
            raise FileNotFoundError(f"run receipt not found: {receipt_path}")
        return run_id

    receipts = sorted(
        runs_root.glob("*/run_receipt.json"),
        key=lambda path: path.stat().st_mtime,
    )
    if not receipts:
        raise FileNotFoundError(f"no run_receipt.json files found under {runs_root}")
    return receipts[-1].parent.name


def _read_receipt(run_root: Path) -> dict[str, Any]:
    receipt_path = run_root / "run_receipt.json"
    if not receipt_path.exists():
        raise FileNotFoundError(f"run receipt not found: {receipt_path}")
    return json.loads(receipt_path.read_text(encoding="utf-8"))


def _require_paths(run_root: Path, pattern: str, label: str) -> list[Path]:
    paths = sorted(run_root.glob(pattern))
    if not paths:
        raise FileNotFoundError(f"missing required surface {label}: pattern={pattern}")
    return paths


def _optional_paths(run_root: Path, pattern: str) -> list[Path]:
    return sorted(run_root.glob(pattern))


def _count_jsonl_rows(paths: list[Path]) -> int:
    total = 0
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    total += 1
    return total


def _iter_jsonl(paths: list[Path]) -> Any:
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    yield json.loads(line)


def _load_s3_integerisation_policy(
    run_root: Path, manifest_fingerprint: str
) -> dict[str, Any]:
    sealed_inputs_path = (
        run_root
        / "data"
        / "layer1"
        / "1A"
        / "sealed_inputs"
        / f"manifest_fingerprint={manifest_fingerprint}"
        / "sealed_inputs_1A.json"
    )
    if not sealed_inputs_path.exists():
        raise FileNotFoundError(f"sealed inputs not found: {sealed_inputs_path}")
    sealed_inputs = json.loads(sealed_inputs_path.read_text(encoding="utf-8"))
    policy_entry = next(
        (
            row
            for row in sealed_inputs
            if isinstance(row, dict)
            and row.get("asset_id") == "policy.s3.integerisation.yaml"
        ),
        None,
    )
    if not isinstance(policy_entry, dict):
        raise KeyError(
            "asset_id=policy.s3.integerisation.yaml missing from sealed_inputs_1A.json"
        )
    policy_path = Path(str(policy_entry.get("path", "")))
    if not policy_path.exists():
        raise FileNotFoundError(f"s3 integerisation policy not found: {policy_path}")
    payload = yaml.safe_load(policy_path.read_text(encoding="utf-8")) or {}
    return {
        "path": policy_path.as_posix(),
        "emit_integerised_counts": bool(payload.get("emit_integerised_counts", False)),
        "emit_site_sequence": bool(payload.get("emit_site_sequence", False)),
    }


def _load_strata(
    run_root: Path, parameter_hash: str, manifest_fingerprint: str
) -> tuple[pl.DataFrame, str]:
    hdm_paths = sorted(
        run_root.glob(
            "data/layer1/1A/hurdle_design_matrix/"
            f"parameter_hash={parameter_hash}/part-*.parquet"
        )
    )
    if hdm_paths:
        strata = pl.read_parquet(hdm_paths).select(
            ["merchant_id", "channel", "mcc", "gdp_bucket_id"]
        )
        source = "hurdle_design_matrix"
    else:
        sealed_inputs_path = (
            run_root
            / "data"
            / "layer1"
            / "1A"
            / "sealed_inputs"
            / f"manifest_fingerprint={manifest_fingerprint}"
            / "sealed_inputs_1A.json"
        )
        if not sealed_inputs_path.exists():
            raise FileNotFoundError(f"sealed inputs not found: {sealed_inputs_path}")
        sealed_inputs = json.loads(sealed_inputs_path.read_text(encoding="utf-8"))
        by_id = {
            row["asset_id"]: row
            for row in sealed_inputs
            if isinstance(row, dict) and "asset_id" in row
        }
        tx_path = Path(str(by_id["transaction_schema_merchant_ids"]["path"]))
        gdp_path = Path(str(by_id["gdp_bucket_map_2024"]["path"]))
        tx = pl.read_parquet(tx_path).select(
            ["merchant_id", "channel", "mcc", "home_country_iso"]
        )
        gdp = pl.read_parquet(gdp_path).select(
            [
                pl.col("country_iso").alias("home_country_iso"),
                pl.col("bucket_id").cast(pl.Int32).alias("gdp_bucket_id"),
            ]
        )
        strata = tx.join(gdp, on="home_country_iso", how="left").select(
            ["merchant_id", "channel", "mcc", "gdp_bucket_id"]
        )
        source = "transaction_schema_merchant_ids+gdp_bucket_map_2024"

    strata = strata.with_columns(
        ((pl.col("mcc").cast(pl.Int64) // 1000) * 1000)
        .cast(pl.Int64)
        .alias("mcc_broad_group")
    )
    return strata.select(
        ["merchant_id", "channel", "mcc_broad_group", "gdp_bucket_id"]
    ), source


def _spearman(values_x: list[float], values_y: list[float]) -> float | None:
    if len(values_x) < 2 or len(values_y) < 2:
        return None
    corr = spearmanr(values_x, values_y).correlation
    if corr is None or math.isnan(corr):
        return None
    return float(corr)


def _score_subset(
    subset: pl.DataFrame,
    exhausted_merchants: set[int],
    high_reject_merchants: set[int],
) -> dict[str, Any]:
    merchant_ids = subset["merchant_id"].to_list()
    c_values = subset["C_m"].cast(pl.Float64).to_list()
    r_values = subset["R_m"].cast(pl.Float64).to_list()
    rho_values = subset["rho_m"].cast(pl.Float64).to_list()

    median_c = float(subset.select(pl.col("C_m").median()).item()) if merchant_ids else 0.0
    median_rho = (
        float(subset.select(pl.col("rho_m").median()).item()) if merchant_ids else 0.0
    )
    spearman = _spearman(c_values, r_values)

    c_pos_merchants = {
        int(mid)
        for mid, c_val in zip(merchant_ids, subset["C_m"].to_list(), strict=True)
        if int(c_val) > 0
    }
    denom = len(c_pos_merchants)
    exhausted_num = len(c_pos_merchants & exhausted_merchants)
    high_reject_num = len(c_pos_merchants & high_reject_merchants)
    share_exhausted = (exhausted_num / denom) if denom > 0 else 0.0
    share_high_reject = (high_reject_num / denom) if denom > 0 else 0.0

    checks = {
        "median_C_in_B_band": MEDIAN_C_B_BAND[0] <= median_c <= MEDIAN_C_B_BAND[1],
        "spearman_C_R_ge_0_30": spearman is not None and spearman >= SPEARMAN_MIN_B,
        "median_rho_ge_0_10": median_rho >= MEDIAN_RHO_MIN_B,
        "share_exhausted_le_0_02": share_exhausted <= SHARE_EXHAUSTED_MAX,
        "share_high_reject_le_0_10": share_high_reject <= SHARE_HIGH_REJECT_MAX,
    }

    return {
        "merchant_count": len(merchant_ids),
        "merchants_with_C_gt_0": denom,
        "median_C_m": median_c,
        "spearman_C_m_R_m": spearman,
        "median_rho_m": median_rho,
        "share_exhausted": share_exhausted,
        "share_high_reject_gt16": share_high_reject,
        "checks": checks,
        "core_checks_pass": all(
            checks[key]
            for key in ("median_C_in_B_band", "spearman_C_R_ge_0_30", "median_rho_ge_0_10")
        ),
        "pathology_checks_pass": all(
            checks[key]
            for key in ("share_exhausted_le_0_02", "share_high_reject_le_0_10")
        ),
    }


def build_scorecard(runs_root: Path, run_id: str) -> dict[str, Any]:
    run_root = runs_root / run_id
    receipt = _read_receipt(run_root)
    seed = int(receipt["seed"])
    parameter_hash = str(receipt["parameter_hash"])
    manifest_fingerprint = str(receipt["manifest_fingerprint"])
    policy = _load_s3_integerisation_policy(run_root, manifest_fingerprint)

    s3_paths = _require_paths(
        run_root,
        f"data/layer1/1A/s3_candidate_set/parameter_hash={parameter_hash}/part-*.parquet",
        "s3_candidate_set",
    )
    s6_paths = _require_paths(
        run_root,
        (
            "data/layer1/1A/s6/membership/"
            f"seed={seed}/parameter_hash={parameter_hash}/part-*.parquet"
        ),
        "s6_membership",
    )
    ztp_final_paths = _require_paths(
        run_root,
        (
            "logs/layer1/1A/rng/events/ztp_final/"
            f"seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl"
        ),
        "rng_event_ztp_final",
    )
    ztp_reject_paths = _require_paths(
        run_root,
        (
            "logs/layer1/1A/rng/events/ztp_rejection/"
            f"seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl"
        ),
        "rng_event_ztp_rejection",
    )
    gumbel_paths = _require_paths(
        run_root,
        (
            "logs/layer1/1A/rng/events/gumbel_key/"
            f"seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl"
        ),
        "rng_event_gumbel_key",
    )
    s4_metrics_paths = _require_paths(
        run_root,
        (
            "logs/layer1/1A/metrics/s4/"
            f"seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/s4_metrics.jsonl"
        ),
        "s4_metrics_log",
    )
    ztp_retry_paths = _optional_paths(
        run_root,
        (
            "logs/layer1/1A/rng/events/ztp_retry_exhausted/"
            f"seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl"
        ),
    )
    s3_integerised_paths = _optional_paths(
        run_root,
        (
            "data/layer1/1A/s3_integerised_counts/"
            f"parameter_hash={parameter_hash}/part-*.parquet"
        ),
    )
    if policy["emit_integerised_counts"] and not s3_integerised_paths:
        raise FileNotFoundError(
            "policy.s3.integerisation.yaml requires s3_integerised_counts, but none found"
        )

    strata, strata_source = _load_strata(run_root, parameter_hash, manifest_fingerprint)

    s3_df = pl.read_parquet(s3_paths).select(["merchant_id", "is_home"])
    s6_df = pl.read_parquet(s6_paths).select(["merchant_id", "country_iso"])

    c_counts = (
        s3_df.filter(~pl.col("is_home"))
        .group_by("merchant_id")
        .len()
        .rename({"len": "C_m"})
    )
    r_counts = s6_df.group_by("merchant_id").len().rename({"len": "R_m"})

    base = (
        strata.join(c_counts, on="merchant_id", how="left")
        .join(r_counts, on="merchant_id", how="left")
        .with_columns(
            [
                pl.col("C_m").fill_null(0).cast(pl.Int64),
                pl.col("R_m").fill_null(0).cast(pl.Int64),
            ]
        )
        .with_columns(
            pl.when(pl.col("C_m") > 0)
            .then(pl.col("R_m") / pl.col("C_m"))
            .otherwise(pl.col("R_m"))
            .cast(pl.Float64)
            .alias("rho_m")
        )
    )

    reject_counts: dict[int, int] = {}
    for row in _iter_jsonl(ztp_reject_paths):
        mid = int(row["merchant_id"])
        reject_counts[mid] = reject_counts.get(mid, 0) + 1
    high_reject_merchants = {
        mid for mid, count in reject_counts.items() if count > HIGH_REJECT_THRESHOLD
    }

    exhausted_merchants: set[int] = set()
    for row in _iter_jsonl(ztp_retry_paths):
        exhausted_merchants.add(int(row["merchant_id"]))

    global_metrics = _score_subset(
        base.select(["merchant_id", "C_m", "R_m", "rho_m"]),
        exhausted_merchants=exhausted_merchants,
        high_reject_merchants=high_reject_merchants,
    )

    stratified: dict[str, list[dict[str, Any]]] = {}
    for dim in ("channel", "mcc_broad_group", "gdp_bucket_id"):
        rows: list[dict[str, Any]] = []
        distinct_values = (
            base.select(pl.col(dim).drop_nulls().unique().sort()).to_series().to_list()
        )
        for value in distinct_values:
            subset = base.filter(pl.col(dim) == value).select(
                ["merchant_id", "C_m", "R_m", "rho_m"]
            )
            metrics = _score_subset(
                subset,
                exhausted_merchants=exhausted_merchants,
                high_reject_merchants=high_reject_merchants,
            )
            rows.append({"stratum": value, **metrics})
        stratified[dim] = rows

    stratified_summary = {}
    for dim, rows in stratified.items():
        count = len(rows)
        core_pass = sum(1 for row in rows if row["core_checks_pass"])
        pathology_pass = sum(1 for row in rows if row["pathology_checks_pass"])
        stratified_summary[dim] = {
            "strata_count": count,
            "core_checks_pass_count": core_pass,
            "core_checks_pass_share": (core_pass / count) if count > 0 else None,
            "pathology_checks_pass_count": pathology_pass,
            "pathology_checks_pass_share": (pathology_pass / count) if count > 0 else None,
        }

    scorecard = {
        "generated_utc": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "wave": "P2.1",
        "description": "Segment 1A P2 baseline scorecard over S0->S6 surfaces.",
        "run": {
            "run_id": run_id,
            "seed": seed,
            "parameter_hash": parameter_hash,
            "manifest_fingerprint": manifest_fingerprint,
        },
        "definitions": {
            "C_m": "Foreign candidate breadth per merchant from s3_candidate_set (is_home=false).",
            "R_m": "Realized foreign membership count per merchant from s6_membership.",
            "rho_m": "R_m / max(C_m, 1).",
            "mcc_broad_group": "Broad MCC thousand-band (floor(mcc/1000)*1000).",
        },
        "thresholds_B": {
            "median_C_m_band": list(MEDIAN_C_B_BAND),
            "spearman_C_m_R_m_min": SPEARMAN_MIN_B,
            "median_rho_m_min": MEDIAN_RHO_MIN_B,
            "share_exhausted_max": SHARE_EXHAUSTED_MAX,
            "share_high_reject_gt16_max": SHARE_HIGH_REJECT_MAX,
            "high_reject_threshold": HIGH_REJECT_THRESHOLD,
        },
        "surface_summary": {
            "s3_integerisation_policy": policy,
            "strata_source": strata_source,
            "files": {
                "s3_candidate_set": len(s3_paths),
                "s3_integerised_counts": len(s3_integerised_paths),
                "s6_membership": len(s6_paths),
                "rng_event_ztp_final": len(ztp_final_paths),
                "rng_event_ztp_rejection": len(ztp_reject_paths),
                "rng_event_ztp_retry_exhausted": len(ztp_retry_paths),
                "rng_event_gumbel_key": len(gumbel_paths),
                "s4_metrics_log": len(s4_metrics_paths),
            },
            "rows": {
                "s3_candidate_set": int(s3_df.height),
                "s3_integerised_counts": int(
                    pl.read_parquet(s3_integerised_paths).height
                    if s3_integerised_paths
                    else 0
                ),
                "s6_membership": int(s6_df.height),
                "rng_event_ztp_final": _count_jsonl_rows(ztp_final_paths),
                "rng_event_ztp_rejection": _count_jsonl_rows(ztp_reject_paths),
                "rng_event_ztp_retry_exhausted": _count_jsonl_rows(ztp_retry_paths),
                "rng_event_gumbel_key": _count_jsonl_rows(gumbel_paths),
                "s4_metrics_log": _count_jsonl_rows(s4_metrics_paths),
            },
            "notes": [
                "rng_event_ztp_retry_exhausted can be absent when no merchant exhausts retries.",
                "s3_integerised_counts is policy-gated by policy.s3.integerisation.yaml.",
            ],
        },
        "metrics": {
            "global": global_metrics,
            "stratified": stratified,
            "stratified_summary": stratified_summary,
        },
        "dod": {
            "baseline_scorecard_written": True,
            "pathology_hard_checks_computed": True,
            "global_and_stratified_metrics_computed": True,
        },
    }
    return scorecard


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runs-root",
        required=True,
        help="Runs root, e.g. runs/fix-data-engine/segment_1A",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Run id to score; defaults to latest run under --runs-root.",
    )
    parser.add_argument(
        "--out",
        required=True,
        help="Output JSON path for baseline scorecard.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    runs_root = Path(args.runs_root).resolve()
    run_id = _resolve_run_id(runs_root, args.run_id)
    scorecard = build_scorecard(runs_root=runs_root, run_id=run_id)

    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(scorecard, indent=2), encoding="utf-8")
    print(f"Wrote {out_path.as_posix()}")
    print(
        json.dumps(
            {
                "run_id": run_id,
                "global": scorecard["metrics"]["global"],
                "stratified_summary": scorecard["metrics"]["stratified_summary"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
