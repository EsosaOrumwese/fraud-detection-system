from __future__ import annotations

import json
import math
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import polars as pl
import seaborn as sns
import yaml
from matplotlib.ticker import PercentFormatter


REPO = Path(__file__).resolve().parents[5]
WORKBENCH = REPO / "analysis" / "dev_full_offline_investigation" / "00_investigation" / "watson_workbench"
EXPORTS = WORKBENCH / "exports" / "hurdle_coefficients"
EXPORTS.mkdir(parents=True, exist_ok=True)

RUN_ID = "a3bd8cac9a4284cd36072c6b9624a0c1"
PARAMETER_HASH = "0ea66cf0adf1c64bbaad68e566d1e49be502d771df78c608a4d2c23887d60f00"
MANIFEST_FINGERPRINT = "76ec81ce37897b0837f5f1b242a3fa557532067d416e5177efb8fc27c4865460"
SEED = 42

ACTIVE_BUNDLE = REPO / "config/layer1/1A/models/hurdle/exports/version=2026-02-14/20260214T173000Z/hurdle_coefficients.yaml"
ORIGINAL_BUNDLE = REPO / "config/layer1/1A/models/hurdle/exports/version=2026-01-03/20260103T184840Z/hurdle_coefficients.yaml"
TRAINING_DIR = REPO / "artefacts/training/1A/hurdle_sim/simulation_version=2026-01-03/seed=9248923/20260103T184840Z"
RUN_DIR = REPO / "runs/local_full_run-7" / RUN_ID
DESIGN_PATH = RUN_DIR / "data/layer1/1A/hurdle_design_matrix" / f"parameter_hash={PARAMETER_HASH}" / "part-00000.parquet"
PI_PATH = RUN_DIR / "data/layer1/1A/hurdle_pi_probs" / f"parameter_hash={PARAMETER_HASH}" / "part-00000.parquet"
EVENT_PATH = RUN_DIR / "logs/layer1/1A/rng/events/hurdle_bernoulli" / f"seed={SEED}" / f"parameter_hash={PARAMETER_HASH}" / f"run_id={RUN_ID}" / "part-00000.jsonl"

plt.style.use("seaborn-v0_8-whitegrid")
sns.set_context("talk")

COLORS = {
    "blue": "#245f87",
    "orange": "#c26d2d",
    "green": "#2a9d8f",
    "red": "#c94c4c",
    "gray": "#6c757d",
    "light_gray": "#d8dee4",
    "dark": "#222222",
    "purple": "#6b5b95",
    "gold": "#d7a22a",
}


def style_axes(ax, *, xgrid: bool = False) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(COLORS["dark"])
    ax.spines["bottom"].set_color(COLORS["dark"])
    ax.spines["left"].set_linewidth(1.0)
    ax.spines["bottom"].set_linewidth(1.0)
    ax.tick_params(colors=COLORS["dark"], labelsize=10)
    ax.title.set_fontsize(14)
    ax.xaxis.label.set_size(11)
    ax.yaxis.label.set_size(11)
    ax.grid(axis="y", color="#d9d9d9", linewidth=0.8, alpha=0.8)
    if xgrid:
        ax.grid(axis="x", color="#eeeeee", linewidth=0.7, alpha=0.7)
    else:
        ax.grid(axis="x", visible=False)


def save(fig, name: str) -> None:
    fig.tight_layout()
    fig.savefig(EXPORTS / name, dpi=170, bbox_inches="tight")
    plt.close(fig)


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def normalize_channel_expr(col: str = "channel") -> pl.Expr:
    return (
        pl.when(pl.col(col).is_in(["card_present", "CP"]))
        .then(pl.lit("CP"))
        .when(pl.col(col).is_in(["card_not_present", "CNP"]))
        .then(pl.lit("CNP"))
        .otherwise(pl.col(col))
    )


def split_bundle(bundle: dict) -> dict:
    dict_mcc = [int(x) for x in bundle["dict_mcc"]]
    dict_ch = list(bundle["dict_ch"])
    dict_dev5 = [int(x) for x in bundle["dict_dev5"]]
    beta = np.array(bundle["beta"], dtype=float)
    beta_mu = np.array(bundle["beta_mu"], dtype=float)

    mcc_start = 1
    ch_start = mcc_start + len(dict_mcc)
    bucket_start = ch_start + len(dict_ch)

    mu_mcc_start = 1
    mu_ch_start = mu_mcc_start + len(dict_mcc)

    return {
        "dict_mcc": dict_mcc,
        "dict_ch": dict_ch,
        "dict_dev5": dict_dev5,
        "beta": beta,
        "beta_intercept": float(beta[0]),
        "beta_mcc": beta[mcc_start:ch_start],
        "beta_ch": beta[ch_start:bucket_start],
        "beta_bucket": beta[bucket_start:bucket_start + len(dict_dev5)],
        "beta_mu": beta_mu,
        "beta_mu_intercept": float(beta_mu[0]),
        "beta_mu_mcc": beta_mu[mu_mcc_start:mu_ch_start],
        "beta_mu_ch": beta_mu[mu_ch_start:mu_ch_start + len(dict_ch)],
    }


def sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def score_hurdle(design: pl.DataFrame, parts: dict) -> np.ndarray:
    mcc_index = {code: idx for idx, code in enumerate(parts["dict_mcc"])}
    ch_index = {ch: idx for idx, ch in enumerate(parts["dict_ch"])}
    bucket_index = {b: idx for idx, b in enumerate(parts["dict_dev5"])}

    mcc = design["mcc"].to_numpy()
    channel = design["channel_norm"].to_list()
    bucket = design["gdp_bucket_id"].to_numpy()

    eta = np.full(len(design), parts["beta_intercept"], dtype=float)
    eta += np.array([parts["beta_mcc"][mcc_index[int(x)]] for x in mcc], dtype=float)
    eta += np.array([parts["beta_ch"][ch_index[str(x)]] for x in channel], dtype=float)
    eta += np.array([parts["beta_bucket"][bucket_index[int(x)]] for x in bucket], dtype=float)
    return eta


def score_mu(design: pl.DataFrame, parts: dict) -> np.ndarray:
    mcc_index = {code: idx for idx, code in enumerate(parts["dict_mcc"])}
    ch_index = {ch: idx for idx, ch in enumerate(parts["dict_ch"])}

    mcc = design["mcc"].to_numpy()
    channel = design["channel_norm"].to_list()
    eta = np.full(len(design), parts["beta_mu_intercept"], dtype=float)
    eta += np.array([parts["beta_mu_mcc"][mcc_index[int(x)]] for x in mcc], dtype=float)
    eta += np.array([parts["beta_mu_ch"][ch_index[str(x)]] for x in channel], dtype=float)
    return eta


def load_runtime() -> pl.DataFrame:
    design = pl.read_parquet(DESIGN_PATH).with_columns(normalize_channel_expr().alias("channel_norm"))
    pi = pl.read_parquet(PI_PATH).select(["merchant_id", "logit", "pi"]).rename({"logit": "diag_logit", "pi": "diag_pi"})
    rows = []
    with EVENT_PATH.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                obj = json.loads(line)
                rows.append(
                    {
                        "merchant_id": obj["merchant_id"],
                        "event_pi": float(obj["pi"]),
                        "u": None if obj["u"] is None else float(obj["u"]),
                        "is_multi": bool(obj["is_multi"]),
                        "draws": int(obj["draws"]),
                    }
                )
    events = pl.DataFrame(
        rows,
        schema={
            "merchant_id": pl.UInt64,
            "event_pi": pl.Float64,
            "u": pl.Float64,
            "is_multi": pl.Boolean,
            "draws": pl.Int64,
        },
        strict=False,
    )
    return design.join(pi, on="merchant_id", how="left").join(events, on="merchant_id", how="left")


def plot_training_corpus_surfaces() -> None:
    logistic = pl.read_parquet(TRAINING_DIR / "logistic.parquet").with_columns(normalize_channel_expr().alias("channel_norm"))
    nb = pl.read_parquet(TRAINING_DIR / "nb_mean.parquet").with_columns(normalize_channel_expr().alias("channel_norm"))

    fig, axes = plt.subplots(2, 2, figsize=(15, 10))

    ax = axes[0, 0]
    vals = logistic.group_by("y_hurdle").len().sort("y_hurdle")
    ax.bar(["single (0)", "multi (1)"], vals["len"].to_list(), color=[COLORS["gray"], COLORS["blue"]], edgecolor="none")
    ax.set_title("Training Hurdle Labels")
    ax.set_ylabel("Merchants")
    style_axes(ax)

    ax = axes[0, 1]
    rate = logistic.group_by(["gdp_bucket", "channel_norm"]).agg(pl.mean("y_hurdle").alias("multi_rate")).sort(["gdp_bucket", "channel_norm"])
    for ch, color in [("CP", COLORS["blue"]), ("CNP", COLORS["orange"])]:
        sub = rate.filter(pl.col("channel_norm") == ch)
        ax.plot(sub["gdp_bucket"].to_list(), sub["multi_rate"].to_list(), marker="o", linewidth=2.5, label=ch, color=color)
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.set_title("Training Multi-Site Rate by Bucket and Channel")
    ax.set_xlabel("GDP bucket")
    ax.set_ylabel("Multi-site rate")
    ax.legend(frameon=False)
    style_axes(ax)

    ax = axes[1, 0]
    y_nb = nb["y_nb"].to_numpy()
    bins = np.arange(2, min(int(y_nb.max()) + 2, 35))
    ax.hist(y_nb, bins=bins, color=COLORS["green"], edgecolor="none", alpha=0.9)
    ax.set_title("NB-Count Training Target Distribution")
    ax.set_xlabel("y_nb")
    ax.set_ylabel("Merchants")
    style_axes(ax)

    ax = axes[1, 1]
    means = nb.group_by(["gdp_bucket", "channel_norm"]).agg(pl.mean("y_nb").alias("mean_y_nb")).sort(["gdp_bucket", "channel_norm"])
    for ch, color in [("CP", COLORS["blue"]), ("CNP", COLORS["orange"])]:
        sub = means.filter(pl.col("channel_norm") == ch)
        ax.plot(sub["gdp_bucket"].to_list(), sub["mean_y_nb"].to_list(), marker="o", linewidth=2.5, label=ch, color=color)
    ax.set_title("Mean y_nb by Bucket and Channel")
    ax.set_xlabel("GDP bucket")
    ax.set_ylabel("Mean y_nb")
    ax.legend(frameon=False)
    style_axes(ax)

    save(fig, "hurdle_coefficients_training_corpus_surfaces.png")


def plot_active_bundle_block_summary(parts: dict) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(17, 5.6))

    ax = axes[0]
    labels = ["hurdle beta", "NB beta_mu"]
    ax.bar(labels, [parts["beta_intercept"], parts["beta_mu_intercept"]], color=[COLORS["blue"], COLORS["green"]], edgecolor="none")
    ax.set_title("Intercepts")
    ax.set_ylabel("Coefficient value")
    style_axes(ax)

    ax = axes[1]
    x = np.arange(len(parts["dict_ch"]))
    w = 0.36
    ax.bar(x - w / 2, parts["beta_ch"], width=w, label="beta: hurdle", color=COLORS["blue"], edgecolor="none")
    ax.bar(x + w / 2, parts["beta_mu_ch"], width=w, label="beta_mu: NB mean", color=COLORS["green"], edgecolor="none")
    ax.axhline(0, color=COLORS["dark"], linewidth=1)
    ax.set_xticks(x)
    ax.set_xticklabels(parts["dict_ch"])
    ax.set_title("Channel Terms")
    ax.set_ylabel("Coefficient value")
    ax.legend(frameon=False, fontsize=9)
    style_axes(ax)

    ax = axes[2]
    ax.plot(parts["dict_dev5"], parts["beta_bucket"], marker="o", linewidth=2.8, color=COLORS["orange"])
    ax.axhline(0, color=COLORS["dark"], linewidth=1)
    ax.set_title("Hurdle GDP-Bucket Terms")
    ax.set_xlabel("GDP bucket")
    ax.set_ylabel("beta coefficient")
    style_axes(ax)

    save(fig, "hurdle_coefficients_active_bundle_block_summary.png")


def coeff_extremes_df(codes: list[int], values: np.ndarray, n: int = 10) -> pl.DataFrame:
    df = pl.DataFrame({"mcc": [str(x) for x in codes], "coef": values.tolist()})
    top = df.sort("coef", descending=True).head(n).with_columns(pl.lit("positive").alias("side"))
    bottom = df.sort("coef").head(n).with_columns(pl.lit("negative").alias("side"))
    return pl.concat([top, bottom])


def plot_mcc_spreads(parts: dict) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(16, 11))

    lanes = [
        ("Hurdle beta MCC block", parts["beta_mcc"], COLORS["blue"]),
        ("NB-mean beta_mu MCC block", parts["beta_mu_mcc"], COLORS["green"]),
    ]
    for row, (title, values, color) in enumerate(lanes):
        ax = axes[row, 0]
        ax.hist(values, bins=45, color=color, edgecolor="none", alpha=0.9)
        ax.axvline(0, color=COLORS["dark"], linewidth=1)
        ax.set_title(f"{title}: Distribution")
        ax.set_xlabel("Coefficient value")
        ax.set_ylabel("MCC count")
        style_axes(ax)

        ax = axes[row, 1]
        ext = coeff_extremes_df(parts["dict_mcc"], values, n=8)
        labels = ext["mcc"].to_list()
        vals = ext["coef"].to_list()
        colors = [COLORS["green"] if v >= 0 else COLORS["red"] for v in vals]
        ax.barh(labels, vals, color=colors, edgecolor="none")
        ax.axvline(0, color=COLORS["dark"], linewidth=1)
        ax.set_title(f"{title}: Strongest MCC Terms")
        ax.set_xlabel("Coefficient value")
        style_axes(ax, xgrid=True)

    save(fig, "hurdle_coefficients_mcc_block_spreads.png")


def plot_runtime_scoring_surface(runtime: pl.DataFrame, parts: dict) -> None:
    runtime = runtime.with_columns([
        pl.Series("recomputed_logit", score_hurdle(runtime, parts)),
        pl.Series("recomputed_pi", sigmoid(score_hurdle(runtime, parts))),
        pl.Series("eta_mu", score_mu(runtime, parts)),
        pl.Series("mu_pred", np.exp(score_mu(runtime, parts))),
    ])

    fig, axes = plt.subplots(2, 2, figsize=(16, 11))

    ax = axes[0, 0]
    for ch, color in [("CP", COLORS["blue"]), ("CNP", COLORS["orange"])]:
        vals = runtime.filter(pl.col("channel_norm") == ch)["event_pi"].to_numpy()
        ax.hist(vals, bins=45, alpha=0.55, color=color, edgecolor="none", label=ch)
    ax.set_title("Active Runtime pi Distribution by Channel")
    ax.set_xlabel("event pi")
    ax.set_ylabel("Merchants")
    ax.legend(frameon=False)
    style_axes(ax)

    ax = axes[0, 1]
    box_data = [runtime.filter(pl.col("gdp_bucket_id") == b)["event_pi"].to_numpy() for b in sorted(runtime["gdp_bucket_id"].unique().to_list())]
    ax.boxplot(box_data, patch_artist=True, widths=0.55, boxprops=dict(facecolor="#dce9f5", color=COLORS["blue"]), medianprops=dict(color=COLORS["dark"]), whiskerprops=dict(color=COLORS["blue"]), capprops=dict(color=COLORS["blue"]), flierprops=dict(marker=".", markersize=2, markerfacecolor=COLORS["gray"], markeredgecolor="none", alpha=0.35))
    ax.set_xticklabels([str(b) for b in sorted(runtime["gdp_bucket_id"].unique().to_list())])
    ax.set_title("Active Runtime pi by GDP Bucket")
    ax.set_xlabel("GDP bucket")
    ax.set_ylabel("event pi")
    style_axes(ax)

    ax = axes[1, 0]
    cal = (
        runtime.with_columns((pl.col("event_pi") * 10).floor().clip(0, 9).cast(pl.Int64).alias("pi_decile"))
        .group_by("pi_decile")
        .agg([
            pl.mean("event_pi").alias("mean_pi"),
            pl.col("is_multi").cast(pl.Float64).mean().alias("observed_multi_rate"),
            pl.len().alias("n"),
        ])
        .sort("pi_decile")
    )
    ax.plot(cal["mean_pi"].to_list(), cal["observed_multi_rate"].to_list(), marker="o", linewidth=2.6, color=COLORS["blue"])
    ax.plot([0, 1], [0, 1], linestyle="--", color=COLORS["gray"], linewidth=1.3, label="ideal")
    for x, y, n in zip(cal["mean_pi"].to_list(), cal["observed_multi_rate"].to_list(), cal["n"].to_list()):
        ax.text(x, y + 0.025, str(n), ha="center", fontsize=8, color=COLORS["dark"])
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.xaxis.set_major_formatter(PercentFormatter(1.0))
    ax.set_title("Realized Multi-Site Rate by pi Band")
    ax.set_xlabel("Mean pi in band")
    ax.set_ylabel("Observed is_multi rate")
    ax.legend(frameon=False, fontsize=9)
    style_axes(ax, xgrid=True)

    ax = axes[1, 1]
    diff = runtime.with_columns((pl.col("event_pi") - pl.col("diag_pi")).abs().alias("abs_diff"))
    ax.hist(diff["abs_diff"].to_numpy(), bins=40, color=COLORS["purple"], edgecolor="none", alpha=0.9)
    ax.set_title("Event pi vs Diagnostic pi Difference")
    ax.set_xlabel("absolute difference")
    ax.set_ylabel("Merchants")
    style_axes(ax)

    save(fig, "hurdle_coefficients_active_runtime_scoring_surface.png")


def bundle_sort_key(path: Path) -> tuple[str, str]:
    version_match = re.search(r"version=([^/\\]+)", path.as_posix())
    timestamp = path.parent.name
    version = version_match.group(1) if version_match else ""
    return (version, timestamp)


def load_bundle_lineage() -> pl.DataFrame:
    rows = []
    for path in sorted((REPO / "config/layer1/1A/models/hurdle/exports").glob("version=*/**/hurdle_coefficients.yaml"), key=bundle_sort_key):
        y = load_yaml(path)
        if not {"dict_mcc", "dict_ch", "beta", "beta_mu"}.issubset(set(y.keys())):
            continue
        parts = split_bundle(y)
        meta = y.get("metadata", {}) or {}
        remediation = meta.get("remediation", {}) or {}
        version_match = re.search(r"version=([^/\\]+)", path.as_posix())
        rows.append(
            {
                "path": path.as_posix(),
                "version_path": version_match.group(1) if version_match else "",
                "timestamp": path.parent.name,
                "internal_version": str(y.get("version")),
                "beta_intercept": parts["beta_intercept"],
                "beta_mu_intercept": parts["beta_mu_intercept"],
                "beta_mcc_std": float(np.std(parts["beta_mcc"])),
                "beta_mu_mcc_std": float(np.std(parts["beta_mu_mcc"])),
                "beta_mcc_l2": float(np.linalg.norm(parts["beta_mcc"])),
                "beta_mu_mcc_l2": float(np.linalg.norm(parts["beta_mu_mcc"])),
                "change": remediation.get("change", "direct_export"),
                "wave": remediation.get("wave", ""),
            }
        )
    return pl.DataFrame(rows).with_row_index("idx")


def plot_bundle_lineage_progression() -> None:
    lineage = load_bundle_lineage()
    milestone_ts = [
        "20251009T120000Z",
        "20251024T234923Z",
        "20251231T134200Z",
        "20260103T184840Z",
        "20260212T171900Z",
        "20260212T200823Z",
        "20260213T104600Z",
        "20260214T125000Z",
        "20260214T173000Z",
    ]
    lineage = lineage.filter(pl.col("timestamp").is_in(milestone_ts)).sort("idx").with_row_index("plot_idx")
    label_map = {
        "20251009T120000Z": "initial\nOct09",
        "20251024T234923Z": "regen\nOct24",
        "20251231T134200Z": "late-Dec\nretune",
        "20260103T184840Z": "Jan03\ntraining export",
        "20260212T171900Z": "P1b\nhurdle shift",
        "20260212T200823Z": "P1\nfreeze",
        "20260213T104600Z": "Feb13\nmu lift",
        "20260214T125000Z": "P4.R4A\nfirst pass",
        "20260214T173000Z": "active\nFeb14",
    }
    labels = [label_map[row["timestamp"]] for row in lineage.to_dicts()]
    x = np.arange(lineage.height)

    fig, axes = plt.subplots(2, 1, figsize=(18, 10), sharex=True)

    ax = axes[0]
    ax.plot(x, lineage["beta_intercept"].to_numpy(), marker="o", linewidth=2.2, color=COLORS["blue"], label="hurdle beta intercept")
    ax.plot(x, lineage["beta_mu_intercept"].to_numpy(), marker="o", linewidth=2.2, color=COLORS["green"], label="NB beta_mu intercept")
    p1b_x = int(lineage.filter(pl.col("timestamp") == "20260212T171900Z")["plot_idx"][0])
    active_x = int(lineage.filter(pl.col("timestamp") == "20260214T173000Z")["plot_idx"][0])
    ax.axvline(p1b_x, color=COLORS["red"], linestyle="--", linewidth=1.3)
    ax.axvline(active_x, color=COLORS["orange"], linestyle="--", linewidth=1.3)
    ymin, ymax = ax.get_ylim()
    ax.text(p1b_x + 0.05, ymax - (ymax - ymin) * 0.05, "P1b hurdle shift", va="top", fontsize=9, color=COLORS["red"])
    ax.text(active_x - 0.05, ymax - (ymax - ymin) * 0.15, "active bundle", va="top", ha="right", fontsize=9, color=COLORS["orange"])
    ax.set_title("Coefficient Bundle Intercepts Across Export Lineage")
    ax.set_ylabel("Intercept")
    ax.legend(frameon=False)
    style_axes(ax)

    ax = axes[1]
    ax.plot(x, lineage["beta_mcc_std"].to_numpy(), marker="o", linewidth=2.2, color=COLORS["blue"], label="hurdle MCC std")
    ax.plot(x, lineage["beta_mu_mcc_std"].to_numpy(), marker="o", linewidth=2.2, color=COLORS["green"], label="NB-mean MCC std")
    ax.axvline(p1b_x, color=COLORS["red"], linestyle="--", linewidth=1.3)
    ax.axvline(active_x, color=COLORS["orange"], linestyle="--", linewidth=1.3)
    ax.set_title("MCC Block Spread Across Export Lineage")
    ax.set_ylabel("Standard deviation")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=9)
    ax.legend(frameon=False)
    style_axes(ax)

    save(fig, "hurdle_coefficients_bundle_lineage_progression.png")


def plot_original_vs_active_deltas(original_parts: dict, active_parts: dict) -> None:
    beta_delta = active_parts["beta"] - original_parts["beta"]
    beta_mu_delta = active_parts["beta_mu"] - original_parts["beta_mu"]

    fig, axes = plt.subplots(1, 3, figsize=(18, 5.6))

    ax = axes[0]
    vals = [original_parts["beta_intercept"], active_parts["beta_intercept"]]
    ax.bar(["original\nJan export", "active\nFeb bundle"], vals, color=[COLORS["gray"], COLORS["blue"]], edgecolor="none")
    ax.set_title("Hurdle Intercept Shift")
    ax.set_ylabel("beta[0]")
    style_axes(ax)

    ax = axes[1]
    blocks = {
        "intercept": beta_delta[:1],
        "MCC": beta_delta[1:1 + len(active_parts["dict_mcc"])],
        "channel": beta_delta[1 + len(active_parts["dict_mcc"]):1 + len(active_parts["dict_mcc"]) + len(active_parts["dict_ch"])],
        "bucket": beta_delta[-len(active_parts["dict_dev5"]):],
    }
    ax.bar(list(blocks.keys()), [float(np.linalg.norm(v)) for v in blocks.values()], color=COLORS["blue"], edgecolor="none")
    ax.set_title("Hurdle beta Delta by Block")
    ax.set_ylabel("L2 norm of delta")
    style_axes(ax)

    ax = axes[2]
    mu_blocks = {
        "intercept": beta_mu_delta[:1],
        "MCC": beta_mu_delta[1:1 + len(active_parts["dict_mcc"])],
        "channel": beta_mu_delta[-len(active_parts["dict_ch"]):],
    }
    ax.bar(list(mu_blocks.keys()), [float(np.linalg.norm(v)) for v in mu_blocks.values()], color=COLORS["green"], edgecolor="none")
    ax.set_title("NB beta_mu Delta by Block")
    ax.set_ylabel("L2 norm of delta")
    style_axes(ax)

    save(fig, "hurdle_coefficients_original_vs_active_deltas.png")


def plot_training_fit_alignment(parts: dict) -> None:
    logistic = pl.read_parquet(TRAINING_DIR / "logistic.parquet").with_columns(normalize_channel_expr().alias("channel_norm"))
    fig, axes = plt.subplots(2, 2, figsize=(15, 9.5))

    ax = axes[0, 0]
    train_rate = logistic.group_by("gdp_bucket").agg(pl.mean("y_hurdle").alias("rate")).sort("gdp_bucket")
    ax.plot(train_rate["gdp_bucket"].to_list(), train_rate["rate"].to_list(), marker="o", linewidth=2.5, color=COLORS["blue"], label="training y_hurdle rate")
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.set_title("Training Multi-Site Rate by Bucket")
    ax.set_xlabel("GDP bucket")
    ax.set_ylabel("Training multi-site rate")
    style_axes(ax)

    ax = axes[0, 1]
    ax.plot(parts["dict_dev5"], parts["beta_bucket"], marker="s", linewidth=2.5, color=COLORS["orange"])
    ax.axhline(0, color=COLORS["dark"], linewidth=1)
    ax.set_title("Fitted Hurdle Bucket Terms")
    ax.set_xlabel("GDP bucket")
    ax.set_ylabel("beta bucket coefficient")
    style_axes(ax)

    ax = axes[1, 0]
    rates = logistic.group_by("channel_norm").agg(pl.mean("y_hurdle").alias("rate")).sort("channel_norm")
    coef_map = {ch: coef for ch, coef in zip(parts["dict_ch"], parts["beta_ch"])}
    x = np.arange(rates.height)
    ax.bar(x, rates["rate"].to_list(), color=COLORS["blue"], edgecolor="none")
    ax.set_xticks(x)
    ax.set_xticklabels(rates["channel_norm"].to_list())
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.set_title("Training Multi-Site Rate by Channel")
    ax.set_ylabel("Training multi-site rate")
    style_axes(ax)

    ax = axes[1, 1]
    coef_vals = [coef_map[ch] for ch in rates["channel_norm"].to_list()]
    ax.bar(x, coef_vals, color=COLORS["orange"], edgecolor="none")
    ax.axhline(0, color=COLORS["dark"], linewidth=1)
    ax.set_xticks(x)
    ax.set_xticklabels(rates["channel_norm"].to_list())
    ax.set_title("Fitted Hurdle Channel Terms")
    ax.set_ylabel("beta channel coefficient")
    style_axes(ax)

    save(fig, "hurdle_coefficients_training_fit_alignment.png")


def main() -> None:
    active = load_yaml(ACTIVE_BUNDLE)
    original = load_yaml(ORIGINAL_BUNDLE)
    active_parts = split_bundle(active)
    original_parts = split_bundle(original)
    runtime = load_runtime()

    plot_training_corpus_surfaces()
    plot_active_bundle_block_summary(active_parts)
    plot_mcc_spreads(active_parts)
    plot_runtime_scoring_surface(runtime, active_parts)
    plot_bundle_lineage_progression()
    plot_original_vs_active_deltas(original_parts, active_parts)
    plot_training_fit_alignment(active_parts)


if __name__ == "__main__":
    main()
