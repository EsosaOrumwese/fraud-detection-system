#!/usr/bin/env python3
"""Build Segment 1A P3.1 baseline scorecard (S0->S8 surfaces)."""

from __future__ import annotations

import argparse
import json
import math
import random
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import polars as pl


RUN_ID_RE = re.compile(r"^[0-9a-f]{32}$")

MISMATCH_B_BAND = (0.10, 0.25)
MISMATCH_B_PLUS_BAND = (0.12, 0.20)
SIZE_GRADIENT_B_MIN_PP = 5.0
SIZE_GRADIENT_B_PLUS_MIN_PP = 8.0


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


def _wilson_interval(successes: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if n <= 0:
        return (math.nan, math.nan)
    p = successes / n
    denom = 1.0 + (z * z) / n
    center = (p + (z * z) / (2.0 * n)) / denom
    margin = (
        z
        * math.sqrt((p * (1.0 - p) / n) + ((z * z) / (4.0 * n * n)))
        / denom
    )
    lo = max(0.0, center - margin)
    hi = min(1.0, center + margin)
    return (lo, hi)


def _quantile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        return math.nan
    if len(sorted_values) == 1:
        return sorted_values[0]
    idx = (len(sorted_values) - 1) * q
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    if lo == hi:
        return sorted_values[lo]
    frac = idx - lo
    return sorted_values[lo] * (1.0 - frac) + sorted_values[hi] * frac


def _bootstrap_gradient_ci_pp(
    merchant_rows_top: list[tuple[int, int]],
    merchant_rows_bottom: list[tuple[int, int]],
    *,
    seed: int,
    samples: int,
) -> tuple[float, float] | None:
    if samples <= 0:
        return None
    if len(merchant_rows_top) < 2 or len(merchant_rows_bottom) < 2:
        return None

    rng = random.Random(seed)
    gradients_pp: list[float] = []
    n_top = len(merchant_rows_top)
    n_bottom = len(merchant_rows_bottom)

    for _ in range(samples):
        sampled_top = [merchant_rows_top[rng.randrange(n_top)] for _ in range(n_top)]
        sampled_bottom = [
            merchant_rows_bottom[rng.randrange(n_bottom)] for _ in range(n_bottom)
        ]
        top_mismatch = sum(m for m, _ in sampled_top)
        top_total = sum(t for _, t in sampled_top)
        bottom_mismatch = sum(m for m, _ in sampled_bottom)
        bottom_total = sum(t for _, t in sampled_bottom)
        if top_total <= 0 or bottom_total <= 0:
            continue
        top_rate = top_mismatch / top_total
        bottom_rate = bottom_mismatch / bottom_total
        gradients_pp.append((top_rate - bottom_rate) * 100.0)

    if not gradients_pp:
        return None
    gradients_pp.sort()
    return (_quantile(gradients_pp, 0.025), _quantile(gradients_pp, 0.975))


def _assign_size_deciles(size_df: pl.DataFrame) -> pl.DataFrame:
    if size_df.height == 0:
        raise ValueError("size table is empty; cannot assign deciles")
    ordered = size_df.sort(["n_outlets", "merchant_id"]).with_row_index("row_idx")
    n = ordered.height
    return ordered.with_columns(
        (((pl.col("row_idx") * 10) // n) + 1).cast(pl.Int8).alias("size_decile")
    ).drop("row_idx")


def _duplicate_diagnostics(outlet_df: pl.DataFrame) -> dict[str, Any]:
    pk_dups = (
        outlet_df.group_by(["merchant_id", "legal_country_iso", "site_order"])
        .len()
        .filter(pl.col("len") > 1)
    )
    local_site_dups = (
        outlet_df.group_by(["merchant_id", "legal_country_iso", "site_id"])
        .len()
        .filter(pl.col("len") > 1)
    )
    local_scope = outlet_df.group_by(["merchant_id", "legal_country_iso"]).agg(
        [
            pl.len().alias("row_count"),
            pl.col("site_order").n_unique().alias("site_order_unique"),
            pl.col("site_order").min().alias("site_order_min"),
            pl.col("site_order").max().alias("site_order_max"),
        ]
    )
    non_contiguous_scopes = local_scope.filter(
        (pl.col("site_order_min") != 1)
        | (pl.col("site_order_max") != pl.col("site_order_unique"))
        | (pl.col("row_count") != pl.col("site_order_unique"))
    )

    format_mismatch_rows = outlet_df.filter(
        pl.col("site_id") != pl.col("site_order").cast(pl.Utf8).str.zfill(6)
    )
    cross_country_reuse = (
        outlet_df.group_by(["merchant_id", "site_id"])
        .agg(pl.col("legal_country_iso").n_unique().alias("country_count"))
        .filter(pl.col("country_count") > 1)
    )

    unexpected = {
        "duplicate_pk_groups": int(pk_dups.height),
        "duplicate_pk_excess_rows": int(
            pk_dups.select((pl.col("len") - 1).sum()).item() if pk_dups.height else 0
        ),
        "duplicate_local_site_id_groups": int(local_site_dups.height),
        "duplicate_local_site_id_excess_rows": int(
            local_site_dups.select((pl.col("len") - 1).sum()).item()
            if local_site_dups.height
            else 0
        ),
        "non_contiguous_site_order_scopes": int(non_contiguous_scopes.height),
        "site_id_format_mismatch_rows": int(format_mismatch_rows.height),
    }

    has_unexplained = any(value > 0 for value in unexpected.values())
    return {
        "contract_basis": {
            "site_id_scope": "(merchant_id, legal_country_iso)",
            "site_id_not_global_physical_identifier": True,
        },
        "expected_reuse_signals": {
            "cross_country_reuse_groups_same_merchant_site_id": int(
                cross_country_reuse.height
            ),
            "cross_country_reuse_merchants": int(
                cross_country_reuse.select(pl.col("merchant_id").n_unique()).item()
                if cross_country_reuse.height
                else 0
            ),
        },
        "unexplained_duplicate_anomalies": unexpected,
        "has_unexplained_duplicate_anomalies": has_unexplained,
    }


def _score_slice(
    outlet_slice: pl.DataFrame,
    *,
    bootstrap_seed: int,
    bootstrap_samples: int,
    include_bootstrap: bool,
) -> dict[str, Any]:
    total_rows = int(outlet_slice.height)
    mismatch_rows = (
        int(outlet_slice.select(pl.col("is_mismatch").sum()).item()) if total_rows else 0
    )
    mismatch_rate = (mismatch_rows / total_rows) if total_rows else math.nan
    mismatch_ci = _wilson_interval(mismatch_rows, total_rows)

    top_slice = outlet_slice.filter(pl.col("size_decile") == 10)
    bottom_slice = outlet_slice.filter(pl.col("size_decile") <= 3)

    top_rows = int(top_slice.height)
    bottom_rows = int(bottom_slice.height)
    top_mismatch_rows = (
        int(top_slice.select(pl.col("is_mismatch").sum()).item()) if top_rows else 0
    )
    bottom_mismatch_rows = (
        int(bottom_slice.select(pl.col("is_mismatch").sum()).item())
        if bottom_rows
        else 0
    )
    top_rate = (top_mismatch_rows / top_rows) if top_rows else math.nan
    bottom_rate = (bottom_mismatch_rows / bottom_rows) if bottom_rows else math.nan
    gradient_pp = (
        (top_rate - bottom_rate) * 100.0
        if top_rows > 0 and bottom_rows > 0
        else math.nan
    )

    top_merchants = int(
        top_slice.select(pl.col("merchant_id").n_unique()).item() if top_rows else 0
    )
    bottom_merchants = int(
        bottom_slice.select(pl.col("merchant_id").n_unique()).item() if bottom_rows else 0
    )
    top_ci = _wilson_interval(top_mismatch_rows, top_rows)
    bottom_ci = _wilson_interval(bottom_mismatch_rows, bottom_rows)

    gradient_ci_bootstrap = None
    if include_bootstrap and top_merchants >= 2 and bottom_merchants >= 2:
        merchant_rows = outlet_slice.group_by(["merchant_id", "size_decile"]).agg(
            [
                pl.sum("is_mismatch").alias("mismatch_rows"),
                pl.len().alias("row_count"),
            ]
        )
        merchant_rows_top = [
            (int(row["mismatch_rows"]), int(row["row_count"]))
            for row in merchant_rows.filter(pl.col("size_decile") == 10).iter_rows(named=True)
        ]
        merchant_rows_bottom = [
            (int(row["mismatch_rows"]), int(row["row_count"]))
            for row in merchant_rows.filter(pl.col("size_decile") <= 3).iter_rows(named=True)
        ]
        gradient_ci_bootstrap = _bootstrap_gradient_ci_pp(
            merchant_rows_top,
            merchant_rows_bottom,
            seed=bootstrap_seed,
            samples=bootstrap_samples,
        )

    checks = {
        "mismatch_rate_in_B_band": (
            MISMATCH_B_BAND[0] <= mismatch_rate <= MISMATCH_B_BAND[1]
            if not math.isnan(mismatch_rate)
            else False
        ),
        "mismatch_rate_in_B_plus_band": (
            MISMATCH_B_PLUS_BAND[0] <= mismatch_rate <= MISMATCH_B_PLUS_BAND[1]
            if not math.isnan(mismatch_rate)
            else False
        ),
        "size_gradient_pp_ge_B": (
            gradient_pp >= SIZE_GRADIENT_B_MIN_PP if not math.isnan(gradient_pp) else False
        ),
        "size_gradient_pp_ge_B_plus": (
            gradient_pp >= SIZE_GRADIENT_B_PLUS_MIN_PP
            if not math.isnan(gradient_pp)
            else False
        ),
    }

    return {
        "rows": total_rows,
        "merchants": int(
            outlet_slice.select(pl.col("merchant_id").n_unique()).item()
            if total_rows
            else 0
        ),
        "mismatch_rows": mismatch_rows,
        "home_legal_mismatch_rate": mismatch_rate,
        "home_legal_mismatch_rate_ci95_wilson": list(mismatch_ci),
        "top_decile_rows": top_rows,
        "bottom_deciles_rows": bottom_rows,
        "top_decile_merchants": top_merchants,
        "bottom_deciles_merchants": bottom_merchants,
        "top_decile_mismatch_rate": top_rate,
        "top_decile_mismatch_rate_ci95_wilson": list(top_ci),
        "bottom_deciles_mismatch_rate": bottom_rate,
        "bottom_deciles_mismatch_rate_ci95_wilson": list(bottom_ci),
        "size_gradient_pp_top_minus_bottom": gradient_pp,
        "size_gradient_pp_ci95_bootstrap": (
            list(gradient_ci_bootstrap) if gradient_ci_bootstrap else None
        ),
        "checks": checks,
    }


def build_scorecard(
    runs_root: Path,
    run_id: str,
    *,
    bootstrap_seed: int,
    bootstrap_samples: int,
) -> dict[str, Any]:
    run_root = runs_root / run_id
    receipt = _read_receipt(run_root)
    seed = int(receipt["seed"])
    parameter_hash = str(receipt["parameter_hash"])
    manifest_fingerprint = str(receipt["manifest_fingerprint"])

    outlet_paths = _require_paths(
        run_root,
        (
            "data/layer1/1A/outlet_catalogue/"
            f"seed={seed}/manifest_fingerprint={manifest_fingerprint}/part-*.parquet"
        ),
        "outlet_catalogue",
    )
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
    nb_paths = _require_paths(
        run_root,
        (
            "logs/layer1/1A/rng/events/nb_final/"
            f"seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl"
        ),
        "rng_event_nb_final",
    )
    seq_paths = _require_paths(
        run_root,
        (
            "logs/layer1/1A/rng/events/sequence_finalize/"
            f"seed={seed}/parameter_hash={parameter_hash}/run_id={run_id}/part-*.jsonl"
        ),
        "rng_event_sequence_finalize",
    )
    overflow_paths = _optional_paths(
        run_root,
        (
            "logs/layer1/1A/rng/events/site_sequence_overflow/"
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

    strata, strata_source = _load_strata(run_root, parameter_hash, manifest_fingerprint)

    outlet_df = pl.read_parquet(outlet_paths).select(
        [
            "merchant_id",
            "home_country_iso",
            "legal_country_iso",
            "site_id",
            "site_order",
            "raw_nb_outlet_draw",
        ]
    )
    if outlet_df.height == 0:
        raise ValueError("outlet_catalogue is empty; cannot build P3 scorecard")

    nb_rows: dict[int, int] = {}
    for row in _iter_jsonl(nb_paths):
        mid = int(row["merchant_id"])
        n_outlets = int(row["n_outlets"])
        prev = nb_rows.get(mid)
        if prev is not None and prev != n_outlets:
            raise ValueError(f"conflicting nb_final n_outlets for merchant_id={mid}")
        nb_rows[mid] = n_outlets

    if nb_rows:
        size_df = pl.DataFrame(
            {
                "merchant_id": list(nb_rows.keys()),
                "n_outlets": list(nb_rows.values()),
            }
        )
        size_source = "rng_event_nb_final.n_outlets"
    else:
        size_df = outlet_df.group_by("merchant_id").agg(
            pl.col("raw_nb_outlet_draw").max().cast(pl.Int64).alias("n_outlets")
        )
        size_source = "outlet_catalogue.raw_nb_outlet_draw_fallback"

    size_deciles = _assign_size_deciles(size_df)
    outlet_scored = (
        outlet_df.join(
            size_deciles.select(["merchant_id", "n_outlets", "size_decile"]),
            on="merchant_id",
            how="left",
        )
        .join(strata, on="merchant_id", how="left")
        .with_columns(
            (pl.col("home_country_iso") != pl.col("legal_country_iso"))
            .cast(pl.Int8)
            .alias("is_mismatch")
        )
    )

    if outlet_scored.select(pl.col("size_decile").null_count()).item() > 0:
        raise ValueError("size_decile assignment missing for one or more outlet rows")

    global_metrics = _score_slice(
        outlet_scored.select(
            [
                "merchant_id",
                "size_decile",
                "is_mismatch",
            ]
        ),
        bootstrap_seed=bootstrap_seed,
        bootstrap_samples=bootstrap_samples,
        include_bootstrap=True,
    )

    stratified: dict[str, list[dict[str, Any]]] = {}
    for dim_index, dim in enumerate(("channel", "mcc_broad_group", "gdp_bucket_id"), start=1):
        rows: list[dict[str, Any]] = []
        distinct_values = (
            outlet_scored.select(pl.col(dim).drop_nulls().unique().sort())
            .to_series()
            .to_list()
        )
        for value_index, value in enumerate(distinct_values, start=1):
            subset = outlet_scored.filter(pl.col(dim) == value).select(
                ["merchant_id", "size_decile", "is_mismatch"]
            )
            metrics = _score_slice(
                subset,
                bootstrap_seed=bootstrap_seed + (dim_index * 10_000) + value_index,
                bootstrap_samples=bootstrap_samples,
                include_bootstrap=False,
            )
            rows.append({"stratum": value, **metrics})
        stratified[dim] = rows

    stratified_summary: dict[str, dict[str, Any]] = {}
    for dim, rows in stratified.items():
        count = len(rows)
        mismatch_pass = sum(
            1 for row in rows if row["checks"]["mismatch_rate_in_B_band"]
        )
        gradient_pass = sum(1 for row in rows if row["checks"]["size_gradient_pp_ge_B"])
        stratified_summary[dim] = {
            "strata_count": count,
            "mismatch_B_pass_count": mismatch_pass,
            "mismatch_B_pass_share": (mismatch_pass / count) if count > 0 else None,
            "gradient_B_pass_count": gradient_pass,
            "gradient_B_pass_share": (gradient_pass / count) if count > 0 else None,
        }

    duplicate_diagnostics = _duplicate_diagnostics(outlet_df)
    global_checks = {
        **global_metrics["checks"],
        "no_unexplained_duplicate_anomalies": not duplicate_diagnostics[
            "has_unexplained_duplicate_anomalies"
        ],
    }

    scorecard = {
        "generated_utc": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "wave": "P3.1",
        "description": "Segment 1A P3.1 baseline scorecard over S0->S8 surfaces.",
        "run": {
            "run_id": run_id,
            "seed": seed,
            "parameter_hash": parameter_hash,
            "manifest_fingerprint": manifest_fingerprint,
        },
        "definitions": {
            "home_legal_mismatch_rate": "mean(home_country_iso != legal_country_iso) over outlet_catalogue rows.",
            "size_deciles": "Merchant-size deciles from n_outlets authority, ascending; decile 10 is largest merchants.",
            "bottom_deciles": "Deciles 1..3 combined.",
            "size_gradient_pp_top_minus_bottom": "100 * (top_decile_mismatch_rate - bottom_deciles_mismatch_rate).",
            "site_id_contract": "site_id is merchant-local sequence scoped to (merchant_id, legal_country_iso).",
        },
        "thresholds": {
            "B": {
                "home_legal_mismatch_rate_band": list(MISMATCH_B_BAND),
                "size_gradient_pp_min": SIZE_GRADIENT_B_MIN_PP,
            },
            "B_plus": {
                "home_legal_mismatch_rate_band": list(MISMATCH_B_PLUS_BAND),
                "size_gradient_pp_min": SIZE_GRADIENT_B_PLUS_MIN_PP,
            },
        },
        "surface_summary": {
            "size_authority_source": size_source,
            "strata_source": strata_source,
            "files": {
                "outlet_catalogue": len(outlet_paths),
                "s3_candidate_set": len(s3_paths),
                "s6_membership": len(s6_paths),
                "s3_integerised_counts": len(s3_integerised_paths),
                "rng_event_nb_final": len(nb_paths),
                "rng_event_sequence_finalize": len(seq_paths),
                "rng_event_site_sequence_overflow": len(overflow_paths),
            },
            "rows": {
                "outlet_catalogue": int(outlet_df.height),
                "s3_candidate_set": int(pl.read_parquet(s3_paths).height),
                "s6_membership": int(pl.read_parquet(s6_paths).height),
                "s3_integerised_counts": int(
                    pl.read_parquet(s3_integerised_paths).height
                    if s3_integerised_paths
                    else 0
                ),
                "rng_event_nb_final": _count_jsonl_rows(nb_paths),
                "rng_event_sequence_finalize": _count_jsonl_rows(seq_paths),
                "rng_event_site_sequence_overflow": _count_jsonl_rows(overflow_paths),
            },
            "bootstrap": {
                "seed": bootstrap_seed,
                "samples": bootstrap_samples,
                "global_gradient_ci": "merchant-bootstrap 95% CI",
            },
        },
        "metrics": {
            "global": {**global_metrics, "checks": global_checks},
            "stratified": stratified,
            "stratified_summary": stratified_summary,
            "identity_semantics_diagnostics": duplicate_diagnostics,
        },
        "dod": {
            "baseline_scorecard_written": True,
            "global_and_stratified_metrics_computed": True,
            "wilson_cis_computed": True,
            "bootstrap_gradient_ci_computed": global_metrics[
                "size_gradient_pp_ci95_bootstrap"
            ]
            is not None,
            "duplicate_semantics_diagnostics_computed": True,
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
    parser.add_argument(
        "--bootstrap-seed",
        type=int,
        default=20260213,
        help="Deterministic seed for gradient bootstrap CI.",
    )
    parser.add_argument(
        "--bootstrap-samples",
        type=int,
        default=400,
        help="Number of merchant-bootstrap samples for global size-gradient CI.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    runs_root = Path(args.runs_root).resolve()
    run_id = _resolve_run_id(runs_root, args.run_id)
    scorecard = build_scorecard(
        runs_root=runs_root,
        run_id=run_id,
        bootstrap_seed=args.bootstrap_seed,
        bootstrap_samples=args.bootstrap_samples,
    )

    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(scorecard, indent=2), encoding="utf-8")
    print(f"Wrote {out_path.as_posix()}")
    print(
        json.dumps(
            {
                "run_id": run_id,
                "global": scorecard["metrics"]["global"],
                "identity_semantics": scorecard["metrics"][
                    "identity_semantics_diagnostics"
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
