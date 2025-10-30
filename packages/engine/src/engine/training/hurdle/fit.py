"""Fitting utilities for hurdle/NB coefficients."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

import numpy as np

from .design import DesignMatrices


@dataclass(frozen=True)
class FitDiagnostics:
    logistic_iterations: int
    logistic_converged: bool
    logistic_final_step: float


@dataclass(frozen=True)
class HurdleFit:
    beta: np.ndarray
    beta_mu: np.ndarray
    beta_phi: np.ndarray
    diagnostics: FitDiagnostics


_DISPERSION_MIN_PHI = 5e-3
_DISPERSION_MAX_PHI = 5.0
_DISPERSION_MIN_ROWS = 8
_DISPERSION_GDP_BINS = 8
_EPS = 1e-6


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def fit_hurdle_coefficients(
    matrices: DesignMatrices,
    *,
    ridge: float = 1e-6,
    max_iter: int = 50,
    tol: float = 1e-6,
) -> HurdleFit:
    """Fit hurdle logistic + NB mean + dispersion coefficients."""

    x_h = matrices.x_hurdle
    y_h = matrices.y_hurdle
    beta = np.zeros(x_h.shape[1], dtype=np.float64)
    converged = False
    final_step = np.inf

    for iteration in range(1, max_iter + 1):
        eta = x_h @ beta
        mu = _sigmoid(eta)
        w = mu * (1.0 - mu)
        # guard against zeros
        w = np.clip(w, 1e-6, None)
        z = eta + (y_h - mu) / w
        wx = x_h * w[:, None]
        xtwx = x_h.T @ wx
        xtwx += ridge * np.eye(xtwx.shape[0])
        xtwz = x_h.T @ (w * z)
        new_beta = np.linalg.solve(xtwx, xtwz)
        step = np.linalg.norm(new_beta - beta)
        beta = new_beta
        final_step = step
        if step < tol:
            converged = True
            break

    # NB mean (log-linear)
    x_nb = matrices.x_nb_mean
    y_nb = matrices.y_nb
    log_y = np.log(np.clip(y_nb, 1e-3, None))
    xtx_nb = x_nb.T @ x_nb + ridge * np.eye(x_nb.shape[1])
    xty_nb = x_nb.T @ log_y
    beta_mu = np.linalg.solve(xtx_nb, xty_nb)

    beta_phi = _fit_dispersion_head(
        matrices=matrices,
        ridge=ridge,
        min_phi=_DISPERSION_MIN_PHI,
        max_phi=_DISPERSION_MAX_PHI,
        min_rows=_DISPERSION_MIN_ROWS,
        gdp_bins=_DISPERSION_GDP_BINS,
    )

    diagnostics = FitDiagnostics(
        logistic_iterations=iteration,
        logistic_converged=converged,
        logistic_final_step=float(final_step),
    )

    return HurdleFit(
        beta=beta,
        beta_mu=beta_mu,
        beta_phi=beta_phi,
        diagnostics=diagnostics,
    )


def _fit_dispersion_head(
    *,
    matrices: DesignMatrices,
    ridge: float,
    min_phi: float,
    max_phi: float,
    min_rows: int,
    gdp_bins: int,
) -> np.ndarray:
    row_thresholds = sorted(
        {max(min_rows, 2), max(min_rows // 2, 2), 2}, reverse=True
    )
    bin_candidates = sorted({max(gdp_bins, 2), max(gdp_bins // 2, 2), 2}, reverse=True)

    for rows_threshold in row_thresholds:
        for bins in bin_candidates:
            x_phi, log_phi_targets, weights = _build_dispersion_design(
                matrices=matrices,
                min_phi=min_phi,
                max_phi=max_phi,
                min_rows=rows_threshold,
                gdp_bins=bins,
            )
            if x_phi.size:
                return _solve_weighted_ridge(x_phi, log_phi_targets, weights, ridge)

    # Final fallback: treat the corpus as a single GDP bin with minimal filtering.
    x_phi, log_phi_targets, weights = _build_dispersion_design(
        matrices=matrices,
        min_phi=min_phi,
        max_phi=max_phi,
        min_rows=1,
        gdp_bins=1,
    )
    if x_phi.size == 0:
        raise ValueError("no dispersion cells available to fit beta_phi")
    return _solve_weighted_ridge(x_phi, log_phi_targets, weights, ridge)


def _build_dispersion_design(
    *,
    matrices: DesignMatrices,
    min_phi: float,
    max_phi: float,
    min_rows: int,
    gdp_bins: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    ln_g = matrices.dispersion_ln_g
    if ln_g.size == 0:
        return np.zeros((0, matrices.x_dispersion.shape[1])), np.zeros(0), np.zeros(0)
    edges = _compute_bin_edges(ln_g, gdp_bins)
    bin_ids = np.searchsorted(edges, ln_g, side="right") - 1
    bin_ids = np.clip(bin_ids, 0, len(edges) - 2)

    stats: dict[tuple[int, str, int], dict[str, float]] = {}
    counts = matrices.y_nb
    for idx in range(len(counts)):
        key = (
            int(matrices.dispersion_mcc[idx]),
            str(matrices.dispersion_channel[idx]),
            int(bin_ids[idx]),
        )
        record = stats.setdefault(
            key, {"n": 0.0, "sum_k": 0.0, "sum_sq": 0.0, "sum_ln": 0.0}
        )
        record["n"] += 1.0
        k = float(counts[idx])
        record["sum_k"] += k
        record["sum_sq"] += k * k
        record["sum_ln"] += float(ln_g[idx])

    rows: list[tuple[int, str, float, float, float]] = []
    for (mcc, channel, _bin), record in stats.items():
        n = int(record["n"])
        if n < min_rows:
            continue
        mean = record["sum_k"] / n
        if n > 1:
            var = max((record["sum_sq"] - n * mean * mean) / (n - 1), 0.0)
        else:
            var = 0.0
        denom = max(var - mean, _EPS)
        phi_mom = (mean * mean) / denom
        phi_clamped = float(max(min_phi, min(phi_mom, max_phi)))
        ln_g_mean = record["sum_ln"] / n
        rows.append((mcc, channel, ln_g_mean, phi_clamped, float(n)))

    dicts = matrices.dictionaries
    cols = 1 + len(dicts.mcc) + len(dicts.channel) + 1
    design = np.zeros((len(rows), cols), dtype=np.float64)
    log_targets = np.zeros(len(rows), dtype=np.float64)
    weights = np.zeros(len(rows), dtype=np.float64)

    mcc_index = {int(code): idx for idx, code in enumerate(dicts.mcc)}
    channel_index = {name: idx for idx, name in enumerate(dicts.channel)}
    channel_offset = 1 + len(dicts.mcc)
    ln_g_col = channel_offset + len(dicts.channel)

    for row_idx, (mcc, channel, ln_g_mean, phi_value, weight) in enumerate(rows):
        if mcc not in mcc_index or channel not in channel_index:
            continue
        design[row_idx, 0] = 1.0
        design[row_idx, 1 + mcc_index[mcc]] = 1.0
        design[row_idx, channel_offset + channel_index[channel]] = 1.0
        design[row_idx, ln_g_col] = ln_g_mean
        log_targets[row_idx] = math.log(phi_value)
        weights[row_idx] = max(weight, 1.0)

    mask = weights > 0
    design = design[mask]
    log_targets = log_targets[mask]
    weights = weights[mask]

    return design, log_targets, weights


def _solve_weighted_ridge(
    design: np.ndarray,
    targets: np.ndarray,
    weights: np.ndarray,
    ridge: float,
) -> np.ndarray:
    sqrt_w = np.sqrt(np.clip(weights, _EPS, None))
    design_w = design * sqrt_w[:, None]
    targets_w = targets * sqrt_w
    xtx = design_w.T @ design_w + ridge * np.eye(design_w.shape[1])
    xty = design_w.T @ targets_w
    return np.linalg.solve(xtx, xty)


def _compute_bin_edges(values: np.ndarray, bins: int) -> np.ndarray:
    if values.size == 0:
        return np.array([0.0, 1.0], dtype=np.float64)
    quantiles = np.linspace(0.0, 1.0, bins + 1)
    edges = np.quantile(values, quantiles)
    edges[0] -= 1e-9
    for idx in range(1, len(edges)):
        if edges[idx] <= edges[idx - 1]:
            edges[idx] = edges[idx - 1] + 1e-6
    edges[-1] += 1e-9
    return edges
