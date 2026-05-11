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
        / "03_population_pathway_analysis"
    )
    metrics_dir = root / "metrics"
    figures_dir = root / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    sns.set_theme(style="whitegrid", context="talk")

    fact_pack = json.loads((metrics_dir / "execution_fact_pack.json").read_text())
    source_profile = pd.DataFrame(fact_pack["source_profile"])
    event_case_alignment = pd.DataFrame(fact_pack["event_case_alignment"])
    kpi_summary = pd.DataFrame(fact_pack["kpi_summary"])
    pathway_summary = pd.DataFrame(fact_pack["pathway_summary"])
    cohort_summary = pd.DataFrame(fact_pack["cohort_summary"])

    source_map = dict(zip(source_profile["metric_name"], source_profile["metric_value"]))
    align_map = dict(zip(event_case_alignment["metric_name"], event_case_alignment["metric_value"]))

    fig, axes = plt.subplots(
        1,
        2,
        figsize=(17, 6),
        gridspec_kw={"width_ratios": [1.05, 1]},
    )

    population_df = pd.DataFrame(
        {
            "surface": [
                "Entry population flows",
                "Case-linked flows",
                "Case-linked cases",
            ],
            "value": [
                source_map["event_distinct_flows"],
                source_map["case_distinct_flows"],
                source_map["case_distinct_cases"],
            ],
        }
    )
    sns.barplot(
        data=population_df,
        x="surface",
        y="value",
        hue="surface",
        palette=["#1f4e79", "#6aa84f", "#93c47d"],
        dodge=False,
        legend=False,
        ax=axes[0],
    )
    axes[0].set_title("Bounded Population and Suspicious-Pathway Subset")
    axes[0].set_xlabel("")
    axes[0].set_ylabel("Flows / cases")
    axes[0].tick_params(axis="x", rotation=12)
    max_value = population_df["value"].max()
    axes[0].set_ylim(0, max_value * 1.18)
    for i, row in population_df.iterrows():
        axes[0].text(i, row["value"] + max_value * 0.015, comma(row["value"]), ha="center", fontsize=11)

    axes[1].axis("off")
    trust_lines = [
        ("Exact event-to-case-open matches", comma(align_map["exact_event_case_open_ts_match_flows"])),
        ("Avg seconds event to case open", f"{align_map['avg_seconds_event_to_case_open']:.0f}"),
        ("Flows with multiple cases", comma(align_map["flows_with_multiple_cases"])),
        ("Case-linked share of entry population", pct(source_map["case_distinct_flows"] / source_map["event_distinct_flows"])),
        ("AUTH_REQUEST rows", comma(source_map["event_auth_request_rows"])),
        ("AUTH_RESPONSE rows", comma(source_map["event_auth_response_rows"])),
    ]
    axes[1].text(0.02, 0.94, "Trust Gate", fontsize=18, fontweight="bold", ha="left", va="top")
    axes[1].text(
        0.02,
        0.84,
        "The raw event stream was treated as the bounded entry population, then validated\nagainst `CASE_OPENED` as the trusted suspicious-pathway analogue.",
        fontsize=12,
        ha="left",
        va="top",
    )
    y = 0.68
    for label, value in trust_lines:
        axes[1].text(0.04, y, label, fontsize=12, ha="left", va="center")
        axes[1].text(0.96, y, value, fontsize=12, ha="right", va="center", fontweight="bold")
        y -= 0.09
    axes[1].text(
        0.04,
        0.08,
        "Result: the bounded linked path was defensible enough to support pathway and cohort analysis.",
        fontsize=12,
        ha="left",
        va="bottom",
        bbox={"boxstyle": "round,pad=0.5", "facecolor": "#eef5fb", "edgecolor": "#9fc5e8"},
    )

    fig.suptitle("Population Linkage and Trust Boundary", y=1.02, fontsize=18)
    fig.tight_layout()
    fig.savefig(figures_dir / "population_linkage_and_trust_gate.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    test_pathway = pathway_summary[pathway_summary["split_role"] == "test"].copy()
    stage_order = [
        "no_case",
        "opened_only",
        "detection_event_attached",
        "customer_dispute",
        "chargeback_decision",
    ]
    test_pathway["pathway_stage"] = pd.Categorical(test_pathway["pathway_stage"], categories=stage_order, ordered=True)
    test_pathway = test_pathway.sort_values("pathway_stage")
    pathway_long = test_pathway.melt(
        id_vars=["pathway_stage", "flow_rows"],
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
    axes[0].set_title("Test Pathway Outcome Surface")
    axes[0].set_xlabel("Pathway stage")
    axes[0].set_ylabel("Rate")
    axes[0].tick_params(axis="x", rotation=15)
    axes[0].legend(title="")

    sns.barplot(
        data=test_pathway,
        x="pathway_stage",
        y="flow_rows",
        hue="pathway_stage",
        palette=["#c9daf8", "#9fc5e8", "#6fa8dc", "#3d85c6", "#1c4587"],
        dodge=False,
        legend=False,
        ax=axes[1],
    )
    axes[1].set_title("Test Pathway Volume")
    axes[1].set_xlabel("Pathway stage")
    axes[1].set_ylabel("Flows")
    axes[1].tick_params(axis="x", rotation=15)
    max_rows = test_pathway["flow_rows"].max()
    axes[1].set_ylim(0, max_rows * 1.16)
    for i, row in enumerate(test_pathway.itertuples(index=False)):
        axes[1].text(i, row.flow_rows + max_rows * 0.015, comma(row.flow_rows), ha="center", fontsize=10)

    fig.suptitle("Pathway Stage Outcomes and Volume on the Test Window", y=1.02, fontsize=18)
    fig.tight_layout()
    fig.savefig(figures_dir / "pathway_stage_test_surface.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    test_kpi = kpi_summary[kpi_summary["split_role"] == "test"].iloc[0]
    test_cohort = cohort_summary[cohort_summary["split_role"] == "test"].copy()
    cohort_order = [
        "fast_converting_high_yield",
        "slow_converting_high_yield",
        "high_burden_low_yield",
        "low_burden_low_yield",
    ]
    test_cohort["cohort_label"] = pd.Categorical(test_cohort["cohort_label"], categories=cohort_order, ordered=True)
    test_cohort = test_cohort.sort_values("cohort_label")
    test_cohort["case_selected_share"] = test_cohort["flow_rows"] / float(test_kpi["case_selected_flows"])

    fig, axes = plt.subplots(1, 2, figsize=(18, 6))
    sns.barplot(
        data=test_cohort,
        x="cohort_label",
        y="case_selected_share",
        hue="cohort_label",
        palette=["#6aa84f", "#38761d", "#e69138", "#f6b26b"],
        dodge=False,
        legend=False,
        ax=axes[0],
    )
    axes[0].set_title("Share of Case-Selected Test Workload")
    axes[0].set_xlabel("Retrospective cohort")
    axes[0].set_ylabel("Share of case-selected flows")
    axes[0].tick_params(axis="x", rotation=15)
    for i, row in enumerate(test_cohort.itertuples(index=False)):
        axes[0].text(i, row.case_selected_share + 0.01, pct(row.case_selected_share), ha="center", fontsize=10)

    sns.barplot(
        data=test_cohort,
        x="cohort_label",
        y="avg_lifecycle_hours",
        hue="cohort_label",
        palette=["#6aa84f", "#38761d", "#e69138", "#f6b26b"],
        dodge=False,
        legend=False,
        ax=axes[1],
    )
    axes[1].set_title("Burden and Comparison-Surface Differences")
    axes[1].set_xlabel("Retrospective cohort")
    axes[1].set_ylabel("Avg lifecycle hours")
    axes[1].tick_params(axis="x", rotation=15)

    rate_ax = axes[1].twinx()
    rate_ax.plot(
        range(len(test_cohort)),
        test_cohort["bank_positive_rate"],
        color="#bf2f39",
        marker="o",
        linewidth=2.5,
        label="Bank-positive rate",
    )
    rate_ax.set_ylabel("Bank-positive rate")
    rate_ax.set_ylim(0, max(0.7, float(test_cohort["bank_positive_rate"].max()) * 1.15))

    for i, row in enumerate(test_cohort.itertuples(index=False)):
        axes[1].text(i, row.avg_lifecycle_hours + 40, comma(row.avg_lifecycle_hours), ha="center", fontsize=10)
        rate_ax.text(i, row.bank_positive_rate + 0.03, pct(row.bank_positive_rate), ha="center", color="#bf2f39", fontsize=10)

    fig.suptitle("Retrospective Cohort Surface on the Test Window", y=1.02, fontsize=18)
    fig.tight_layout()
    fig.savefig(figures_dir / "cohort_burden_value_surface.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    manifest = {
        "generated_figures": [
            "population_linkage_and_trust_gate.png",
            "pathway_stage_test_surface.png",
            "cohort_burden_value_surface.png",
        ]
    }
    (figures_dir / "figure_manifest.json").write_text(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
