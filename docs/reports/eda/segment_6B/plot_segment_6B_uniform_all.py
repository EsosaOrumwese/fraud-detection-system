from __future__ import annotations

from pathlib import Path

import duckdb
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


RUN_BASE = Path(r"runs/local_full_run-5/c25a2675fbfbacd952b13bb594880e92/data")
OUT_DIR = Path(r"docs/reports/eda/segment_6B/plots")

TITLE_KW = {"fontsize": 20, "fontweight": "semibold"}
LABEL_FS = 14
TICK_FS = 12


def con() -> duckdb.DuckDBPyConnection:
    return duckdb.connect()


def apply_style() -> None:
    sns.set_theme(style="whitegrid", context="talk", font="DejaVu Sans")
    plt.rcParams["figure.dpi"] = 160
    plt.rcParams["savefig.dpi"] = 160
    plt.rcParams["axes.titlesize"] = TITLE_KW["fontsize"]
    plt.rcParams["axes.labelsize"] = LABEL_FS
    plt.rcParams["xtick.labelsize"] = TICK_FS
    plt.rcParams["ytick.labelsize"] = TICK_FS


def plot_01_truth_dist(cx: duckdb.DuckDBPyConnection) -> None:
    q_truth = f"""
    SELECT is_fraud_truth, count(*) AS n
    FROM parquet_scan('{(RUN_BASE / "layer3/6B/s4_flow_truth_labels_6B").as_posix()}/**/*.parquet',
                      hive_partitioning=true, union_by_name=true)
    GROUP BY 1
    ORDER BY 1
    """
    q_lbl = f"""
    SELECT fraud_label, count(*) AS n
    FROM parquet_scan('{(RUN_BASE / "layer3/6B/s4_flow_truth_labels_6B").as_posix()}/**/*.parquet',
                      hive_partitioning=true, union_by_name=true)
    GROUP BY 1
    ORDER BY n
    """
    t = cx.execute(q_truth).fetchdf()
    l = cx.execute(q_lbl).fetchdf()

    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    sns.barplot(data=t, x=t["is_fraud_truth"].astype(str), y="n", color="#4E79A7", ax=axes[0])
    axes[0].set_yscale("log")
    axes[0].set_title("Truth Flag Distribution", **TITLE_KW)
    axes[0].set_xlabel("is_fraud_truth")
    axes[0].set_ylabel("count (log scale)")
    for p in axes[0].patches:
        h = p.get_height()
        axes[0].annotate(f"{int(h):,}", (p.get_x() + p.get_width() / 2, h), ha="center", va="bottom", fontsize=11)

    sns.barplot(data=l, x="fraud_label", y="n", color="#B55D2A", ax=axes[1])
    axes[1].set_yscale("log")
    axes[1].set_title("Truth Label Distribution", **TITLE_KW)
    axes[1].set_xlabel("fraud_label")
    axes[1].set_ylabel("count (log scale)")
    for p in axes[1].patches:
        h = p.get_height()
        axes[1].annotate(f"{int(h):,}", (p.get_x() + p.get_width() / 2, h), ha="center", va="bottom", fontsize=11)

    plt.tight_layout()
    plt.savefig(OUT_DIR / "01_truth_label_saturation.png")
    plt.close()


def plot_02_bank_heatmap(cx: duckdb.DuckDBPyConnection) -> None:
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
    GROUP BY 1,2
    """
    df = cx.execute(q).fetchdf()
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
    df["primary_demand_class"] = pd.Categorical(df["primary_demand_class"], categories=class_order, ordered=True)
    df["amount_bin"] = pd.Categorical(df["amount_bin"], categories=bin_order, ordered=True)
    df = df.sort_values(["primary_demand_class", "amount_bin"])
    rate_pt = df.pivot(index="primary_demand_class", columns="amount_bin", values="bank_fraud_rate")
    n_pt = df.pivot(index="primary_demand_class", columns="amount_bin", values="n")
    rate_pt = rate_pt.mask(n_pt < 1_000).dropna(axis=1, how="all")

    plt.figure(figsize=(14, 8))
    ax = sns.heatmap(
        rate_pt,
        annot=True,
        fmt=".3f",
        cmap="viridis",
        linewidths=0.4,
        linecolor="white",
        cbar_kws={"label": "bank_fraud_rate"},
    )
    ax.set_title("Bank-View Fraud Rate by Amount Bin and Merchant Class (5M sample)\nCells with n < 1,000 are masked", **TITLE_KW)
    ax.set_xlabel("amount_bin")
    ax.set_ylabel("merchant class")
    plt.tight_layout()
    plt.savefig(OUT_DIR / "02_bank_view_flatness_heatmap.png")
    plt.close()


def plot_03_confusion(cx: duckdb.DuckDBPyConnection) -> None:
    q = f"""
    SELECT
      t.is_fraud_truth,
      b.is_fraud_bank_view,
      count(*) AS n
    FROM parquet_scan('{(RUN_BASE / "layer3/6B/s4_flow_truth_labels_6B").as_posix()}/**/*.parquet',
                      hive_partitioning=true, union_by_name=true) t
    JOIN parquet_scan('{(RUN_BASE / "layer3/6B/s4_flow_bank_view_6B").as_posix()}/**/*.parquet',
                      hive_partitioning=true, union_by_name=true) b
      USING(flow_id)
    GROUP BY 1,2
    """
    df = cx.execute(q).fetchdf()
    mat = pd.DataFrame(0, index=[False, True], columns=[False, True], dtype=float)
    for _, r in df.iterrows():
        mat.loc[bool(r["is_fraud_truth"]), bool(r["is_fraud_bank_view"])] = r["n"]

    plt.figure(figsize=(9, 7))
    ax = sns.heatmap(mat, annot=False, cmap="Reds", cbar=True)
    ax.set_title("Truth vs Bank-View Confusion Matrix", **TITLE_KW)
    ax.set_xlabel("Bank View")
    ax.set_ylabel("Truth")
    ax.set_xticklabels(["Bank False", "Bank True"])
    ax.set_yticklabels(["Truth False", "Truth True"], rotation=90, va="center")
    vmax = float(mat.to_numpy().max()) if float(mat.to_numpy().max()) > 0 else 1.0
    for i in range(2):
        for j in range(2):
            v = int(mat.iloc[i, j])
            color = "white" if (v / vmax) > 0.55 else "#1f1f1f"
            ax.text(j + 0.5, i + 0.5, f"{v:,}", ha="center", va="center", fontsize=18, color=color)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "03_truth_bank_confusion.png")
    plt.close()


def plot_04_case_gaps(cx: duckdb.DuckDBPyConnection) -> None:
    q = f"""
    WITH ct AS (
      SELECT case_id, try_strptime(ts_utc, '%Y-%m-%dT%H:%M:%S.%fZ') AS ts, case_event_seq
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
    GROUP BY 1
    ORDER BY 1
    """
    df = cx.execute(q).fetchdf()
    total = int(df["n"].sum())
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

    fig, axes = plt.subplots(1, 2, figsize=(17, 7))
    sns.barplot(data=df, x="gap_sec", y="n", ax=axes[0], color="#4E79A7")
    axes[0].set_title("Case Event Time Gaps (sample, exact values)", **TITLE_KW)
    axes[0].set_xlabel("gap seconds")
    axes[0].set_ylabel("count")
    axes[0].ticklabel_format(axis="y", style="sci", scilimits=(0, 0))
    for p in axes[0].patches:
        h = p.get_height()
        axes[0].annotate(f"{int(h):,}", (p.get_x() + p.get_width() / 2, h), ha="center", va="bottom", fontsize=10)

    sns.barplot(
        data=sign_df,
        x="gap_sign",
        y="share",
        hue="gap_sign",
        dodge=False,
        palette=["#E15759", "#BAB0AC", "#59A14F"],
        legend=False,
        ax=axes[1],
    )
    axes[1].set_title("Gap Sign Composition", **TITLE_KW)
    axes[1].set_xlabel("gap sign")
    axes[1].set_ylabel("share")
    axes[1].set_ylim(0, 1)
    for p in axes[1].patches:
        h = p.get_height()
        axes[1].annotate(f"{h:.1%}", (p.get_x() + p.get_width() / 2, h), ha="center", va="bottom", fontsize=11)

    plt.tight_layout()
    plt.savefig(OUT_DIR / "04_case_gap_distribution.png")
    plt.close()


def plot_05_case_duration(cx: duckdb.DuckDBPyConnection) -> None:
    q = f"""
    WITH ct AS (
      SELECT case_id,
             min(try_strptime(ts_utc, '%Y-%m-%dT%H:%M:%S.%fZ')) AS ts_min,
             max(try_strptime(ts_utc, '%Y-%m-%dT%H:%M:%S.%fZ')) AS ts_max
      FROM parquet_scan('{(RUN_BASE / "layer3/6B/s4_case_timeline_6B").as_posix()}/**/*.parquet',
                        hive_partitioning=true, union_by_name=true)
      WHERE case_id % 20 = 0
      GROUP BY 1
    )
    SELECT date_diff('second', ts_min, ts_max) AS duration_sec, count(*) AS n
    FROM ct
    GROUP BY 1
    ORDER BY 1
    """
    df = cx.execute(q).fetchdf()
    total = int(df["n"].sum())
    df["label"] = df["duration_sec"].map(lambda x: f"{int(x):,}s")

    plt.figure(figsize=(11, 7))
    ax = sns.barplot(data=df, x="label", y="n", color="#F28E2B")
    ax.set_title("Case Duration Distribution (sample, exact values)", **TITLE_KW)
    ax.set_xlabel("duration")
    ax.set_ylabel("count")
    ax.ticklabel_format(axis="y", style="sci", scilimits=(0, 0))
    for p, n in zip(ax.patches, df["n"]):
        ax.annotate(f"{int(n):,}\n({n / total:.1%})", (p.get_x() + p.get_width() / 2, p.get_height()), ha="center", va="bottom", fontsize=11)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "05_case_duration_distribution.png")
    plt.close()


def plot_06_lorenz(cx: duckdb.DuckDBPyConnection) -> None:
    q = f"""
    SELECT merchant_id, count(*) AS fraud_n
    FROM parquet_scan('{(RUN_BASE / "layer3/6B/s3_flow_anchor_with_fraud_6B").as_posix()}/**/*.parquet',
                      hive_partitioning=true, union_by_name=true)
    WHERE fraud_flag = TRUE
    GROUP BY 1
    """
    df = cx.execute(q).fetchdf()
    vals = np.sort(df["fraud_n"].to_numpy())
    if len(vals) == 0:
        vals = np.array([0.0])
    cum_y = np.concatenate([[0.0], np.cumsum(vals) / np.sum(vals)])
    cum_x = np.linspace(0, 1, len(cum_y))
    gini = 1 - 2 * np.trapezoid(cum_y, cum_x)

    plt.figure(figsize=(8.5, 8.5))
    plt.plot(cum_x, cum_y, color="#3E6FB0", linewidth=3, label="Fraud per merchant")
    plt.plot([0, 1], [0, 1], "--", color="gray", linewidth=2, label="Equality")
    plt.title("Lorenz Curve: Fraud Concentration by Merchant\n" + f"Gini = {gini:.3f}", **TITLE_KW)
    plt.xlabel("Cumulative share of merchants")
    plt.ylabel("Cumulative share of fraud")
    plt.legend()
    plt.tight_layout(rect=[0, 0, 1, 0.98])
    plt.savefig(OUT_DIR / "06_fraud_lorenz_curve.png")
    plt.close()


def _topk_share(arr: np.ndarray, pct: float) -> float:
    if arr.size == 0:
        return 0.0
    k = max(1, int(np.ceil(arr.size * pct)))
    return float(np.sort(arr)[::-1][:k].sum() / arr.sum())


def plot_07_topk(cx: duckdb.DuckDBPyConnection) -> None:
    q_party = f"""
    SELECT party_id, count(*) AS n
    FROM parquet_scan('{(RUN_BASE / "layer3/6B/s3_flow_anchor_with_fraud_6B").as_posix()}/**/*.parquet',
                      hive_partitioning=true, union_by_name=true)
    GROUP BY 1
    """
    q_merch = f"""
    SELECT merchant_id, count(*) AS n
    FROM parquet_scan('{(RUN_BASE / "layer3/6B/s3_flow_anchor_with_fraud_6B").as_posix()}/**/*.parquet',
                      hive_partitioning=true, union_by_name=true)
    WHERE fraud_flag = TRUE
    GROUP BY 1
    """
    party = cx.execute(q_party).fetchdf()["n"].to_numpy()
    merch = cx.execute(q_merch).fetchdf()["n"].to_numpy()
    ks = [0.01, 0.05, 0.10]
    labels = ["top1%", "top5%", "top10%"]
    party_s = [_topk_share(party, k) for k in ks]
    merch_s = [_topk_share(merch, k) for k in ks]

    x = np.arange(len(labels))
    w = 0.35
    fig, ax = plt.subplots(figsize=(10, 7))
    b1 = ax.bar(x - w / 2, party_s, width=w, color="#3E6FB0", label="flows per party")
    b2 = ax.bar(x + w / 2, merch_s, width=w, color="#D6844F", label="fraud per merchant")
    ax.set_title("Top-k Share Comparison", **TITLE_KW)
    ax.set_xlabel("k bucket")
    ax.set_ylabel("share")
    ax.set_xticks(x, labels)
    ax.set_ylim(0, max(max(party_s), max(merch_s)) * 1.15)
    ax.legend()
    for bars in [b1, b2]:
        for p in bars:
            h = p.get_height()
            ax.annotate(f"{h:.3f}", (p.get_x() + p.get_width() / 2, h), ha="center", va="bottom", fontsize=10)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "07_topk_share_bars.png")
    plt.close()


def plot_08_amount_dist(cx: duckdb.DuckDBPyConnection) -> None:
    q = f"""
    SELECT amount, count(*) AS n
    FROM parquet_scan('{(RUN_BASE / "layer3/6B/s2_flow_anchor_baseline_6B").as_posix()}/**/*.parquet',
                      hive_partitioning=true, union_by_name=true)
    GROUP BY 1
    ORDER BY 1
    """
    df = cx.execute(q).fetchdf()
    total = int(df["n"].sum())
    df["share"] = df["n"] / total
    df["amount_label"] = df["amount"].map(lambda x: f"{x:.2f}")

    fig, axes = plt.subplots(1, 2, figsize=(17, 7))
    sns.barplot(data=df, x="amount_label", y="n", color="#76B7B2", ax=axes[0])
    axes[0].set_title("Amount Distribution (Exact Price Points)", **TITLE_KW)
    axes[0].set_xlabel("amount")
    axes[0].set_ylabel("count")
    axes[0].ticklabel_format(axis="y", style="sci", scilimits=(0, 0))

    sns.barplot(data=df, x="amount_label", y="share", color="#4E79A7", ax=axes[1])
    axes[1].set_title("Amount Share by Price Point", **TITLE_KW)
    axes[1].set_xlabel("amount")
    axes[1].set_ylabel("share")
    axes[1].set_ylim(0, max(df["share"]) * 1.12)
    for p, s in zip(axes[1].patches, df["share"]):
        axes[1].annotate(f"{s:.2%}", (p.get_x() + p.get_width() / 2, p.get_height()), ha="center", va="bottom", fontsize=11)

    plt.tight_layout()
    plt.savefig(OUT_DIR / "08_amount_distribution.png")
    plt.close()


def plot_09_uplift(cx: duckdb.DuckDBPyConnection) -> None:
    q = f"""
    WITH b AS (
      SELECT flow_id, amount AS base_amount
      FROM parquet_scan('{(RUN_BASE / "layer3/6B/s2_flow_anchor_baseline_6B").as_posix()}/**/*.parquet',
                        hive_partitioning=true, union_by_name=true)
      WHERE flow_id % 25 = 0
    ),
    f AS (
      SELECT flow_id, amount AS fraud_amount, fraud_flag
      FROM parquet_scan('{(RUN_BASE / "layer3/6B/s3_flow_anchor_with_fraud_6B").as_posix()}/**/*.parquet',
                        hive_partitioning=true, union_by_name=true)
      WHERE flow_id % 25 = 0
    )
    SELECT base_amount, fraud_amount / NULLIF(base_amount, 0) AS uplift_ratio
    FROM b JOIN f USING(flow_id)
    WHERE fraud_flag = TRUE
    """
    df = cx.execute(q).fetchdf()
    order = [1.99, 4.99, 9.99, 14.99, 19.99, 29.99, 49.99, 99.99]
    df["base_label"] = pd.Categorical(df["base_amount"].round(2).astype(str), categories=[f"{x:.2f}" for x in order], ordered=True)

    plt.figure(figsize=(13, 7))
    sns.boxplot(data=df, x="base_label", y="uplift_ratio", color="#3E6FB0", showfliers=False)
    plt.title("Fraud Uplift Ratio by Base Amount (5M sample)", **TITLE_KW)
    plt.xlabel("base_amount")
    plt.ylabel("fraud_amount / base_amount")
    plt.tight_layout()
    plt.savefig(OUT_DIR / "09_fraud_uplift_by_base_amount.png")
    plt.close()


def plot_10_cross_border(cx: duckdb.DuckDBPyConnection) -> None:
    q = f"""
    WITH flows AS (
      SELECT flow_id, merchant_id, party_id
      FROM parquet_scan('{(RUN_BASE / "layer3/6B/s3_flow_anchor_with_fraud_6B").as_posix()}/**/*.parquet',
                        hive_partitioning=true, union_by_name=true)
      WHERE flow_id % 25 = 0
    ),
    party_country AS (
      SELECT party_id, country_iso AS party_country
      FROM parquet_scan('{(RUN_BASE / "layer3/6A/s1_party_base_6A").as_posix()}/**/*.parquet',
                        hive_partitioning=true, union_by_name=true)
    ),
    merch_country_raw AS (
      SELECT merchant_id, legal_country_iso, count(*) AS n
      FROM parquet_scan('{(RUN_BASE / "layer2/5A/merchant_zone_profile").as_posix()}/**/*.parquet',
                        hive_partitioning=true, union_by_name=true)
      GROUP BY 1,2
    ),
    merch_country AS (
      SELECT merchant_id, arg_max(legal_country_iso, n) AS merchant_country
      FROM merch_country_raw
      GROUP BY 1
    ),
    classes AS (
      SELECT merchant_id, primary_demand_class
      FROM parquet_scan('{(RUN_BASE / "layer2/5A/merchant_class_profile").as_posix()}/**/*.parquet',
                        hive_partitioning=true, union_by_name=true)
    ),
    joined AS (
      SELECT c.primary_demand_class,
             CASE WHEN p.party_country <> m.merchant_country THEN 1 ELSE 0 END AS is_cross_border
      FROM flows f
      LEFT JOIN party_country p USING(party_id)
      LEFT JOIN merch_country m USING(merchant_id)
      LEFT JOIN classes c USING(merchant_id)
      WHERE p.party_country IS NOT NULL
        AND m.merchant_country IS NOT NULL
        AND c.primary_demand_class IS NOT NULL
    )
    SELECT primary_demand_class, count(*) AS n, avg(is_cross_border) AS cross_border_rate
    FROM joined
    GROUP BY 1
    ORDER BY cross_border_rate DESC
    """
    df = cx.execute(q).fetchdf()
    overall = float((df["cross_border_rate"] * df["n"]).sum() / df["n"].sum())

    plt.figure(figsize=(13, 7))
    ax = sns.barplot(data=df, y="primary_demand_class", x="cross_border_rate", color="#0B6E77")
    ax.axvline(overall, color="red", linestyle="--", linewidth=2, label=f"flow-weighted overall {overall:.2f}")
    ax.set_title("Cross-border Rate by Merchant Class (5M sample)", **TITLE_KW)
    ax.set_xlabel("cross_border_rate")
    ax.set_ylabel("merchant class")
    ax.set_xlim(0, 1.05)
    ax.text(
        overall + 0.005,
        len(df) - 0.2,
        f"flow-weighted overall={overall:.3f}",
        color="red",
        fontsize=10,
        ha="left",
        va="top",
    )
    for p in ax.patches:
        w = p.get_width()
        ax.annotate(f"{w:.3f}", (w, p.get_y() + p.get_height() / 2), xytext=(5, 0), textcoords="offset points", va="center", fontsize=10)
    ax.legend(loc="lower right")
    plt.tight_layout()
    plt.savefig(OUT_DIR / "10_cross_border_rate_by_class.png")
    plt.close()


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    apply_style()
    cx = con()
    plot_01_truth_dist(cx)
    plot_02_bank_heatmap(cx)
    plot_03_confusion(cx)
    plot_04_case_gaps(cx)
    plot_05_case_duration(cx)
    plot_06_lorenz(cx)
    plot_07_topk(cx)
    plot_08_amount_dist(cx)
    plot_09_uplift(cx)
    plot_10_cross_border(cx)
    cx.close()
    print("plots_written", 10)


if __name__ == "__main__":
    main()
