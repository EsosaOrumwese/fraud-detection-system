from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import polars as pl
import seaborn as sns
import yaml
from matplotlib.ticker import PercentFormatter


REPO = Path(__file__).resolve().parents[5]
WORKBENCH = REPO / "analysis" / "dev_full_offline_investigation" / "00_investigation" / "watson_workbench"
EXPORTS = WORKBENCH / "exports" / "rng_event_hurdle_bernoulli"
EXPORTS.mkdir(parents=True, exist_ok=True)

RUN_ID = "a3bd8cac9a4284cd36072c6b9624a0c1"
SEED = 42
PARAMETER_HASH = "0ea66cf0adf1c64bbaad68e566d1e49be502d771df78c608a4d2c23887d60f00"

RUN_DIR = REPO / "runs" / "local_full_run-7" / RUN_ID
EVENT_PATH = (
    RUN_DIR
    / "logs"
    / "layer1"
    / "1A"
    / "rng"
    / "events"
    / "hurdle_bernoulli"
    / f"seed={SEED}"
    / f"parameter_hash={PARAMETER_HASH}"
    / f"run_id={RUN_ID}"
    / "part-00000.jsonl"
)
TRACE_PATH = (
    RUN_DIR
    / "logs"
    / "layer1"
    / "1A"
    / "rng"
    / "trace"
    / f"seed={SEED}"
    / f"parameter_hash={PARAMETER_HASH}"
    / f"run_id={RUN_ID}"
    / "rng_trace_log.jsonl"
)
DESIGN_PATH = (
    RUN_DIR
    / "data"
    / "layer1"
    / "1A"
    / "hurdle_design_matrix"
    / f"parameter_hash={PARAMETER_HASH}"
    / "part-00000.parquet"
)
PI_PATH = (
    RUN_DIR
    / "data"
    / "layer1"
    / "1A"
    / "hurdle_pi_probs"
    / f"parameter_hash={PARAMETER_HASH}"
    / "part-00000.parquet"
)
ACTIVE_BUNDLE = REPO / "config/layer1/1A/models/hurdle/exports/version=2026-02-14/20260214T173000Z/hurdle_coefficients.yaml"

COLORS = {
    "blue": "#245F87",
    "orange": "#C26D2D",
    "green": "#2A9D8F",
    "red": "#C94C4C",
    "gray": "#6C757D",
    "light_gray": "#D8DEE4",
    "dark": "#222222",
    "purple": "#6B5B95",
}


def style_axes(ax, *, xgrid: bool = False, ygrid: bool = True) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(COLORS["dark"])
    ax.spines["bottom"].set_color(COLORS["dark"])
    ax.tick_params(colors=COLORS["dark"], labelsize=9)
    ax.set_axisbelow(True)
    if ygrid:
        ax.grid(axis="y", color="#D9D9D9", linewidth=0.8, alpha=0.8)
    else:
        ax.grid(axis="y", visible=False)
    if xgrid:
        ax.grid(axis="x", color="#EAEAEA", linewidth=0.7, alpha=0.75)
    else:
        ax.grid(axis="x", visible=False)


def load_jsonl(path: Path) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return pd.DataFrame(rows)


def normalize_channel(value: str) -> str:
    if value == "card_present":
        return "CP"
    if value == "card_not_present":
        return "CNP"
    return value


def sigmoid(x: np.ndarray) -> np.ndarray:
    out = np.empty_like(x, dtype=float)
    pos = x >= 0
    out[pos] = 1.0 / (1.0 + np.exp(-x[pos]))
    exp_x = np.exp(x[~pos])
    out[~pos] = exp_x / (1.0 + exp_x)
    return out


def recompute_pi(design: pd.DataFrame, bundle: dict) -> pd.DataFrame:
    dict_mcc = [int(x) for x in bundle["dict_mcc"]]
    dict_ch = list(bundle["dict_ch"])
    dict_dev5 = [int(x) for x in bundle["dict_dev5"]]
    beta = np.array(bundle["beta"], dtype=float)

    mcc_start = 1
    ch_start = mcc_start + len(dict_mcc)
    bucket_start = ch_start + len(dict_ch)

    mcc_terms = {mcc: beta[mcc_start + idx] for idx, mcc in enumerate(dict_mcc)}
    ch_terms = {ch: beta[ch_start + idx] for idx, ch in enumerate(dict_ch)}
    bucket_terms = {bucket: beta[bucket_start + idx] for idx, bucket in enumerate(dict_dev5)}

    eta = (
        beta[0]
        + design["mcc"].map(mcc_terms).astype(float)
        + design["channel"].map(normalize_channel).map(ch_terms).astype(float)
        + design["gdp_bucket_id"].map(bucket_terms).astype(float)
    )
    return pd.DataFrame(
        {
            "merchant_id": design["merchant_id"],
            "recomputed_logit": eta,
            "recomputed_pi": sigmoid(eta.to_numpy(dtype=float)),
        }
    )


def load_joined() -> tuple[pd.DataFrame, pd.DataFrame]:
    events = load_jsonl(EVENT_PATH).rename(columns={"pi": "event_pi"})
    events["draws_int"] = events["draws"].astype(int)
    events["decision_match"] = events["is_multi"] == (events["u"] < events["event_pi"])
    events["counter_lo_delta"] = events["rng_counter_after_lo"] - events["rng_counter_before_lo"]
    events["counter_hi_delta"] = events["rng_counter_after_hi"] - events["rng_counter_before_hi"]

    design = pl.read_parquet(DESIGN_PATH).to_pandas()
    pi_probs = pl.read_parquet(PI_PATH).to_pandas()
    bundle = yaml.safe_load(ACTIVE_BUNDLE.read_text(encoding="utf-8"))
    scored = recompute_pi(design, bundle)

    joined = (
        events.merge(design, on="merchant_id", how="left", suffixes=("", "_design"))
        .merge(pi_probs.rename(columns={"logit": "diag_logit", "pi": "diag_pi"}), on="merchant_id", how="left")
        .merge(scored, on="merchant_id", how="left")
    )
    joined["event_minus_diag_pi"] = joined["event_pi"] - joined["diag_pi"]
    joined["event_minus_recomputed_pi"] = joined["event_pi"] - joined["recomputed_pi"]
    trace = load_jsonl(TRACE_PATH)
    return joined, trace


def save(fig: plt.Figure, name: str) -> Path:
    out = EXPORTS / name
    fig.tight_layout()
    fig.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_probability_alignment(df: pd.DataFrame) -> Path:
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))

    ax = axes[0, 0]
    ax.scatter(df["event_pi"], df["diag_pi"], s=8, alpha=0.22, color=COLORS["blue"], edgecolors="none")
    ax.plot([0, 1], [0, 1], color=COLORS["dark"], linewidth=1.4, linestyle="--", label="perfect alignment")
    ax.set_title("Event pi vs Diagnostic pi Cache")
    ax.set_xlabel("event pi")
    ax.set_ylabel("hurdle_pi_probs pi")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.xaxis.set_major_formatter(PercentFormatter(1.0))
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.legend(frameon=False, loc="upper left")
    style_axes(ax, xgrid=True)

    ax = axes[0, 1]
    residual_scaled = df["event_minus_diag_pi"] * 1e8
    ax.hist(residual_scaled, bins=50, color=COLORS["orange"], edgecolor="none", alpha=0.9)
    ax.axvline(0, color=COLORS["dark"], linewidth=1)
    ax.set_title("Event pi - Diagnostic pi Residuals")
    ax.set_xlabel("Residual scaled by 1e8")
    ax.set_ylabel("Merchants")
    style_axes(ax)

    ax = axes[1, 0]
    metrics = pd.DataFrame(
        {
            "comparison": ["event vs diagnostic", "event vs recomputed"],
            "max_abs_diff": [
                df["event_minus_diag_pi"].abs().max(),
                df["event_minus_recomputed_pi"].abs().max(),
            ],
            "mean_abs_diff": [
                df["event_minus_diag_pi"].abs().mean(),
                df["event_minus_recomputed_pi"].abs().mean(),
            ],
        }
    )
    x = np.arange(len(metrics))
    width = 0.36
    # Keep a small floor so near-machine-zero errors remain visible on a log axis.
    floor = 1e-18
    max_vals = metrics["max_abs_diff"].clip(lower=floor)
    mean_vals = metrics["mean_abs_diff"].clip(lower=floor)
    bars_a = ax.bar(x - width / 2, max_vals, width=width, color=COLORS["blue"], label="max abs diff", edgecolor="none")
    bars_b = ax.bar(x + width / 2, mean_vals, width=width, color=COLORS["green"], label="mean abs diff", edgecolor="none")
    ax.set_yscale("log")
    ax.set_ylim(floor, 1e-7)
    ax.set_xticks(x)
    ax.set_xticklabels(metrics["comparison"])
    ax.set_title("Alignment Error Magnitude")
    ax.set_ylabel("Absolute difference, log scale")
    ax.legend(frameon=False)
    style_axes(ax)
    for bars, source in [(bars_a, metrics["max_abs_diff"]), (bars_b, metrics["mean_abs_diff"])]:
        for bar, actual in zip(bars, source):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                max(bar.get_height() * 1.4, floor * 2),
                f"{actual:.1e}",
                ha="center",
                va="bottom",
                fontsize=8,
            )

    ax = axes[1, 1]
    sorted_df = df.sort_values("event_pi").reset_index(drop=True)
    ax.plot(sorted_df.index, sorted_df["event_pi"], color=COLORS["dark"], linewidth=2.2, label="event pi")
    ax.plot(sorted_df.index, sorted_df["diag_pi"], color=COLORS["orange"], linewidth=1.2, alpha=0.8, label="diagnostic pi")
    ax.plot(sorted_df.index, sorted_df["recomputed_pi"], color=COLORS["green"], linewidth=1.0, alpha=0.85, linestyle="--", label="recomputed pi")
    ax.set_title("Sorted Probability Surface Overlay")
    ax.set_xlabel("Merchants sorted by event pi")
    ax.set_ylabel("pi")
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.legend(frameon=False, loc="upper left")
    style_axes(ax, xgrid=False)

    fig.suptitle("Probability Alignment Checks for S1 Hurdle Events", fontsize=16, y=1.02)
    return save(fig, "rng_event_hurdle_probability_alignment.png")


def plot_decision_threshold(df: pd.DataFrame) -> Path:
    fig, ax = plt.subplots(figsize=(10.5, 8))
    false_df = df.loc[~df["is_multi"]]
    true_df = df.loc[df["is_multi"]]
    ax.scatter(false_df["event_pi"], false_df["u"], s=10, alpha=0.28, color=COLORS["gray"], edgecolors="none", label="is_multi = false")
    ax.scatter(true_df["event_pi"], true_df["u"], s=10, alpha=0.28, color=COLORS["green"], edgecolors="none", label="is_multi = true")
    ax.plot([0, 1], [0, 1], color=COLORS["dark"], linewidth=1.8, linestyle="--", label="decision threshold: u = pi")
    ax.fill_between([0, 1], [0, 1], [0, 0], color=COLORS["green"], alpha=0.08)
    ax.fill_between([0, 1], [0, 1], [1, 1], color=COLORS["gray"], alpha=0.08)
    ax.set_title("Uniform Draw Thresholded into Bernoulli Outcome")
    ax.set_xlabel("event pi")
    ax.set_ylabel("uniform draw u")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.xaxis.set_major_formatter(PercentFormatter(1.0))
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.legend(frameon=False, loc="upper left")
    style_axes(ax, xgrid=True)
    ax.text(
        0.98,
        0.04,
        f"decision mismatches: {(~df['decision_match']).sum():,}\n"
        f"multi-site: {int(df['is_multi'].sum()):,} / {len(df):,}",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=10,
        bbox={"facecolor": "white", "edgecolor": "#BBBBBB", "boxstyle": "round,pad=0.35"},
    )
    return save(fig, "rng_event_hurdle_decision_threshold_surface.png")


def plot_uniform_and_accounting(df: pd.DataFrame) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(15, 6.5))

    ax = axes[0]
    counts, bins, _ = ax.hist(df["u"], bins=25, color=COLORS["blue"], edgecolor="none", alpha=0.92)
    expected_per_bin = len(df) / 25
    ax.axhline(expected_per_bin, color=COLORS["orange"], linewidth=2, linestyle="--", label="uniform expectation per bin")
    ax.set_title("Uniform Draw Distribution")
    ax.set_xlabel("u")
    ax.set_ylabel("Merchants")
    ax.xaxis.set_major_formatter(PercentFormatter(1.0))
    ax.legend(frameon=False)
    style_axes(ax)
    ax.text(
        0.98,
        0.92,
        f"mean = {df['u'].mean():.4f}\nmedian = {df['u'].median():.4f}",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=10,
        bbox={"facecolor": "white", "edgecolor": "#BBBBBB", "boxstyle": "round,pad=0.35"},
    )

    ax = axes[1]
    checks = pd.DataFrame(
        {
            "check": [
                "stochastic rows",
                "draws = 1",
                "blocks = 1",
                "u non-null",
                "counter lo +1",
                "decision matches",
            ],
            "rows": [
                int((~df["deterministic"]).sum()),
                int((df["draws_int"] == 1).sum()),
                int((df["blocks"] == 1).sum()),
                int(df["u"].notna().sum()),
                int((df["counter_lo_delta"] == 1).sum()),
                int(df["decision_match"].sum()),
            ],
        }
    )
    colors = [COLORS["green"] if value == len(df) else COLORS["red"] for value in checks["rows"]]
    ax.barh(checks["check"], checks["rows"], color=colors, edgecolor="none")
    ax.axvline(len(df), color=COLORS["dark"], linewidth=1.3, linestyle="--", label="expected row count")
    ax.set_title("Per-Event Accounting Checks")
    ax.set_xlabel("Rows satisfying check")
    ax.set_xlim(0, len(df) * 1.05)
    ax.invert_yaxis()
    style_axes(ax, xgrid=True, ygrid=False)
    for y, value in enumerate(checks["rows"]):
        ax.text(value + len(df) * 0.01, y, f"{value:,}", va="center", fontsize=10)

    fig.suptitle("RNG and Decision Accounting for S1 Hurdle Events", fontsize=16, y=1.02)
    return save(fig, "rng_event_hurdle_uniform_and_accounting.png")


def plot_trace_reconciliation(trace: pd.DataFrame) -> Path:
    hurdle_trace = trace.loc[trace["substream_label"] == "hurdle_bernoulli"].copy().reset_index(drop=True)
    hurdle_trace["trace_row"] = np.arange(1, len(hurdle_trace) + 1)

    fig, ax = plt.subplots(figsize=(11, 6.5))
    ax.plot(hurdle_trace["trace_row"], hurdle_trace["events_total"], color=COLORS["blue"], linewidth=2.2, label="events_total")
    ax.plot(hurdle_trace["trace_row"], hurdle_trace["draws_total"].astype(int), color=COLORS["orange"], linewidth=1.5, linestyle="--", label="draws_total")
    ax.plot(hurdle_trace["trace_row"], hurdle_trace["blocks_total"].astype(int), color=COLORS["green"], linewidth=1.2, linestyle=":", label="blocks_total")
    ax.set_title("Hurdle Trace Reconciliation")
    ax.set_xlabel("Hurdle trace row")
    ax.set_ylabel("Cumulative total")
    ax.legend(frameon=False)
    style_axes(ax, xgrid=True)
    ax.text(
        0.98,
        0.04,
        f"final events = {int(hurdle_trace['events_total'].max()):,}\n"
        f"final draws = {int(hurdle_trace['draws_total'].astype(int).max()):,}\n"
        f"final blocks = {int(hurdle_trace['blocks_total'].astype(int).max()):,}",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=10,
        bbox={"facecolor": "white", "edgecolor": "#BBBBBB", "boxstyle": "round,pad=0.35"},
    )
    ax.text(
        0.03,
        0.92,
        "overlap means one event,\none draw and one block\nper hurdle row",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=10,
        bbox={"facecolor": "white", "edgecolor": "#BBBBBB", "boxstyle": "round,pad=0.35"},
    )
    return save(fig, "rng_event_hurdle_trace_reconciliation.png")


def main() -> None:
    sns.set_theme(style="whitegrid")
    df, trace = load_joined()
    outputs = [
        plot_probability_alignment(df),
        plot_decision_threshold(df),
        plot_uniform_and_accounting(df),
        plot_trace_reconciliation(trace),
    ]
    for path in outputs:
        print(path.relative_to(REPO))


if __name__ == "__main__":
    main()
