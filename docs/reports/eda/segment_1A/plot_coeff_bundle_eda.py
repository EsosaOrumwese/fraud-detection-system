"""Coefficient realism plots for Segment 1A (hurdle + NB dispersion).

This script focuses on model-bundle realism diagnostics for:
- hurdle_coefficients.yaml
- nb_dispersion_coefficients.yaml

It writes plots into docs/reports/eda/segment_1A/plots.
"""

from __future__ import annotations

from pathlib import Path
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[5]
PLOTS_DIR = ROOT / "docs/reports/eda/segment_1A/plots"
PLOTS_DIR.mkdir(parents=True, exist_ok=True)

RUN_BASE = ROOT / "runs/local_full_run-5/c25a2675fbfbacd952b13bb594880e92/data/layer1/1A"
PH = "56d45126eaabedd083a1d8428a763e0278c89efec5023cfd6cf3cab7fc8dd2d7"
MF = "c8fd43cd60ce0ede0c63d2ceb4610f167c9b107e1d59b9b8c7d7b8d0028b05c8"
EXP = ROOT / "config/layer1/1A/models/hurdle/exports/version=2026-01-03/20260103T184840Z"

MERCHANT_PATH = ROOT / "reference/layer1/transaction_schema_merchant_ids/2026-01-03/transaction_schema_merchant_ids.parquet"
GDP_PATH = ROOT / "reference/economic/world_bank_gdp_per_capita/2025-04-15/gdp.parquet"


plt.style.use("seaborn-v0_8")
plt.rcParams.update(
    {
        "figure.dpi": 150,
        "savefig.dpi": 150,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.labelsize": 11,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.fontsize": 10,
    }
)


def _quantiles(arr: np.ndarray) -> dict[str, float]:
    return {
        "min": float(np.min(arr)),
        "p01": float(np.quantile(arr, 0.01)),
        "p05": float(np.quantile(arr, 0.05)),
        "p50": float(np.quantile(arr, 0.50)),
        "p95": float(np.quantile(arr, 0.95)),
        "p99": float(np.quantile(arr, 0.99)),
        "max": float(np.max(arr)),
        "mean": float(np.mean(arr)),
        "std": float(np.std(arr, ddof=0)),
    }


def main() -> None:
    with (EXP / "hurdle_coefficients.yaml").open("r", encoding="utf-8") as f:
        hurdle = yaml.safe_load(f)
    with (EXP / "nb_dispersion_coefficients.yaml").open("r", encoding="utf-8") as f:
        disp = yaml.safe_load(f)

    dict_mcc = hurdle["dict_mcc"]
    k = len(dict_mcc)
    beta = np.asarray(hurdle["beta"], dtype=float)
    beta_mu = np.asarray(hurdle["beta_mu"], dtype=float)
    beta_phi = np.asarray(disp["beta_phi"], dtype=float)

    # Block slices by contract
    beta_mcc = beta[1 : 1 + k]
    beta_ch = beta[1 + k : 1 + k + 2]
    beta_gdp = beta[1 + k + 2 : 1 + k + 2 + 5]
    beta_mu_mcc = beta_mu[1 : 1 + k]
    beta_mu_ch = beta_mu[1 + k : 1 + k + 2]
    beta_phi_mcc = beta_phi[1 : 1 + k]
    beta_phi_ch = beta_phi[1 + k : 1 + k + 2]
    beta_phi_lngdp = float(beta_phi[1 + k + 2])

    hdm = pd.read_parquet(RUN_BASE / f"hurdle_design_matrix/parameter_hash={PH}/part-00000.parquet")
    hpi = pd.read_parquet(RUN_BASE / f"hurdle_pi_probs/parameter_hash={PH}/part-00000.parquet")
    merchants = pd.read_parquet(MERCHANT_PATH)
    gdp = pd.read_parquet(GDP_PATH)

    country_col = next(c for c in merchants.columns if "country" in c.lower() and "iso" in c.lower())
    gdp_country_col = next(c for c in gdp.columns if "country" in c.lower() and "iso" in c.lower())
    gdp_val_col = next(c for c in gdp.columns if "gdp" in c.lower())

    df = (
        hdm[["merchant_id", "mcc", "channel", "gdp_bucket_id"]]
        .merge(hpi[["merchant_id", "pi"]], on="merchant_id", how="left")
        .merge(merchants[["merchant_id", country_col]], on="merchant_id", how="left")
        .merge(
            gdp[[gdp_country_col, gdp_val_col]].drop_duplicates(gdp_country_col),
            left_on=country_col,
            right_on=gdp_country_col,
            how="left",
        )
    )

    mcc_idx = df["mcc"].map({int(m): i for i, m in enumerate(dict_mcc)}).astype(int).to_numpy()
    ch_idx = (
        df["channel"]
        .map({"card_present": 0, "card_not_present": 1, "CP": 0, "CNP": 1})
        .astype(int)
        .to_numpy()
    )
    gdp_bucket_idx = df["gdp_bucket_id"].astype(int).to_numpy() - 1
    ln_gdp = np.log(df[gdp_val_col].astype(float).to_numpy())

    # Implied eta/pi/mu/phi from coefficient contract
    eta = beta[0] + beta_mcc[mcc_idx] + beta_ch[ch_idx] + beta_gdp[gdp_bucket_idx]
    pi_hat = 1.0 / (1.0 + np.exp(-np.clip(eta, -35.0, 35.0)))

    eta_mu = beta_mu[0] + beta_mu_mcc[mcc_idx] + beta_mu_ch[ch_idx]
    mu_hat = np.exp(np.clip(eta_mu, -35.0, 35.0))

    eta_phi = beta_phi[0] + beta_phi_mcc[mcc_idx] + beta_phi_ch[ch_idx] + beta_phi_lngdp * ln_gdp
    phi_hat = np.exp(np.clip(eta_phi, -35.0, 35.0))

    # Contribution scales in eta space
    phi_mcc_contrib = beta_phi_mcc[mcc_idx]
    phi_ch_contrib = beta_phi_ch[ch_idx]
    phi_gdp_contrib = beta_phi_lngdp * ln_gdp
    mu_mcc_contrib = beta_mu_mcc[mcc_idx]
    mu_ch_contrib = beta_mu_ch[ch_idx]

    # Two "expectation" views:
    # (A) sensitivity of the current learned dispersion signal
    centered_phi_effect = (
        (phi_mcc_contrib - np.mean(phi_mcc_contrib))
        + (phi_ch_contrib - np.mean(phi_ch_contrib))
        + (phi_gdp_contrib - np.mean(phi_gdp_contrib))
    )
    # (B) illustrative strong counterfactual profile (not model output).
    # Use meaningful feature variation and re-center to the same median phi.
    z_mcc = (mu_mcc_contrib - np.mean(mu_mcc_contrib)) / (np.std(mu_mcc_contrib) + 1e-12)
    z_ch = (ch_idx - np.mean(ch_idx)) / (np.std(ch_idx) + 1e-12)
    z_gdp = (ln_gdp - np.mean(ln_gdp)) / (np.std(ln_gdp) + 1e-12)
    eta_phi_ref_raw = np.log(np.median(phi_hat)) + 0.20 * z_mcc + 0.10 * z_ch + 0.10 * z_gdp
    phi_ref_raw = np.exp(np.clip(eta_phi_ref_raw, -35.0, 35.0))
    phi_ref = phi_ref_raw * (np.median(phi_hat) / np.median(phi_ref_raw))

    # NB2 rejection probability (N<=1) under actual and reference phi
    def nb2_prej(mu: np.ndarray, phi: np.ndarray) -> np.ndarray:
        p = phi / (phi + mu)
        p = np.clip(p, 1e-12, 1.0)
        p0 = np.exp(phi * np.log(p))
        p1 = phi * (1.0 - p) * p0
        return p0 + p1

    prej_actual = nb2_prej(mu_hat, phi_hat)
    prej_ref = nb2_prej(mu_hat, phi_ref)

    # Plot 20: coefficient blocks (actual bundles)
    # Use scatter for dispersion blocks (n=290,2,1) because boxplots are low-information for n<=2.
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.8))
    axes[0].boxplot([beta_mcc, beta_ch, beta_gdp], tick_labels=["MCC", "Channel", "GDP bucket"], showfliers=False)
    axes[0].set_title("Hurdle beta Blocks")
    axes[0].set_ylabel("Coefficient value")
    axes[0].grid(alpha=0.25)

    axes[1].boxplot([beta_mu_mcc, beta_mu_ch], tick_labels=["MCC", "Channel"], showfliers=False)
    axes[1].set_title("NB Mean beta_mu Blocks")
    axes[1].grid(alpha=0.25)

    x_mcc = np.full(beta_phi_mcc.shape[0], 1.0)
    x_ch = np.array([2.0, 2.0])
    x_gdp = np.array([3.0])
    axes[2].scatter(x_mcc, beta_phi_mcc, s=8, alpha=0.55, color="#577590", label="MCC terms")
    axes[2].scatter(x_ch, beta_phi_ch, s=50, alpha=0.9, color="#f3722c", label="Channel terms")
    axes[2].scatter(x_gdp, [beta_phi_lngdp], s=65, alpha=0.95, color="#2a9d8f", label="ln(GDP) term")
    axes[2].set_xticks([1, 2, 3])
    axes[2].set_xticklabels(["MCC", "Channel", "ln(GDP)"])
    axes[2].set_yscale("symlog", linthresh=1e-4)
    axes[2].axhline(0.0, linestyle="--", linewidth=1.0, color="#555555", alpha=0.8)
    axes[2].set_ylabel("Coefficient value (symlog)")
    axes[2].set_title("NB Dispersion beta_phi Terms")
    axes[2].grid(alpha=0.25, axis="y")
    axes[2].legend(loc="upper right")

    fig.suptitle("1A Coefficient Block Diagnostics (Actual Bundle)", y=1.02, fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "20_coeff_block_diagnostics.png")
    plt.close(fig)

    # Plot 21: eta contribution scale comparison (mu vs phi)
    labels = ["MCC", "Channel", "GDP/lnGDP"]
    phi_std = [np.std(phi_mcc_contrib), np.std(phi_ch_contrib), np.std(phi_gdp_contrib)]
    mu_std = [np.std(mu_mcc_contrib), np.std(mu_ch_contrib), np.nan]
    x = np.arange(len(labels))
    w = 0.36
    fig, ax = plt.subplots(figsize=(8.4, 4.8))
    ax.bar(x - w / 2, phi_std, w, label="Dispersion eta_phi contribution std", color="#8ecae6")
    ax.bar(x + w / 2, np.nan_to_num(mu_std, nan=0.0), w, label="Mean eta_mu contribution std", color="#219ebc")
    ax.set_yscale("log")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Std of contribution in linear predictor (log scale)")
    ax.set_title("Contribution Scale: Dispersion vs Mean Models")
    ax.grid(alpha=0.25, axis="y")
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "21_eta_contribution_scale_compare.png")
    plt.close(fig)

    # Plot 22: implied phi distribution actual vs strong reference
    # Histogram-only view can hide nearly-degenerate actual profiles, so show ECDF + box diagnostics.
    def _ecdf(arr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        x = np.sort(arr)
        y = np.arange(1, x.size + 1, dtype=float) / x.size
        return x, y

    fig, (ax_l, ax_r) = plt.subplots(1, 2, figsize=(12.0, 4.8))
    x_a, y_a = _ecdf(phi_hat)
    x_r, y_r = _ecdf(phi_ref)
    ax_l.plot(x_a, y_a, color="#1d3557", linewidth=2.0, label="Actual implied phi")
    ax_l.plot(x_r, y_r, color="#e76f51", linewidth=2.0, label="Illustrative strong reference")
    ax_l.set_xlabel("Implied merchant-level phi")
    ax_l.set_ylabel("ECDF")
    ax_l.set_title("ECDF Comparison")
    ax_l.grid(alpha=0.25)
    ax_l.legend(loc="lower right")

    ax_r.boxplot([phi_hat, phi_ref], tick_labels=["Actual", "Reference"], showfliers=False)
    ax_r.set_ylabel("Implied merchant-level phi")
    ax_r.set_title("Spread Comparison (Boxplot)")
    ax_r.grid(alpha=0.25, axis="y")
    ax_r.text(
        0.03,
        0.97,
        f"Actual CV={np.std(phi_hat)/np.mean(phi_hat):.5f}\nRef CV={np.std(phi_ref)/np.mean(phi_ref):.3f}",
        transform=ax_r.transAxes,
        va="top",
        ha="left",
        fontsize=9,
        bbox={"facecolor": "white", "alpha": 0.75, "edgecolor": "none"},
    )

    fig.suptitle("Implied Dispersion: Actual vs Reference Strong Shape", y=1.02, fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "22_phi_actual_vs_reference.png")
    plt.close(fig)

    # Plot 23: phi by channel (actual)
    phi_cp = phi_hat[ch_idx == 0]
    phi_cnp = phi_hat[ch_idx == 1]
    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    ax.boxplot([phi_cp, phi_cnp], tick_labels=["card_present", "card_not_present"], showfliers=False)
    ax.set_ylabel("Implied phi")
    ax.set_title("Implied phi by Channel (Actual Bundle)")
    ax.grid(alpha=0.25, axis="y")
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "23_phi_by_channel_actual.png")
    plt.close(fig)

    # Plot 24: sensitivity curve for dispersion strength expectation
    multipliers = np.array([1, 5, 10, 20, 40, 80, 120, 200, 300, 400, 500, 700, 1000], dtype=float)
    cvs = []
    p95_p05 = []
    for mult in multipliers:
        eta_m = eta_phi + (mult - 1.0) * centered_phi_effect
        phi_m = np.exp(np.clip(eta_m, -35.0, 35.0))
        cvs.append(np.std(phi_m) / np.mean(phi_m))
        p95_p05.append(np.quantile(phi_m, 0.95) / np.quantile(phi_m, 0.05))

    fig, ax1 = plt.subplots(figsize=(8.8, 5.2))
    ax1.plot(multipliers, cvs, marker="o", color="#264653", label="CV(phi)")
    ax1.axhline(0.10, linestyle="--", color="#2a9d8f", linewidth=1.5, label="Illustrative strong CV=0.10")
    ax1.set_xscale("log")
    ax1.set_xlabel("Multiplier on centered dispersion-effect signal (log scale)")
    ax1.set_ylabel("CV of implied phi")
    ax1.grid(alpha=0.25)

    ax2 = ax1.twinx()
    ax2.plot(multipliers, p95_p05, marker="s", color="#e76f51", label="P95/P05(phi)")
    ax2.axhline(1.50, linestyle="--", color="#f4a261", linewidth=1.5, label="Illustrative strong P95/P05=1.50")
    ax2.set_ylabel("Spread ratio")

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")
    ax1.set_title("Sensitivity of Current Dispersion Signal (Expectation Check)")
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "24_phi_strength_sensitivity.png")
    plt.close(fig)

    # Plot 25: rejection probability under actual vs reference phi
    fig, ax = plt.subplots(figsize=(8.6, 4.8))
    ax.hist(prej_actual, bins=50, alpha=0.8, color="#355070", label="Actual phi", density=True)
    ax.hist(prej_ref, bins=50, alpha=0.45, color="#e56b6f", label="Illustrative strong reference phi", density=True)
    ax.set_xlabel("NB2 rejection probability P(N<=1)")
    ax.set_ylabel("Density")
    ax.set_title("Downstream Effect: Rejection-Probability Shape")
    ax.grid(alpha=0.25)
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "25_prej_actual_vs_reference.png")
    plt.close(fig)

    metrics = {
        "beta_stats": _quantiles(beta),
        "beta_mu_stats": _quantiles(beta_mu),
        "beta_phi_stats": _quantiles(beta_phi),
        "implied_pi_stats": _quantiles(pi_hat),
        "implied_phi_stats": _quantiles(phi_hat),
        "implied_phi_reference_stats": _quantiles(phi_ref),
        "prej_actual_stats": _quantiles(prej_actual),
        "prej_reference_stats": _quantiles(prej_ref),
        "phi_cv_actual": float(np.std(phi_hat) / np.mean(phi_hat)),
        "phi_cv_reference": float(np.std(phi_ref) / np.mean(phi_ref)),
        "phi_p95_p05_actual": float(np.quantile(phi_hat, 0.95) / np.quantile(phi_hat, 0.05)),
        "phi_p95_p05_reference": float(np.quantile(phi_ref, 0.95) / np.quantile(phi_ref, 0.05)),
        "reference_profile": {
            "type": "illustrative_counterfactual",
            "eta_components": {
                "mcc_z_weight": 0.20,
                "channel_z_weight": 0.10,
                "lngdp_z_weight": 0.10,
            },
            "median_anchor": float(np.median(phi_hat)),
        },
    }
    with (PLOTS_DIR / "coeff_bundle_metrics.json").open("w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    print("Coefficient plots written to", PLOTS_DIR)


if __name__ == "__main__":
    main()
