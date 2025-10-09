"""Fitting utilities for hurdle/NB coefficients."""

from __future__ import annotations

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

    mu_hat = np.exp(x_nb @ beta_mu)

    # Dispersion fit (method-of-moments inspired)
    phi_obs = (y_nb - mu_hat) / np.clip(mu_hat**2, 1e-6, None)
    phi_obs = np.clip(phi_obs, 1e-6, 1e2)
    log_phi = np.log(phi_obs)

    x_phi = matrices.x_dispersion
    xtx_phi = x_phi.T @ x_phi + ridge * np.eye(x_phi.shape[1])
    xty_phi = x_phi.T @ log_phi
    beta_phi = np.linalg.solve(xtx_phi, xty_phi)

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
