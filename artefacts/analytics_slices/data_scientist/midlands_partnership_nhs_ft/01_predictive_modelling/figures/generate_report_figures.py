from __future__ import annotations

import json
from pathlib import Path

import duckdb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import seaborn as sns


def pct(v: float) -> str:
    return f"{v * 100:.1f}%"


def main() -> None:
    repo = Path(r"c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system")
    root = (
        repo
        / "artefacts"
        / "analytics_slices"
        / "data_scientist"
        / "midlands_partnership_nhs_ft"
        / "01_predictive_modelling"
    )
    metrics_dir = root / "metrics"
    figures_dir = root / "figures"
    extracts_dir = root / "extracts"
    figures_dir.mkdir(parents=True, exist_ok=True)

    sns.set_theme(style="whitegrid", context="talk")

    model_metrics = pd.read_csv(metrics_dir / "model_metrics.csv")
    test_bands = pd.read_csv(metrics_dir / "test_risk_band_metrics.csv")
    validation_bands = pd.read_csv(metrics_dir / "validation_risk_band_metrics.csv")
    forecast_metrics = pd.read_csv(metrics_dir / "case_demand_forecast_metrics.csv")
    fact_pack = json.loads((metrics_dir / "execution_fact_pack.json").read_text())

    con = duckdb.connect()
    cohort = con.execute(
        """
        SELECT
            split_role,
            risk_band,
            fraud_truth_rate,
            bank_view_positive_rate
        FROM parquet_scan(?)
        ORDER BY split_role, CASE risk_band WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END
        """,
        [str(extracts_dir / "flow_risk_cohort_summary_v1.parquet")],
    ).fetchdf()
    forecast_points = con.execute(
        """
        SELECT
            CAST(case_open_date_utc AS DATE) AS case_open_date_utc,
            evaluation_split,
            actual_daily_case_opens,
            predicted_daily_case_opens
        FROM parquet_scan(?)
        ORDER BY case_open_date_utc
        """,
        [str(extracts_dir / "case_demand_forecasts_v1.parquet")],
    ).fetchdf()
    forecast_points["case_open_date_utc"] = pd.to_datetime(forecast_points["case_open_date_utc"])

    baseline_positive_rate = float(model_metrics.loc[model_metrics["split"] == "test", "positive_rate"].iloc[0])

    for df in [validation_bands, test_bands]:
        total_rows = float(df["rows"].sum())
        df["row_share"] = df["rows"] / total_rows

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    band_palette = ["#bf2f39", "#e6a22e", "#6e7f8d"]
    order = ["High", "Medium", "Low"]

    sns.barplot(
        data=test_bands,
        x="risk_band",
        y="row_share",
        hue="risk_band",
        order=order,
        palette=band_palette,
        dodge=False,
        legend=False,
        ax=axes[0],
    )
    axes[0].set_title("Test Band Size")
    axes[0].set_xlabel("Risk band")
    axes[0].set_ylabel("Share of scored test flows")
    for i, row in test_bands.set_index("risk_band").loc[order].reset_index().iterrows():
        axes[0].text(i, row["row_share"] + 0.01, pct(row["row_share"]), ha="center", va="bottom", fontsize=10)

    sns.barplot(
        data=test_bands,
        x="risk_band",
        y="positive_rate",
        hue="risk_band",
        order=order,
        palette=band_palette,
        dodge=False,
        legend=False,
        ax=axes[1],
    )
    axes[1].axhline(baseline_positive_rate, color="#222222", linestyle="--", linewidth=1.5, label="Overall test baseline")
    axes[1].set_title("Test Fraud-Truth Yield")
    axes[1].set_xlabel("Risk band")
    axes[1].set_ylabel("Fraud-truth rate")
    axes[1].legend(loc="upper right")
    for i, row in test_bands.set_index("risk_band").loc[order].reset_index().iterrows():
        axes[1].text(i, row["positive_rate"] + 0.002, pct(row["positive_rate"]), ha="center", va="bottom", fontsize=10)

    sns.barplot(
        data=test_bands,
        x="risk_band",
        y="capture_rate",
        hue="risk_band",
        order=order,
        palette=band_palette,
        dodge=False,
        legend=False,
        ax=axes[2],
    )
    axes[2].set_title("Test Positive Capture")
    axes[2].set_xlabel("Risk band")
    axes[2].set_ylabel("Share of test positives captured")
    for i, row in test_bands.set_index("risk_band").loc[order].reset_index().iterrows():
        axes[2].text(i, row["capture_rate"] + 0.01, pct(row["capture_rate"]), ha="center", va="bottom", fontsize=10)

    fig.suptitle("Prioritisation Surface for Scored Test Flows", y=1.03, fontsize=18)
    fig.tight_layout()
    fig.savefig(figures_dir / "01_flow_risk_band_performance.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    stability = pd.concat(
        [
            validation_bands.assign(evaluation_split="Validation"),
            test_bands.assign(evaluation_split="Test"),
        ],
        ignore_index=True,
    )
    stability["risk_band"] = pd.Categorical(stability["risk_band"], categories=order, ordered=True)
    fig, axes = plt.subplots(1, 2, figsize=(16, 6), sharex=True)
    sns.barplot(
        data=stability.sort_values("risk_band"),
        x="risk_band",
        y="lift_vs_baseline",
        hue="evaluation_split",
        palette=["#1f4e79", "#6aa84f"],
        ax=axes[0],
    )
    axes[0].set_title("Lift vs Baseline by Split")
    axes[0].set_xlabel("Risk band")
    axes[0].set_ylabel("Lift vs split baseline")
    axes[0].legend(title="")

    sns.barplot(
        data=stability.sort_values("risk_band"),
        x="risk_band",
        y="positive_rate",
        hue="evaluation_split",
        palette=["#1f4e79", "#6aa84f"],
        ax=axes[1],
    )
    axes[1].set_title("Fraud-Truth Yield by Split")
    axes[1].set_xlabel("Risk band")
    axes[1].set_ylabel("Fraud-truth rate")
    axes[1].legend(title="")
    fig.suptitle("Validation/Test Stability of the Risk Bands", y=1.03, fontsize=18)
    fig.tight_layout()
    fig.savefig(figures_dir / "02_validation_test_band_stability.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    cohort_long = cohort.melt(
        id_vars=["split_role", "risk_band"],
        value_vars=["fraud_truth_rate", "bank_view_positive_rate"],
        var_name="metric",
        value_name="rate",
    )
    cohort_long["metric"] = cohort_long["metric"].map(
        {
            "fraud_truth_rate": "Fraud truth rate",
            "bank_view_positive_rate": "Bank-view positive rate",
        }
    )
    fig, axes = plt.subplots(1, 2, figsize=(15, 6), sharey=True)
    for ax, split_name in zip(axes, ["validation", "test"]):
        split_df = cohort_long[cohort_long["split_role"] == split_name]
        sns.barplot(
            data=split_df,
            x="risk_band",
            y="rate",
            hue="metric",
            order=order,
            palette=["#1f4e79", "#6aa84f"],
            ax=ax,
        )
        ax.set_title(f"{split_name.title()} Cohort Separation")
        ax.set_xlabel("Risk band")
        ax.set_ylabel("Rate")
        ax.legend(title="")
    fig.suptitle("Fraud-Truth vs Bank-View Rates by Cohort", y=1.03, fontsize=18)
    fig.tight_layout()
    fig.savefig(figures_dir / "03_cohort_truth_vs_bank_view_rates.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(14, 6))
    validation_points = forecast_points[forecast_points["evaluation_split"] == "validation"].copy()
    test_points = forecast_points[forecast_points["evaluation_split"] == "test"].copy()
    ax.axvspan(
        validation_points["case_open_date_utc"].min(),
        validation_points["case_open_date_utc"].max(),
        color="#d9e7f5",
        alpha=0.45,
        label="Validation window",
    )
    ax.axvspan(
        test_points["case_open_date_utc"].min(),
        test_points["case_open_date_utc"].max(),
        color="#f9e1d5",
        alpha=0.45,
        label="Test window",
    )
    sns.lineplot(
        data=forecast_points,
        x="case_open_date_utc",
        y="actual_daily_case_opens",
        color="#1f4e79",
        linewidth=2.2,
        label="Actual daily case opens",
        ax=ax,
    )
    sns.lineplot(
        data=forecast_points,
        x="case_open_date_utc",
        y="predicted_daily_case_opens",
        color="#bf2f39",
        linewidth=2.2,
        label="Forecast",
        ax=ax,
    )
    test_mape = float(forecast_metrics.loc[forecast_metrics["evaluation_split"] == "test", "mape"].iloc[0])
    ax.set_title(f"Daily Case-Demand Forecast vs Actuals (Test MAPE {pct(test_mape)})")
    ax.set_xlabel("Date")
    ax.set_ylabel("Daily distinct case opens")
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    for label in ax.get_xticklabels():
        label.set_rotation(30)
        label.set_horizontalalignment("right")
    handles, labels = ax.get_legend_handles_labels()
    order_idx = [2, 3, 0, 1]
    ax.legend([handles[i] for i in order_idx], [labels[i] for i in order_idx], loc="upper left", ncol=2)
    fig.tight_layout()
    fig.savefig(figures_dir / "04_case_demand_forecast_vs_actual.png", dpi=200, bbox_inches="tight")
    plt.close(fig)

    manifest = {
        "generated_figures": [
            "01_flow_risk_band_performance.png",
            "02_validation_test_band_stability.png",
            "03_cohort_truth_vs_bank_view_rates.png",
            "04_case_demand_forecast_vs_actual.png",
        ]
    }
    (figures_dir / "figure_manifest.json").write_text(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
