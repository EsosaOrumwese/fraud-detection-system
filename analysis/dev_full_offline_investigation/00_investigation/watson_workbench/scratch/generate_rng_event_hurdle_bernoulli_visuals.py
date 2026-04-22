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
MERCHANT_PATH = REPO / "reference/layer1/transaction_schema_merchant_ids/2026-01-03/transaction_schema_merchant_ids.parquet"

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


def channel_label(value: str) -> str:
    return value.replace("_", " ")


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
    merchant = pl.read_parquet(MERCHANT_PATH).select(["merchant_id", "home_country_iso"]).to_pandas()
    bundle = yaml.safe_load(ACTIVE_BUNDLE.read_text(encoding="utf-8"))
    scored = recompute_pi(design, bundle)

    joined = (
        events.merge(design, on="merchant_id", how="left", suffixes=("", "_design"))
        .merge(pi_probs.rename(columns={"logit": "diag_logit", "pi": "diag_pi"}), on="merchant_id", how="left")
        .merge(scored, on="merchant_id", how="left")
        .merge(merchant, on="merchant_id", how="left")
    )
    joined["event_minus_diag_pi"] = joined["event_pi"] - joined["diag_pi"]
    joined["event_minus_recomputed_pi"] = joined["event_pi"] - joined["recomputed_pi"]
    trace = load_jsonl(TRACE_PATH)
    return joined, trace


def summarize_rates(df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    out = (
        df.groupby(keys, dropna=False)
        .agg(
            merchants=("merchant_id", "size"),
            expected_multi=("event_pi", "sum"),
            realized_multi=("is_multi", "sum"),
            mean_pi=("event_pi", "mean"),
            variance=("event_pi", lambda s: float(np.sum(s.to_numpy() * (1.0 - s.to_numpy())))),
        )
        .reset_index()
    )
    out["expected_rate"] = out["expected_multi"] / out["merchants"]
    out["realized_rate"] = out["realized_multi"] / out["merchants"]
    out["residual_count"] = out["realized_multi"] - out["expected_multi"]
    out["residual_z"] = out.apply(
        lambda row: row["residual_count"] / np.sqrt(row["variance"]) if row["variance"] > 0 else np.nan,
        axis=1,
    )
    return out


def save(fig: plt.Figure, name: str) -> Path:
    out = EXPORTS / name
    fig.tight_layout()
    fig.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_coverage_lineage(df: pd.DataFrame) -> Path:
    coverage = pd.DataFrame(
        {
            "surface": [
                "event rows",
                "event merchants",
                "design matched",
                "pi matched",
                "recomputed pi",
                "country matched",
            ],
            "rows": [
                len(df),
                df["merchant_id"].nunique(),
                int(df["mcc"].notna().sum()),
                int(df["diag_pi"].notna().sum()),
                int(df["recomputed_pi"].notna().sum()),
                int(df["home_country_iso"].notna().sum()),
            ],
        }
    )
    missing = pd.DataFrame(
        {
            "join check": ["missing design", "missing pi", "missing country"],
            "rows": [
                int(df["mcc"].isna().sum()),
                int(df["diag_pi"].isna().sum()),
                int(df["home_country_iso"].isna().sum()),
            ],
        }
    )
    lineage = pd.DataFrame(
        {
            "field": ["seed", "parameter hash", "fingerprint", "run id", "module", "substream"],
            "unique values": [
                df["seed"].nunique(),
                df["parameter_hash_x"].nunique(),
                df["manifest_fingerprint"].nunique(),
                df["run_id"].nunique(),
                df["module"].nunique(),
                df["substream_label"].nunique(),
            ],
        }
    )

    integrity = pd.concat(
        [
            missing.assign(kind="missing").rename(columns={"join check": "check"}),
            lineage.assign(kind="lineage").rename(columns={"field": "check", "unique values": "rows"}),
        ],
        ignore_index=True,
    )

    fig, axes = plt.subplots(1, 2, figsize=(14, 5.8), gridspec_kw={"width_ratios": [1.2, 1.0]})

    ax = axes[0]
    ax.barh(coverage["surface"], coverage["rows"], color=COLORS["blue"], edgecolor="none")
    ax.axvline(len(df), color=COLORS["dark"], linestyle="--", linewidth=1.1)
    ax.set_title("Coverage Across Joined Surfaces")
    ax.set_xlabel("Rows / merchants")
    ax.set_xlim(0, len(df) * 1.18)
    style_axes(ax, xgrid=True, ygrid=False)
    for y, value in enumerate(coverage["rows"]):
        ax.text(value + len(df) * 0.01, y, f"{value:,}", va="center", fontsize=9)
    ax.text(
        0.98,
        0.06,
        "dashed line = event row count",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=9,
        bbox={"facecolor": "white", "edgecolor": "#BBBBBB", "boxstyle": "round,pad=0.25", "alpha": 0.9},
    )

    ax = axes[1]
    y = np.arange(len(integrity))
    colors = [COLORS["green"] if kind == "missing" else COLORS["purple"] for kind in integrity["kind"]]
    ax.barh(y, integrity["rows"], color=colors, edgecolor="none")
    ax.axvline(1, color=COLORS["dark"], linestyle="--", linewidth=1.1, label="single-lineage target")
    ax.set_yticks(y)
    ax.set_yticklabels(integrity["check"])
    ax.set_title("Join Gaps and Lineage Cardinality")
    ax.set_xlabel("Count")
    ax.set_xlim(0, 2.1)
    ax.legend(frameon=False, loc="lower right")
    style_axes(ax, xgrid=True, ygrid=False)
    for y_pos, row in enumerate(integrity.itertuples(index=False)):
        label = f"{int(row.rows):,} missing" if row.kind == "missing" else f"{int(row.rows):,} unique"
        ax.text(row.rows + 0.05, y_pos, label, va="center", fontsize=9)

    fig.suptitle("Hurdle Event Stream Coverage and Lineage Sanity Check", fontsize=16, y=1.02)
    return save(fig, "rng_event_hurdle_coverage_lineage.png")


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


def plot_branch_population_summary(df: pd.DataFrame) -> Path:
    n = len(df)
    expected_multi = float(df["event_pi"].sum())
    realized_multi = int(df["is_multi"].sum())
    expected_single = n - expected_multi
    realized_single = n - realized_multi
    variance = float(np.sum(df["event_pi"].to_numpy() * (1.0 - df["event_pi"].to_numpy())))
    sd = float(np.sqrt(variance))
    residual = realized_multi - expected_multi

    fig, axes = plt.subplots(1, 2, figsize=(14, 6.3), gridspec_kw={"width_ratios": [1.15, 1]})

    ax = axes[0]
    x = np.arange(2)
    width = 0.34
    ax.bar(x - width / 2, [expected_single, expected_multi], width=width, color=COLORS["blue"], label="expected", edgecolor="none")
    ax.bar(x + width / 2, [realized_single, realized_multi], width=width, color=COLORS["green"], label="realized", edgecolor="none")
    ax.set_xticks(x)
    ax.set_xticklabels(["single-site", "multi-site"])
    ax.set_title("Expected vs Realized Branch Population")
    ax.set_ylabel("Merchants")
    ax.legend(frameon=False)
    style_axes(ax)
    for xpos, val in zip(x - width / 2, [expected_single, expected_multi]):
        ax.text(xpos, val + 90, f"{val:,.1f}", ha="center", va="bottom", fontsize=9)
    for xpos, val in zip(x + width / 2, [realized_single, realized_multi]):
        ax.text(xpos, val + 90, f"{val:,.0f}", ha="center", va="bottom", fontsize=9)

    ax = axes[1]
    ax.axhspan(-1, 1, color=COLORS["green"], alpha=0.08, label="within +/-1 sd")
    ax.axhline(0, color=COLORS["dark"], linewidth=1.2)
    ax.scatter([0], [residual / sd], s=140, color=COLORS["orange"], zorder=3)
    ax.set_xlim(-0.65, 0.65)
    ax.set_ylim(-3, 3)
    ax.set_xticks([0])
    ax.set_xticklabels(["realized - expected"])
    ax.set_title("Branch Count Residual")
    ax.set_ylabel("Residual in Bernoulli standard deviations")
    style_axes(ax, xgrid=False)
    ax.text(
        0.96,
        0.08,
        f"expected multi = {expected_multi:,.2f}\n"
        f"realized multi = {realized_multi:,.0f}\n"
        f"residual = {residual:,.2f}\n"
        f"z = {residual / sd:.3f}",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=10,
        bbox={"facecolor": "white", "edgecolor": "#BBBBBB", "boxstyle": "round,pad=0.35"},
    )

    fig.suptitle("The Branch World Created by S1", fontsize=16, y=1.02)
    return save(fig, "rng_event_hurdle_branch_population_summary.png")


def plot_runtime_pi_surface(df: pd.DataFrame) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(15, 6.2))

    ax = axes[0]
    ax.hist(df["event_pi"], bins=45, color=COLORS["blue"], alpha=0.9, edgecolor="none")
    for q, label, color in [
        (df["event_pi"].quantile(0.05), "p05", COLORS["gray"]),
        (df["event_pi"].median(), "median", COLORS["orange"]),
        (df["event_pi"].quantile(0.95), "p95", COLORS["gray"]),
    ]:
        ax.axvline(q, color=color, linewidth=1.8, linestyle="--")
        ax.text(q, ax.get_ylim()[1] * 0.94, label, rotation=90, ha="right", va="top", fontsize=9, color=color)
    ax.set_title("Runtime pi Distribution")
    ax.set_xlabel("event pi")
    ax.set_ylabel("Merchants")
    ax.xaxis.set_major_formatter(PercentFormatter(1.0))
    style_axes(ax)

    ax = axes[1]
    sorted_pi = np.sort(df["event_pi"].to_numpy())
    y = np.arange(1, len(sorted_pi) + 1) / len(sorted_pi)
    ax.plot(sorted_pi, y, color=COLORS["purple"], linewidth=2.4)
    ax.set_title("Runtime pi Cumulative Surface")
    ax.set_xlabel("event pi")
    ax.set_ylabel("Share of merchants <= pi")
    ax.xaxis.set_major_formatter(PercentFormatter(1.0))
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    style_axes(ax, xgrid=True)
    ax.text(
        0.04,
        0.96,
        f"min = {df['event_pi'].min():.4f}\n"
        f"mean = {df['event_pi'].mean():.4f}\n"
        f"median = {df['event_pi'].median():.4f}\n"
        f"max = {df['event_pi'].max():.4f}",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=10,
        bbox={"facecolor": "white", "edgecolor": "#BBBBBB", "boxstyle": "round,pad=0.35"},
    )

    fig.suptitle("Runtime Probability Surface Emitted into the Hurdle Event Stream", fontsize=16, y=1.02)
    return save(fig, "rng_event_hurdle_runtime_pi_surface.png")


def plot_channel_and_bucket_shape(df: pd.DataFrame) -> Path:
    channel = summarize_rates(df, ["channel"]).sort_values("expected_rate")
    bucket = summarize_rates(df, ["gdp_bucket_id"]).sort_values("gdp_bucket_id")

    fig, axes = plt.subplots(1, 2, figsize=(15, 6.4))

    ax = axes[0]
    x = np.arange(len(channel))
    width = 0.34
    ax.bar(x - width / 2, channel["expected_rate"], width=width, color=COLORS["blue"], label="expected rate", edgecolor="none")
    ax.bar(x + width / 2, channel["realized_rate"], width=width, color=COLORS["green"], label="realized rate", edgecolor="none")
    ax.set_xticks(x)
    ax.set_xticklabels([channel_label(value) for value in channel["channel"]], rotation=10)
    ax.set_ylim(0, 0.8)
    ax.set_title("Branch Rate by Channel")
    ax.set_ylabel("Multi-site rate")
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.legend(frameon=False)
    style_axes(ax)
    for xpos, merchants in zip(x, channel["merchants"]):
        ax.text(xpos, 0.03, f"n={merchants:,}", ha="center", va="bottom", fontsize=9, color="white")

    ax = axes[1]
    ax.plot(bucket["gdp_bucket_id"], bucket["expected_rate"], marker="o", linewidth=2.4, color=COLORS["blue"], label="expected rate")
    ax.plot(bucket["gdp_bucket_id"], bucket["realized_rate"], marker="o", linewidth=2.4, color=COLORS["green"], label="realized rate")
    ax.set_xticks(bucket["gdp_bucket_id"].tolist())
    ax.set_ylim(0.35, 0.8)
    ax.set_title("Branch Rate by GDP Bucket")
    ax.set_xlabel("GDP bucket")
    ax.set_ylabel("Multi-site rate")
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.legend(frameon=False)
    style_axes(ax, xgrid=True)
    for row in bucket.itertuples(index=False):
        ax.text(row.gdp_bucket_id, row.expected_rate + 0.025, f"n={row.merchants:,}", ha="center", fontsize=9)

    fig.suptitle("Channel and GDP Bucket Shape of the S1 Branch Law", fontsize=16, y=1.02)
    return save(fig, "rng_event_hurdle_channel_gdp_branch_shape.png")


def plot_channel_bucket_heatmap(df: pd.DataFrame) -> Path:
    cb = summarize_rates(df, ["channel", "gdp_bucket_id"])
    expected = cb.pivot(index="channel", columns="gdp_bucket_id", values="expected_rate")
    realized = cb.pivot(index="channel", columns="gdp_bucket_id", values="realized_rate")
    residual = (realized - expected) * 100.0

    fig, axes = plt.subplots(1, 3, figsize=(16, 5.2), gridspec_kw={"width_ratios": [1, 1, 1.05]})
    for ax, data, title, cmap, center in [
        (axes[0], expected, "Expected Multi-site Rate", "YlGnBu", None),
        (axes[1], realized, "Realized Multi-site Rate", "YlGnBu", None),
        (axes[2], residual, "Realized - Expected (pp)", "RdBu_r", 0),
    ]:
        sns.heatmap(
            data,
            ax=ax,
            annot=True,
            fmt=".1f" if title.endswith("(pp)") else ".1%",
            cmap=cmap,
            center=center,
            linewidths=0,
            cbar=True,
        )
        ax.set_title(title)
        ax.set_xlabel("GDP bucket")
        ax.set_ylabel("")

    fig.suptitle("Channel by GDP Bucket Branch Surface", fontsize=16, y=1.02)
    return save(fig, "rng_event_hurdle_channel_bucket_heatmap.png")


def plot_decile_calibration(df: pd.DataFrame) -> Path:
    plot_df = df.sort_values("event_pi").copy()
    plot_df["pi_decile"] = pd.qcut(plot_df["event_pi"], q=10, labels=False, duplicates="drop") + 1
    decile = summarize_rates(plot_df, ["pi_decile"]).sort_values("pi_decile")

    fig, axes = plt.subplots(1, 2, figsize=(15, 6.2), gridspec_kw={"width_ratios": [1.25, 1]})

    ax = axes[0]
    ax.plot(decile["pi_decile"], decile["expected_rate"], marker="o", linewidth=2.4, color=COLORS["blue"], label="expected rate")
    ax.plot(decile["pi_decile"], decile["realized_rate"], marker="o", linewidth=2.4, color=COLORS["green"], label="realized rate")
    ax.set_title("Expected vs Realized Rate by pi Decile")
    ax.set_xlabel("pi decile")
    ax.set_ylabel("Multi-site rate")
    ax.set_xticks(decile["pi_decile"].tolist())
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.legend(frameon=False)
    style_axes(ax, xgrid=True)

    ax = axes[1]
    colors = [COLORS["green"] if abs(v) <= 2 else COLORS["orange"] for v in decile["residual_z"]]
    ax.bar(decile["pi_decile"].astype(str), decile["residual_z"], color=colors, edgecolor="none")
    ax.axhline(0, color=COLORS["dark"], linewidth=1)
    ax.axhline(2, color=COLORS["gray"], linestyle="--", linewidth=1)
    ax.axhline(-2, color=COLORS["gray"], linestyle="--", linewidth=1)
    ax.set_title("Decile Residuals")
    ax.set_xlabel("pi decile")
    ax.set_ylabel("Residual z-score")
    ax.set_ylim(-3, 3)
    style_axes(ax)

    fig.suptitle("Probability Decile Calibration Check", fontsize=16, y=1.02)
    return save(fig, "rng_event_hurdle_decile_calibration.png")


def plot_country_branch_read(df: pd.DataFrame) -> Path:
    country = summarize_rates(df, ["home_country_iso"]).sort_values("merchants", ascending=False).head(15)
    country = country.sort_values("merchants", ascending=True)

    fig, axes = plt.subplots(1, 2, figsize=(16, 7.2), gridspec_kw={"width_ratios": [1.15, 1]})

    ax = axes[0]
    y = np.arange(len(country))
    ax.barh(y, country["merchants"], color=COLORS["light_gray"], edgecolor="none", label="merchant count")
    ax.barh(y, country["realized_multi"], color=COLORS["green"], edgecolor="none", label="realized multi-site")
    ax.set_yticks(y)
    ax.set_yticklabels(country["home_country_iso"])
    ax.set_title("Top Countries: Merchant Count vs Multi-site Count")
    ax.set_xlabel("Merchants")
    ax.legend(frameon=False, loc="lower right")
    style_axes(ax, xgrid=True, ygrid=False)

    ax = axes[1]
    ax.plot(country["expected_rate"], y, marker="o", linewidth=0, color=COLORS["blue"], label="expected rate")
    ax.plot(country["realized_rate"], y, marker="o", linewidth=0, color=COLORS["green"], label="observed rate")
    for row_idx, row in enumerate(country.itertuples(index=False)):
        ax.plot([row.expected_rate, row.realized_rate], [row_idx, row_idx], color=COLORS["gray"], linewidth=1.2, alpha=0.8)
    ax.set_yticks(y)
    ax.set_yticklabels(country["home_country_iso"])
    ax.set_xlim(0.35, 0.8)
    ax.set_title("Top Countries: Expected vs Realized Branch Rate")
    ax.set_xlabel("Multi-site rate")
    ax.xaxis.set_major_formatter(PercentFormatter(1.0))
    ax.legend(frameon=False, loc="lower right")
    style_axes(ax, xgrid=True, ygrid=False)
    for row_idx, row in enumerate(country.itertuples(index=False)):
        if row.home_country_iso == "GH":
            ax.text(0.36, row_idx, "GH: S0 count artifact,\nlower S1 propensity", va="center", ha="left", fontsize=9)

    fig.suptitle("Country Read: S0 Merchant Weight Through the S1 Hurdle Gate", fontsize=16, y=1.02)
    return save(fig, "rng_event_hurdle_country_branch_read.png")


def plot_mcc_caution_view(df: pd.DataFrame) -> Path:
    mcc = summarize_rates(df, ["mcc"])
    top = mcc.sort_values("merchants", ascending=False).head(25).copy()
    top = top.sort_values("residual_z")

    fig, ax = plt.subplots(figsize=(11, 8))
    colors = [COLORS["orange"] if abs(v) > 2 else COLORS["blue"] for v in top["residual_z"]]
    labels = [str(int(v)) for v in top["mcc"]]
    ax.barh(labels, top["residual_z"], color=colors, edgecolor="none")
    ax.axvline(0, color=COLORS["dark"], linewidth=1)
    ax.axvline(2, color=COLORS["gray"], linewidth=1, linestyle="--")
    ax.axvline(-2, color=COLORS["gray"], linewidth=1, linestyle="--")
    ax.set_title("Top MCCs by Merchant Count: Realized vs Expected Residual")
    ax.set_xlabel("Residual z-score")
    ax.set_ylabel("MCC")
    style_axes(ax, xgrid=True, ygrid=False)
    ax.text(
        0.98,
        0.04,
        "MCC cells are small;\nlarge residuals here are leads,\nnot conclusions.",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=10,
        bbox={"facecolor": "white", "edgecolor": "#BBBBBB", "boxstyle": "round,pad=0.35"},
    )
    return save(fig, "rng_event_hurdle_mcc_caution_residuals.png")


def plot_overall_storyboard(df: pd.DataFrame) -> Path:
    expected_multi = float(df["event_pi"].sum())
    realized_multi = int(df["is_multi"].sum())
    channel = summarize_rates(df, ["channel"]).sort_values("expected_rate")
    bucket = summarize_rates(df, ["gdp_bucket_id"]).sort_values("gdp_bucket_id")

    fig, axes = plt.subplots(2, 2, figsize=(15, 10))

    ax = axes[0, 0]
    ax.bar(["expected", "realized"], [expected_multi, realized_multi], color=[COLORS["blue"], COLORS["green"]], edgecolor="none")
    ax.set_title("Multi-site Population")
    ax.set_ylabel("Merchants")
    style_axes(ax)
    for i, val in enumerate([expected_multi, realized_multi]):
        ax.text(i, val + 80, f"{val:,.1f}" if i == 0 else f"{val:,.0f}", ha="center", fontsize=10)

    ax = axes[0, 1]
    ax.hist(df["event_pi"], bins=35, color=COLORS["blue"], edgecolor="none", alpha=0.9)
    ax.set_title("Runtime Probability Surface")
    ax.set_xlabel("event probability")
    ax.set_ylabel("Merchants")
    ax.xaxis.set_major_formatter(PercentFormatter(1.0))
    style_axes(ax)

    ax = axes[1, 0]
    x = np.arange(len(channel))
    ax.bar(x - 0.18, channel["expected_rate"], width=0.36, color=COLORS["blue"], edgecolor="none", label="expected")
    ax.bar(x + 0.18, channel["realized_rate"], width=0.36, color=COLORS["green"], edgecolor="none", label="realized")
    ax.set_xticks(x)
    ax.set_xticklabels([channel_label(value) for value in channel["channel"]], rotation=10)
    ax.set_ylim(0.35, 0.7)
    ax.set_title("Channel Branch Rate")
    ax.set_ylabel("Multi-site rate")
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.legend(frameon=False)
    style_axes(ax)

    ax = axes[1, 1]
    ax.plot(bucket["gdp_bucket_id"], bucket["expected_rate"], marker="o", color=COLORS["blue"], linewidth=2.4, label="expected")
    ax.plot(bucket["gdp_bucket_id"], bucket["realized_rate"], marker="o", color=COLORS["green"], linewidth=2.4, label="realized")
    ax.set_xticks(bucket["gdp_bucket_id"])
    ax.set_title("GDP Bucket Branch Rate")
    ax.set_xlabel("GDP bucket")
    ax.set_ylabel("Multi-site rate")
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.legend(frameon=False)
    style_axes(ax, xgrid=True)

    fig.suptitle("S1 Hurdle Event Stream: Overall EDA Storyboard", fontsize=16, y=1.02)
    return save(fig, "rng_event_hurdle_overall_storyboard.png")


def main() -> None:
    sns.set_theme(style="whitegrid")
    df, trace = load_joined()
    outputs = [
        plot_coverage_lineage(df),
        plot_probability_alignment(df),
        plot_decision_threshold(df),
        plot_uniform_and_accounting(df),
        plot_trace_reconciliation(trace),
        plot_branch_population_summary(df),
        plot_runtime_pi_surface(df),
        plot_channel_and_bucket_shape(df),
        plot_channel_bucket_heatmap(df),
        plot_decile_calibration(df),
        plot_country_branch_read(df),
        plot_mcc_caution_view(df),
        plot_overall_storyboard(df),
    ]
    for path in outputs:
        print(path.relative_to(REPO))


if __name__ == "__main__":
    main()
