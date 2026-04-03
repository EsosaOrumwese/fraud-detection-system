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


def stage_label(value: str) -> str:
    mapping = {
        "opened_only": "Opened\nonly",
        "detection_event_attached": "Detection\nevent attached",
        "customer_dispute": "Customer\ndispute",
        "chargeback_decision": "Chargeback\ndecision",
    }
    return mapping.get(value, value.replace("_", "\n"))


def main() -> None:
    repo = Path(r"c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system")
    root = (
        repo
        / "artefacts"
        / "analytics_slices"
        / "data_scientist"
        / "midlands_partnership_nhs_ft"
        / "04_flow_quality_assurance"
    )
    metrics_dir = root / "metrics"
    figures_dir = root / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    sns.set_theme(style="whitegrid", context="talk")

    fact_pack = json.loads((metrics_dir / "execution_fact_pack.json").read_text())
    kpi_df = pd.DataFrame(fact_pack["kpi_before_after"])
    reporting_df = pd.DataFrame(fact_pack["reporting_ready"])
    anomaly_df = pd.DataFrame(fact_pack["anomaly_checks"])
    headline = fact_pack["headline_facts"]

    fig, axes = plt.subplots(
        1,
        2,
        figsize=(17, 6),
        gridspec_kw={"width_ratios": [1.05, 1]},
    )

    trust_checks = [
        "Multi-case defects",
        "Missing truth rows",
        "Missing bank rows",
        "Duplicate truth rows",
        "Duplicate bank rows",
    ]
    axes[0].set_title("Structural Quality Gate")
    axes[0].set_xlim(0, 1)
    axes[0].set_ylim(0, len(trust_checks) + 0.8)
    axes[0].axis("off")
    for i, check in enumerate(reversed(trust_checks), start=1):
        y_pos = i
        axes[0].scatter(0.08, y_pos, s=500, color="#6aa84f", edgecolor="#38761d", linewidth=1.5, zorder=3)
        axes[0].text(0.08, y_pos, "0", ha="center", va="center", fontsize=11, color="white", fontweight="bold")
        axes[0].text(0.16, y_pos, check, ha="left", va="center", fontsize=12)
    axes[0].text(
        0.02,
        len(trust_checks) + 0.45,
        "All structural gate checks passed on the bounded slice.",
        ha="left",
        va="center",
        fontsize=12,
        fontweight="bold",
        color="#38761d",
    )

    axes[1].axis("off")
    info_lines = [
        ("Case-selected flows", comma(headline["case_selected_flows"])),
        ("Test mismatch rate", pct(45960 / headline["test_case_selected_flows"])),
        ("Truth-negative / bank-positive", comma(headline["truth_negative_bank_positive_case_selected_flows"])),
        ("Truth-positive / bank-negative", comma(headline["truth_positive_bank_negative_case_selected_flows"])),
        ("Event-to-case link rate", pct(headline["event_to_case_link_rate"])),
    ]
    axes[1].text(0.02, 0.94, "Semantic Defect", fontsize=18, fontweight="bold", ha="left", va="top")
    axes[1].text(
        0.02,
        0.84,
        "The path itself is structurally clean. The defect is source misuse:\n"
        "bank view materially diverges from authoritative fraud truth and is unsafe\n"
        "as a stand-in for yield KPIs.",
        fontsize=12,
        ha="left",
        va="top",
    )
    y = 0.64
    for label, value in info_lines:
        axes[1].text(0.04, y, label, fontsize=12, ha="left", va="center")
        axes[1].text(0.96, y, value, fontsize=12, ha="right", va="center", fontweight="bold")
        y -= 0.09
    axes[1].text(
        0.04,
        0.08,
        "Result: the key quality problem is semantic and governance-related, not broken linkage.",
        fontsize=12,
        ha="left",
        va="bottom",
        bbox={"boxstyle": "round,pad=0.5", "facecolor": "#eef5fb", "edgecolor": "#9fc5e8"},
    )

    fig.suptitle("Flow Quality Gate and Defect Boundary", y=1.02, fontsize=18)
    fig.tight_layout()
    fig.savefig(figures_dir / "flow_quality_gate_and_defect_boundary.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    overall_df = kpi_df[kpi_df["kpi_scope"] == "all_case_selected_flows"].copy()
    split_order = ["train", "validation", "test"]
    overall_df["split_role"] = pd.Categorical(overall_df["split_role"], categories=split_order, ordered=True)
    overall_df = overall_df.sort_values("split_role")
    overall_long = overall_df.melt(
        id_vars=["split_role"],
        value_vars=["raw_bank_view_rate", "corrected_truth_rate"],
        var_name="metric",
        value_name="rate",
    )
    overall_long["metric"] = overall_long["metric"].map(
        {
            "raw_bank_view_rate": "Raw bank-view reading",
            "corrected_truth_rate": "Corrected truth reading",
        }
    )

    fig, ax = plt.subplots(figsize=(11, 6))
    sns.barplot(
        data=overall_long,
        x="split_role",
        y="rate",
        hue="metric",
        palette=["#bf2f39", "#1f4e79"],
        ax=ax,
    )
    ax.set_title("Overall Case-Selected Yield Distortion", pad=18)
    ax.set_xlabel("")
    ax.set_ylabel("Yield rate")
    ax.set_ylim(0, 0.62)
    ax.legend(title="", loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=2, frameon=True)
    for i, row in enumerate(overall_df.reset_index(drop=True).itertuples(index=False)):
        ax.text(i, row.raw_bank_view_rate + 0.018, pct(row.raw_bank_view_rate), ha="center", fontsize=10, color="#7f1d1d")
        ax.text(i + 0.4, row.corrected_truth_rate + 0.018, pct(row.corrected_truth_rate), ha="center", fontsize=10, color="#17324d")
        ax.text(i + 0.2, max(row.raw_bank_view_rate, row.corrected_truth_rate) + 0.055, f"Gap {pct(row.absolute_gap)}", ha="center", fontsize=11, fontweight="bold")

    fig.tight_layout(rect=[0, 0.08, 1, 1])
    fig.savefig(figures_dir / "overall_case_selected_yield_distortion.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    test_reporting = reporting_df[reporting_df["split_role"] == "test"].copy()
    stage_order = [
        "opened_only",
        "detection_event_attached",
        "customer_dispute",
        "chargeback_decision",
    ]
    test_reporting["pathway_stage"] = pd.Categorical(test_reporting["pathway_stage"], categories=stage_order, ordered=True)
    test_reporting = test_reporting.sort_values("pathway_stage")
    stage_long = test_reporting.melt(
        id_vars=["pathway_stage", "mismatch_rate"],
        value_vars=["comparison_outcome_rate", "authoritative_outcome_rate"],
        var_name="metric",
        value_name="rate",
    )
    stage_long["metric"] = stage_long["metric"].map(
        {
            "comparison_outcome_rate": "Bank-view outcome rate",
            "authoritative_outcome_rate": "Authoritative truth rate",
        }
    )
    stage_long["stage_label"] = stage_long["pathway_stage"].map(stage_label)
    test_reporting["stage_label"] = test_reporting["pathway_stage"].map(stage_label)

    fig, axes = plt.subplots(1, 2, figsize=(16, 6), gridspec_kw={"width_ratios": [1.4, 1]})
    sns.barplot(
        data=stage_long,
        x="stage_label",
        y="rate",
        hue="metric",
        palette=["#bf2f39", "#1f4e79"],
        ax=axes[0],
    )
    axes[0].set_title("Yield Rate by Pathway Stage")
    axes[0].set_xlabel("Pathway stage")
    axes[0].set_ylabel("Outcome rate")
    axes[0].tick_params(axis="x", rotation=0)
    axes[0].legend(title="", loc="upper left")

    sns.barplot(
        data=test_reporting,
        x="stage_label",
        y="mismatch_rate",
        hue="stage_label",
        palette=["#f4cccc", "#f9cb9c", "#ffe599", "#b6d7a8"],
        dodge=False,
        legend=False,
        ax=axes[1],
    )
    axes[1].set_title("Mismatch Rate by Stage")
    axes[1].set_xlabel("Pathway stage")
    axes[1].set_ylabel("Mismatch rate")
    axes[1].set_ylim(0, 0.8)
    axes[1].tick_params(axis="x", rotation=0)
    for i, row in enumerate(test_reporting.itertuples(index=False)):
        axes[1].text(i, row.mismatch_rate + 0.03, pct(row.mismatch_rate), ha="center", color="#38761d", fontsize=10)

    fig.suptitle("Test Pathway Stage Distortion", y=1.02, fontsize=18)
    fig.tight_layout()
    fig.savefig(figures_dir / "test_pathway_stage_distortion.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    manifest = {
        "generated_figures": [
            "flow_quality_gate_and_defect_boundary.png",
            "overall_case_selected_yield_distortion.png",
            "test_pathway_stage_distortion.png",
        ]
    }
    (figures_dir / "figure_manifest.json").write_text(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
