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
        / "02_case_analytics_product"
    )
    metrics_dir = root / "metrics"
    figures_dir = root / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    sns.set_theme(style="whitegrid", context="talk")

    fact_pack = json.loads((metrics_dir / "execution_fact_pack.json").read_text())

    grain = pd.DataFrame(fact_pack["case_grain_profile"])
    fit = pd.DataFrame(fact_pack["fit_for_use"])
    link_shape = pd.DataFrame(fact_pack["case_link_shape"])
    split_summary = pd.DataFrame(fact_pack["product_split_summary"])
    pathway = pd.DataFrame(fact_pack["pathway_summary"])

    grain_map = dict(zip(grain["metric_name"], grain["metric_value"]))
    link_map = dict(zip(link_shape["metric_name"], link_shape["metric_value"]))
    fit_map = dict(zip(fit["metric_name"], fit["metric_value"]))

    fig, axes = plt.subplots(
        1,
        2,
        figsize=(16, 6),
        gridspec_kw={"width_ratios": [1.15, 1]},
    )

    coverage_df = pd.DataFrame(
        {
            "metric": [
                "Distinct cases",
                "Distinct linked flows",
                "Anchor coverage",
                "Truth coverage",
                "Bank-view coverage",
            ],
            "value": [
                grain_map["distinct_case_id_count"],
                grain_map["distinct_flow_id_in_case_timeline"],
                grain_map["cases_with_all_linked_flows_in_anchor"],
                grain_map["cases_with_all_linked_flows_in_truth"],
                grain_map["cases_with_all_linked_flows_in_bank_view"],
            ],
        }
    )
    sns.barplot(
        data=coverage_df,
        y="metric",
        x="value",
        hue="metric",
        palette=["#1f4e79", "#5b9bd5", "#6aa84f", "#93c47d", "#b6d7a8"],
        dodge=False,
        legend=False,
        ax=axes[0],
    )
    axes[0].set_title("Case Grain Coverage and Link Completeness")
    axes[0].set_xlabel("Case count")
    axes[0].set_ylabel("")
    max_value = coverage_df["value"].max()
    axes[0].set_xlim(0, max_value * 1.18)
    for i, row in coverage_df.iterrows():
        axes[0].text(row["value"] + max_value * 0.01, i, comma(row["value"]), va="center", fontsize=11)

    axes[1].axis("off")
    integrity_lines = [
        ("Avg chronology rows per case", f"{grain_map['avg_chronology_rows_per_case']:.2f}"),
        ("Max chronology rows per case", comma(grain_map["max_chronology_rows_per_case"])),
        ("Cases with multiple flows", comma(grain_map["cases_with_multiple_flows"])),
        ("Flows with multiple cases", comma(link_map["flows_with_multiple_cases"])),
        ("Duplicate case rows in base", comma(fit_map["analytics_base_duplicate_case_rows"])),
        ("Null case IDs in base", comma(fit_map["analytics_base_null_case_id_rows"])),
        ("Null flow IDs in base", comma(fit_map["analytics_base_null_flow_id_rows"])),
        ("Negative lifecycle rows", comma(fit_map["analytics_base_negative_lifecycle_rows"])),
    ]
    axes[1].text(
        0.02,
        0.94,
        "Fit-for-Use Gate",
        fontsize=18,
        fontweight="bold",
        ha="left",
        va="top",
    )
    axes[1].text(
        0.02,
        0.84,
        "The bounded slice passed the grain and integrity gate cleanly.",
        fontsize=12,
        ha="left",
        va="top",
    )
    y = 0.72
    for label, value in integrity_lines:
        axes[1].text(0.04, y, label, fontsize=12, ha="left", va="center")
        axes[1].text(0.96, y, value, fontsize=12, ha="right", va="center", fontweight="bold")
        y -= 0.08
    axes[1].text(
        0.04,
        0.08,
        "Result: `case_id` was stable enough to carry one analytical base and two downstream outputs.",
        fontsize=12,
        ha="left",
        va="bottom",
        bbox={"boxstyle": "round,pad=0.5", "facecolor": "#eef5fb", "edgecolor": "#9fc5e8"},
    )

    fig.suptitle("Case-Product Grain Viability and Trust Gate", y=1.02, fontsize=18)
    fig.tight_layout()
    fig.savefig(figures_dir / "case_grain_fit_gate.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    output_df = pd.DataFrame(
        {
            "output": [
                "Analytical base",
                "Model-ready",
                "Reporting-ready",
            ],
            "rows": [
                fit_map["analytics_base_rows"],
                fit_map["model_ready_rows"],
                fit_map["reporting_ready_rows"],
            ],
        }
    )
    split_long = split_summary.melt(
        id_vars=["split_role", "case_rows"],
        value_vars=["fraud_truth_rate", "bank_positive_rate"],
        var_name="metric",
        value_name="rate",
    )
    split_long["metric"] = split_long["metric"].map(
        {
            "fraud_truth_rate": "Fraud-truth rate",
            "bank_positive_rate": "Bank-positive rate",
        }
    )
    split_order = ["train", "validation", "test"]
    split_long["split_role"] = pd.Categorical(split_long["split_role"], categories=split_order, ordered=True)
    split_summary["split_role"] = pd.Categorical(split_summary["split_role"], categories=split_order, ordered=True)

    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    sns.barplot(
        data=output_df,
        x="output",
        y="rows",
        hue="output",
        palette=["#1f4e79", "#6aa84f", "#e6a22e"],
        dodge=False,
        legend=False,
        ax=axes[0],
    )
    axes[0].set_title("One Base Reused Across Two Outputs")
    axes[0].set_xlabel("")
    axes[0].set_ylabel("Rows")
    max_rows = output_df["rows"].max()
    axes[0].set_ylim(0, max_rows * 1.16)
    for i, row in output_df.iterrows():
        axes[0].text(i, row["rows"] + max_rows * 0.015, comma(row["rows"]), ha="center", fontsize=11)

    sns.lineplot(
        data=split_long.sort_values("split_role"),
        x="split_role",
        y="rate",
        hue="metric",
        style="metric",
        markers=True,
        dashes=False,
        palette=["#bf2f39", "#1f4e79"],
        linewidth=2.5,
        markersize=10,
        ax=axes[1],
    )
    axes[1].set_title("Stable Outcome Rates Across Product Splits")
    axes[1].set_xlabel("Split")
    axes[1].set_ylabel("Rate")
    axes[1].legend(title="")
    for _, row in split_summary.sort_values("split_role").iterrows():
        axes[1].text(
            row["split_role"],
            row["fraud_truth_rate"] + 0.015,
            f"{comma(row['case_rows'])} cases",
            ha="center",
            fontsize=10,
            color="#555555",
        )

    fig.suptitle("Reusable Product Structure and Time-Split Stability", y=1.02, fontsize=18)
    fig.tight_layout()
    fig.savefig(figures_dir / "case_product_reuse_and_split_stability.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    test_pathway = pathway[pathway["split_role"] == "test"].copy()
    stage_order = [
        "opened_only",
        "detection_event_attached",
        "customer_dispute",
        "chargeback_decision",
    ]
    test_pathway["pathway_stage"] = pd.Categorical(test_pathway["pathway_stage"], categories=stage_order, ordered=True)
    test_pathway = test_pathway.sort_values("pathway_stage")
    pathway_long = test_pathway.melt(
        id_vars=["pathway_stage", "case_rows"],
        value_vars=["fraud_truth_rate", "bank_positive_rate"],
        var_name="metric",
        value_name="rate",
    )
    pathway_long["metric"] = pathway_long["metric"].map(
        {
            "fraud_truth_rate": "Fraud-truth rate",
            "bank_positive_rate": "Bank-positive rate",
        }
    )

    fig, axes = plt.subplots(1, 2, figsize=(18, 6))
    sns.barplot(
        data=pathway_long,
        x="pathway_stage",
        y="rate",
        hue="metric",
        palette=["#bf2f39", "#1f4e79"],
        ax=axes[0],
    )
    axes[0].set_title("Test Pathway-Stage Separation")
    axes[0].set_xlabel("Pathway stage")
    axes[0].set_ylabel("Rate")
    axes[0].legend(title="")
    axes[0].tick_params(axis="x", rotation=20)

    sns.barplot(
        data=test_pathway,
        x="pathway_stage",
        y="case_rows",
        hue="pathway_stage",
        palette=["#9fc5e8", "#6fa8dc", "#3d85c6", "#1c4587"],
        dodge=False,
        legend=False,
        ax=axes[1],
    )
    axes[1].set_title("Test Pathway Volume")
    axes[1].set_xlabel("Pathway stage")
    axes[1].set_ylabel("Case rows")
    axes[1].tick_params(axis="x", rotation=20)
    max_case_rows = test_pathway["case_rows"].max()
    axes[1].set_ylim(0, max_case_rows * 1.16)
    for i, row in enumerate(test_pathway.itertuples(index=False)):
        axes[1].text(i, row.case_rows + max_case_rows * 0.015, comma(row.case_rows), ha="center", fontsize=10)

    fig.suptitle("Reporting-Ready Consumer Surface on the Test Window", y=1.02, fontsize=18)
    fig.tight_layout()
    fig.savefig(figures_dir / "case_pathway_stage_consumer_surface.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    manifest = {
        "generated_figures": [
            "case_grain_fit_gate.png",
            "case_product_reuse_and_split_stability.png",
            "case_pathway_stage_consumer_surface.png",
        ]
    }
    (figures_dir / "figure_manifest.json").write_text(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
