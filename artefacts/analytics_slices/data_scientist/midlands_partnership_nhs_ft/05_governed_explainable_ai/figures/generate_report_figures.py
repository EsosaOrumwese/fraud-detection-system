from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def comma(value: float) -> str:
    return f"{int(round(value)):,}"


def main() -> None:
    repo = Path(r"c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system")
    root = (
        repo
        / "artefacts"
        / "analytics_slices"
        / "data_scientist"
        / "midlands_partnership_nhs_ft"
        / "05_governed_explainable_ai"
    )
    metrics_dir = root / "metrics"
    figures_dir = root / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    sns.set_theme(style="whitegrid", context="talk")

    fact_pack = json.loads((metrics_dir / "execution_fact_pack.json").read_text(encoding="utf-8"))
    gate = fact_pack["governance_gate"]
    compare_df = pd.DataFrame(fact_pack["comparison_metrics"])
    val_bands = pd.DataFrame(fact_pack["selected_validation_risk_bands"])
    test_bands = pd.DataFrame(fact_pack["selected_test_risk_bands"])
    top_coeffs = pd.DataFrame(fact_pack["top_coefficients"])

    split_order = ["validation", "test"]
    band_order = ["High", "Medium", "Low"]

    fig, axes = plt.subplots(1, 2, figsize=(17, 6.4), gridspec_kw={"width_ratios": [1.0, 1.05]})

    gate_checks = [
        ("Flow rows", comma(gate["flow_rows"])),
        ("Distinct flow_id", comma(gate["distinct_flow_id"])),
        ("Fraud-truth rate", pct(gate["fraud_truth_rate"])),
        ("Bank-view rate", pct(gate["bank_view_rate"])),
        ("Case-open rate", pct(gate["case_open_rate"])),
        ("Truth-bank mismatch", pct(gate["truth_bank_mismatch_rate"])),
    ]
    axes[0].axis("off")
    axes[0].text(0.02, 0.95, "Governance Gate", fontsize=20, fontweight="bold", ha="left", va="top")
    axes[0].text(
        0.02,
        0.82,
        "The bounded modelling context is usable: target authority is pinned,\n"
        "core feature fields are complete, and bank-view remains comparison-only.",
        fontsize=12,
        ha="left",
        va="top",
    )
    y = 0.60
    for label, value in gate_checks:
        axes[0].text(0.04, y, label, fontsize=12, ha="left", va="center")
        axes[0].text(0.96, y, value, fontsize=12, ha="right", va="center", fontweight="bold")
        y -= 0.085
    axes[0].text(
        0.04,
        0.025,
        "Result: the governed use case is valid, but source meaning still matters because\n"
        "bank-view differs materially from authoritative fraud truth.",
        fontsize=12,
        ha="left",
        va="bottom",
        bbox={"boxstyle": "round,pad=0.5", "facecolor": "#eef5fb", "edgecolor": "#9fc5e8"},
    )

    completeness_fields = [
        "amount",
        "arrival_seq",
        "merchant_id",
        "party_id",
        "account_id",
        "instrument_id",
        "device_id",
        "ip_id",
    ]
    axes[1].set_title("First-Pass Feature Completeness")
    axes[1].set_xlim(0, 1)
    axes[1].set_ylim(0, len(completeness_fields) + 1.2)
    axes[1].axis("off")
    for i, field in enumerate(reversed(completeness_fields), start=1):
        y_pos = i
        axes[1].scatter(0.08, y_pos, s=380, color="#6aa84f", edgecolor="#38761d", linewidth=1.4, zorder=3)
        axes[1].text(0.08, y_pos, "0%", ha="center", va="center", fontsize=9, color="white", fontweight="bold")
        axes[1].text(0.16, y_pos, field, ha="left", va="center", fontsize=12)
    axes[1].text(
        0.02,
        len(completeness_fields) + 0.55,
        "All core first-pass modelling fields were complete in the bounded slice.",
        ha="left",
        va="center",
        fontsize=12,
        fontweight="bold",
        color="#38761d",
    )

    fig.suptitle("Governed Model Context", y=1.02, fontsize=18)
    fig.tight_layout()
    fig.savefig(figures_dir / "governed_model_context.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    auc_df = compare_df.copy()
    auc_df["split_role"] = pd.Categorical(auc_df["split_role"], categories=split_order, ordered=True)
    auc_df["model_label"] = auc_df["model_name"].map(
        {
            "baseline_logistic_structural": "Baseline",
            "challenger_logistic_encoded_history": "Challenger",
        }
    )
    auc_df = auc_df.sort_values(["split_role", "model_label"])
    sns.barplot(
        data=auc_df,
        x="split_role",
        y="roc_auc",
        hue="model_label",
        palette=["#9fc5e8", "#1f4e79"],
        ax=axes[0],
    )
    axes[0].set_title("ROC AUC Comparison")
    axes[0].set_xlabel("Split")
    axes[0].set_ylabel("ROC AUC")
    axes[0].legend(title="", loc="upper left", frameon=True, fontsize=11)
    for container in axes[0].containers:
        axes[0].bar_label(container, fmt="%.3f", padding=3, fontsize=10)
    axes[0].text(
        0.02,
        0.02,
        "Average precision moved from roughly 0.028 in the baseline\n"
        "to roughly 0.046 in the selected challenger.",
        transform=axes[0].transAxes,
        fontsize=10,
        va="bottom",
        ha="left",
        bbox={"boxstyle": "round,pad=0.4", "facecolor": "#eef5fb", "edgecolor": "#9fc5e8"},
    )

    high_band_rates = (
        pd.concat([val_bands, test_bands], ignore_index=True)
        .loc[lambda d: d["risk_band"] == "High", ["model_name", "split_role", "positive_rate", "lift_vs_baseline"]]
        .rename(columns={"positive_rate": "high_band_truth_rate"})
    )
    band_compare = compare_df.merge(high_band_rates, on=["model_name", "split_role"], how="left")
    band_compare["split_role"] = pd.Categorical(band_compare["split_role"], categories=split_order, ordered=True)
    band_compare["model_label"] = band_compare["model_name"].map(
        {
            "baseline_logistic_structural": "Baseline",
            "challenger_logistic_encoded_history": "Challenger",
        }
    )
    sns.barplot(
        data=band_compare.sort_values(["split_role", "model_label"]),
        x="split_role",
        y="high_band_truth_rate",
        hue="model_label",
        palette=["#9fc5e8", "#1f4e79"],
        ax=axes[1],
    )
    axes[1].set_title("High-Band Truth Rate Comparison")
    axes[1].set_xlabel("Split")
    axes[1].set_ylabel("Truth rate")
    axes[1].set_ylim(0, 0.08)
    axes[1].legend(title="", loc="upper left", frameon=True, fontsize=11)
    for container in axes[1].containers:
        axes[1].bar_label(container, labels=[pct(v) for v in container.datavalues], padding=3, fontsize=10)
    axes[1].text(
        0.02,
        0.02,
        "Selected decision signal: the challenger materially improves\n"
        "high-band truth concentration while staying reviewable.",
        transform=axes[1].transAxes,
        fontsize=10,
        va="bottom",
        ha="left",
        bbox={"boxstyle": "round,pad=0.4", "facecolor": "#eef5fb", "edgecolor": "#9fc5e8"},
    )
    axes[1].text(
        0.98,
        0.96,
        "High-band lift:\n2.31x test",
        transform=axes[1].transAxes,
        fontsize=10,
        va="top",
        ha="right",
        bbox={"boxstyle": "round,pad=0.35", "facecolor": "#f4f4f4", "edgecolor": "#cccccc"},
    )

    fig.suptitle("Model Choice and Selected Value Surface", y=1.02, fontsize=18)
    fig.tight_layout()
    fig.savefig(figures_dir / "model_choice_and_value_surface.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(16, 6), gridspec_kw={"width_ratios": [1.2, 1]})

    selected_bands = pd.concat([val_bands, test_bands], ignore_index=True)
    selected_bands["split_role"] = pd.Categorical(selected_bands["split_role"], categories=split_order, ordered=True)
    selected_bands["risk_band"] = pd.Categorical(selected_bands["risk_band"], categories=band_order, ordered=True)
    selected_bands = selected_bands.sort_values(["split_role", "risk_band"])
    sns.barplot(
        data=selected_bands,
        x="risk_band",
        y="positive_rate",
        hue="split_role",
        palette=["#6fa8dc", "#3d85c6"],
        ax=axes[0],
    )
    axes[0].set_title("Selected Risk-Band Truth Rate")
    axes[0].set_xlabel("Risk band")
    axes[0].set_ylabel("Truth rate")
    axes[0].legend(title="", loc="upper right")
    for container in axes[0].containers:
        axes[0].bar_label(container, labels=[pct(v) for v in container.datavalues], padding=3, fontsize=9)

    coeffs = top_coeffs.copy().sort_values("abs_coefficient", ascending=True)
    sns.barplot(
        data=coeffs,
        x="abs_coefficient",
        y="feature",
        hue="feature",
        palette=["#cfe2f3"] * len(coeffs),
        dodge=False,
        legend=False,
        ax=axes[1],
    )
    axes[1].set_title("Top Selected-Model Drivers")
    axes[1].set_xlabel("Absolute coefficient")
    axes[1].set_ylabel("")

    fig.suptitle("Threshold and Explanation Surface", y=1.02, fontsize=18)
    fig.tight_layout()
    fig.savefig(figures_dir / "threshold_and_explanation_surface.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    manifest = {
        "generated_figures": [
            "governed_model_context.png",
            "model_choice_and_value_surface.png",
            "threshold_and_explanation_surface.png",
        ]
    }
    (figures_dir / "figure_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
