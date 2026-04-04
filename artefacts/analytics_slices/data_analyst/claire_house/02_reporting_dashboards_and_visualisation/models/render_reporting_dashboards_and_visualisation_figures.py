from __future__ import annotations

import matplotlib
matplotlib.use("Agg")

from pathlib import Path

import duckdb
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


BASE = Path(__file__).resolve().parents[1]
EXTRACTS = BASE / "extracts"
FIGURES = BASE / "figures"

BAND_ORDER = ["under_10", "10_to_25", "25_to_50", "50_plus"]
HIGHLIGHT = "50_plus"


def pct(v: float) -> str:
    return f"{v * 100:.2f}%"


def pp(v: float) -> str:
    sign = "+" if v >= 0 else ""
    return f"{sign}{v * 100:.2f} pp"


def load_data():
    con = duckdb.connect()
    summary = con.execute(
        f"select * from read_parquet('{(EXTRACTS / 'trusted_reporting_summary_v1.parquet').as_posix()}')"
    ).fetchdf()
    detail = con.execute(
        f"select * from read_parquet('{(EXTRACTS / 'trusted_reporting_ad_hoc_detail_v1.parquet').as_posix()}')"
    ).fetchdf()
    detail["amount_band"] = pd.Categorical(detail["amount_band"], categories=BAND_ORDER, ordered=True)
    detail = detail.sort_values("amount_band").reset_index(drop=True)
    return summary, detail


def render_scheduled_profile(summary: pd.DataFrame, detail: pd.DataFrame) -> None:
    overall_case_open = float(summary.iloc[0]["overall_case_open_rate"])
    overall_truth = float(summary.iloc[0]["overall_truth_quality"])
    labels = detail["band_label"].tolist()
    y = np.arange(len(labels))
    colors = ["#d47c6a" if band == HIGHLIGHT else "#8da2b8" for band in detail["amount_band"]]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.2, 6.4), sharey=True)
    fig.suptitle(
        "Scheduled Reporting KPI Profile By Band\nBounded monthly summary built from the trusted Claire House provision lane",
        fontsize=15,
        fontweight="bold",
        y=0.98,
    )

    case_open = detail["case_open_rate"].to_numpy()
    truth = detail["case_truth_rate"].to_numpy()

    for ax, values, overall, title, color_label in [
        (ax1, case_open, overall_case_open, "Case-open rate", "#b05246"),
        (ax2, truth, overall_truth, "Truth quality", "#2f6e4b"),
    ]:
        ax.hlines(y, 0, values, color="#c9d3dc", linewidth=1.3)
        ax.scatter(values, y, s=95, color=colors, zorder=3)
        ax.axvline(overall, linestyle="--", color="#586b7a", linewidth=1.2)
        ax.set_title(title, fontsize=12, fontweight="bold")
        ax.set_xlabel("Rate")
        ax.grid(axis="x", linestyle="--", alpha=0.25)
        ax.set_yticks(y, labels)
        ax.invert_yaxis()
        ax.text(
            overall + 0.0012,
            len(labels) - 0.35,
            f"overall {pct(overall)}",
            fontsize=9,
            color="#586b7a",
        )
        for i, value in enumerate(values):
            txt_color = color_label if detail.iloc[i]["amount_band"] == HIGHLIGHT else "#516271"
            ax.text(value + 0.0012, i, pct(value), va="center", fontsize=9, color=txt_color)

    fig.tight_layout()
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES / "scheduled_kpi_profile_by_band.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def render_ad_hoc_supporting_gaps(detail: pd.DataFrame) -> None:
    labels = detail["band_label"].tolist()
    y = np.arange(len(labels))
    case_gap = detail["case_open_gap_pp"].to_numpy() * 100
    truth_gap = detail["truth_quality_gap_pp"].to_numpy() * 100
    burden_gap = detail["burden_minus_yield_pp"].to_numpy() * 100
    colors = ["#d47c6a" if band == HIGHLIGHT else "#aebccc" for band in detail["amount_band"]]

    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(13.0, 6.5), sharey=True, gridspec_kw={"width_ratios": [1.5, 1]}
    )
    fig.suptitle(
        "Ad Hoc Supporting Gap Profile By Band\nThe supporting cut answers which band deserves the next look after the scheduled summary",
        fontsize=15,
        fontweight="bold",
        y=0.98,
    )

    h = 0.33
    ax1.barh(y + h / 2, case_gap, height=h, color="#4d8ac7", label="Case-open gap vs overall")
    ax1.barh(y - h / 2, truth_gap, height=h, color="#6aa57b", label="Truth-quality gap vs overall")
    ax1.axvline(0, color="#586b7a", linewidth=1.2)
    ax1.set_yticks(y, labels)
    ax1.set_xlabel("Gap to overall (percentage points)")
    ax1.set_title("Rate gaps", fontsize=12, fontweight="bold")
    ax1.grid(axis="x", linestyle="--", alpha=0.25)
    ax1.invert_yaxis()
    ax1.legend(loc="lower right", frameon=False, fontsize=9)
    for i in range(len(labels)):
        ax1.text(case_gap[i] + (0.12 if case_gap[i] >= 0 else -0.75), i + h / 2, pp(case_gap[i] / 100), va="center", fontsize=9, color="#255987")
        ax1.text(truth_gap[i] + (0.12 if truth_gap[i] >= 0 else -0.95), i - h / 2, pp(truth_gap[i] / 100), va="center", fontsize=9, color="#2f6e4b")

    ax2.barh(y, burden_gap, color=colors, height=0.48)
    ax2.axvline(0, color="#586b7a", linewidth=1.2)
    ax2.set_yticks(y, labels)
    ax2.set_xlabel("Burden minus yield (percentage points)")
    ax2.set_title("Priority gap", fontsize=12, fontweight="bold")
    ax2.grid(axis="x", linestyle="--", alpha=0.25)
    ax2.invert_yaxis()
    for i, value in enumerate(burden_gap):
        color = "#8a3d33" if detail.iloc[i]["amount_band"] == HIGHLIGHT else "#516271"
        ax2.text(value + (0.12 if value >= 0 else -0.75), i, pp(value / 100), va="center", fontsize=9, color=color)

    fig.tight_layout()
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES / "ad_hoc_supporting_gap_profile.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    summary, detail = load_data()
    render_scheduled_profile(summary, detail)
    render_ad_hoc_supporting_gaps(detail)


if __name__ == "__main__":
    main()
