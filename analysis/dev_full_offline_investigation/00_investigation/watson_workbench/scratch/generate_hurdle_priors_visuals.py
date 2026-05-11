from __future__ import annotations

import json
import math
from pathlib import Path

import duckdb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import polars as pl
import seaborn as sns
import yaml
from matplotlib.ticker import PercentFormatter


REPO = Path(__file__).resolve().parents[5]
EXPORTS = (
    REPO
    / "analysis"
    / "dev_full_offline_investigation"
    / "00_investigation"
    / "watson_workbench"
    / "exports"
    / "hurdle_priors"
)
EXPORTS.mkdir(parents=True, exist_ok=True)

plt.style.use("seaborn-v0_8-whitegrid")
sns.set_context("talk")

COLORS = {
    "guide": "#657b83",
    "current": "#1d5f8c",
    "high": "#c26d2d",
    "cp": "#2a6f97",
    "cnp": "#c96f3d",
    "positive": "#2a9d8f",
    "negative": "#d1495b",
    "corridor": "#6c757d",
    "actual": "#1f77b4",
    "original": "#4c78a8",
    "active": "#d3722c",
}


def style_axes(ax):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#222")
    ax.spines["bottom"].set_color("#222")
    ax.spines["left"].set_linewidth(1.0)
    ax.spines["bottom"].set_linewidth(1.0)
    ax.tick_params(colors="#222", labelsize=10)
    ax.title.set_fontsize(14)
    ax.xaxis.label.set_size(11)
    ax.yaxis.label.set_size(11)
    ax.grid(axis="y", color="#d9d9d9", linewidth=0.8, alpha=0.8)
    ax.grid(axis="x", visible=False)


def load_priors():
    return yaml.safe_load((REPO / "config/layer1/1A/models/hurdle/hurdle_simulation.priors.yaml").read_text(encoding="utf-8"))


def parse_ranges(items):
    out = []
    for item in items:
        lo, hi = str(item["range"]).split("-", 1)
        out.append((int(lo), int(hi), float(item["offset"])))
    return out


def mcc_map(direct, ranges, mcc_values):
    direct_map = {int(k): float(v) for k, v in direct.items()}
    offsets = np.zeros(len(mcc_values), dtype=float)
    for i, code in enumerate(mcc_values):
        total = direct_map.get(int(code), 0.0)
        for lo, hi, delta in ranges:
            if lo <= code <= hi:
                total += delta
        offsets[i] = total
    return offsets


def channel_map(direct, channels):
    mapping = {str(k): float(v) for k, v in direct.items()}
    return np.array([mapping.get(ch, 0.0) for ch in channels], dtype=float)


def bucket_map(direct, buckets):
    mapping = {int(k): float(v) for k, v in direct.items()}
    return np.array([mapping.get(int(b), 0.0) for b in buckets], dtype=float)


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def clip(x, lo, hi):
    return np.minimum(np.maximum(x, lo), hi)


def weighted_median(values, weights):
    order = np.argsort(values)
    values = values[order]
    weights = weights[order]
    cumulative = np.cumsum(weights)
    cutoff = 0.5 * cumulative[-1]
    idx = np.searchsorted(cumulative, cutoff, side="left")
    return float(values[min(idx, len(values) - 1)])


def load_merchant_enriched():
    pri = load_priors()
    merchant_path = REPO / "reference/layer1/transaction_schema_merchant_ids/2026-01-03/transaction_schema_merchant_ids.parquet"
    gdp_path = REPO / "reference/economic/world_bank_gdp_per_capita/2025-04-15/gdp.parquet"
    bucket_path = REPO / "reference/economic/gdp_bucket_map/2024/gdp_bucket_map.parquet"
    iso_path = REPO / "reference/iso/iso3166_canonical/2024-12-31/iso3166.parquet"

    merchants = pl.read_parquet(merchant_path).sort("merchant_id").with_columns(
        pl.when(pl.col("channel") == "card_present")
        .then(pl.lit("CP"))
        .when(pl.col("channel") == "card_not_present")
        .then(pl.lit("CNP"))
        .otherwise(pl.col("channel"))
        .alias("channel")
    )
    gdp = pl.read_parquet(gdp_path).filter(pl.col("observation_year") == 2024)
    buckets = pl.read_parquet(bucket_path).select(["country_iso", "bucket_id"])
    iso = pl.read_parquet(iso_path).select(["country_iso"]).with_columns(pl.lit(1).alias("iso_present"))

    merchants = merchants.join(gdp.select(["country_iso", "gdp_pc_usd_2015"]), left_on="home_country_iso", right_on="country_iso", how="left")
    if "country_iso" in merchants.columns:
        merchants = merchants.drop("country_iso")
    merchants = merchants.join(buckets, left_on="home_country_iso", right_on="country_iso", how="left")
    if "country_iso" in merchants.columns:
        merchants = merchants.drop("country_iso")
    merchants = merchants.join(iso, left_on="home_country_iso", right_on="country_iso", how="left")
    if "country_iso" in merchants.columns:
        merchants = merchants.drop("country_iso")
    if "iso_present" in merchants.columns:
        merchants = merchants.drop("iso_present")

    merchants = merchants.with_columns(pl.col("gdp_pc_usd_2015").log().alias("ln_gdp_pc_usd_2015"))

    rng = np.random.default_rng(int(pri["rng"]["seed"]))
    channel = np.array(merchants["channel"].to_list(), dtype=object)
    mcc = np.array(merchants["mcc"].to_list(), dtype=int)
    gdp_bucket = np.array(merchants["bucket_id"].to_list(), dtype=int)
    ln_gdp = np.array(merchants["ln_gdp_pc_usd_2015"].to_list(), dtype=float)

    return pri, merchants, rng, channel, mcc, gdp_bucket, ln_gdp


def build_offset_context():
    pri, merchants, rng, channel, mcc, gdp_bucket, ln_gdp = load_merchant_enriched()
    h = pri["hurdle"]
    n = pri["nb_mean"]
    d = pri["dispersion"]
    noise = pri["noise"]
    clamps = pri["clamps"]

    ctx = {
        "pri": pri,
        "merchants": merchants,
        "channel": channel,
        "mcc": mcc,
        "gdp_bucket": gdp_bucket,
        "ln_gdp": ln_gdp,
        "h_mcc": mcc_map(h.get("mcc_offsets", {}), parse_ranges(h.get("mcc_range_offsets", [])), mcc),
        "n_mcc": mcc_map(n.get("mcc_offsets", {}), parse_ranges(n.get("mcc_range_offsets", [])), mcc),
        "d_mcc": mcc_map(d.get("mcc_offsets", {}), parse_ranges(d.get("mcc_range_offsets", [])), mcc),
        "h_ch": channel_map(h.get("channel_offsets", {}), channel),
        "n_ch": channel_map(n.get("channel_offsets", {}), channel),
        "d_ch": channel_map(d.get("channel_offsets", {}), channel),
        "h_b": bucket_map(h.get("bucket_offsets", {}), gdp_bucket),
        "noise_logit": rng.normal(0.0, float(noise.get("per_merchant_logit_sd", 0.0)), size=len(channel)),
        "noise_mu": rng.normal(0.0, float(noise.get("per_merchant_log_mu_sd", 0.0)), size=len(channel)),
        "noise_phi": rng.normal(0.0, float(noise.get("per_merchant_log_phi_sd", 0.0)), size=len(channel)),
        "clamps": {
            "pi_lo": float(clamps["pi"]["min"]),
            "pi_hi": float(clamps["pi"]["max"]),
            "mu_lo": float(clamps["mu"]["min"]),
            "mu_hi": float(clamps["mu"]["max"]),
            "phi_lo": float(clamps["phi"]["min"]),
            "phi_hi": float(clamps["phi"]["max"]),
        },
    }
    return ctx


def solve_calibration(ctx, target_pi, target_mu, target_phi, iters=64):
    pri = ctx["pri"]
    d = pri["dispersion"]
    calib = pri["calibration"]
    h_ch, h_b, h_mcc = ctx["h_ch"], ctx["h_b"], ctx["h_mcc"]
    n_ch, n_mcc = ctx["n_ch"], ctx["n_mcc"]
    d_ch, d_mcc = ctx["d_ch"], ctx["d_mcc"]
    noise_logit, noise_mu, noise_phi = ctx["noise_logit"], ctx["noise_mu"], ctx["noise_phi"]
    ln_gdp = ctx["ln_gdp"]
    pi_lo, pi_hi = ctx["clamps"]["pi_lo"], ctx["clamps"]["pi_hi"]
    mu_lo_clip, mu_hi_clip = ctx["clamps"]["mu_lo"], ctx["clamps"]["mu_hi"]
    phi_lo_clip, phi_hi_clip = ctx["clamps"]["phi_lo"], ctx["clamps"]["phi_hi"]

    logit_lo, logit_hi = calib["brackets"]["base_logit"]
    mu_lo, mu_hi = calib["brackets"]["base_log_mean"]
    phi_lo, phi_hi = calib["brackets"]["base_log_phi"]

    for _ in range(iters):
        mid = 0.5 * (logit_lo + logit_hi)
        eta = mid + h_ch + h_b + h_mcc + noise_logit
        pi = sigmoid(eta)
        if pi.mean() > target_pi:
            logit_hi = mid
        else:
            logit_lo = mid
    base_logit = 0.5 * (logit_lo + logit_hi)

    for _ in range(iters):
        mid = 0.5 * (mu_lo + mu_hi)
        log_mu = mid + n_ch + n_mcc + noise_mu
        mu = clip(np.exp(log_mu), mu_lo_clip, mu_hi_clip)
        eta = base_logit + h_ch + h_b + h_mcc + noise_logit
        pi = sigmoid(eta)
        weighted_mean = float(np.average(mu, weights=pi))
        if weighted_mean > target_mu:
            mu_hi = mid
        else:
            mu_lo = mid
    base_log_mean = 0.5 * (mu_lo + mu_hi)

    for _ in range(iters):
        mid = 0.5 * (phi_lo + phi_hi)
        log_phi = mid + float(d.get("gdp_log_slope", 0.0)) * ln_gdp + d_ch + d_mcc + noise_phi
        phi = clip(np.exp(log_phi), phi_lo_clip, phi_hi_clip)
        eta = base_logit + h_ch + h_b + h_mcc + noise_logit
        pi = sigmoid(eta)
        med = weighted_median(phi, pi)
        if med > target_phi:
            phi_hi = mid
        else:
            phi_lo = mid
    base_log_phi = 0.5 * (phi_lo + phi_hi)

    eta = base_logit + h_ch + h_b + h_mcc + noise_logit
    pi = clip(sigmoid(eta), pi_lo, pi_hi)
    mu = clip(np.exp(base_log_mean + n_ch + n_mcc + noise_mu), mu_lo_clip, mu_hi_clip)
    phi = clip(np.exp(base_log_phi + float(d.get("gdp_log_slope", 0.0)) * ln_gdp + d_ch + d_mcc + noise_phi), phi_lo_clip, phi_hi_clip)

    return {
        "base_logit": base_logit,
        "base_log_mean": base_log_mean,
        "base_log_phi": base_log_phi,
        "mean_pi": float(pi.mean()),
        "weighted_mean_mu": float(np.average(mu, weights=pi)),
        "weighted_median_phi": weighted_median(phi, pi),
        "pi": pi,
        "mu": mu,
        "phi": phi,
    }


def save(fig, name):
    fig.tight_layout()
    fig.savefig(EXPORTS / name, dpi=170, bbox_inches="tight")
    plt.close(fig)


def plot_calibration_scenarios(ctx):
    scenarios = {
        "Guide Example": (0.12, 5.0, 22.0, COLORS["guide"]),
        "Current Priors": (0.16, 6.5, 45.0, COLORS["current"]),
        "Late-Dec High": (0.16, 9.0, 45.0, COLORS["high"]),
    }
    solved = {}
    for label, (a, b, c, color) in scenarios.items():
        solved[label] = solve_calibration(ctx, a, b, c)

    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))

    ax = axes[0]
    labels = list(scenarios.keys())
    x = np.arange(len(labels))
    width = 0.22
    target_series = [
        [scenarios[l][0] for l in labels],
        [scenarios[l][1] for l in labels],
        [scenarios[l][2] for l in labels],
    ]
    names = ["mean_pi_target", "mean_mu_target_multi", "median_phi_target"]
    bars_colors = [COLORS["guide"], COLORS["current"], COLORS["high"]]
    for i, (series, name, col) in enumerate(zip(target_series, names, bars_colors)):
        ax.bar(x + (i - 1) * width, series, width=width, label=name, color=col, edgecolor="none")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=12, ha="right")
    ax.set_title("Calibration Targets Across Priors Postures")
    ax.set_ylabel("Target Value")
    ax.legend(frameon=False, fontsize=9)
    style_axes(ax)

    ax = axes[1]
    solved_series = [
        [solved[l]["base_logit"] for l in labels],
        [solved[l]["base_log_mean"] for l in labels],
        [solved[l]["base_log_phi"] for l in labels],
    ]
    for i, (series, name, col) in enumerate(zip(solved_series, ["base_logit", "base_log_mean", "base_log_phi"], bars_colors)):
        ax.bar(x + (i - 1) * width, series, width=width, label=name, color=col, edgecolor="none")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=12, ha="right")
    ax.set_title("Solved Base Levels After Calibration")
    ax.set_ylabel("Solved Base Value")
    ax.legend(frameon=False, fontsize=9)
    style_axes(ax)

    save(fig, "hurdle_priors_calibration_scenarios.png")


def plot_calibration_response_curves(ctx):
    pri = ctx["pri"]
    d = pri["dispersion"]
    calib = pri["calibration"]
    h_ch, h_b, h_mcc = ctx["h_ch"], ctx["h_b"], ctx["h_mcc"]
    n_ch, n_mcc = ctx["n_ch"], ctx["n_mcc"]
    d_ch, d_mcc = ctx["d_ch"], ctx["d_mcc"]
    noise_logit, noise_mu, noise_phi = ctx["noise_logit"], ctx["noise_mu"], ctx["noise_phi"]
    ln_gdp = ctx["ln_gdp"]
    pi_lo, pi_hi = ctx["clamps"]["pi_lo"], ctx["clamps"]["pi_hi"]
    mu_lo_clip, mu_hi_clip = ctx["clamps"]["mu_lo"], ctx["clamps"]["mu_hi"]
    phi_lo_clip, phi_hi_clip = ctx["clamps"]["phi_lo"], ctx["clamps"]["phi_hi"]

    solved = solve_calibration(ctx, float(calib["mean_pi_target"]), float(calib["mean_mu_target_multi"]), float(calib["median_phi_target"]))

    fig, axes = plt.subplots(1, 3, figsize=(18, 5.5))

    xs = np.linspace(calib["brackets"]["base_logit"][0], calib["brackets"]["base_logit"][1], 120)
    ys = []
    for x in xs:
        eta = x + h_ch + h_b + h_mcc + noise_logit
        ys.append(sigmoid(eta).mean())
    ax = axes[0]
    ax.plot(xs, ys, color=COLORS["current"], linewidth=2.5)
    ax.axhline(calib["mean_pi_target"], color=COLORS["negative"], linestyle="--", linewidth=1.5)
    ax.axvline(solved["base_logit"], color="#222", linestyle=":", linewidth=1.5)
    ax.set_title("Calibrating base_logit")
    ax.set_xlabel("base_logit")
    ax.set_ylabel("mean(pi)")
    style_axes(ax)

    xs = np.linspace(calib["brackets"]["base_log_mean"][0], calib["brackets"]["base_log_mean"][1], 120)
    ys = []
    eta = solved["base_logit"] + h_ch + h_b + h_mcc + noise_logit
    pi = sigmoid(eta)
    for x in xs:
        mu = clip(np.exp(x + n_ch + n_mcc + noise_mu), mu_lo_clip, mu_hi_clip)
        ys.append(float(np.average(mu, weights=pi)))
    ax = axes[1]
    ax.plot(xs, ys, color=COLORS["current"], linewidth=2.5)
    ax.axhline(calib["mean_mu_target_multi"], color=COLORS["negative"], linestyle="--", linewidth=1.5)
    ax.axvline(solved["base_log_mean"], color="#222", linestyle=":", linewidth=1.5)
    ax.set_title("Calibrating base_log_mean")
    ax.set_xlabel("base_log_mean")
    ax.set_ylabel("weighted mean(mu)")
    style_axes(ax)

    xs = np.linspace(calib["brackets"]["base_log_phi"][0], calib["brackets"]["base_log_phi"][1], 120)
    ys = []
    for x in xs:
        phi = clip(np.exp(x + float(d.get("gdp_log_slope", 0.0)) * ln_gdp + d_ch + d_mcc + noise_phi), phi_lo_clip, phi_hi_clip)
        ys.append(weighted_median(phi, pi))
    ax = axes[2]
    ax.plot(xs, ys, color=COLORS["current"], linewidth=2.5)
    ax.axhline(calib["median_phi_target"], color=COLORS["negative"], linestyle="--", linewidth=1.5)
    ax.axvline(solved["base_log_phi"], color="#222", linestyle=":", linewidth=1.5)
    ax.set_title("Calibrating base_log_phi")
    ax.set_xlabel("base_log_phi")
    ax.set_ylabel("weighted median(phi)")
    style_axes(ax)

    save(fig, "hurdle_priors_calibration_response_curves.png")


def top_offsets(mapping, top_n=12):
    items = [(str(k), float(v)) for k, v in mapping.items()]
    pos = sorted([x for x in items if x[1] > 0], key=lambda x: x[1], reverse=True)[:top_n // 2]
    neg = sorted([x for x in items if x[1] < 0], key=lambda x: x[1])[:top_n - len(pos)]
    return pos + neg


def plot_authored_offsets(pri, section_name, filename):
    node = pri[section_name]
    fig, axes = plt.subplots(1, 3, figsize=(18, 5.8))

    # channel
    ax = axes[0]
    ch_items = list(node["channel_offsets"].items())
    colors = [COLORS["cp"] if k == "CP" else COLORS["cnp"] for k, _ in ch_items]
    ax.bar([k for k, _ in ch_items], [v for _, v in ch_items], color=colors, edgecolor="none")
    ax.axhline(0, color="#222", linewidth=1)
    ax.set_title(f"{section_name}: Channel Offsets")
    ax.set_ylabel("Offset")
    style_axes(ax)

    # range offsets
    ax = axes[1]
    ranges = node.get("mcc_range_offsets", [])
    labels = [r["range"] for r in ranges]
    vals = [float(r["offset"]) for r in ranges]
    colors = [COLORS["positive"] if v >= 0 else COLORS["negative"] for v in vals]
    ax.barh(labels, vals, color=colors, edgecolor="none")
    ax.axvline(0, color="#222", linewidth=1)
    ax.set_title(f"{section_name}: MCC Range Offsets")
    ax.set_xlabel("Offset")
    style_axes(ax)

    # explicit MCC overrides
    ax = axes[2]
    items = top_offsets(node.get("mcc_offsets", {}), top_n=12)
    labels = [k for k, _ in items]
    vals = [v for _, v in items]
    colors = [COLORS["positive"] if v >= 0 else COLORS["negative"] for v in vals]
    ax.barh(labels, vals, color=colors, edgecolor="none")
    ax.axvline(0, color="#222", linewidth=1)
    ax.set_title(f"{section_name}: Explicit MCC Overrides")
    ax.set_xlabel("Offset")
    style_axes(ax)

    save(fig, filename)


def plot_hurdle_bucket_ladder(pri):
    node = pri["hurdle"]
    fig, ax = plt.subplots(figsize=(9, 5.5))
    buckets = list(node["bucket_offsets"].keys())
    vals = [node["bucket_offsets"][k] for k in buckets]
    ax.plot(buckets, vals, color=COLORS["current"], linewidth=3, marker="o", markersize=8)
    ax.axhline(0, color="#222", linewidth=1)
    ax.set_title("Hurdle GDP-Bucket Ladder in the Priors")
    ax.set_xlabel("GDP bucket")
    ax.set_ylabel("Hurdle offset")
    style_axes(ax)
    save(fig, "hurdle_priors_hurdle_bucket_ladder.png")


def plot_training_outputs():
    logistic_path = REPO / "artefacts/training/1A/hurdle_sim/simulation_version=2026-01-03/seed=9248923/20260103T184840Z/logistic.parquet"
    nb_path = REPO / "artefacts/training/1A/hurdle_sim/simulation_version=2026-01-03/seed=9248923/20260103T184840Z/nb_mean.parquet"
    logistic = pl.read_parquet(logistic_path)
    nb = pl.read_parquet(nb_path)

    fig, axes = plt.subplots(1, 3, figsize=(17, 5.5))

    ax = axes[0]
    hurdle_counts = logistic.group_by("y_hurdle").len().sort("y_hurdle")
    labels = ["single (0)", "multi (1)"]
    vals = hurdle_counts["len"].to_list()
    ax.bar(labels, vals, color=[COLORS["corridor"], COLORS["current"]], edgecolor="none")
    ax.set_title("Synthetic Hurdle Output")
    ax.set_ylabel("Merchants")
    style_axes(ax)

    ax = axes[1]
    bucket_multi = (
        logistic.group_by("gdp_bucket")
        .agg(pl.mean("y_hurdle").alias("multi_rate"))
        .sort("gdp_bucket")
    )
    ax.plot(bucket_multi["gdp_bucket"].to_list(), bucket_multi["multi_rate"].to_list(), color=COLORS["current"], linewidth=3, marker="o")
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.set_title("Synthetic Multi-Site Rate by GDP Bucket")
    ax.set_xlabel("GDP bucket")
    ax.set_ylabel("Multi-site rate")
    style_axes(ax)

    ax = axes[2]
    nb_counts = nb["y_nb"].to_list()
    bins = np.arange(2, min(max(nb_counts) + 2, 26))
    ax.hist(nb_counts, bins=bins, color=COLORS["current"], edgecolor="none", alpha=0.9)
    ax.set_title("Synthetic Multi-Site Outlet Counts")
    ax.set_xlabel("y_nb")
    ax.set_ylabel("Merchants")
    style_axes(ax)

    save(fig, "hurdle_priors_synthetic_training_outputs.png")


def plot_corridor_selfcheck():
    selfcheck = json.loads((REPO / "config/layer1/1A/models/hurdle/exports/version=2026-01-03/20260103T184840Z/bundle_selfcheck.json").read_text(encoding="utf-8"))
    metrics = [
        ("mean_pi", selfcheck["mean_pi"], 0.05, 0.30),
        ("q90_mu", selfcheck["q90_mu"], 3.0, 40.0),
        ("median_phi", selfcheck["median_phi"], 12.0, 80.0),
        ("rho_hat", selfcheck["rho_hat"], 0.0, 0.055),
        ("max_infl", selfcheck["max_infl"], 0.0, 1.20),
        ("max_p_rej", selfcheck["max_p_rej"], 0.0, 0.25),
    ]

    fig, ax = plt.subplots(figsize=(11, 6))
    labels = [m[0] for m in metrics]
    y = np.arange(len(metrics))
    for i, (label, actual, lo, hi) in enumerate(metrics):
        ax.hlines(i, lo, hi, color="#cfcfcf", linewidth=8, zorder=1)
        ax.plot(actual, i, "o", color=COLORS["current"], markersize=9, zorder=2)
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_title("January Export Belt-and-Braces Corridor Check")
    ax.set_xlabel("Metric value (gray band = allowed corridor)")
    style_axes(ax)
    save(fig, "hurdle_priors_belt_and_braces_corridor.png")


def plot_origin_vs_active():
    orig = yaml.safe_load((REPO / "config/layer1/1A/models/hurdle/exports/version=2026-01-03/20260103T184840Z/hurdle_coefficients.yaml").read_text(encoding="utf-8"))
    active = yaml.safe_load((REPO / "config/layer1/1A/models/hurdle/exports/version=2026-02-14/20260214T173000Z/hurdle_coefficients.yaml").read_text(encoding="utf-8"))
    run_events = REPO / "runs/local_full_run-7/a3bd8cac9a4284cd36072c6b9624a0c1/logs/layer1/1A/rng/events/hurdle_bernoulli/seed=42/parameter_hash=0ea66cf0adf1c64bbaad68e566d1e49be502d771df78c608a4d2c23887d60f00/run_id=a3bd8cac9a4284cd36072c6b9624a0c1/part-00000.jsonl"
    mean_pi_active_run = np.mean([json.loads(line)["pi"] for line in run_events.read_text(encoding="utf-8").splitlines() if line.strip()])
    mean_pi_orig = json.loads((REPO / "config/layer1/1A/models/hurdle/exports/version=2026-01-03/20260103T184840Z/bundle_selfcheck.json").read_text(encoding="utf-8"))["mean_pi"]

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))
    ax = axes[0]
    ax.bar(["original export", "active run"], [orig["beta"][0], active["beta"][0]], color=[COLORS["original"], COLORS["active"]], edgecolor="none")
    ax.set_title("Hurdle Intercept: Original vs Active")
    ax.set_ylabel("Intercept value")
    style_axes(ax)

    ax = axes[1]
    ax.bar(["original export", "active run"], [mean_pi_orig, mean_pi_active_run], color=[COLORS["original"], COLORS["active"]], edgecolor="none")
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.set_title("Mean Hurdle Probability: Original vs Active")
    ax.set_ylabel("Mean pi")
    style_axes(ax)
    save(fig, "hurdle_priors_origin_vs_active_branch_world.png")


def plot_clamp_effect(ctx):
    pri = ctx["pri"]
    d = pri["dispersion"]
    calib = pri["calibration"]
    solved = solve_calibration(ctx, float(calib["mean_pi_target"]), float(calib["mean_mu_target_multi"]), float(calib["median_phi_target"]))

    h_ch, h_b, h_mcc = ctx["h_ch"], ctx["h_b"], ctx["h_mcc"]
    n_ch, n_mcc = ctx["n_ch"], ctx["n_mcc"]
    d_ch, d_mcc = ctx["d_ch"], ctx["d_mcc"]
    noise_logit, noise_mu, noise_phi = ctx["noise_logit"], ctx["noise_mu"], ctx["noise_phi"]
    ln_gdp = ctx["ln_gdp"]

    raw_pi = sigmoid(solved["base_logit"] + h_ch + h_b + h_mcc + noise_logit)
    raw_mu = np.exp(solved["base_log_mean"] + n_ch + n_mcc + noise_mu)
    raw_phi = np.exp(solved["base_log_phi"] + float(d.get("gdp_log_slope", 0.0)) * ln_gdp + d_ch + d_mcc + noise_phi)
    clamped_pi = clip(raw_pi, ctx["clamps"]["pi_lo"], ctx["clamps"]["pi_hi"])
    clamped_mu = clip(raw_mu, ctx["clamps"]["mu_lo"], ctx["clamps"]["mu_hi"])
    clamped_phi = clip(raw_phi, ctx["clamps"]["phi_lo"], ctx["clamps"]["phi_hi"])

    fig, axes = plt.subplots(1, 3, figsize=(18, 5.5))
    specs = [
        ("pi", raw_pi, clamped_pi, ctx["clamps"]["pi_lo"], ctx["clamps"]["pi_hi"]),
        ("mu", raw_mu, clamped_mu, ctx["clamps"]["mu_lo"], ctx["clamps"]["mu_hi"]),
        ("phi", raw_phi, clamped_phi, ctx["clamps"]["phi_lo"], ctx["clamps"]["phi_hi"]),
    ]
    for ax, (name, raw, clamped, lo, hi) in zip(axes, specs):
        ax.hist(raw, bins=40, color=COLORS["guide"], alpha=0.45, label="raw", edgecolor="none")
        ax.hist(clamped, bins=40, color=COLORS["current"], alpha=0.7, label="clamped", edgecolor="none")
        ax.axvline(lo, color=COLORS["negative"], linestyle="--", linewidth=1.2)
        ax.axvline(hi, color=COLORS["negative"], linestyle="--", linewidth=1.2)
        ax.set_title(f"{name}: Raw vs Clamped")
        ax.set_xlabel(name)
        ax.set_ylabel("Merchants")
        style_axes(ax)
        ax.legend(frameon=False, fontsize=9)
    save(fig, "hurdle_priors_clamp_effects.png")


def plot_authoring_flow():
    fig, ax = plt.subplots(figsize=(15, 4.8))
    ax.axis("off")
    boxes = [
        (0.03, 0.35, 0.18, 0.34, "Priors\nhurdle_simulation.priors.yaml"),
        (0.25, 0.35, 0.18, 0.34, "Synthetic Corpus\nlogistic.parquet\nnb_mean.parquet"),
        (0.47, 0.35, 0.18, 0.34, "Original Export\n2026-01-03 bundle"),
        (0.69, 0.35, 0.12, 0.34, "P1b\n+2.2 hurdle\nintercept"),
        (0.84, 0.35, 0.12, 0.34, "Active Bundle\n2026-02-14"),
    ]
    for x, y, w, h, text in boxes:
        patch = plt.Rectangle((x, y), w, h, facecolor="#f7f7f7", edgecolor="#222", linewidth=1.2)
        ax.add_patch(patch)
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=12)

    arrows = [
        ((0.21, 0.52), (0.25, 0.52)),
        ((0.43, 0.52), (0.47, 0.52)),
        ((0.65, 0.52), (0.69, 0.52)),
        ((0.81, 0.52), (0.84, 0.52)),
    ]
    for start, end in arrows:
        ax.annotate("", xy=end, xytext=start, arrowprops=dict(arrowstyle="->", lw=2, color="#333"))

    ax.text(0.34, 0.78, "offline simulation + fit", ha="center", va="center", fontsize=11, color="#444")
    ax.text(0.75, 0.78, "governed remediation", ha="center", va="center", fontsize=11, color="#444")
    ax.set_title("From Priors to the Active Hurdle Bundle", fontsize=16, pad=12)
    fig.savefig(EXPORTS / "hurdle_priors_authoring_flow.png", dpi=170, bbox_inches="tight")
    plt.close(fig)


def main():
    ctx = build_offset_context()
    pri = ctx["pri"]
    plot_authoring_flow()
    plot_calibration_scenarios(ctx)
    plot_calibration_response_curves(ctx)
    plot_clamp_effect(ctx)
    plot_hurdle_bucket_ladder(pri)
    plot_authored_offsets(pri, "hurdle", "hurdle_priors_hurdle_authored_offsets.png")
    plot_authored_offsets(pri, "nb_mean", "hurdle_priors_nb_mean_authored_offsets.png")
    plot_authored_offsets(pri, "dispersion", "hurdle_priors_dispersion_authored_offsets.png")
    plot_training_outputs()
    plot_corridor_selfcheck()
    plot_origin_vs_active()


if __name__ == "__main__":
    main()
