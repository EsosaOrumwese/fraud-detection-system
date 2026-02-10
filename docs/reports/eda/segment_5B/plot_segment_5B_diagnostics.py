from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, Tuple

import duckdb
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

RUN_BASE = Path(r"runs/local_full_run-5/c25a2675fbfbacd952b13bb594880e92/data")
BASE_5B = RUN_BASE / "layer2/5B"
BASE_5A = RUN_BASE / "layer2/5A"
OUT_DIR = Path(r"docs/reports/eda/segment_5B/plots")

SAMPLE_KEY_MOD = 1000  # ~0.1% key sample for duplication/conservation plots
SAMPLE_DST_MOD = 200   # ~0.5% arrival sample for DST diagnostics


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


def topk_curve(values: np.ndarray, k_grid: np.ndarray) -> np.ndarray:
    vals = np.sort(values)[::-1]
    csum = np.cumsum(vals)
    total = float(csum[-1]) if csum.size else 1.0
    n = len(vals)
    out = []
    for k in k_grid:
        kk = max(1, int(np.ceil(n * k)))
        out.append(float(csum[kk - 1] / total))
    return np.array(out)


def lorenz(values: np.ndarray) -> Tuple[np.ndarray, np.ndarray, float]:
    v = np.sort(values)
    if v.size == 0:
        return np.array([0.0, 1.0]), np.array([0.0, 1.0]), 0.0
    cum_y = np.concatenate([[0.0], np.cumsum(v) / np.sum(v)])
    cum_x = np.linspace(0.0, 1.0, len(cum_y))
    gini = 1.0 - 2.0 * np.trapezoid(cum_y, cum_x)
    return cum_x, cum_y, float(gini)


def plot_01_duplicate_key_anatomy(cx: duckdb.DuckDBPyConnection) -> None:
    q_s2 = f"""
    WITH k AS (
      SELECT merchant_id, zone_representation, channel_group, bucket_index, count(*) AS comp_n
      FROM {scan(BASE_5B, 's2_realised_intensity')}
      GROUP BY 1,2,3,4
    )
    SELECT comp_n, count(*) AS n_keys
    FROM k
    GROUP BY 1
    ORDER BY 1
    """
    q_s3 = f"""
    WITH k AS (
      SELECT merchant_id, zone_representation, channel_group, bucket_index, count(*) AS comp_n
      FROM {scan(BASE_5B, 's3_bucket_counts')}
      GROUP BY 1,2,3,4
    )
    SELECT comp_n, count(*) AS n_keys
    FROM k
    GROUP BY 1
    ORDER BY 1
    """
    s2 = cx.execute(q_s2).fetchdf()
    s3 = cx.execute(q_s3).fetchdf()

    fig, axes = plt.subplots(1, 2, figsize=(15, 6), sharey=True)
    sns.barplot(data=s2, x="comp_n", y="n_keys", color="#4E79A7", ax=axes[0])
    sns.barplot(data=s3, x="comp_n", y="n_keys", color="#E15759", ax=axes[1])
    axes[0].set_title("S2 Duplicate-Key Anatomy")
    axes[1].set_title("S3 Duplicate-Key Anatomy")
    axes[0].set_xlabel("components per logical key")
    axes[1].set_xlabel("components per logical key")
    axes[0].set_ylabel("number of keys (log scale)")
    axes[1].set_ylabel("")
    axes[0].set_yscale("log")
    axes[1].set_yscale("log")
    plt.tight_layout()
    plt.savefig(OUT_DIR / "01_duplicate_key_anatomy.png")
    plt.close()


def plot_02_conservation_pre_post(cx: duckdb.DuckDBPyConnection) -> None:
    q = f"""
    WITH s3_raw AS (
      SELECT merchant_id, zone_representation, channel_group, bucket_index, count_N,
             hash(merchant_id, zone_representation, channel_group, bucket_index) AS h
      FROM {scan(BASE_5B, 's3_bucket_counts')}
    ),
    arr AS (
      SELECT merchant_id, zone_representation, channel_group, bucket_index, count(*) AS arr_n,
             hash(merchant_id, zone_representation, channel_group, bucket_index) AS h
      FROM {scan(BASE_5B, 'arrival_events')}
      GROUP BY 1,2,3,4
    ),
    s3_agg AS (
      SELECT merchant_id, zone_representation, channel_group, bucket_index, sum(count_N) AS s3_n,
             hash(merchant_id, zone_representation, channel_group, bucket_index) AS h
      FROM s3_raw
      GROUP BY 1,2,3,4
    ),
    pre AS (
      SELECT r.count_N::DOUBLE AS s3_n, a.arr_n::DOUBLE AS arr_n
      FROM s3_raw r
      JOIN arr a USING(merchant_id, zone_representation, channel_group, bucket_index)
      WHERE mod(r.h, {SAMPLE_KEY_MOD}) = 0
    ),
    post AS (
      SELECT s.s3_n::DOUBLE AS s3_n, a.arr_n::DOUBLE AS arr_n
      FROM s3_agg s
      JOIN arr a USING(merchant_id, zone_representation, channel_group, bucket_index)
      WHERE mod(s.h, {SAMPLE_KEY_MOD}) = 0
    )
    SELECT 'pre' AS stage, * FROM pre
    UNION ALL
    SELECT 'post' AS stage, * FROM post
    """
    df = cx.execute(q).fetchdf()
    pre = df[df["stage"] == "pre"]
    post = df[df["stage"] == "post"]

    fig, axes = plt.subplots(1, 2, figsize=(15, 6), sharex=True, sharey=True)
    axes[0].hexbin(pre["arr_n"], pre["s3_n"], gridsize=55, bins="log", cmap="Blues", mincnt=1)
    axes[1].hexbin(post["arr_n"], post["s3_n"], gridsize=55, bins="log", cmap="Greens", mincnt=1)

    mx = float(max(df["arr_n"].max(), df["s3_n"].max()))
    for ax in axes:
        ax.plot([0, mx], [0, mx], "--", color="gray", linewidth=1.8)
        ax.set_xlim(0, mx)
        ax.set_ylim(0, mx)
        ax.set_xlabel("arrivals by key")
    axes[0].set_ylabel("S3 count by key")
    axes[0].set_title("Before Aggregation (Component Rows)")
    axes[1].set_title("After Aggregation (Logical Keys)")

    pre_mis = float((pre["arr_n"] != pre["s3_n"]).mean())
    post_mis = float((post["arr_n"] != post["s3_n"]).mean())
    axes[0].text(0.02, 0.97, f"mismatch rate={pre_mis:.2%}", transform=axes[0].transAxes, va="top")
    axes[1].text(0.02, 0.97, f"mismatch rate={post_mis:.2%}", transform=axes[1].transAxes, va="top")

    plt.tight_layout()
    plt.savefig(OUT_DIR / "02_conservation_pre_post_scatter.png")
    plt.close()


def plot_03_conservation_residuals(cx: duckdb.DuckDBPyConnection) -> None:
    q = f"""
    WITH s3_raw AS (
      SELECT merchant_id, zone_representation, channel_group, bucket_index, count_N,
             hash(merchant_id, zone_representation, channel_group, bucket_index) AS h
      FROM {scan(BASE_5B, 's3_bucket_counts')}
    ),
    arr AS (
      SELECT merchant_id, zone_representation, channel_group, bucket_index, count(*) AS arr_n
      FROM {scan(BASE_5B, 'arrival_events')}
      GROUP BY 1,2,3,4
    ),
    s3_agg AS (
      SELECT merchant_id, zone_representation, channel_group, bucket_index, sum(count_N) AS s3_n,
             hash(merchant_id, zone_representation, channel_group, bucket_index) AS h
      FROM s3_raw
      GROUP BY 1,2,3,4
    ),
    pre AS (
      SELECT (r.count_N - a.arr_n)::DOUBLE AS residual
      FROM s3_raw r JOIN arr a USING(merchant_id, zone_representation, channel_group, bucket_index)
      WHERE mod(r.h, {SAMPLE_KEY_MOD}) = 0
    ),
    post AS (
      SELECT (s.s3_n - a.arr_n)::DOUBLE AS residual
      FROM s3_agg s JOIN arr a USING(merchant_id, zone_representation, channel_group, bucket_index)
      WHERE mod(s.h, {SAMPLE_KEY_MOD}) = 0
    )
    SELECT 'pre' AS stage, residual FROM pre
    UNION ALL
    SELECT 'post' AS stage, residual FROM post
    """
    df = cx.execute(q).fetchdf()
    pre = df[df["stage"] == "pre"]["residual"].to_numpy()
    post = df[df["stage"] == "post"]["residual"].to_numpy()

    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    pre_clip = np.clip(pre, -50, 50)
    axes[0].hist(pre_clip, bins=101, color="#4E79A7", alpha=0.9)
    axes[0].set_title("Pre-Aggregation Residuals (clipped to [-50, 50])")
    axes[0].set_xlabel("S3 count_N - arrivals")
    axes[0].set_ylabel("frequency")
    axes[0].set_yscale("log")

    def ecdf(a: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        x = np.sort(np.abs(a))
        y = np.arange(1, len(x) + 1) / len(x)
        return x, y

    x1, y1 = ecdf(pre)
    x2, y2 = ecdf(post)
    axes[1].plot(x1, y1, label="pre")
    axes[1].plot(x2, y2, label="post")
    axes[1].set_xscale("symlog", linthresh=1)
    axes[1].set_title("ECDF of Absolute Residual")
    axes[1].set_xlabel("|residual|")
    axes[1].set_ylabel("ECDF")
    axes[1].legend()

    plt.tight_layout()
    plt.savefig(OUT_DIR / "03_conservation_residuals.png")
    plt.close()


def _dst_sample_base(cx: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    q = f"""
    WITH b AS (
      SELECT
        merchant_id,
        bucket_index,
        arrival_seq,
        tzid_primary,
        try_strptime(ts_utc, '%Y-%m-%dT%H:%M:%S.%fZ') AS ts_utc_ts,
        try_strptime(ts_local_primary, '%Y-%m-%dT%H:%M:%S.%fZ') AS ts_local_obs,
        hash(merchant_id, bucket_index, arrival_seq) AS h
      FROM {scan(BASE_5B, 'arrival_events')}
    )
    SELECT
      tzid_primary,
      ts_utc_ts,
      ts_local_obs,
      ((ts_utc_ts AT TIME ZONE 'UTC') AT TIME ZONE tzid_primary) AS ts_local_exp,
      date_diff('second', ((ts_utc_ts AT TIME ZONE 'UTC') AT TIME ZONE tzid_primary), ts_local_obs) AS diff_sec
    FROM b
    WHERE mod(h, {SAMPLE_DST_MOD}) = 0
      AND tzid_primary IS NOT NULL
      AND ts_utc_ts IS NOT NULL
      AND ts_local_obs IS NOT NULL
    """
    return cx.execute(q).fetchdf()


def plot_04_dst_offset_distribution(cx: duckdb.DuckDBPyConnection) -> None:
    df = _dst_sample_base(cx)
    off = df.groupby("diff_sec", as_index=False).size().rename(columns={"size": "n"}).sort_values("diff_sec")

    plt.figure(figsize=(11, 6))
    ax = sns.barplot(data=off, x="diff_sec", y="n", color="#E15759")
    ax.set_title("DST Offset Distribution (Observed local - Expected local)")
    ax.set_xlabel("offset seconds")
    ax.set_ylabel("count (sample)")
    ax.ticklabel_format(axis="y", style="sci", scilimits=(0, 0))
    for p in ax.patches:
        h = p.get_height()
        if h > 0:
            ax.annotate(f"{int(h):,}", (p.get_x() + p.get_width() / 2, h), ha="center", va="bottom", fontsize=10)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "04_dst_offset_distribution.png")
    plt.close()


def plot_05_dst_date_tz_heatmap(cx: duckdb.DuckDBPyConnection) -> None:
    df = _dst_sample_base(cx)
    df["local_date_exp"] = pd.to_datetime(df["ts_local_exp"]).dt.date
    grp_total = df.groupby(["tzid_primary", "local_date_exp"], as_index=False).size().rename(columns={"size": "n_total"})
    grp_mis = (
        df[df["diff_sec"] != 0]
        .groupby(["tzid_primary", "local_date_exp"], as_index=False)
        .size()
        .rename(columns={"size": "n_mis"})
    )
    g = grp_total.merge(grp_mis, on=["tzid_primary", "local_date_exp"], how="left").fillna({"n_mis": 0})
    g["mis_rate"] = g["n_mis"] / g["n_total"]

    top_tz = (
        g.groupby("tzid_primary", as_index=False)["n_mis"]
        .sum()
        .sort_values("n_mis", ascending=False)
        .head(12)["tzid_primary"]
        .tolist()
    )
    g = g[g["tzid_primary"].isin(top_tz)]
    g = g[g["n_mis"] > 0]

    if g.empty:
        return

    pt = g.pivot(index="tzid_primary", columns="local_date_exp", values="mis_rate").fillna(0.0)
    pt = pt.loc[top_tz]

    plt.figure(figsize=(16, 7))
    ax = sns.heatmap(pt, cmap="Reds", vmin=0.0, vmax=max(0.01, float(pt.to_numpy().max())), cbar_kws={"label": "mismatch rate"})
    ax.set_title("DST Mismatch Rate by Timezone and Date (sample)")
    ax.set_xlabel("date")
    ax.set_ylabel("tzid_primary")
    ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(OUT_DIR / "05_dst_mismatch_date_tz_heatmap.png")
    plt.close()


def plot_06_dst_hour_shift_matrix(cx: duckdb.DuckDBPyConnection) -> None:
    df = _dst_sample_base(cx)
    df = df[df["diff_sec"] != 0].copy()
    if df.empty:
        return

    df["hour_exp"] = pd.to_datetime(df["ts_local_exp"]).dt.hour
    df["hour_obs"] = pd.to_datetime(df["ts_local_obs"]).dt.hour
    mat = (
        df.groupby(["hour_exp", "hour_obs"], as_index=False)
        .size()
        .pivot(index="hour_exp", columns="hour_obs", values="size")
        .fillna(0)
    )
    all_hours = list(range(24))
    mat = mat.reindex(index=all_hours, columns=all_hours, fill_value=0)

    plt.figure(figsize=(10, 8))
    ax = sns.heatmap(mat, cmap="magma", norm=matplotlib.colors.LogNorm(vmin=1, vmax=max(1, float(mat.to_numpy().max()))), cbar_kws={"label": "count (log)"})
    ax.set_title("DST Mismatch Hour-Shift Matrix (sample)")
    ax.set_xlabel("observed local hour")
    ax.set_ylabel("expected local hour")
    plt.tight_layout()
    plt.savefig(OUT_DIR / "06_dst_hour_shift_matrix.png")
    plt.close()


def plot_07_routing_temporal_profile(cx: duckdb.DuckDBPyConnection) -> None:
    q = f"""
    SELECT
      is_virtual,
      CAST(substr(ts_local_primary, 12, 2) AS INTEGER) AS hour_local,
      count(*) AS n
    FROM {scan(BASE_5B, 'arrival_events')}
    GROUP BY 1,2
    """
    df = cx.execute(q).fetchdf()
    df["route"] = np.where(df["is_virtual"], "virtual", "physical")
    df["share"] = df["n"] / df.groupby("route")["n"].transform("sum")

    plt.figure(figsize=(12, 6))
    sns.lineplot(data=df, x="hour_local", y="share", hue="route", marker="o", linewidth=2.5)
    plt.title("Physical vs Virtual Hour-of-Day Profile")
    plt.xlabel("local hour")
    plt.ylabel("share within routing class")
    plt.xlim(0, 23)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "07_routing_temporal_profile.png")
    plt.close()


def plot_08_weekend_share_alignment(cx: duckdb.DuckDBPyConnection) -> None:
    q_expected = f"""
    WITH s2 AS (
      SELECT bucket_index, sum(lambda_realised) AS lam
      FROM {scan(BASE_5B, 's2_realised_intensity')}
      GROUP BY 1
    )
    SELECT
      sum(CASE WHEN g.is_weekend THEN s2.lam ELSE 0 END) / sum(s2.lam) AS expected_weekend
    FROM s2
    JOIN {scan(BASE_5B, 's1_time_grid')} g USING(bucket_index)
    """
    expected = float(cx.execute(q_expected).fetchone()[0])

    q_observed = f"""
    WITH a AS (
      SELECT is_virtual,
             CAST(substr(ts_local_primary, 1, 10) AS DATE) AS local_date
      FROM {scan(BASE_5B, 'arrival_events')}
    )
    SELECT
      CASE WHEN is_virtual THEN 'observed_virtual' ELSE 'observed_physical' END AS metric,
      avg(CASE WHEN date_part('dayofweek', local_date) IN (0,6) THEN 1 ELSE 0 END) AS weekend_share
    FROM a
    GROUP BY 1
    UNION ALL
    SELECT 'observed_overall' AS metric,
           avg(CASE WHEN date_part('dayofweek', local_date) IN (0,6) THEN 1 ELSE 0 END) AS weekend_share
    FROM a
    """
    obs = cx.execute(q_observed).fetchdf()
    all_rows = pd.concat(
        [
            pd.DataFrame({"metric": ["expected_from_intensity"], "weekend_share": [expected]}),
            obs,
        ],
        ignore_index=True,
    )
    order = ["expected_from_intensity", "observed_overall", "observed_physical", "observed_virtual"]
    all_rows["metric"] = pd.Categorical(all_rows["metric"], categories=order, ordered=True)
    all_rows = all_rows.sort_values("metric")

    plt.figure(figsize=(11, 6))
    ax = sns.barplot(data=all_rows, x="metric", y="weekend_share", color="#59A14F")
    ax.set_title("Weekend Share: Expected vs Observed Routing Views")
    ax.set_xlabel("")
    ax.set_ylabel("weekend share")
    ax.set_ylim(0, max(0.36, float(all_rows["weekend_share"].max() * 1.15)))
    for p, v in zip(ax.patches, all_rows["weekend_share"]):
        ax.annotate(f"{v:.4f}", (p.get_x() + p.get_width() / 2, p.get_height()), ha="center", va="bottom", fontsize=10)
    plt.xticks(rotation=15)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "08_weekend_share_alignment.png")
    plt.close()


def plot_09_site_edge_lorenz(cx: duckdb.DuckDBPyConnection) -> None:
    q_site = f"""
    SELECT site_id, count(*) AS n
    FROM {scan(BASE_5B, 'arrival_events')}
    WHERE is_virtual = FALSE AND site_id IS NOT NULL
    GROUP BY 1
    """
    q_edge = f"""
    SELECT edge_id, count(*) AS n
    FROM {scan(BASE_5B, 'arrival_events')}
    WHERE is_virtual = TRUE AND edge_id IS NOT NULL
    GROUP BY 1
    """
    site = cx.execute(q_site).fetchdf()["n"].to_numpy()
    edge = cx.execute(q_edge).fetchdf()["n"].to_numpy()

    x1, y1, g1 = lorenz(site)
    x2, y2, g2 = lorenz(edge)

    plt.figure(figsize=(8.5, 8.5))
    plt.plot(x1, y1, linewidth=2.5, label=f"sites (Gini={g1:.3f})", color="#4E79A7")
    plt.plot(x2, y2, linewidth=2.5, label=f"edges (Gini={g2:.3f})", color="#E15759")
    plt.plot([0, 1], [0, 1], "--", color="gray", linewidth=1.8, label="equality")
    plt.title("Lorenz Curves: Physical Sites vs Virtual Edges")
    plt.xlabel("cumulative share of entities")
    plt.ylabel("cumulative share of arrivals")
    plt.legend()
    plt.tight_layout()
    plt.savefig(OUT_DIR / "09_site_edge_lorenz.png")
    plt.close()


def plot_10_topk_concentration_curves(cx: duckdb.DuckDBPyConnection) -> None:
    q = f"""
    WITH site AS (
      SELECT count(*) AS n, 'site' AS grp
      FROM {scan(BASE_5B, 'arrival_events')}
      WHERE is_virtual = FALSE AND site_id IS NOT NULL
      GROUP BY site_id
    ),
    edge AS (
      SELECT count(*) AS n, 'edge' AS grp
      FROM {scan(BASE_5B, 'arrival_events')}
      WHERE is_virtual = TRUE AND edge_id IS NOT NULL
      GROUP BY edge_id
    ),
    merch AS (
      SELECT count(*) AS n, 'merchant' AS grp
      FROM {scan(BASE_5B, 'arrival_events')}
      GROUP BY merchant_id
    ),
    tz AS (
      SELECT count(*) AS n, 'timezone' AS grp
      FROM {scan(BASE_5B, 'arrival_events')}
      GROUP BY tzid_primary
    )
    SELECT * FROM site
    UNION ALL SELECT * FROM edge
    UNION ALL SELECT * FROM merch
    UNION ALL SELECT * FROM tz
    """
    df = cx.execute(q).fetchdf()

    k_grid = np.linspace(0.001, 0.20, 120)
    plt.figure(figsize=(11, 7))
    palette = {"site": "#4E79A7", "edge": "#E15759", "merchant": "#59A14F", "timezone": "#B07AA1"}
    for grp, gdf in df.groupby("grp"):
        vals = gdf["n"].to_numpy(dtype=float)
        y = topk_curve(vals, k_grid)
        plt.plot(k_grid * 100.0, y, linewidth=2.2, label=grp, color=palette.get(grp))

    plt.title("Top-k Concentration Curves Across 5B Surfaces")
    plt.xlabel("top k% of entities")
    plt.ylabel("cumulative share of arrivals")
    plt.xlim(0.1, 20)
    plt.ylim(0, 1)
    plt.legend(title="surface")
    plt.tight_layout()
    plt.savefig(OUT_DIR / "10_topk_concentration_curves.png")
    plt.close()


def plot_11_merchant_tail_intensity_vs_arrivals(cx: duckdb.DuckDBPyConnection) -> None:
    q = f"""
    WITH arr AS (
      SELECT merchant_id, count(*)::DOUBLE AS arrivals
      FROM {scan(BASE_5B, 'arrival_events')}
      GROUP BY 1
    ),
    s2 AS (
      SELECT merchant_id, sum(lambda_realised)::DOUBLE AS sum_lambda
      FROM {scan(BASE_5B, 's2_realised_intensity')}
      GROUP BY 1
    )
    SELECT a.merchant_id, a.arrivals, s2.sum_lambda
    FROM arr a
    JOIN s2 USING(merchant_id)
    """
    df = cx.execute(q).fetchdf()
    corr = float(df[["arrivals", "sum_lambda"]].corr().iloc[0, 1])

    mn = float(min(df["arrivals"].min(), df["sum_lambda"].min()))
    mx = float(max(df["arrivals"].max(), df["sum_lambda"].max()))

    plt.figure(figsize=(8.5, 8.5))
    plt.scatter(df["sum_lambda"], df["arrivals"], s=28, alpha=0.6, color="#4E79A7")
    plt.plot([mn, mx], [mn, mx], "--", color="gray", linewidth=1.8)
    plt.xscale("log")
    plt.yscale("log")
    plt.title("Merchant Tail: Intensity vs Realised Arrivals")
    plt.xlabel("sum lambda_realised (S2)")
    plt.ylabel("arrivals (S4)")
    plt.text(0.02, 0.98, f"corr={corr:.6f}", transform=plt.gca().transAxes, va="top")
    plt.tight_layout()
    plt.savefig(OUT_DIR / "11_merchant_tail_intensity_vs_arrivals.png")
    plt.close()


def plot_12_timezone_concentration_profile(cx: duckdb.DuckDBPyConnection) -> None:
    q = f"""
    SELECT tzid_primary, count(*)::DOUBLE AS n
    FROM {scan(BASE_5B, 'arrival_events')}
    GROUP BY 1
    ORDER BY n DESC
    """
    df = cx.execute(q).fetchdf()
    df["cum_share"] = df["n"].cumsum() / df["n"].sum()
    df["rank_pct"] = (np.arange(1, len(df) + 1) / len(df)) * 100.0

    top10_share = float(df["n"].head(10).sum() / df["n"].sum())

    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    axes[0].plot(df["rank_pct"], df["cum_share"], color="#3E6FB0", linewidth=2.5)
    axes[0].set_title("Timezone Concentration Profile")
    axes[0].set_xlabel("rank percentile of timezones")
    axes[0].set_ylabel("cumulative arrival share")
    axes[0].axhline(top10_share, color="red", linestyle="--", linewidth=1.6)
    axes[0].text(0.02, 0.92, f"top10 share={top10_share:.2%}", transform=axes[0].transAxes)

    top = df.head(12).copy()
    sns.barplot(data=top, x="tzid_primary", y="n", color="#B07AA1", ax=axes[1])
    axes[1].set_title("Top Timezones by Arrivals")
    axes[1].set_xlabel("")
    axes[1].set_ylabel("arrivals")
    axes[1].tick_params(axis="x", rotation=60)

    plt.tight_layout()
    plt.savefig(OUT_DIR / "12_timezone_concentration_profile.png")
    plt.close()


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    style()
    cx = duckdb.connect()

    plot_01_duplicate_key_anatomy(cx)
    plot_02_conservation_pre_post(cx)
    plot_03_conservation_residuals(cx)
    plot_04_dst_offset_distribution(cx)
    plot_05_dst_date_tz_heatmap(cx)
    plot_06_dst_hour_shift_matrix(cx)
    plot_07_routing_temporal_profile(cx)
    plot_08_weekend_share_alignment(cx)
    plot_09_site_edge_lorenz(cx)
    plot_10_topk_concentration_curves(cx)
    plot_11_merchant_tail_intensity_vs_arrivals(cx)
    plot_12_timezone_concentration_profile(cx)

    cx.close()
    print("plots_written", 12)


if __name__ == "__main__":
    main()
