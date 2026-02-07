from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, Tuple
from zoneinfo import ZoneInfo

import duckdb
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

RUN_BASE = Path(r"runs/local_full_run-5/c25a2675fbfbacd952b13bb594880e92/data")
BASE_5A = RUN_BASE / "layer2/5A"
BASE_3A = RUN_BASE / "layer1/3A"
OUT_DIR = Path(r"docs/reports/eda/segment_5A/plots")

SCENARIO_START_UTC = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
SCENARIO_END_UTC = datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc)

# This alignment constant is empirically recovered from the sealed run by
# minimizing baseline*overlay reconstruction error on a sampled subset.
WEEK_ALIGNMENT_SHIFT = 72


def scan(base: Path, ds: str) -> str:
    p = (base / ds).as_posix()
    return f"parquet_scan('{p}/**/*.parquet', hive_partitioning=true, union_by_name=true)"


def style() -> None:
    sns.set_theme(style="whitegrid", context="talk", font="DejaVu Sans")
    plt.rcParams["figure.dpi"] = 160
    plt.rcParams["savefig.dpi"] = 160
    plt.rcParams["axes.titlesize"] = 20
    plt.rcParams["axes.titleweight"] = "semibold"
    plt.rcParams["axes.labelsize"] = 14
    plt.rcParams["xtick.labelsize"] = 11
    plt.rcParams["ytick.labelsize"] = 11


def lorenz(values: np.ndarray) -> Tuple[np.ndarray, np.ndarray, float]:
    v = np.sort(values)
    if v.size == 0:
        return np.array([0.0, 1.0]), np.array([0.0, 1.0]), 0.0
    cum_y = np.concatenate([[0.0], np.cumsum(v) / np.sum(v)])
    cum_x = np.linspace(0.0, 1.0, len(cum_y))
    gini = 1.0 - 2.0 * np.trapezoid(cum_y, cum_x)
    return cum_x, cum_y, float(gini)


def topk_share(values: np.ndarray, k: float) -> float:
    vals = np.sort(values)[::-1]
    kk = max(1, int(np.ceil(vals.size * k)))
    return float(vals[:kk].sum() / vals.sum())


def _r2(y: np.ndarray, x_cols: Iterable[np.ndarray]) -> float:
    y = np.asarray(y, dtype=float)
    xs = [np.asarray(c, dtype=float) for c in x_cols]
    X = np.column_stack([np.ones_like(y)] + xs)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    yhat = X @ beta
    ss_res = float(np.sum((y - yhat) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    return 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0


def _vif(df: pd.DataFrame, cols: list[str]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for c in cols:
        y = df[c].to_numpy(dtype=float)
        x_cols = [df[k].to_numpy(dtype=float) for k in cols if k != c]
        r2 = _r2(y, x_cols)
        out[c] = float(np.inf) if r2 >= 0.999999999 else float(1.0 / (1.0 - r2))
    return out


def _channel_order() -> list[str]:
    return [
        "bills_utilities",
        "consumer_daytime",
        "evening_weekend",
        "fuel_convenience",
        "office_hours",
        "online_24h",
        "online_bursty",
        "travel_hospitality",
    ]


def plot_01_zero_volume_site_contingency(cx: duckdb.DuckDBPyConnection) -> None:
    q = f"""
    WITH m AS (
      SELECT merchant_id, legal_country_iso, tzid, weekly_volume_expected
      FROM {scan(BASE_5A, 'merchant_zone_profile')}
    ),
    z AS (
      SELECT merchant_id, legal_country_iso, tzid, max(zone_site_count) AS zone_site_count
      FROM {scan(BASE_3A, 'zone_alloc')}
      GROUP BY 1,2,3
    ),
    j AS (
      SELECT
        (coalesce(z.zone_site_count, 0) > 0) AS has_site,
        (m.weekly_volume_expected > 0) AS has_volume
      FROM m
      LEFT JOIN z USING(merchant_id, legal_country_iso, tzid)
    )
    SELECT has_site, has_volume, count(*)::DOUBLE AS n
    FROM j
    GROUP BY 1,2
    ORDER BY 1,2
    """
    df = cx.execute(q).fetchdf()
    pivot = df.pivot(index="has_site", columns="has_volume", values="n").fillna(0.0)
    total = float(pivot.to_numpy().sum())

    ann = pivot.copy().astype(object)
    for r in ann.index:
        for c in ann.columns:
            n = float(ann.loc[r, c])
            ann.loc[r, c] = f"{int(n):,}\n({(100*n/total):.2f}%)"

    fig, ax = plt.subplots(figsize=(8, 6.5))
    sns.heatmap(
        pivot,
        annot=ann,
        fmt="",
        cmap="Blues",
        cbar=False,
        linewidths=1.0,
        linecolor="white",
        ax=ax,
    )
    ax.set_title("Site Presence vs Nonzero Weekly Volume")
    ax.set_xlabel("has weekly_volume_expected > 0")
    ax.set_ylabel("has zone_site_count > 0")
    ax.set_xticklabels(["False", "True"], rotation=0)
    ax.set_yticklabels(["False", "True"], rotation=0)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "01_zero_volume_site_contingency.png")
    plt.close()


def plot_02_active_zone_breadth_vs_volume(cx: duckdb.DuckDBPyConnection) -> None:
    q = f"""
    WITH m AS (
      SELECT
        merchant_id,
        sum(weekly_volume_expected) AS weekly_volume_total,
        sum(CASE WHEN weekly_volume_expected > 0 THEN 1 ELSE 0 END) AS active_zones,
        count(*) AS total_zones
      FROM {scan(BASE_5A, 'merchant_zone_profile')}
      GROUP BY 1
    )
    SELECT * FROM m
    """
    df = cx.execute(q).fetchdf()
    df["log_volume"] = np.log10(df["weekly_volume_total"] + 1.0)

    fig, axes = plt.subplots(1, 2, figsize=(15, 6.5))
    hb = axes[0].hexbin(
        df["active_zones"],
        df["log_volume"],
        gridsize=28,
        bins="log",
        cmap="viridis",
        mincnt=1,
    )
    cbar = plt.colorbar(hb, ax=axes[0])
    cbar.set_label("merchant count (log)")
    axes[0].set_title("Merchant Volume vs Active Zone Breadth")
    axes[0].set_xlabel("active zones per merchant")
    axes[0].set_ylabel("log10(weekly volume total + 1)")

    by_a = (
        df.groupby("active_zones", as_index=False)["weekly_volume_total"]
        .median()
        .sort_values("active_zones")
    )
    axes[1].plot(
        by_a["active_zones"],
        by_a["weekly_volume_total"],
        marker="o",
        linewidth=2.2,
        color="#4E79A7",
    )
    axes[1].set_yscale("log")
    axes[1].set_title("Median Volume by Active-Zone Count")
    axes[1].set_xlabel("active zones per merchant")
    axes[1].set_ylabel("median weekly volume (log scale)")
    plt.tight_layout()
    plt.savefig(OUT_DIR / "02_active_zone_breadth_vs_volume.png")
    plt.close()


def plot_03_priors_shares_counts_transition(cx: duckdb.DuckDBPyConnection) -> None:
    q = f"""
    WITH s4 AS (
      SELECT merchant_id, legal_country_iso, tzid, zone_site_count, fractional_target
      FROM {scan(BASE_3A, 's4_zone_counts')}
      WHERE mod(hash(merchant_id, legal_country_iso, tzid), 120) = 0
    ),
    s3 AS (
      SELECT merchant_id, legal_country_iso, tzid, share_drawn
      FROM {scan(BASE_3A, 's3_zone_shares')}
    ),
    s2 AS (
      SELECT country_iso, tzid, share_effective
      FROM {scan(BASE_3A, 's2_country_zone_priors')}
    )
    SELECT
      (s4.zone_site_count > 0) AS active_zone,
      s2.share_effective,
      s3.share_drawn,
      s4.fractional_target
    FROM s4
    JOIN s3 USING(merchant_id, legal_country_iso, tzid)
    JOIN s2 ON s2.country_iso = s4.legal_country_iso AND s2.tzid = s4.tzid
    """
    df = cx.execute(q).fetchdf()

    long = df.melt(
        id_vars=["active_zone"],
        value_vars=["share_effective", "share_drawn", "fractional_target"],
        var_name="metric",
        value_name="value",
    )
    long["value_log10"] = np.log10(long["value"].astype(float) + 1e-12)
    long["active_zone"] = np.where(long["active_zone"], "active", "inactive")

    fig, ax = plt.subplots(figsize=(13, 7))
    sns.violinplot(
        data=long,
        x="metric",
        y="value_log10",
        hue="active_zone",
        split=True,
        inner="quartile",
        palette={"active": "#4E79A7", "inactive": "#E15759"},
        ax=ax,
    )
    ax.set_title("Priors -> Drawn Shares -> Fractional Targets (Active vs Inactive)")
    ax.set_xlabel("")
    ax.set_ylabel("log10(value + 1e-12)")
    ax.legend(title="zone status", loc="upper right")
    plt.tight_layout()
    plt.savefig(OUT_DIR / "03_priors_shares_counts_transition.png")
    plt.close()


def _load_driver_df(cx: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    q = f"""
    WITH m AS (
      SELECT merchant_id, legal_country_iso, tzid, weekly_volume_expected
      FROM {scan(BASE_5A, 'merchant_zone_profile')}
      WHERE weekly_volume_expected > 0
    ),
    s4 AS (
      SELECT merchant_id, legal_country_iso, tzid, zone_site_count, fractional_target
      FROM {scan(BASE_3A, 's4_zone_counts')}
    ),
    s3 AS (
      SELECT merchant_id, legal_country_iso, tzid, share_drawn
      FROM {scan(BASE_3A, 's3_zone_shares')}
    )
    SELECT
      m.weekly_volume_expected,
      s4.zone_site_count::DOUBLE AS zone_site_count,
      s4.fractional_target::DOUBLE AS fractional_target,
      s3.share_drawn::DOUBLE AS share_drawn
    FROM m
    JOIN s4 USING(merchant_id, legal_country_iso, tzid)
    JOIN s3 USING(merchant_id, legal_country_iso, tzid)
    """
    return cx.execute(q).fetchdf()


def plot_04_multicollinearity_diagnostics(cx: duckdb.DuckDBPyConnection) -> None:
    df = _load_driver_df(cx)
    cols = ["zone_site_count", "fractional_target", "share_drawn"]
    corr = df[cols].corr(method="spearman")
    vif = _vif(df, cols)

    fig, axes = plt.subplots(1, 2, figsize=(15.5, 6.5))
    sns.heatmap(
        corr,
        annot=True,
        fmt=".3f",
        cmap="coolwarm",
        vmin=-1,
        vmax=1,
        square=True,
        ax=axes[0],
    )
    axes[0].set_title("Predictor Correlation (Spearman)")

    sns.scatterplot(
        data=df,
        x="fractional_target",
        y="zone_site_count",
        s=34,
        alpha=0.45,
        color="#4E79A7",
        ax=axes[1],
    )
    m, b = np.polyfit(df["fractional_target"], df["zone_site_count"], 1)
    xx = np.linspace(df["fractional_target"].min(), df["fractional_target"].max(), 100)
    axes[1].plot(xx, m * xx + b, "--", color="black", linewidth=2.0)
    axes[1].set_title("zone_site_count vs fractional_target")
    axes[1].set_xlabel("fractional_target")
    axes[1].set_ylabel("zone_site_count")
    text = "\n".join(
        [
            f"rho={corr.loc['zone_site_count','fractional_target']:.3f}",
            f"VIF(zone_site_count)={vif['zone_site_count']:.1f}",
            f"VIF(fractional_target)={vif['fractional_target']:.1f}",
        ]
    )
    axes[1].text(0.02, 0.98, text, transform=axes[1].transAxes, va="top")
    plt.tight_layout()
    plt.savefig(OUT_DIR / "04_multicollinearity_diagnostics.png")
    plt.close()


def plot_05_driver_dominance_raw_vs_log(cx: duckdb.DuckDBPyConnection) -> None:
    df = _load_driver_df(cx)
    y_raw = df["weekly_volume_expected"].to_numpy()
    y_log = np.log1p(y_raw)
    x1 = df["zone_site_count"].to_numpy()
    x2 = df["fractional_target"].to_numpy()
    x3 = df["share_drawn"].to_numpy()

    models = ["zone_site_count", "fractional_target", "share_drawn", "full"]
    raw_vals = [
        _r2(y_raw, [x1]),
        _r2(y_raw, [x2]),
        _r2(y_raw, [x3]),
        _r2(y_raw, [x1, x2, x3]),
    ]
    log_vals = [
        _r2(y_log, [x1]),
        _r2(y_log, [x2]),
        _r2(y_log, [x3]),
        _r2(y_log, [x1, x2, x3]),
    ]

    fig, axes = plt.subplots(1, 2, figsize=(15, 6.5), sharey=False)
    sns.barplot(x=models, y=raw_vals, color="#4E79A7", ax=axes[0])
    axes[0].set_title("Raw-Scale Driver Dominance (R²)")
    axes[0].set_xlabel("")
    axes[0].set_ylabel("R²")
    axes[0].set_ylim(0, 1.02)
    for i, v in enumerate(raw_vals):
        axes[0].text(i, v + 0.01, f"{v:.3f}", ha="center", va="bottom", fontsize=10)

    sns.barplot(x=models, y=log_vals, color="#E15759", ax=axes[1])
    axes[1].set_title("Log-Scale Driver Dominance (R²)")
    axes[1].set_xlabel("")
    axes[1].set_ylabel("R²")
    axes[1].set_ylim(0, max(log_vals) * 1.2)
    for i, v in enumerate(log_vals):
        axes[1].text(i, v + 0.01, f"{v:.3f}", ha="center", va="bottom", fontsize=10)

    plt.tight_layout()
    plt.savefig(OUT_DIR / "05_driver_dominance_raw_vs_log.png")
    plt.close()


def plot_06_country_sparsity_elasticity(cx: duckdb.DuckDBPyConnection) -> None:
    q = f"""
    WITH base AS (
      SELECT merchant_id, legal_country_iso, zone_site_count::DOUBLE AS zone_site_count, alpha_sum_country::DOUBLE AS alpha
      FROM {scan(BASE_3A, 's4_zone_counts')}
    ),
    row_level AS (
      SELECT
        legal_country_iso,
        avg(CASE WHEN zone_site_count > 0 THEN 1 ELSE 0 END) AS site_share_row,
        avg(alpha) AS alpha_mean
      FROM base
      GROUP BY 1
    ),
    merchant_level AS (
      SELECT
        legal_country_iso,
        merchant_id,
        avg(CASE WHEN zone_site_count > 0 THEN 1 ELSE 0 END) AS site_share_m
      FROM base
      GROUP BY 1,2
    ),
    merchant_country AS (
      SELECT legal_country_iso, avg(site_share_m) AS site_share_merchant
      FROM merchant_level
      GROUP BY 1
    )
    SELECT
      r.legal_country_iso,
      r.alpha_mean,
      r.site_share_row,
      m.site_share_merchant
    FROM row_level r
    JOIN merchant_country m USING(legal_country_iso)
    """
    df = cx.execute(q).fetchdf()

    for col in ["site_share_row", "site_share_merchant"]:
        df[col + "_clip"] = df[col].clip(1e-6, 1 - 1e-6)
        df[col + "_logit"] = np.log(df[col + "_clip"] / (1.0 - df[col + "_clip"]))
    df["log_alpha"] = np.log(df["alpha_mean"])

    fig, ax = plt.subplots(figsize=(11, 7))
    sns.scatterplot(
        data=df,
        x="log_alpha",
        y="site_share_row_logit",
        s=75,
        color="#4E79A7",
        label="row-level site share",
        ax=ax,
    )
    sns.scatterplot(
        data=df,
        x="log_alpha",
        y="site_share_merchant_logit",
        s=65,
        color="#E15759",
        marker="s",
        label="merchant-level site share",
        ax=ax,
    )

    for ycol, color in [("site_share_row_logit", "#4E79A7"), ("site_share_merchant_logit", "#E15759")]:
        m, b = np.polyfit(df["log_alpha"], df[ycol], 1)
        xx = np.linspace(df["log_alpha"].min(), df["log_alpha"].max(), 100)
        ax.plot(xx, m * xx + b, linestyle="--", linewidth=2, color=color)

    ax.set_title("Country Sparsity Elasticity vs alpha_sum_country")
    ax.set_xlabel("log(alpha_sum_country_mean)")
    ax.set_ylabel("logit(site share)")
    ax.legend(loc="best")
    plt.tight_layout()
    plt.savefig(OUT_DIR / "06_country_sparsity_elasticity.png")
    plt.close()


def plot_07_share_sum_country_invariance(cx: duckdb.DuckDBPyConnection) -> None:
    q = f"""
    SELECT
      legal_country_iso AS country,
      avg(share_sum_country) AS mean_share_sum,
      stddev_pop(share_sum_country) AS std_share_sum
    FROM {scan(BASE_3A, 's3_zone_shares')}
    GROUP BY 1
    """
    df = cx.execute(q).fetchdf()
    df["mean_dev_ppb"] = (df["mean_share_sum"] - 1.0) * 1e9
    df["std_ppb"] = df["std_share_sum"] * 1e9
    df = df.sort_values("country")

    fig, axes = plt.subplots(1, 2, figsize=(15, 7), sharey=True)
    sns.barplot(data=df, x="mean_dev_ppb", y="country", color="#4E79A7", ax=axes[0])
    axes[0].axvline(0.0, color="black", linestyle="--", linewidth=1.5)
    axes[0].set_title("Mean Deviation of share_sum_country (ppb)")
    axes[0].set_xlabel("(mean - 1.0) * 1e9")
    axes[0].set_ylabel("")

    sns.barplot(data=df, x="std_ppb", y="country", color="#E15759", ax=axes[1])
    axes[1].set_title("Std Dev of share_sum_country (ppb)")
    axes[1].set_xlabel("std * 1e9")
    axes[1].set_ylabel("")
    plt.tight_layout()
    plt.savefig(OUT_DIR / "07_share_sum_country_invariance.png")
    plt.close()


def plot_08_merchant_heavytail_concentration(cx: duckdb.DuckDBPyConnection) -> None:
    q = f"""
    SELECT weekly_volume_total_expected::DOUBLE AS volume
    FROM {scan(BASE_5A, 'merchant_class_profile')}
    WHERE weekly_volume_total_expected > 0
    """
    v = cx.execute(q).fetchdf()["volume"].to_numpy(dtype=float)
    x, y, g = lorenz(v)
    t1, t5, t10 = topk_share(v, 0.01), topk_share(v, 0.05), topk_share(v, 0.10)

    fig, axes = plt.subplots(1, 2, figsize=(15, 6.5))
    axes[0].plot(x, y, linewidth=2.6, label="merchant weekly volume", color="#3E6FB0")
    axes[0].plot([0, 1], [0, 1], "--", color="gray", linewidth=1.8, label="equality")
    axes[0].set_title(f"Lorenz Curve: Merchant Volume Concentration (Gini={g:.3f})")
    axes[0].set_xlabel("cumulative share of merchants")
    axes[0].set_ylabel("cumulative share of volume")
    axes[0].legend(loc="upper left")

    bars = pd.DataFrame(
        {"bucket": ["top1%", "top5%", "top10%"], "share": [t1, t5, t10]}
    )
    sns.barplot(data=bars, x="bucket", y="share", color="#D0814F", ax=axes[1])
    axes[1].set_title("Top-k Share of Merchant Volume")
    axes[1].set_xlabel("")
    axes[1].set_ylabel("share")
    axes[1].set_ylim(0, 1)
    for i, val in enumerate(bars["share"]):
        axes[1].text(i, val + 0.015, f"{val:.1%}", ha="center", va="bottom", fontsize=11)

    plt.tight_layout()
    plt.savefig(OUT_DIR / "08_merchant_heavytail_concentration.png")
    plt.close()


def plot_09_class_mix_size_country(cx: duckdb.DuckDBPyConnection) -> None:
    q_mc = f"""
    SELECT
      merchant_id,
      primary_demand_class AS demand_class,
      weekly_volume_total_expected::DOUBLE AS weekly_volume_total_expected
    FROM {scan(BASE_5A, 'merchant_class_profile')}
    """
    mc = cx.execute(q_mc).fetchdf()

    mc["size_tier"] = pd.qcut(
        mc["weekly_volume_total_expected"],
        q=4,
        labels=["micro", "small", "mid", "large"],
        duplicates="drop",
    )
    left = (
        mc.groupby(["size_tier", "demand_class"], as_index=False, observed=False)["merchant_id"]
        .count()
        .rename(columns={"merchant_id": "n"})
    )
    left["share"] = left["n"] / left.groupby("size_tier", observed=False)["n"].transform("sum")
    left_p = left.pivot(index="size_tier", columns="demand_class", values="share").fillna(0.0)

    q_home = f"""
    WITH p AS (
      SELECT merchant_id, legal_country_iso, sum(weekly_volume_expected) AS vol
      FROM {scan(BASE_5A, 'merchant_zone_profile')}
      WHERE demand_subclass LIKE '%primary_zone%'
      GROUP BY 1,2
    ),
    r AS (
      SELECT
        merchant_id,
        legal_country_iso,
        vol,
        row_number() OVER (PARTITION BY merchant_id ORDER BY vol DESC, legal_country_iso) AS rn
      FROM p
    )
    SELECT merchant_id, legal_country_iso
    FROM r
    WHERE rn = 1
    """
    home = cx.execute(q_home).fetchdf()
    mc2 = mc.merge(home, on="merchant_id", how="left")
    top_countries = (
        mc2.groupby("legal_country_iso", as_index=False)["weekly_volume_total_expected"]
        .sum()
        .sort_values("weekly_volume_total_expected", ascending=False)
        .head(6)["legal_country_iso"]
        .tolist()
    )
    right = mc2[mc2["legal_country_iso"].isin(top_countries)].copy()
    right = (
        right.groupby(["legal_country_iso", "demand_class"], as_index=False)["weekly_volume_total_expected"]
        .sum()
        .rename(columns={"weekly_volume_total_expected": "vol"})
    )
    right["share"] = right["vol"] / right.groupby("legal_country_iso")["vol"].transform("sum")
    right_p = right.pivot(index="legal_country_iso", columns="demand_class", values="share").fillna(0.0)

    cls_order = [c for c in _channel_order() if c in left_p.columns or c in right_p.columns]
    palette = sns.color_palette("tab10", n_colors=max(8, len(cls_order)))

    fig, axes = plt.subplots(1, 2, figsize=(17, 7), sharey=True)
    left_p = left_p.reindex(columns=cls_order, fill_value=0.0)
    left_p.plot(kind="bar", stacked=True, ax=axes[0], color=palette, width=0.85, legend=False)
    axes[0].set_title("Class Mix by Merchant Size Tier")
    axes[0].set_xlabel("")
    axes[0].set_ylabel("share")
    axes[0].tick_params(axis="x", rotation=0)

    right_p = right_p.reindex(columns=cls_order, fill_value=0.0)
    right_p.plot(kind="bar", stacked=True, ax=axes[1], color=palette, width=0.85, legend=True)
    axes[1].set_title("Class Mix in Top-Volume Home Countries")
    axes[1].set_xlabel("")
    axes[1].set_ylabel("")
    axes[1].tick_params(axis="x", rotation=30)
    axes[1].legend(title="demand_class", bbox_to_anchor=(1.02, 1), loc="upper left")
    plt.tight_layout()
    plt.savefig(OUT_DIR / "09_class_mix_size_country.png")
    plt.close()


def plot_10_temporal_archetype_map(cx: duckdb.DuckDBPyConnection) -> None:
    q_h = f"""
    SELECT
      demand_class,
      mod(bucket_index, 24) AS hour_local,
      sum(lambda_local_base_class) AS lam
    FROM {scan(BASE_5A, 'class_zone_baseline_local')}
    GROUP BY 1,2
    """
    h = cx.execute(q_h).fetchdf()
    h["share"] = h["lam"] / h.groupby("demand_class")["lam"].transform("sum")
    p = h.pivot(index="demand_class", columns="hour_local", values="share").fillna(0.0)

    q_w = f"""
    WITH b AS (
      SELECT
        demand_class,
        cast(floor(bucket_index / 24) as integer) AS dow,
        sum(lambda_local_base_class) AS lam
      FROM {scan(BASE_5A, 'class_zone_baseline_local')}
      GROUP BY 1,2
    )
    SELECT
      demand_class,
      sum(CASE WHEN dow IN (5,6) THEN lam ELSE 0 END) / sum(lam) AS weekend_share
    FROM b
    GROUP BY 1
    """
    w = cx.execute(q_w).fetchdf().sort_values("weekend_share", ascending=True)

    fig, axes = plt.subplots(1, 2, figsize=(16, 7), gridspec_kw={"width_ratios": [2.3, 1.0]})
    sns.heatmap(
        p.reindex(_channel_order()),
        cmap="magma",
        cbar_kws={"label": "hour share within class"},
        ax=axes[0],
    )
    axes[0].set_title("Class x Hour Temporal Archetype Map")
    axes[0].set_xlabel("local hour")
    axes[0].set_ylabel("demand_class")

    sns.scatterplot(data=w, x="weekend_share", y="demand_class", s=130, color="#4E79A7", ax=axes[1])
    for _, r in w.iterrows():
        axes[1].hlines(r["demand_class"], 0, r["weekend_share"], color="#B0B0B0", linewidth=1.2)
        axes[1].text(r["weekend_share"] + 0.005, r["demand_class"], f"{r['weekend_share']:.3f}", va="center", fontsize=10)
    axes[1].set_xlim(0, max(0.5, float(w["weekend_share"].max() + 0.05)))
    axes[1].set_title("Weekend Share by Class")
    axes[1].set_xlabel("weekend share")
    axes[1].set_ylabel("")
    plt.tight_layout()
    plt.savefig(OUT_DIR / "10_temporal_archetype_map.png")
    plt.close()


def plot_11_tailzone_artifact_macro_shape(cx: duckdb.DuckDBPyConnection) -> None:
    q = f"""
    WITH p AS (
      SELECT
        merchant_id,
        legal_country_iso,
        tzid,
        max(CASE WHEN demand_subclass LIKE '%primary_zone%' THEN 1 ELSE 0 END) AS is_primary,
        max(CASE WHEN demand_subclass LIKE '%secondary_zone%' THEN 1 ELSE 0 END) AS is_secondary,
        sum(weekly_volume_expected) AS weekly_total
      FROM {scan(BASE_5A, 'merchant_zone_profile')}
      GROUP BY 1,2,3
    ),
    b AS (
      SELECT
        merchant_id,
        legal_country_iso,
        tzid,
        mod(bucket_index, 24) AS hour_local,
        sum(lambda_local_base) AS lam
      FROM {scan(BASE_5A, 'merchant_zone_baseline_local')}
      GROUP BY 1,2,3,4
    ),
    j AS (
      SELECT
        b.hour_local,
        b.lam,
        p.weekly_total,
        p.is_primary,
        p.is_secondary
      FROM b
      JOIN p USING(merchant_id, legal_country_iso, tzid)
    )
    SELECT
      hour_local,
      sum(lam) AS all_zones,
      sum(CASE WHEN weekly_total > 1.0 THEN lam ELSE 0 END) AS nontrivial_tz,
      sum(CASE WHEN (is_primary = 1 OR is_secondary = 1) THEN lam ELSE 0 END) AS primary_secondary
    FROM j
    GROUP BY 1
    ORDER BY 1
    """
    df = cx.execute(q).fetchdf()
    long = df.melt("hour_local", var_name="surface", value_name="lam")

    fig, axes = plt.subplots(1, 2, figsize=(16, 6.5), sharex=True)
    sns.lineplot(data=long, x="hour_local", y="lam", hue="surface", marker="o", linewidth=2.2, ax=axes[0])
    axes[0].set_title("Hour-of-Day Totals: Raw vs Tail-Filtered Views")
    axes[0].set_xlabel("local hour")
    axes[0].set_ylabel("summed lambda")
    axes[0].legend(title="")

    ratio = (df["primary_secondary"] / df["all_zones"]).clip(0, 1.2)
    sns.barplot(x=df["hour_local"], y=ratio, color="#59A14F", ax=axes[1])
    axes[1].set_title("Trim Ratio: Primary+Secondary / All")
    axes[1].set_xlabel("local hour")
    axes[1].set_ylabel("ratio")
    axes[1].set_ylim(0.94, 1.01)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "11_tailzone_artifact_macro_shape.png")
    plt.close()


def _tz_meta_from_data(tzids: Iterable[str]) -> pd.DataFrame:
    rows = []
    for tz in sorted(set(tzids)):
        try:
            z = ZoneInfo(tz)
            off_start = int(SCENARIO_START_UTC.astimezone(z).utcoffset().total_seconds() // 3600)
            off_end = int(SCENARIO_END_UTC.astimezone(z).utcoffset().total_seconds() // 3600)
            dst_shift = off_end - off_start
        except Exception:
            off_start = 0
            dst_shift = 0
        rows.append((tz, off_start, dst_shift))
    return pd.DataFrame(rows, columns=["tzid", "offset_start_h", "dst_shift_h"])


def plot_12_dst_residual_diagnostics(cx: duckdb.DuckDBPyConnection) -> None:
    tzids = [r[0] for r in cx.execute(f"select distinct tzid from {scan(BASE_5A, 'merchant_zone_scenario_local')}").fetchall()]
    tz_meta = _tz_meta_from_data(tzids)
    cx.register("tz_meta_df", tz_meta)
    cx.execute("create or replace temp table tz_meta as select * from tz_meta_df")

    # Sampled reconstruction for tractable diagnostics.
    q = f"""
    WITH b AS (
      SELECT merchant_id, legal_country_iso, tzid, channel_group, bucket_index, sum(lambda_local_base) AS lb
      FROM {scan(BASE_5A, 'merchant_zone_baseline_local')}
      GROUP BY 1,2,3,4,5
    ),
    s AS (
      SELECT
        merchant_id,
        legal_country_iso,
        tzid,
        channel_group,
        local_horizon_bucket_index,
        lambda_local_scenario AS ls,
        overlay_factor_total AS ov
      FROM {scan(BASE_5A, 'merchant_zone_scenario_local')}
      WHERE mod(hash(merchant_id, legal_country_iso, tzid, local_horizon_bucket_index), 80) = 0
    ),
    j AS (
      SELECT
        s.tzid,
        DATE '2026-01-01' + CAST(floor(s.local_horizon_bucket_index / 24) AS INTEGER) AS local_date,
        abs(s.ls - b.lb * s.ov) AS err
      FROM s
      JOIN tz_meta t USING(tzid)
      JOIN b
        ON b.merchant_id = s.merchant_id
       AND b.legal_country_iso = s.legal_country_iso
       AND b.tzid = s.tzid
       AND b.channel_group = s.channel_group
       AND b.bucket_index = mod(s.local_horizon_bucket_index + t.offset_start_h + {WEEK_ALIGNMENT_SHIFT} + 168000, 168)
    )
    SELECT
      tzid,
      local_date,
      avg(CASE WHEN err > 1e-6 THEN 1 ELSE 0 END) AS mismatch_rate,
      avg(err) AS mae,
      count(*) AS n
    FROM j
    GROUP BY 1,2
    """
    daily = cx.execute(q).fetchdf()

    if daily.empty:
        return

    tz_rank = (
        daily.groupby("tzid", as_index=False)["n"]
        .sum()
        .sort_values("n", ascending=False)
        .head(12)["tzid"]
        .tolist()
    )
    dsub = daily[daily["tzid"].isin(tz_rank)].copy()
    dsub = dsub[dsub["local_date"] >= pd.Timestamp("2026-03-01")]
    hm = dsub.pivot(index="tzid", columns="local_date", values="mismatch_rate").fillna(0.0)
    hm = hm.reindex(tz_rank)

    tz_rate = (
        daily.groupby("tzid", as_index=False)["mismatch_rate"]
        .mean()
        .merge(tz_meta[["tzid", "dst_shift_h"]], on="tzid", how="left")
    )
    tz_rate["dst_shift_h"] = tz_rate["dst_shift_h"].fillna(0).astype(int)
    rho = float(tz_rate["mismatch_rate"].corr(tz_rate["dst_shift_h"], method="spearman"))

    fig, axes = plt.subplots(1, 2, figsize=(18, 7), gridspec_kw={"width_ratios": [2.3, 1.0]})
    sns.heatmap(
        hm,
        cmap="Reds",
        vmin=0,
        vmax=max(0.02, float(hm.to_numpy().max())),
        cbar_kws={"label": "mismatch rate"},
        ax=axes[0],
    )
    axes[0].set_title("DST Residual Mismatch by Timezone and Date (sample)")
    axes[0].set_xlabel("local date")
    axes[0].set_ylabel("tzid")

    sns.boxplot(data=tz_rate, x="dst_shift_h", y="mismatch_rate", color="#C44E52", ax=axes[1])
    sns.stripplot(
        data=tz_rate,
        x="dst_shift_h",
        y="mismatch_rate",
        color="black",
        alpha=0.55,
        size=4,
        ax=axes[1],
    )
    axes[1].set_title("Mismatch Rate vs DST Shift Group")
    axes[1].set_xlabel("DST shift over horizon (hours)")
    axes[1].set_ylabel("timezone mismatch rate")
    axes[1].text(0.02, 0.98, f"Spearman rho={rho:.3f}", transform=axes[1].transAxes, va="top")

    plt.tight_layout()
    plt.savefig(OUT_DIR / "12_dst_residual_diagnostics.png")
    plt.close()


def plot_13_channel_group_realization(cx: duckdb.DuckDBPyConnection) -> None:
    q = f"""
    SELECT
      channel_group,
      sum(lambda_local_base_class) AS lam
    FROM {scan(BASE_5A, 'class_zone_baseline_local')}
    GROUP BY 1
    """
    df = cx.execute(q).fetchdf()
    df["share"] = df["lam"] / df["lam"].sum()
    df = df.sort_values("share", ascending=False)

    fig, ax = plt.subplots(figsize=(8.5, 6))
    sns.barplot(data=df, x="channel_group", y="share", color="#4E79A7", ax=ax)
    ax.set_title("Observed Channel-Group Realization in 5A")
    ax.set_xlabel("channel_group")
    ax.set_ylabel("share of baseline mass")
    ax.set_ylim(0, 1.05)
    for p, v in zip(ax.patches, df["share"]):
        ax.annotate(f"{v:.2%}", (p.get_x() + p.get_width() / 2, p.get_height()), ha="center", va="bottom", fontsize=12)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "13_channel_group_realization.png")
    plt.close()


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    style()
    cx = duckdb.connect()
    cx.execute("PRAGMA threads=8")

    plot_01_zero_volume_site_contingency(cx)
    plot_02_active_zone_breadth_vs_volume(cx)
    plot_03_priors_shares_counts_transition(cx)
    plot_04_multicollinearity_diagnostics(cx)
    plot_05_driver_dominance_raw_vs_log(cx)
    plot_06_country_sparsity_elasticity(cx)
    plot_07_share_sum_country_invariance(cx)
    plot_08_merchant_heavytail_concentration(cx)
    plot_09_class_mix_size_country(cx)
    plot_10_temporal_archetype_map(cx)
    plot_11_tailzone_artifact_macro_shape(cx)
    plot_12_dst_residual_diagnostics(cx)
    plot_13_channel_group_realization(cx)

    print("plots_written", len(list(OUT_DIR.glob("*.png"))))


if __name__ == "__main__":
    main()
