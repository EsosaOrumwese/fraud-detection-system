from __future__ import annotations

import matplotlib
matplotlib.use("Agg")

from pathlib import Path

import duckdb
import matplotlib.pyplot as plt
import numpy as np


BASE = Path(__file__).resolve().parents[1]
EXTRACTS = BASE / "extracts"
FIGURES = BASE / "figures"
REPO_ROOT = Path(__file__).resolve().parents[6]
INHEALTH_EXTRACTS = (
    REPO_ROOT
    / "artefacts"
    / "analytics_slices"
    / "data_analyst"
    / "inhealth_group"
    / "02_patient_level_dataset_stewardship"
    / "extracts"
)

BAND_ORDER = ["under_10", "10_to_25", "25_to_50", "50_plus"]
BAND_LABELS = {
    "under_10": "<10",
    "10_to_25": "10-25",
    "25_to_50": "25-50",
    "50_plus": "50+",
}


def fmt_m(value: float) -> str:
    return f"{value / 1_000_000:.2f}M"


def fmt_pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def load_frames():
    con = duckdb.connect()
    protected_summary = con.execute(
        f"select * from read_parquet('{(EXTRACTS / 'trusted_data_provision_summary_v1.parquet').as_posix()}')"
    ).fetchdf()
    inherited_source = con.execute(
        f"select * from read_parquet('{(INHEALTH_EXTRACTS / 'patient_level_source_profile_v1.parquet').as_posix()}')"
    ).fetchdf()
    return protected_summary, inherited_source


def render_provision_volume_control(inherited_source):
    df = inherited_source[inherited_source["amount_band"].isin(BAND_ORDER)].copy()
    df["amount_band"] = pd.Categorical(df["amount_band"], categories=BAND_ORDER, ordered=True)
    df = df.sort_values("amount_band")

    labels = [BAND_LABELS[b] for b in df["amount_band"]]
    y = np.arange(len(labels))
    h = 0.32

    raw_m = df["raw_case_event_rows_on_linked_flows"].to_numpy() / 1_000_000
    maintained_m = df["case_opened_rows"].to_numpy() / 1_000_000
    avg_rows = df["avg_case_event_rows_when_linked"].to_numpy()

    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(13.2, 6.4), gridspec_kw={"width_ratios": [1.45, 1]}
    )
    fig.suptitle(
        "Provision Control At The Detailed Grain\nRaw event rows must be controlled before the lane is safe for downstream provision",
        fontsize=15,
        fontweight="bold",
        y=0.98,
    )

    ax1.barh(y + h / 2, raw_m, height=h, color="#d47c6a", label="Raw case-event rows on linked flows")
    ax1.barh(y - h / 2, maintained_m, height=h, color="#4d8ac7", label="Controlled maintained rows")
    ax1.set_yticks(y, labels)
    ax1.set_xlabel("Rows (millions)")
    ax1.set_title("Linked-flow subset by amount band", fontsize=12, fontweight="bold")
    ax1.grid(axis="x", linestyle="--", alpha=0.25)
    ax1.invert_yaxis()
    ax1.legend(loc="lower right", frameon=False, fontsize=9)

    for i, (raw, maintained) in enumerate(zip(raw_m, maintained_m)):
        ax1.text(raw + 0.06, i + h / 2, f"{raw:.2f}M", va="center", fontsize=9, color="#7a3d33")
        ax1.text(
            maintained + 0.06,
            i - h / 2,
            f"{maintained:.2f}M",
            va="center",
            fontsize=9,
            color="#244f7a",
        )

    ax2.plot(avg_rows, y, color="#335f83", linewidth=1.5, alpha=0.8)
    ax2.scatter(avg_rows, y, s=70, color="#335f83")
    ax2.axvline(avg_rows.mean(), linestyle="--", color="#7f8c99", linewidth=1.2)
    ax2.set_yticks(y, labels)
    ax2.set_xlabel("Average raw case-event rows per linked flow")
    ax2.set_title("Inflation before control", fontsize=12, fontweight="bold")
    ax2.grid(axis="x", linestyle="--", alpha=0.25)
    ax2.invert_yaxis()
    ax2.text(
        avg_rows.mean() + 0.015,
        len(labels) - 0.35,
        f"overall avg {avg_rows.mean():.2f}",
        fontsize=9,
        color="#63717d",
    )
    for i, value in enumerate(avg_rows):
        ax2.text(value + 0.015, i, f"{value:.2f}", va="center", fontsize=9, color="#244f7a")

    fig.tight_layout()
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES / "provision_volume_control_by_band.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def render_protected_release_profile(protected_summary):
    df = protected_summary[protected_summary["amount_band"].isin(BAND_ORDER)].copy()
    overall = protected_summary[protected_summary["amount_band"] == "__overall__"].iloc[0]
    df["amount_band"] = pd.Categorical(df["amount_band"], categories=BAND_ORDER, ordered=True)
    df = df.sort_values("amount_band")

    labels = [BAND_LABELS[b] for b in df["amount_band"]]
    y = np.arange(len(labels))

    case_open = df["case_open_rate"].to_numpy()
    truth_quality = df["case_truth_rate"].to_numpy()

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.0, 6.2), sharey=True)
    fig.suptitle(
        "Protected Downstream Release Profile\nThe controlled provision lane releases a stable analytical reading by band",
        fontsize=15,
        fontweight="bold",
        y=0.98,
    )

    for ax, values, overall_value, color, title in [
        (ax1, case_open, overall["case_open_rate"], "#3f78b5", "Case-open rate"),
        (ax2, truth_quality, overall["case_truth_rate"], "#2d8a57", "Truth quality"),
    ]:
        ax.hlines(y, 0, values, color=color, linewidth=2.2)
        ax.scatter(values, y, color=color, s=75, zorder=3)
        ax.axvline(overall_value, linestyle="--", color="#7f8c99", linewidth=1.2)
        ax.set_title(title, fontsize=12, fontweight="bold")
        ax.set_xlabel("Rate")
        ax.grid(axis="x", linestyle="--", alpha=0.25)
        ax.set_yticks(y, labels)
        ax.invert_yaxis()
        ax.text(
            overall_value + 0.0015,
            len(labels) - 0.35,
            f"overall {fmt_pct(overall_value)}",
            fontsize=9,
            color="#63717d",
        )
        for i, value in enumerate(values):
            ax.text(value + 0.0015, i, fmt_pct(value), va="center", fontsize=9, color=color)

    fig.tight_layout()
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES / "protected_release_profile_by_band.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    import pandas as pd

    globals()["pd"] = pd
    protected_summary, inherited_source = load_frames()
    render_provision_volume_control(inherited_source)
    render_protected_release_profile(protected_summary)


if __name__ == "__main__":
    main()
