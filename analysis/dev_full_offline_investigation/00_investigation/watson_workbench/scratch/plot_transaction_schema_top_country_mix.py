from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


ROOT = Path(r"c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system")
WORKBENCH = ROOT / "analysis/dev_full_offline_investigation/00_investigation/watson_workbench"
EXPORTS = WORKBENCH / "exports"
EXPORTS.mkdir(parents=True, exist_ok=True)

MIX_PATH = EXPORTS / "transaction_schema_top_country_mix_summary.csv"
CHANNEL_PATH = EXPORTS / "transaction_schema_top_country_channel_mix.csv"
POLICY_PATH = EXPORTS / "transaction_schema_top_country_policy_artifact_summary.csv"


POLICY_COLOR = "#4C78A8"
ARTIFACT_COLOR = "#E45756"
NEUTRAL = "#7F7F7F"


def draw_mcc_mix_plot() -> Path:
    df = pd.read_csv(MIX_PATH).sort_values("merchant_count", ascending=False).copy()
    global_top10_share_pct = 4.91

    palette = {
        "policy-shaped": POLICY_COLOR,
        "artifact-amplified": ARTIFACT_COLOR,
    }

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6), gridspec_kw={"width_ratios": [1.2, 1]})

    scatter = ax1.scatter(
        df["top10_mcc_share_pct"],
        df["distinct_mcc"],
        s=df["merchant_count"] * 0.9,
        c=df["shape_classification"].map(palette),
        alpha=0.85,
        edgecolors="white",
        linewidths=0.9,
    )
    ax1.axvline(global_top10_share_pct, color=NEUTRAL, linestyle="--", linewidth=1.5, label="Global top-10 MCC share")
    ax1.set_title("Top-Country MCC Mix Breadth vs Concentration")
    ax1.set_xlabel("Top 10 MCC Share (%)")
    ax1.set_ylabel("Distinct MCCs")
    ax1.grid(axis="both", color="#D9D9D9", linewidth=0.8)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)

    for row in df.itertuples(index=False):
        ax1.text(row.top10_mcc_share_pct + 0.08, row.distinct_mcc + 1.5, row.country_iso, fontsize=9)

    df_jsd = df.sort_values("mcc_jsd_vs_global_bits", ascending=True)
    ax2.barh(
        df_jsd["country_iso"],
        df_jsd["mcc_jsd_vs_global_bits"],
        color=df_jsd["shape_classification"].map(palette),
    )
    ax2.set_title("Distance from Global MCC Mix")
    ax2.set_xlabel("JSD vs Global MCC Mix (bits)")
    ax2.set_ylabel("")
    ax2.grid(axis="x", color="#D9D9D9", linewidth=0.8)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)

    for y, row in enumerate(df_jsd.itertuples(index=False)):
        ax2.text(row.mcc_jsd_vs_global_bits + 0.004, y, f"{row.mcc_jsd_vs_global_bits:.3f}", va="center", fontsize=9)

    handles = [
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=POLICY_COLOR, markersize=9, label="Policy-shaped"),
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=ARTIFACT_COLOR, markersize=9, label="Artifact-amplified"),
        plt.Line2D([0], [0], color=NEUTRAL, linestyle="--", linewidth=1.5, label="Global top-10 MCC share"),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False, bbox_to_anchor=(0.5, -0.02))
    fig.tight_layout(rect=(0, 0.05, 1, 1))

    out_path = EXPORTS / "transaction_schema_top_country_mcc_mix.png"
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return out_path


def draw_channel_mix_plot() -> Path:
    df = pd.read_csv(CHANNEL_PATH).sort_values("card_not_present_pct", ascending=True).copy()
    global_cnp_pct = float(df["global_cnp_pct"].iloc[0])
    us_override_min = 25.0
    us_override_max = 40.0

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.axvspan(us_override_min, us_override_max, color="#FDE0A1", alpha=0.45, zorder=0, label="US override band")
    ax.axvline(global_cnp_pct, color=NEUTRAL, linestyle="--", linewidth=1.5, label="Global CNP share")

    colors = [ARTIFACT_COLOR if iso == "US" else POLICY_COLOR for iso in df["country_iso"]]
    ax.barh(df["country_iso"], df["card_not_present_pct"], color=colors)
    ax.set_title("Top-Country Channel Mix")
    ax.set_xlabel("Card-Not-Present Share (%)")
    ax.set_ylabel("")
    ax.grid(axis="x", color="#D9D9D9", linewidth=0.8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_xlim(0, max(35, df["card_not_present_pct"].max() + 4))

    for y, row in enumerate(df.itertuples(index=False)):
        ax.text(row.card_not_present_pct + 0.25, y, f"{row.card_not_present_pct:.2f}%", va="center", fontsize=9)

    handles = [
        plt.Line2D([0], [0], color=NEUTRAL, linestyle="--", linewidth=1.5, label="Global CNP share"),
        plt.Rectangle((0, 0), 1, 1, color="#FDE0A1", alpha=0.45, label="US override band"),
        plt.Rectangle((0, 0), 1, 1, color=POLICY_COLOR, label="Policy-pinned countries"),
        plt.Rectangle((0, 0), 1, 1, color=ARTIFACT_COLOR, label="US override active"),
    ]
    ax.legend(handles=handles, loc="lower right", frameon=False)

    fig.tight_layout()
    out_path = EXPORTS / "transaction_schema_top_country_channel_mix.png"
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return out_path


def draw_policy_artifact_plot() -> Path:
    df = pd.read_csv(POLICY_PATH).sort_values("builder_vs_standard_delta", ascending=True).copy()
    palette = {
        "policy-shaped": POLICY_COLOR,
        "artifact-amplified": ARTIFACT_COLOR,
    }

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 6), gridspec_kw={"width_ratios": [1, 1.2]})

    zoom_df = df.copy()
    ax1.barh(zoom_df["country_iso"], zoom_df["builder_vs_standard_delta"], color=zoom_df["shape_classification"].map(palette))
    ax1.set_title("Residual Effect: Policy-Shaped Countries")
    ax1.set_xlabel("Builder vs Standard Largest-Remainder Delta")
    ax1.set_ylabel("")
    ax1.set_xlim(-2, 2)
    ax1.grid(axis="x", color="#D9D9D9", linewidth=0.8)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)

    full_df = df.copy()
    ax2.barh(full_df["country_iso"], full_df["builder_vs_standard_delta"], color=full_df["shape_classification"].map(palette))
    ax2.set_title("Residual Effect: Full Scale")
    ax2.set_xlabel("Builder vs Standard Largest-Remainder Delta")
    ax2.set_ylabel("")
    ax2.grid(axis="x", color="#D9D9D9", linewidth=0.8)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)

    for y, row in enumerate(full_df.itertuples(index=False)):
        xpos = row.builder_vs_standard_delta + (4 if row.builder_vs_standard_delta >= 0 else -6)
        ha = "left" if row.builder_vs_standard_delta >= 0 else "right"
        ax2.text(xpos, y, f"{int(row.builder_vs_standard_delta)}", va="center", ha=ha, fontsize=9)

    handles = [
        plt.Rectangle((0, 0), 1, 1, color=POLICY_COLOR, label="Policy-shaped"),
        plt.Rectangle((0, 0), 1, 1, color=ARTIFACT_COLOR, label="Artifact-amplified"),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=2, frameon=False, bbox_to_anchor=(0.5, -0.02))
    fig.tight_layout(rect=(0, 0.05, 1, 1))

    out_path = EXPORTS / "transaction_schema_top_country_policy_artifact_effect.png"
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return out_path


def main() -> None:
    sns.set_theme(style="whitegrid")
    outputs = [
        draw_mcc_mix_plot(),
        draw_channel_mix_plot(),
        draw_policy_artifact_plot(),
    ]
    for path in outputs:
        print(path)


if __name__ == "__main__":
    main()
