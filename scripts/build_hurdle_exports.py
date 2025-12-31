#!/usr/bin/env python3
"""Offline training + export for hurdle + dispersion bundles (Layer-1 1A)."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import polars as pl
import yaml


os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")


ROOT = Path(__file__).resolve().parents[1]


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_bytes(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _load_yaml(path: Path) -> Dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _drop_if_present(df: pl.DataFrame, name: str) -> pl.DataFrame:
    if name in df.columns:
        return df.drop(name)
    return df


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def _clip(x: np.ndarray, low: float, high: float) -> np.ndarray:
    return np.minimum(np.maximum(x, low), high)


def _parse_range_offsets(items: Iterable[dict]) -> List[Tuple[int, int, float]]:
    ranges: List[Tuple[int, int, float]] = []
    for entry in items:
        span = str(entry["range"])
        start, end = span.split("-", maxsplit=1)
        ranges.append((int(start), int(end), float(entry["offset"])))
    return ranges


def _mcc_offset_map(
    mcc_offsets: Dict[str, object],
    mcc_ranges: List[Tuple[int, int, float]],
    mcc_values: np.ndarray,
) -> np.ndarray:
    direct = {int(k): float(v) for k, v in mcc_offsets.items()}
    offsets = np.zeros(len(mcc_values), dtype=float)
    for idx, code in enumerate(mcc_values):
        total = direct.get(int(code), 0.0)
        for lo, hi, delta in mcc_ranges:
            if lo <= code <= hi:
                total += delta
        offsets[idx] = total
    return offsets


def _channel_offset_map(
    channel_offsets: Dict[str, object], channels: np.ndarray
) -> np.ndarray:
    mapping = {str(k): float(v) for k, v in channel_offsets.items()}
    return np.array([mapping.get(ch, 0.0) for ch in channels], dtype=float)


def _bucket_offset_map(
    bucket_offsets: Dict[str, object], buckets: np.ndarray
) -> np.ndarray:
    mapping = {int(k): float(v) for k, v in bucket_offsets.items()}
    return np.array([mapping.get(int(b), 0.0) for b in buckets], dtype=float)


def _weighted_median(values: np.ndarray, weights: np.ndarray) -> float:
    order = np.argsort(values)
    values = values[order]
    weights = weights[order]
    cumulative = np.cumsum(weights)
    cutoff = 0.5 * cumulative[-1]
    idx = np.searchsorted(cumulative, cutoff, side="left")
    return float(values[min(idx, len(values) - 1)])


def _fit_logistic_ridge(
    X: np.ndarray,
    y: np.ndarray,
    l2: float,
    max_iter: int,
    tol: float,
) -> np.ndarray:
    beta = np.zeros(X.shape[1], dtype=float)
    for _ in range(max_iter):
        eta = X @ beta
        pi = _clip(_sigmoid(eta), 1e-6, 1.0 - 1e-6)
        w = pi * (1.0 - pi)
        z = eta + (y - pi) / w
        sw = np.sqrt(w)
        Xw = X * sw[:, None]
        zw = z * sw
        lhs = Xw.T @ Xw
        lhs += l2 * np.eye(lhs.shape[0])
        rhs = Xw.T @ zw
        beta_new = np.linalg.solve(lhs, rhs)
        if np.max(np.abs(beta_new - beta)) <= tol:
            beta = beta_new
            break
        beta = beta_new
    return beta


def _fit_linear_ridge(
    X: np.ndarray,
    y: np.ndarray,
    l2: float,
    weights: np.ndarray | None = None,
) -> np.ndarray:
    if weights is None:
        Xw = X
        yw = y
    else:
        sw = np.sqrt(weights)
        Xw = X * sw[:, None]
        yw = y * sw
    lhs = Xw.T @ Xw
    lhs += l2 * np.eye(lhs.shape[0])
    rhs = Xw.T @ yw
    return np.linalg.solve(lhs, rhs)


def _adjust_beta_mu(
    beta_mu: np.ndarray,
    X_mu: np.ndarray,
    pi_mask: np.ndarray,
    mu_floor: float,
    q90_cap: float,
) -> tuple[np.ndarray, float, float]:
    log_mu_raw = X_mu @ beta_mu
    mean_log_mu = float(np.mean(log_mu_raw))

    def eval_scale(scale: float) -> tuple[float, float, float]:
        log_mu = mean_log_mu + scale * (log_mu_raw - mean_log_mu)
        mu = np.exp(log_mu)
        shift = 0.0
        mu_min = float(mu.min())
        if mu_min < mu_floor:
            shift = math.log(mu_floor / mu_min)
            mu = mu * math.exp(shift)
        q90 = float(np.quantile(mu[pi_mask], 0.9)) if pi_mask.any() else float(
            np.quantile(mu, 0.9)
        )
        return q90, shift, mu_min

    q90, shift, _ = eval_scale(1.0)
    if q90 <= q90_cap:
        adjusted = beta_mu.copy()
        if shift != 0.0:
            adjusted[0] += shift
        return adjusted, shift, 1.0

    low, high = 0.2, 1.0
    best_scale = 1.0
    best_shift = shift
    for _ in range(36):
        mid = 0.5 * (low + high)
        q90_mid, shift_mid, _ = eval_scale(mid)
        if q90_mid > q90_cap:
            high = mid
        else:
            low = mid
            best_scale = mid
            best_shift = shift_mid

    adjusted = beta_mu.copy()
    adjusted[1:] *= best_scale
    adjusted[0] = best_scale * beta_mu[0] + (1.0 - best_scale) * mean_log_mu
    if best_shift != 0.0:
        adjusted[0] += best_shift
    return adjusted, best_shift, best_scale


def _build_design_matrix(
    *,
    mcc: np.ndarray,
    channel: np.ndarray,
    gdp_bucket: np.ndarray | None,
    dict_mcc: List[int],
    include_bucket: bool,
) -> np.ndarray:
    mcc_index = {code: idx for idx, code in enumerate(dict_mcc)}
    n = len(mcc)
    mcc_size = len(dict_mcc)
    ch_size = 2
    bucket_size = 5 if include_bucket else 0
    cols = 1 + mcc_size + ch_size + bucket_size
    X = np.zeros((n, cols), dtype=float)
    X[:, 0] = 1.0
    for i, code in enumerate(mcc):
        idx = mcc_index[int(code)]
        X[i, 1 + idx] = 1.0
    ch_offset = 1 + mcc_size
    for i, ch in enumerate(channel):
        if ch == "CP":
            X[i, ch_offset] = 1.0
        else:
            X[i, ch_offset + 1] = 1.0
    if include_bucket:
        b_offset = 1 + mcc_size + ch_size
        for i, bucket in enumerate(gdp_bucket):
            X[i, b_offset + int(bucket) - 1] = 1.0
    return X


def _sample_zero_trunc_nb(
    rng: np.random.Generator, mean: float, phi: float, max_attempts: int
) -> int:
    mean = max(mean, 1.0)
    phi = max(phi, 1e-6)
    prob = phi / (phi + mean)
    for _ in range(max_attempts):
        value = rng.negative_binomial(phi, prob)
        if value >= 2:
            return int(value)
    return 2


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build hurdle/dispersion exports.")
    parser.add_argument(
        "--config-path",
        default="config/models/hurdle/hurdle_simulation.priors.yaml",
    )
    parser.add_argument(
        "--merchant-path",
        default="reference/layer1/transaction_schema_merchant_ids/2025-12-31/transaction_schema_merchant_ids.parquet",
    )
    parser.add_argument(
        "--gdp-path",
        default="reference/economic/world_bank_gdp_per_capita/2025-04-15/gdp.parquet",
    )
    parser.add_argument(
        "--bucket-path",
        default="reference/economic/gdp_bucket_map/2024/gdp_bucket_map.parquet",
    )
    parser.add_argument(
        "--iso-path",
        default="reference/iso/iso3166_canonical/2024-12-31/iso3166.parquet",
    )
    parser.add_argument("--config-version", default=None)
    parser.add_argument("--timestamp", default=None)
    parser.add_argument("--l2", type=float, default=1e-3)
    parser.add_argument("--irls-iter", type=int, default=25)
    parser.add_argument("--irls-tol", type=float, default=1e-6)
    parser.add_argument("--max-nb-attempts", type=int, default=64)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    config_path = ROOT / args.config_path
    priors = _load_yaml(config_path)
    config_version = args.config_version or str(priors.get("version", "0.0.0"))
    rng_node = priors.get("rng", {})
    seed = int(rng_node.get("seed", 0))

    timestamp = args.timestamp
    if not timestamp:
        timestamp = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    training_dir = (
        ROOT
        / "artefacts"
        / "training"
        / "1A"
        / "hurdle_sim"
        / f"simulation_version={config_version}"
        / f"seed={seed}"
        / timestamp
    )
    export_dir = (
        ROOT
        / "config"
        / "models"
        / "hurdle"
        / "exports"
        / f"version={config_version}"
        / timestamp
    )
    training_dir.mkdir(parents=True, exist_ok=True)
    export_dir.mkdir(parents=True, exist_ok=True)

    merchant_path = ROOT / args.merchant_path
    gdp_path = ROOT / args.gdp_path
    bucket_path = ROOT / args.bucket_path
    iso_path = ROOT / args.iso_path

    merchants = pl.read_parquet(merchant_path)
    merchants = merchants.sort("merchant_id")
    gdp = pl.read_parquet(gdp_path).filter(pl.col("observation_year") == 2024)
    buckets = pl.read_parquet(bucket_path).select(["country_iso", "bucket_id"])
    iso = (
        pl.read_parquet(iso_path)
        .select(["country_iso"])
        .with_columns(pl.lit(1).alias("iso_present"))
    )

    merchants = merchants.join(
        gdp.select(["country_iso", "gdp_pc_usd_2015"]),
        left_on="home_country_iso",
        right_on="country_iso",
        how="left",
    )
    merchants = _drop_if_present(merchants, "country_iso")
    merchants = merchants.join(
        buckets,
        left_on="home_country_iso",
        right_on="country_iso",
        how="left",
    )
    merchants = _drop_if_present(merchants, "country_iso")
    merchants = merchants.join(
        iso,
        left_on="home_country_iso",
        right_on="country_iso",
        how="left",
    )

    if merchants["iso_present"].null_count() > 0:
        raise RuntimeError("Missing ISO3166 mapping for some merchants.")
    if merchants["gdp_pc_usd_2015"].null_count() > 0:
        raise RuntimeError("Missing GDP per capita for some merchants.")
    if merchants["bucket_id"].null_count() > 0:
        raise RuntimeError("Missing GDP bucket for some merchants.")

    merchants = _drop_if_present(merchants, "country_iso")
    merchants = _drop_if_present(merchants, "iso_present")
    merchants = merchants.with_columns(
        pl.col("gdp_pc_usd_2015").log().alias("ln_gdp_pc_usd_2015")
    )

    dict_mcc = sorted({int(v) for v in merchants["mcc"].to_list()})
    dict_ch = ["CP", "CNP"]
    dict_dev5 = [1, 2, 3, 4, 5]

    rng = np.random.default_rng(seed)

    channel = np.array(merchants["channel"].to_list(), dtype=object)
    mcc = np.array(merchants["mcc"].to_list(), dtype=int)
    gdp_bucket = np.array(merchants["bucket_id"].to_list(), dtype=int)
    ln_gdp = np.array(merchants["ln_gdp_pc_usd_2015"].to_list(), dtype=float)

    hurdle_node = priors.get("hurdle", {})
    nb_node = priors.get("nb_mean", {})
    disp_node = priors.get("dispersion", {})
    noise_node = priors.get("noise", {})
    clamps_node = priors.get("clamps", {})
    calib_node = priors.get("calibration", {})

    hurdle_ranges = _parse_range_offsets(hurdle_node.get("mcc_range_offsets", []))
    nb_ranges = _parse_range_offsets(nb_node.get("mcc_range_offsets", []))
    disp_ranges = _parse_range_offsets(disp_node.get("mcc_range_offsets", []))

    hurdle_mcc_offset = _mcc_offset_map(
        hurdle_node.get("mcc_offsets", {}), hurdle_ranges, mcc
    )
    nb_mcc_offset = _mcc_offset_map(
        nb_node.get("mcc_offsets", {}), nb_ranges, mcc
    )
    disp_mcc_offset = _mcc_offset_map(
        disp_node.get("mcc_offsets", {}), disp_ranges, mcc
    )

    hurdle_channel_offset = _channel_offset_map(
        hurdle_node.get("channel_offsets", {}), channel
    )
    nb_channel_offset = _channel_offset_map(nb_node.get("channel_offsets", {}), channel)
    disp_channel_offset = _channel_offset_map(
        disp_node.get("channel_offsets", {}), channel
    )

    hurdle_bucket_offset = _bucket_offset_map(
        hurdle_node.get("bucket_offsets", {}), gdp_bucket
    )

    noise_logit = rng.normal(
        loc=0.0,
        scale=float(noise_node.get("per_merchant_logit_sd", 0.0)),
        size=len(channel),
    )
    noise_log_mu = rng.normal(
        loc=0.0,
        scale=float(noise_node.get("per_merchant_log_mu_sd", 0.0)),
        size=len(channel),
    )
    noise_log_phi = rng.normal(
        loc=0.0,
        scale=float(noise_node.get("per_merchant_log_phi_sd", 0.0)),
        size=len(channel),
    )

    base_logit = float(hurdle_node.get("base_logit", 0.0))
    base_log_mean = float(nb_node.get("base_log_mean", 0.0))
    base_log_phi = float(disp_node.get("base_log_phi", 0.0))
    gdp_log_slope = float(disp_node.get("gdp_log_slope", 0.0))

    if bool(calib_node.get("enabled", False)):
        target_pi = float(calib_node.get("mean_pi_target", 0.1))
        target_mu = float(calib_node.get("mean_mu_target_multi", 4.0))
        target_phi = float(calib_node.get("median_phi_target", 20.0))
        iters = int(calib_node.get("fixed_iters", 64))
        logit_lo, logit_hi = calib_node.get("brackets", {}).get("base_logit", [-10, 2])
        mu_lo, mu_hi = calib_node.get("brackets", {}).get("base_log_mean", [-2, 4])
        phi_lo, phi_hi = calib_node.get("brackets", {}).get("base_log_phi", [1, 5])

        for _ in range(iters):
            mid = 0.5 * (logit_lo + logit_hi)
            eta = (
                mid
                + hurdle_channel_offset
                + hurdle_bucket_offset
                + hurdle_mcc_offset
                + noise_logit
            )
            pi = _sigmoid(eta)
            if pi.mean() > target_pi:
                logit_hi = mid
            else:
                logit_lo = mid
        base_logit = 0.5 * (logit_lo + logit_hi)

        for _ in range(iters):
            mid = 0.5 * (mu_lo + mu_hi)
            log_mu = mid + nb_channel_offset + nb_mcc_offset + noise_log_mu
            mu = np.exp(log_mu)
            mu = _clip(
                mu,
                float(clamps_node.get("mu", {}).get("min", 2.0)),
                float(clamps_node.get("mu", {}).get("max", 40.0)),
            )
            eta = (
                base_logit
                + hurdle_channel_offset
                + hurdle_bucket_offset
                + hurdle_mcc_offset
                + noise_logit
            )
            pi = _sigmoid(eta)
            weighted_mean = float(np.average(mu, weights=pi))
            if weighted_mean > target_mu:
                mu_hi = mid
            else:
                mu_lo = mid
        base_log_mean = 0.5 * (mu_lo + mu_hi)

        for _ in range(iters):
            mid = 0.5 * (phi_lo + phi_hi)
            log_phi = (
                mid
                + gdp_log_slope * ln_gdp
                + disp_channel_offset
                + disp_mcc_offset
                + noise_log_phi
            )
            phi = np.exp(log_phi)
            phi = _clip(
                phi,
                float(clamps_node.get("phi", {}).get("min", 8.0)),
                float(clamps_node.get("phi", {}).get("max", 80.0)),
            )
            eta = (
                base_logit
                + hurdle_channel_offset
                + hurdle_bucket_offset
                + hurdle_mcc_offset
                + noise_logit
            )
            pi = _sigmoid(eta)
            median_phi = _weighted_median(phi, pi)
            if median_phi > target_phi:
                phi_hi = mid
            else:
                phi_lo = mid
        base_log_phi = 0.5 * (phi_lo + phi_hi)

    eta = (
        base_logit
        + hurdle_channel_offset
        + hurdle_bucket_offset
        + hurdle_mcc_offset
        + noise_logit
    )
    pi = _sigmoid(eta)
    pi = _clip(
        pi,
        float(clamps_node.get("pi", {}).get("min", 0.01)),
        float(clamps_node.get("pi", {}).get("max", 0.80)),
    )

    draws = rng.uniform(size=len(pi))
    y_hurdle = (draws < pi).astype(int)

    log_mu = base_log_mean + nb_channel_offset + nb_mcc_offset + noise_log_mu
    mu = np.exp(log_mu)
    mu = _clip(
        mu,
        float(clamps_node.get("mu", {}).get("min", 2.0)),
        float(clamps_node.get("mu", {}).get("max", 40.0)),
    )

    log_phi = (
        base_log_phi
        + gdp_log_slope * ln_gdp
        + disp_channel_offset
        + disp_mcc_offset
        + noise_log_phi
    )
    phi = np.exp(log_phi)
    phi = _clip(
        phi,
        float(clamps_node.get("phi", {}).get("min", 8.0)),
        float(clamps_node.get("phi", {}).get("max", 80.0)),
    )

    y_nb = np.zeros(len(pi), dtype=int)
    for idx, flag in enumerate(y_hurdle):
        if flag:
            y_nb[idx] = _sample_zero_trunc_nb(
                rng, float(mu[idx]), float(phi[idx]), args.max_nb_attempts
            )

    logistic_df = pl.DataFrame(
        {
            "merchant_id": merchants["merchant_id"],
            "mcc": merchants["mcc"],
            "channel": merchants["channel"],
            "home_country_iso": merchants["home_country_iso"],
            "gdp_bucket": merchants["bucket_id"],
            "ln_gdp_pc_usd_2015": merchants["ln_gdp_pc_usd_2015"],
            "y_hurdle": y_hurdle,
        }
    )

    nb_df = pl.DataFrame(
        {
            "merchant_id": merchants["merchant_id"],
            "mcc": merchants["mcc"],
            "channel": merchants["channel"],
            "home_country_iso": merchants["home_country_iso"],
            "gdp_bucket": merchants["bucket_id"],
            "ln_gdp_pc_usd_2015": merchants["ln_gdp_pc_usd_2015"],
            "y_nb": y_nb,
        }
    ).filter(pl.col("y_nb") > 0)

    logistic_path = training_dir / "logistic.parquet"
    nb_path = training_dir / "nb_mean.parquet"
    logistic_df.write_parquet(logistic_path)
    nb_df.write_parquet(nb_path)

    manifest_path = training_dir / "manifest.json"

    X_hurdle = _build_design_matrix(
        mcc=mcc,
        channel=channel,
        gdp_bucket=gdp_bucket,
        dict_mcc=dict_mcc,
        include_bucket=True,
    )
    beta = _fit_logistic_ridge(
        X_hurdle, y_hurdle.astype(float), args.l2, args.irls_iter, args.irls_tol
    )

    pi_eval = _sigmoid(X_hurdle @ beta)
    multi_mask = y_hurdle == 1
    X_mu = _build_design_matrix(
        mcc=mcc[multi_mask],
        channel=channel[multi_mask],
        gdp_bucket=None,
        dict_mcc=dict_mcc,
        include_bucket=False,
    )
    y_mu = np.log(y_nb[multi_mask].astype(float))
    beta_mu = _fit_linear_ridge(X_mu, y_mu, args.l2)
    mu_floor = float(clamps_node.get("mu", {}).get("min", 2.0))
    beta_mu, mu_shift, mu_scale = _adjust_beta_mu(
        beta_mu,
        _build_design_matrix(
            mcc=mcc,
            channel=channel,
            gdp_bucket=None,
            dict_mcc=dict_mcc,
            include_bucket=False,
        ),
        pi_eval >= 0.5,
        mu_floor,
        40.0,
    )

    df_nb = nb_df.select(
        ["mcc", "channel", "gdp_bucket", "ln_gdp_pc_usd_2015", "y_nb"]
    )
    cell_stats = (
        df_nb.group_by(["mcc", "channel", "gdp_bucket"])
        .agg(
            [
                pl.len().alias("n"),
                pl.mean("y_nb").alias("mean_y"),
                pl.col("y_nb").var(ddof=0).alias("var_y"),
            ]
        )
        .sort(["mcc", "channel", "gdp_bucket"])
    )
    parent_stats = df_nb.group_by(["mcc", "channel"]).agg(
        [
            pl.len().alias("n_parent"),
            pl.mean("y_nb").alias("mean_parent"),
            pl.col("y_nb").var(ddof=0).alias("var_parent"),
        ]
    )
    global_stats = df_nb.select(
        [
            pl.len().alias("n_global"),
            pl.mean("y_nb").alias("mean_global"),
            pl.col("y_nb").var(ddof=0).alias("var_global"),
        ]
    ).row(0)

    n_min = int(disp_node.get("mom", {}).get("n_min", 30))
    epsilon = float(disp_node.get("mom", {}).get("epsilon", 1.0e-6))
    phi_min = float(clamps_node.get("phi", {}).get("min", 8.0))
    phi_max = float(clamps_node.get("phi", {}).get("max", 80.0))
    weight_rule = str(disp_node.get("mom", {}).get("cell_weight_rule", "n_cell"))

    cell_stats = cell_stats.join(parent_stats, on=["mcc", "channel"], how="left")
    cell_stats = cell_stats.with_columns(
        [
            pl.when(pl.col("n") >= n_min)
            .then(pl.col("mean_y"))
            .when(pl.col("n_parent") >= n_min)
            .then(pl.col("mean_parent"))
            .otherwise(pl.lit(float(global_stats[1])))
            .alias("mean_use"),
            pl.when(pl.col("n") >= n_min)
            .then(pl.col("var_y"))
            .when(pl.col("n_parent") >= n_min)
            .then(pl.col("var_parent"))
            .otherwise(pl.lit(float(global_stats[2])))
            .alias("var_use"),
        ]
    )
    cell_stats = cell_stats.with_columns(
        [
            pl.when(pl.col("var_use") <= pl.col("mean_use") + epsilon)
            .then(phi_max)
            .otherwise((pl.col("mean_use") ** 2) / (pl.col("var_use") - pl.col("mean_use")))
            .alias("phi_hat"),
        ]
    ).with_columns(
        [
            pl.col("phi_hat").clip(phi_min, phi_max).alias("phi_hat"),
            (
                pl.when(weight_rule == "sqrt_n_cell")
                .then(pl.col("n").sqrt())
                .otherwise(pl.col("n"))
            ).alias("cell_weight"),
        ]
    )

    df_nb = df_nb.join(cell_stats.select(["mcc", "channel", "gdp_bucket", "phi_hat", "cell_weight"]), on=["mcc", "channel", "gdp_bucket"], how="left")
    if df_nb["phi_hat"].null_count() > 0:
        raise RuntimeError("Missing phi_hat for some rows.")

    X_phi = _build_design_matrix(
        mcc=df_nb["mcc"].to_numpy(),
        channel=np.array(df_nb["channel"].to_list(), dtype=object),
        gdp_bucket=None,
        dict_mcc=dict_mcc,
        include_bucket=False,
    )
    ln_gdp_nb = df_nb["ln_gdp_pc_usd_2015"].to_numpy()
    X_phi = np.concatenate([X_phi, ln_gdp_nb[:, None]], axis=1)
    y_phi = np.log(df_nb["phi_hat"].to_numpy())
    weights = df_nb["cell_weight"].to_numpy()
    beta_phi = _fit_linear_ridge(X_phi, y_phi, args.l2, weights=weights)

    manifest = {
        "generated_at_utc": timestamp,
        "simulation_config": {
            "config_path": str(config_path.as_posix()),
            "rng": {"algorithm": rng_node.get("algorithm", "philox2x64-10"), "seed": seed},
            "semver": priors.get("semver"),
            "version": config_version,
            "calibration": {
                "base_logit": base_logit,
                "base_log_mean": base_log_mean,
                "base_log_phi": base_log_phi,
            },
        },
        "inputs": {
            "transaction_schema_merchant_ids": {
                "path": str(merchant_path.as_posix()),
                "sha256": _sha256_file(merchant_path),
            },
            "world_bank_gdp_per_capita": {
                "path": str(gdp_path.as_posix()),
                "sha256": _sha256_file(gdp_path),
            },
            "gdp_bucket_map": {
                "path": str(bucket_path.as_posix()),
                "sha256": _sha256_file(bucket_path),
            },
            "iso3166_canonical": {
                "path": str(iso_path.as_posix()),
                "sha256": _sha256_file(iso_path),
            },
            "priors": {
                "path": str(config_path.as_posix()),
                "sha256": _sha256_file(config_path),
            },
        },
        "datasets": {
            "logistic": "logistic.parquet",
            "nb_mean": "nb_mean.parquet",
        },
        "dataset_digests": {
            "logistic": _sha256_file(logistic_path),
            "nb_mean": _sha256_file(nb_path),
        },
        "fit_adjustments": {
            "beta_mu_intercept_shift": mu_shift,
            "mu_floor": mu_floor,
            "beta_mu_scale": mu_scale,
        },
        "summary": {
            "rows_logistic": int(logistic_df.height),
            "rows_nb": int(nb_df.height),
            "mean_pi": float(pi.mean()),
            "mean_mu_multi_weighted": float(np.average(mu, weights=pi)),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    meta_inputs = {
        "priors": {"path": str(config_path.as_posix()), "sha256": _sha256_file(config_path)},
        "transaction_schema_merchant_ids": {
            "path": str(merchant_path.as_posix()),
            "sha256": _sha256_file(merchant_path),
        },
        "world_bank_gdp_per_capita": {
            "path": str(gdp_path.as_posix()),
            "sha256": _sha256_file(gdp_path),
        },
        "gdp_bucket_map": {
            "path": str(bucket_path.as_posix()),
            "sha256": _sha256_file(bucket_path),
        },
        "iso3166_canonical": {
            "path": str(iso_path.as_posix()),
            "sha256": _sha256_file(iso_path),
        },
        "logistic": {"path": str(logistic_path.as_posix()), "sha256": _sha256_file(logistic_path)},
        "nb_mean": {"path": str(nb_path.as_posix()), "sha256": _sha256_file(nb_path)},
    }

    hurdle_bundle = {
        "semver": "1.0.0",
        "version": config_version,
        "metadata": {
            "simulation_manifest": str(manifest_path.as_posix()),
            "simulation_config_path": str(config_path.as_posix()),
            "seed": seed,
            "created_utc": timestamp,
            "inputs": meta_inputs,
        },
        "dict_mcc": dict_mcc,
        "dict_ch": dict_ch,
        "dict_dev5": dict_dev5,
        "design": {
            "beta_order": [
                "intercept",
                "mcc_onehot(dict_mcc)",
                "ch_onehot(['CP','CNP'])",
                "gdp_bucket_onehot([1,2,3,4,5])",
            ],
            "beta_mu_order": [
                "intercept",
                "mcc_onehot(dict_mcc)",
                "ch_onehot(['CP','CNP'])",
            ],
        },
        "beta": beta.tolist(),
        "beta_mu": beta_mu.tolist(),
    }

    hurdle_path = export_dir / "hurdle_coefficients.yaml"
    hurdle_path.write_text(
        yaml.safe_dump(hurdle_bundle, sort_keys=False), encoding="utf-8"
    )

    disp_bundle = {
        "semver": "1.0.0",
        "version": config_version,
        "metadata": {
            "simulation_manifest": str(manifest_path.as_posix()),
            "simulation_config_path": str(config_path.as_posix()),
            "seed": seed,
            "created_utc": timestamp,
            "inputs": meta_inputs,
        },
        "dict_mcc": dict_mcc,
        "dict_ch": dict_ch,
        "design": {
            "beta_phi_order": [
                "intercept",
                "mcc_onehot(dict_mcc)",
                "ch_onehot(['CP','CNP'])",
                "ln_gdp_pc_usd_2015",
            ]
        },
        "beta_phi": beta_phi.tolist(),
    }

    disp_path = export_dir / "nb_dispersion_coefficients.yaml"
    disp_path.write_text(
        yaml.safe_dump(disp_bundle, sort_keys=False), encoding="utf-8"
    )

    X_eval = _build_design_matrix(
        mcc=mcc,
        channel=channel,
        gdp_bucket=gdp_bucket,
        dict_mcc=dict_mcc,
        include_bucket=True,
    )
    X_mu_eval = _build_design_matrix(
        mcc=mcc,
        channel=channel,
        gdp_bucket=None,
        dict_mcc=dict_mcc,
        include_bucket=False,
    )
    X_phi_eval = np.concatenate([X_mu_eval, ln_gdp[:, None]], axis=1)

    pi_eval = _clip(_sigmoid(X_eval @ beta), 1e-12, 1.0 - 1e-12)
    mu_eval = np.exp(X_mu_eval @ beta_mu)
    phi_eval = np.exp(X_phi_eval @ beta_phi)

    if not np.isfinite(pi_eval).all():
        raise RuntimeError("Non-finite hurdle probabilities.")
    if (pi_eval <= 0).any() or (pi_eval >= 1).any():
        raise RuntimeError("Hurdle probabilities saturated.")
    if not np.isfinite(mu_eval).all() or (mu_eval <= 0).any():
        raise RuntimeError("Invalid mu predictions.")
    if not np.isfinite(phi_eval).all() or (phi_eval <= 0).any():
        raise RuntimeError("Invalid phi predictions.")

    p = phi_eval / (phi_eval + mu_eval)
    log_p = np.log(p)
    log1m = np.log1p(-p)
    log_p0 = phi_eval * log_p
    log_p1 = np.log(phi_eval) + log1m + phi_eval * log_p
    p0 = np.exp(log_p0)
    p1 = np.exp(log_p1)
    p_rej = p0 + p1
    infl = 1.0 / np.maximum(1e-12, 1.0 - p_rej)
    w = pi_eval * infl
    rho_hat = float(np.sum(w * p_rej) / np.sum(w))

    pi_mask = pi_eval >= 0.5
    q90_mu = float(np.quantile(mu_eval[pi_mask], 0.9)) if pi_mask.any() else 0.0
    median_mu_over_phi = (
        float(np.median((mu_eval / phi_eval)[pi_mask])) if pi_mask.any() else 0.0
    )

    if rho_hat > 0.055:
        raise RuntimeError(f"Belt-and-braces rho_hat too high: {rho_hat:.6f}")
    if (p_rej >= 0.25).any():
        raise RuntimeError("Belt-and-braces: p_rej >= 0.25 detected.")
    if (infl > 1.20).any():
        raise RuntimeError("Belt-and-braces: inflation > 1.20 detected.")
    if not (0.05 <= float(pi_eval.mean()) <= 0.30):
        raise RuntimeError("Belt-and-braces: mean_pi out of bounds.")
    if not (3.0 <= q90_mu <= 40.0):
        raise RuntimeError(f"Belt-and-braces: q90_mu out of bounds: {q90_mu:.4f}")
    if median_mu_over_phi < 0.02:
        raise RuntimeError("Belt-and-braces: median_mu_over_phi too low.")

    selfcheck = {
        "hurdle_sha256": _sha256_file(hurdle_path),
        "dispersion_sha256": _sha256_file(disp_path),
        "dict_mcc_len": len(dict_mcc),
        "beta_len": len(beta),
        "beta_mu_len": len(beta_mu),
        "beta_phi_len": len(beta_phi),
        "mean_pi": float(pi_eval.mean()),
        "q90_mu": q90_mu,
        "median_mu_over_phi": median_mu_over_phi,
        "median_phi": float(np.median(phi_eval)),
        "rho_hat": rho_hat,
        "max_infl": float(np.max(infl)),
        "max_p_rej": float(np.max(p_rej)),
        "status": "PASS",
    }
    (export_dir / "bundle_selfcheck.json").write_text(
        json.dumps(selfcheck, indent=2, sort_keys=True), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
