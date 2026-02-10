from __future__ import annotations

from pathlib import Path

import duckdb
import matplotlib
import numpy as np
import pandas as pd
import seaborn as sns

matplotlib.use("Agg")
import matplotlib.pyplot as plt

RUN_BASE = Path(
    r"runs/local_full_run-5/c25a2675fbfbacd952b13bb594880e92/data"
)
OUT_DIR = Path(r"docs/reports/eda/segment_6B/plots")


def _connect() -> duckdb.DuckDBPyConnection:
    return duckdb.connect()


def _plot_02_bank_view_heatmap(con: duckdb.DuckDBPyConnection) -> None:
    q = f"""
    WITH s3 AS (
      SELECT flow_id, merchant_id, amount
      FROM parquet_scan('{(RUN_BASE / "layer3/6B/s3_flow_anchor_with_fraud_6B").as_posix()}/**/*.parquet',
                        hive_partitioning=true, union_by_name=true)
      WHERE flow_id % 25 = 0
    ),
    b AS (
      SELECT flow_id, is_fraud_bank_view
      FROM parquet_scan('{(RUN_BASE / "layer3/6B/s4_flow_bank_view_6B").as_posix()}/**/*.parquet',
                        hive_partitioning=true, union_by_name=true)
      WHERE flow_id % 25 = 0
    ),
    mc AS (
      SELECT merchant_id, primary_demand_class
      FROM parquet_scan('{(RUN_BASE / "layer2/5A/merchant_class_profile").as_posix()}/**/*.parquet',
                        hive_partitioning=true, union_by_name=true)
    )
    SELECT
      primary_demand_class,
      CASE
        WHEN amount <= 5 THEN '(0,5]'
        WHEN amount <= 10 THEN '(5,10]'
        WHEN amount <= 20 THEN '(10,20]'
        WHEN amount <= 30 THEN '(20,30]'
        WHEN amount <= 50 THEN '(30,50]'
        WHEN amount <= 100 THEN '(50,100]'
        ELSE '(100,inf]'
      END AS amount_bin,
      count(*) AS n,
      avg(CASE WHEN is_fraud_bank_view THEN 1 ELSE 0 END) AS bank_fraud_rate
    FROM s3
    JOIN b USING(flow_id)
    LEFT JOIN mc USING(merchant_id)
    GROUP BY 1, 2
    """
    df = con.execute(q).fetchdf()
    class_order = [
        "bills_utilities",
        "consumer_daytime",
        "evening_weekend",
        "fuel_convenience",
        "office_hours",
        "online_24h",
        "online_bursty",
        "travel_hospitality",
    ]
    bin_order = ["(0,5]", "(5,10]", "(10,20]", "(20,30]", "(30,50]", "(50,100]", "(100,inf]"]
    df["primary_demand_class"] = pd.Categorical(
        df["primary_demand_class"], categories=class_order, ordered=True
    )
    df["amount_bin"] = pd.Categorical(df["amount_bin"], categories=bin_order, ordered=True)
    df = df.sort_values(["primary_demand_class", "amount_bin"])

    rate_pt = df.pivot(index="primary_demand_class", columns="amount_bin", values="bank_fraud_rate")
    n_pt = df.pivot(index="primary_demand_class", columns="amount_bin", values="n")
    # Very small support in >100 bins creates unstable rates; mask for readability.
    rate_masked = rate_pt.mask(n_pt < 1_000)
    # Remove bins that are fully masked so the heatmap doesn't show empty columns.
    rate_masked = rate_masked.dropna(axis=1, how="all")

    plt.figure(figsize=(14, 7))
    ax = sns.heatmap(
        rate_masked,
        annot=True,
        fmt=".3f",
        cmap="viridis",
        vmin=0.0,
        vmax=float(np.nanmax(rate_masked.values)),
        cbar_kws={"label": "bank_fraud_rate"},
        linewidths=0.4,
        linecolor="white",
    )
    ax.set_title(
        "Bank-View Fraud Rate by Amount Bin and Merchant Class (5M sample)\n"
        "Cells with n < 1,000 are masked"
    )
    ax.set_xlabel("amount_bin")
    ax.set_ylabel("merchant class")
    plt.tight_layout()
    plt.savefig(OUT_DIR / "02_bank_view_flatness_heatmap.png", dpi=160)
    plt.close()


def _plot_04_case_gap_distribution(con: duckdb.DuckDBPyConnection) -> None:
    q = f"""
    WITH ct AS (
      SELECT
        case_id,
        try_strptime(ts_utc, '%Y-%m-%dT%H:%M:%S.%fZ') AS ts,
        case_event_seq
      FROM parquet_scan('{(RUN_BASE / "layer3/6B/s4_case_timeline_6B").as_posix()}/**/*.parquet',
                        hive_partitioning=true, union_by_name=true)
      WHERE case_id % 20 = 0
    ),
    g AS (
      SELECT date_diff('second', lag(ts) OVER (PARTITION BY case_id ORDER BY case_event_seq), ts) AS gap_sec
      FROM ct
    )
    SELECT gap_sec, count(*) AS n
    FROM g
    WHERE gap_sec IS NOT NULL
    GROUP BY gap_sec
    ORDER BY gap_sec
    """
    df = con.execute(q).fetchdf()
    total = int(df["n"].sum())

    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
    sns.barplot(data=df, x="gap_sec", y="n", ax=axes[0], color="#4C78A8")
    axes[0].set_title("Case Event Time Gaps (sample, exact values)")
    axes[0].set_xlabel("gap seconds")
    axes[0].set_ylabel("count")
    axes[0].ticklabel_format(axis="y", style="sci", scilimits=(0, 0))
    for p in axes[0].patches:
        h = p.get_height()
        axes[0].annotate(f"{int(h):,}", (p.get_x() + p.get_width() / 2, h), ha="center", va="bottom", fontsize=8)

    sign_df = pd.DataFrame(
        {
            "gap_sign": ["negative", "zero", "positive"],
            "count": [
                int(df.loc[df["gap_sec"] < 0, "n"].sum()),
                int(df.loc[df["gap_sec"] == 0, "n"].sum()),
                int(df.loc[df["gap_sec"] > 0, "n"].sum()),
            ],
        }
    )
    sign_df["share"] = sign_df["count"] / total
    sns.barplot(data=sign_df, x="gap_sign", y="share", ax=axes[1], hue="gap_sign", dodge=False, palette=["#E15759", "#BAB0AC", "#59A14F"], legend=False)
    axes[1].set_title("Gap Sign Composition")
    axes[1].set_xlabel("gap sign")
    axes[1].set_ylabel("share")
    axes[1].set_ylim(0, 1)
    for p in axes[1].patches:
        h = p.get_height()
        axes[1].annotate(f"{h:.1%}", (p.get_x() + p.get_width() / 2, h), ha="center", va="bottom", fontsize=9)

    plt.tight_layout()
    plt.savefig(OUT_DIR / "04_case_gap_distribution.png", dpi=160)
    plt.close()


def _plot_05_case_duration_distribution(con: duckdb.DuckDBPyConnection) -> None:
    q = f"""
    WITH ct AS (
      SELECT
        case_id,
        min(try_strptime(ts_utc, '%Y-%m-%dT%H:%M:%S.%fZ')) AS ts_min,
        max(try_strptime(ts_utc, '%Y-%m-%dT%H:%M:%S.%fZ')) AS ts_max
      FROM parquet_scan('{(RUN_BASE / "layer3/6B/s4_case_timeline_6B").as_posix()}/**/*.parquet',
                        hive_partitioning=true, union_by_name=true)
      WHERE case_id % 20 = 0
      GROUP BY case_id
    )
    SELECT date_diff('second', ts_min, ts_max) AS duration_sec, count(*) AS n
    FROM ct
    GROUP BY duration_sec
    ORDER BY duration_sec
    """
    df = con.execute(q).fetchdf()
    total = int(df["n"].sum())
    df["hours"] = df["duration_sec"] / 3600.0
    df["label"] = df["duration_sec"].map(lambda x: f"{x:,}s")

    plt.figure(figsize=(9, 5.5))
    ax = sns.barplot(data=df, x="label", y="n", color="#F28E2B")
    ax.set_title("Case Duration Distribution (sample, exact values)")
    ax.set_xlabel("duration")
    ax.set_ylabel("count")
    ax.ticklabel_format(axis="y", style="sci", scilimits=(0, 0))
    for p, n in zip(ax.patches, df["n"]):
        share = n / total
        ax.annotate(f"{int(n):,}\n({share:.1%})", (p.get_x() + p.get_width() / 2, p.get_height()), ha="center", va="bottom", fontsize=9)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "05_case_duration_distribution.png", dpi=160)
    plt.close()


def _plot_08_amount_distribution(con: duckdb.DuckDBPyConnection) -> None:
    q = f"""
    SELECT amount, count(*) AS n
    FROM parquet_scan('{(RUN_BASE / "layer3/6B/s2_flow_anchor_baseline_6B").as_posix()}/**/*.parquet',
                      hive_partitioning=true, union_by_name=true)
    GROUP BY amount
    ORDER BY amount
    """
    df = con.execute(q).fetchdf()
    total = int(df["n"].sum())
    df["share"] = df["n"] / total
    df["amount_label"] = df["amount"].map(lambda x: f"{x:.2f}")

    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
    sns.barplot(data=df, x="amount_label", y="n", ax=axes[0], color="#76B7B2")
    axes[0].set_title("Amount Distribution (Exact Price Points)")
    axes[0].set_xlabel("amount")
    axes[0].set_ylabel("count")
    axes[0].ticklabel_format(axis="y", style="sci", scilimits=(0, 0))

    sns.barplot(data=df, x="amount_label", y="share", ax=axes[1], color="#4E79A7")
    axes[1].set_title("Amount Share by Price Point")
    axes[1].set_xlabel("amount")
    axes[1].set_ylabel("share")
    axes[1].set_ylim(0, max(df["share"]) * 1.12)
    for p, s in zip(axes[1].patches, df["share"]):
        axes[1].annotate(f"{s:.2%}", (p.get_x() + p.get_width() / 2, p.get_height()), ha="center", va="bottom", fontsize=9)

    plt.tight_layout()
    plt.savefig(OUT_DIR / "08_amount_distribution.png", dpi=160)
    plt.close()


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid", context="talk")
    con = _connect()
    _plot_02_bank_view_heatmap(con)
    _plot_04_case_gap_distribution(con)
    _plot_05_case_duration_distribution(con)
    _plot_08_amount_distribution(con)
    con.close()
    print("updated_plots", 4)


if __name__ == "__main__":
    main()
