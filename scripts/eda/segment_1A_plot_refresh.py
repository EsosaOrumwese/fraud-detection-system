from __future__ import annotations

import json
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import polars as pl
import seaborn as sns
from matplotlib.ticker import FuncFormatter

matplotlib.use("Agg")

RUN_ROOT = Path("runs/local_full_run-5/c25a2675fbfbacd952b13bb594880e92/data/layer1/1A")
OUT_PLOTS = Path("docs/reports/reports/eda/segment_1A/plots")


def _set_theme() -> None:
    sns.set_theme(style="whitegrid")
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": "#D2D6DC",
            "grid.color": "#E5E7EB",
            "grid.linestyle": "-",
            "grid.alpha": 1.0,
            "axes.titlesize": 16,
            "axes.titleweight": "semibold",
            "axes.labelsize": 12,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "legend.fontsize": 10,
            "savefig.dpi": 170,
            "figure.dpi": 170,
        }
    )


def _fmt_int(x: float, _: int) -> str:
    return f"{int(x):,}"


def _load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    p_outlet = next((RUN_ROOT / "outlet_catalogue").rglob("*.parquet"))
    p_cand = next((RUN_ROOT / "s3_candidate_set").rglob("*.parquet"))
    p_mem = next((RUN_ROOT / "s6" / "membership").rglob("*.parquet"))
    return (
        pl.read_parquet(str(p_outlet)).to_pandas(),
        pl.read_parquet(str(p_cand)).to_pandas(),
        pl.read_parquet(str(p_mem)).to_pandas(),
    )


def _build_features(
    outlets: pd.DataFrame, cand: pd.DataFrame, mem: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    per_merchant = (
        outlets.groupby("merchant_id", as_index=False)
        .agg(
            outlet_count=("site_id", "size"),
            legal_country_count=("legal_country_iso", "nunique"),
            home_legal_mismatch_rate=("home_country_iso", lambda s: np.nan),  # placeholder
            single_vs_multi_flag=("single_vs_multi_flag", "max"),
        )
        .drop(columns=["home_legal_mismatch_rate"])
    )

    # mismatch rate from full rows per merchant
    mm = (
        (outlets["home_country_iso"] != outlets["legal_country_iso"])
        .groupby(outlets["merchant_id"])
        .mean()
        .reset_index(name="home_legal_mismatch_rate")
    )
    per_merchant = per_merchant.merge(mm, on="merchant_id", how="left")

    cand_all = cand.groupby("merchant_id", as_index=False)["country_iso"].nunique().rename(
        columns={"country_iso": "candidate_count_all"}
    )
    cand_foreign = (
        cand[cand["is_home"] == False]  # noqa: E712
        .groupby("merchant_id", as_index=False)["country_iso"]
        .nunique()
        .rename(columns={"country_iso": "candidate_count_foreign"})
    )
    mem_count = (
        mem.groupby("merchant_id", as_index=False)["country_iso"]
        .nunique()
        .rename(columns={"country_iso": "membership_count"})
    )
    per_merchant = (
        per_merchant.merge(cand_all, on="merchant_id", how="left")
        .merge(cand_foreign, on="merchant_id", how="left")
        .merge(mem_count, on="merchant_id", how="left")
        .fillna(
            {
                "candidate_count_all": 0,
                "candidate_count_foreign": 0,
                "membership_count": 0,
            }
        )
    )

    # Duplicate semantics by merchant-site pair
    pair = (
        outlets.groupby(["merchant_id", "site_id"], as_index=False)
        .agg(
            pair_rows=("legal_country_iso", "size"),
            legal_country_n=("legal_country_iso", "nunique"),
        )
        .sort_values(["merchant_id", "site_id"])
    )
    pair_legal = (
        outlets.groupby(["merchant_id", "site_id", "legal_country_iso"], as_index=False)
        .size()
        .rename(columns={"size": "rows_per_merchant_site_legal"})
    )
    same_country_repeat_pairs = pair_legal[
        pair_legal["rows_per_merchant_site_legal"] > 1
    ][["merchant_id", "site_id"]].drop_duplicates()
    same_country_repeat_pairs["same_country_repeat"] = 1

    pair = pair.merge(same_country_repeat_pairs, on=["merchant_id", "site_id"], how="left").fillna(
        {"same_country_repeat": 0}
    )
    pair["is_duplicate_pair"] = pair["pair_rows"] > 1
    pair["is_cross_country_dup"] = pair["legal_country_n"] > 1
    pair["is_same_country_dup_only"] = (pair["same_country_repeat"] == 1) & (pair["is_cross_country_dup"] == 0)

    dup_stats = (
        pair.groupby("merchant_id", as_index=False)
        .agg(
            site_pairs=("site_id", "size"),
            dup_site_pairs=("is_duplicate_pair", "sum"),
            cross_country_dup_pairs=("is_cross_country_dup", "sum"),
            same_country_dup_only_pairs=("is_same_country_dup_only", "sum"),
            max_legal_country_n=("legal_country_n", "max"),
        )
    )
    dup_stats["dup_pair_rate"] = dup_stats["dup_site_pairs"] / dup_stats["site_pairs"].clip(lower=1)
    dup_stats["cross_country_dup_rate"] = dup_stats["cross_country_dup_pairs"] / dup_stats["site_pairs"].clip(lower=1)
    dup_stats["same_country_dup_only_rate"] = dup_stats["same_country_dup_only_pairs"] / dup_stats["site_pairs"].clip(
        lower=1
    )

    per_merchant = per_merchant.merge(dup_stats, on="merchant_id", how="left").fillna(0)
    return per_merchant, pair, pair_legal


def _plot_1_outlet_hist(per: pd.DataFrame) -> None:
    x = per["outlet_count"].to_numpy()
    fig, ax = plt.subplots(figsize=(8.6, 5.6))
    bins = np.logspace(np.log10(x.min()), np.log10(x.max()), 34)
    ax.hist(x, bins=bins, color="#2A6F97", alpha=0.9, edgecolor="white", linewidth=0.25)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Outlets per merchant (log scale)")
    ax.set_ylabel("Merchant count (log scale)")
    ax.set_title("Outlet Count Distribution (Log-Log Histogram)")
    med, p90 = np.median(x), np.quantile(x, 0.9)
    ax.axvline(med, linestyle="--", color="#E07A5F", linewidth=1.4, label=f"median={med:.0f}")
    ax.axvline(p90, linestyle="--", color="#F2CC8F", linewidth=1.4, label=f"p90={p90:.0f}")
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "1_outlet_hist_loglog.png")
    plt.close(fig)


def _plot_2_ccdf(per: pd.DataFrame) -> None:
    x = np.sort(per["outlet_count"].to_numpy())
    y = 1.0 - np.arange(1, len(x) + 1) / len(x)
    fig, ax = plt.subplots(figsize=(8.6, 5.6))
    ax.loglog(x, y, marker="o", markersize=2.5, linestyle="none", alpha=0.65, color="#1B4332")
    ax.set_xlabel("Outlets per merchant (log scale)")
    ax.set_ylabel("P(X >= x) (log scale)")
    ax.set_title("Outlet Count CCDF (Heavy-Tail View)")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "2_outlet_ccdf_loglog.png")
    plt.close(fig)


def _plot_3_lorenz(per: pd.DataFrame) -> float:
    x = np.sort(per["outlet_count"].to_numpy())
    lorenz_y = np.insert(np.cumsum(x) / x.sum(), 0, 0.0)
    lorenz_x = np.insert(np.arange(1, len(x) + 1) / len(x), 0, 0.0)
    gini = float(1.0 - 2.0 * np.trapezoid(lorenz_y, lorenz_x))
    fig, ax = plt.subplots(figsize=(7.4, 7.2))
    ax.plot(lorenz_x, lorenz_y, linewidth=2.3, color="#264653", label="Lorenz curve")
    ax.plot([0, 1], [0, 1], linestyle="--", color="#B6B8BA", linewidth=1.6, label="Perfect equality")
    ax.set_xlabel("Cumulative share of merchants")
    ax.set_ylabel("Cumulative share of outlets")
    ax.set_title(f"Outlet Concentration (Lorenz Curve, Gini={gini:.3f})")
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "3_lorenz_curve.png")
    plt.close(fig)
    return gini


def _plot_4_topk(per: pd.DataFrame) -> None:
    x = np.sort(per["outlet_count"].to_numpy())[::-1]
    p = np.linspace(1, 100, 100)
    share = np.array([x[: max(1, int(np.ceil(len(x) * q / 100.0)))].sum() / x.sum() for q in p]) * 100.0
    fig, ax = plt.subplots(figsize=(8.6, 5.6))
    ax.plot(p, share, color="#6A4C93", linewidth=2.2)
    for q, c in zip([1, 5, 10], ["#DC2626", "#F59E0B", "#2563EB"]):
        k = max(1, int(np.ceil(len(x) * q / 100.0)))
        s = x[:k].sum() / x.sum() * 100.0
        ax.scatter([q], [s], color=c, s=28, zorder=3)
        ax.text(q + 0.8, s + 0.7, f"top{q}%={s:.1f}%", color=c, fontsize=9)
    ax.set_xlabel("Top X% of merchants")
    ax.set_ylabel("% of outlets held")
    ax.set_title("Top-K Merchant Concentration")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "4_topk_share_curve.png")
    plt.close(fig)


def _plot_5_mismatch_hex(per: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8.4, 5.8))
    hb = ax.hexbin(
        np.log10(per["outlet_count"].to_numpy()),
        per["home_legal_mismatch_rate"].to_numpy(),
        gridsize=28,
        cmap="viridis",
        mincnt=1,
    )
    ax.set_xlabel("log10(outlets per merchant)")
    ax.set_ylabel("Home vs legal mismatch rate")
    ax.set_title("Mismatch Rate vs Merchant Size")
    cb = fig.colorbar(hb, ax=ax)
    cb.set_label("Merchant count")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "5_mismatch_vs_size_hex.png")
    plt.close(fig)


def _plot_6_mismatch_decile(per: pd.DataFrame) -> pd.DataFrame:
    d = per[["outlet_count", "home_legal_mismatch_rate"]].copy()
    d["size_decile"] = pd.qcut(d["outlet_count"], q=10, labels=False, duplicates="drop") + 1
    s = (
        d.groupby("size_decile", as_index=False)
        .agg(
            mismatch_mean=("home_legal_mismatch_rate", "mean"),
            mismatch_std=("home_legal_mismatch_rate", "std"),
            n=("home_legal_mismatch_rate", "size"),
        )
        .sort_values("size_decile")
    )
    s["se"] = s["mismatch_std"].fillna(0) / np.sqrt(s["n"].clip(lower=1))
    s["ci95"] = 1.96 * s["se"]

    fig, ax = plt.subplots(figsize=(9.2, 5.8))
    sns.barplot(data=s, x="size_decile", y="mismatch_mean", color="#F26D85", ax=ax)
    ax.errorbar(
        x=np.arange(len(s)),
        y=s["mismatch_mean"],
        yerr=s["ci95"],
        fmt="none",
        ecolor="#7F1D1D",
        capsize=3,
        linewidth=1.1,
    )
    for i, r in s.reset_index(drop=True).iterrows():
        ax.text(i, r["mismatch_mean"] + r["ci95"] + 0.008, f"n={int(r['n'])}", ha="center", va="bottom", fontsize=8)
    ax.set_xlabel("Merchant size decile (1=smallest)")
    ax.set_ylabel("Mean mismatch rate")
    ax.set_ylim(0, 1.02)
    ax.set_title("Mismatch Rate by Merchant Size Decile (95% CI)")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "6_mismatch_by_decile.png")
    plt.close(fig)
    return s


def _plot_7_legal_ecdf(per: pd.DataFrame) -> None:
    x = np.sort(per["legal_country_count"].to_numpy())
    y = np.arange(1, len(x) + 1) / len(x)
    fig, ax = plt.subplots(figsize=(8.4, 5.6))
    ax.step(x, y, where="post", color="#3D5A80", linewidth=2.2)
    ax.set_xlim(left=1)
    ax.set_xlabel("Legal countries per merchant")
    ax.set_ylabel("ECDF")
    ax.set_title("Distribution of Legal Country Count per Merchant")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "7_legal_country_ecdf.png")
    plt.close(fig)


def _plot_8_size_vs_legal_hex(per: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8.4, 5.8))
    hb = ax.hexbin(
        np.log10(per["outlet_count"].to_numpy()),
        per["legal_country_count"].to_numpy(),
        gridsize=28,
        cmap="magma",
        mincnt=1,
    )
    ax.set_xlabel("log10(outlets per merchant)")
    ax.set_ylabel("Legal countries per merchant")
    ax.set_title("Merchant Size vs Cross-Border Spread")
    cb = fig.colorbar(hb, ax=ax)
    cb.set_label("Merchant count")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "8_size_vs_legal_hex.png")
    plt.close(fig)


def _plot_9_flag_replacement(per: pd.DataFrame) -> None:
    counts = (
        per.groupby("single_vs_multi_flag", as_index=False)["merchant_id"]
        .size()
        .rename(columns={"size": "merchant_count"})
    )
    idx = pd.DataFrame({"single_vs_multi_flag": [False, True]})
    counts = idx.merge(counts, on="single_vs_multi_flag", how="left").fillna({"merchant_count": 0})
    counts["label"] = counts["single_vs_multi_flag"].map({False: "False", True: "True"})
    total = int(counts["merchant_count"].sum())

    fig, ax = plt.subplots(figsize=(7.6, 5.0))
    sns.barplot(data=counts, x="label", y="merchant_count", hue="label", palette=["#C7CED6", "#4C72B0"], dodge=False, legend=False, ax=ax)
    ax.set_title("Flag Coverage: single_vs_multi_flag (Replacement for Violin)")
    ax.set_xlabel("single_vs_multi_flag")
    ax.set_ylabel("Merchant count")
    ax.yaxis.set_major_formatter(FuncFormatter(_fmt_int))
    for i, r in counts.reset_index(drop=True).iterrows():
        pct = (r["merchant_count"] / total * 100.0) if total > 0 else 0.0
        ax.text(i, r["merchant_count"], f"{int(r['merchant_count']):,} ({pct:.1f}%)", ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "9_flag_violin.png")
    plt.close(fig)


def _plot_10_flag_jitter_fixed(per: pd.DataFrame) -> None:
    rng = np.random.default_rng(42)
    true_vals = per.loc[per["single_vs_multi_flag"] == True, "outlet_count"].to_numpy()  # noqa: E712
    false_vals = per.loc[per["single_vs_multi_flag"] == False, "outlet_count"].to_numpy()  # noqa: E712
    fig, ax = plt.subplots(figsize=(8.4, 5.4))
    if false_vals.size > 0:
        x_false = rng.normal(loc=1, scale=0.04, size=false_vals.size)
        ax.scatter(x_false, false_vals, s=12, alpha=0.45, color="#C25E4A")
    x_true = rng.normal(loc=2, scale=0.04, size=true_vals.size)
    ax.scatter(x_true, true_vals, s=10, alpha=0.5, color="#2A9D8F")
    ax.set_xticks([1, 2])
    ax.set_xticklabels([f"False (n={false_vals.size})", f"True (n={true_vals.size})"])
    ax.set_yscale("log")
    ax.set_ylabel("Outlets per merchant (log scale)")
    ax.set_title("Flag Coverage: single_vs_multi_flag (Jitter View)")
    if false_vals.size == 0:
        ax.text(0.03, 0.95, "No merchants flagged False", transform=ax.transAxes, ha="left", va="top", fontsize=10, color="#7F1D1D")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "10_flag_jitter.png")
    plt.close(fig)


def _plot_11_candidate_vs_membership(per: pd.DataFrame) -> None:
    x = per["candidate_count_foreign"].to_numpy()
    y = per["membership_count"].to_numpy()
    fig, ax = plt.subplots(figsize=(8.5, 5.9))
    hb = ax.hexbin(x, y, gridsize=32, cmap="cividis", mincnt=1)
    diag_max = max(float(x.max()), float(y.max()))
    ax.plot([0, diag_max], [0, diag_max], linestyle="--", color="#9CA3AF", linewidth=1.2)
    ax.set_xlabel("Foreign candidate countries per merchant")
    ax.set_ylabel("Actual foreign memberships per merchant")
    ax.set_title("Foreign Candidate Breadth vs Actual Foreign Membership")
    cb = fig.colorbar(hb, ax=ax)
    cb.set_label("Merchant count")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "11_candidate_vs_membership_hex.png")
    plt.close(fig)


def _plot_12_candidate_gap_ecdf(per: pd.DataFrame) -> None:
    gap = np.sort((per["candidate_count_foreign"] - per["membership_count"]).to_numpy())
    y = np.arange(1, len(gap) + 1) / len(gap)
    fig, ax = plt.subplots(figsize=(8.5, 5.6))
    ax.step(gap, y, where="post", color="#FF7F0E", linewidth=2.1)
    p50, p90 = np.quantile(gap, 0.5), np.quantile(gap, 0.9)
    ax.axvline(p50, linestyle="--", color="#6B7280", linewidth=1.1)
    ax.axvline(p90, linestyle="--", color="#374151", linewidth=1.1)
    ax.text(p50, 0.1, f"p50={p50:.0f}", rotation=90, va="bottom", ha="right", fontsize=9, color="#6B7280")
    ax.text(p90, 0.1, f"p90={p90:.0f}", rotation=90, va="bottom", ha="right", fontsize=9, color="#374151")
    ax.set_xlabel("Foreign candidate count minus actual membership count")
    ax.set_ylabel("ECDF")
    ax.set_title("Gap Between Foreign Candidate Set Size and Actual Membership")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "12_candidate_gap_ecdf.png")
    plt.close(fig)


def _plot_13_duplicate_heatmap_fixed(per: pd.DataFrame, pair: pd.DataFrame) -> None:
    top = per.sort_values("dup_pair_rate", ascending=False).head(18)["merchant_id"].tolist()
    sub = pair[pair["merchant_id"].isin(top) & (pair["pair_rows"] > 1)].copy()
    if sub.empty:
        return
    sub["dup_level"] = sub["legal_country_n"].clip(lower=2, upper=10)
    table = (
        sub.groupby(["merchant_id", "dup_level"], as_index=False)
        .size()
        .pivot(index="merchant_id", columns="dup_level", values="size")
        .fillna(0)
    )
    table = table.reindex(index=top).fillna(0)
    table.index = [str(x)[-6:] for x in table.index]

    fig, ax = plt.subplots(figsize=(10.8, 5.8))
    sns.heatmap(
        table,
        cmap="plasma",
        cbar_kws={"label": "Duplicated merchant-site pair count"},
        ax=ax,
    )
    ax.set_xlabel("Distinct legal countries per duplicated site_id")
    ax.set_ylabel("Top merchants by dup_pair_rate (suffix)")
    ax.set_title("Duplicate Site IDs Across Legal Countries (Fixed Anatomy)")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "13_duplicate_site_heatmap.png")
    plt.close(fig)


def _plot_14_dup_rate_ecdf(per: pd.DataFrame) -> None:
    x = np.sort(per["dup_pair_rate"].to_numpy())
    y = np.arange(1, len(x) + 1) / len(x)
    fig, ax = plt.subplots(figsize=(8.5, 5.6))
    ax.step(x, y, where="post", color="#6D597A", linewidth=2.1)
    p90 = np.quantile(x, 0.9)
    ax.axvline(p90, linestyle="--", color="#374151", linewidth=1.2)
    ax.text(p90, 0.1, f"p90={p90:.2f}", rotation=90, va="bottom", ha="right", fontsize=9)
    ax.set_xlabel("Duplicate site-pair rate per merchant")
    ax.set_ylabel("ECDF")
    ax.set_title("Distribution of Duplicate Merchant-Site Pairs")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "14_dup_pair_rate_ecdf.png")
    plt.close(fig)


def _plot_15_flag_coverage_bar(per: pd.DataFrame) -> None:
    c = (
        per.groupby("single_vs_multi_flag", as_index=False)["merchant_id"]
        .size()
        .rename(columns={"size": "merchant_count"})
    )
    c = pd.DataFrame({"single_vs_multi_flag": [False, True]}).merge(c, on="single_vs_multi_flag", how="left").fillna(
        {"merchant_count": 0}
    )
    total = max(float(c["merchant_count"].sum()), 1.0)
    c["share"] = c["merchant_count"] / total
    c["label"] = c["single_vs_multi_flag"].map({False: "False", True: "True"})
    fig, ax = plt.subplots(figsize=(7.0, 4.8))
    sns.barplot(data=c, x="label", y="share", hue="label", palette=["#9CA3AF", "#2563EB"], dodge=False, legend=False, ax=ax)
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("single_vs_multi_flag")
    ax.set_ylabel("Share of merchants")
    ax.set_title("Flag Coverage Share")
    for i, r in c.reset_index(drop=True).iterrows():
        ax.text(i, r["share"], f"{r['share']*100:.1f}%\n(n={int(r['merchant_count'])})", ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "15_flag_coverage_bar.png")
    plt.close(fig)


def _plot_16_mismatch_decomposition(per: pd.DataFrame) -> None:
    d = per.copy()
    d["size_decile"] = pd.qcut(d["outlet_count"], q=10, labels=False, duplicates="drop") + 1
    d["legal_bucket"] = pd.cut(
        d["legal_country_count"],
        bins=[0, 1, 2, 3, 5, 8, 20],
        labels=["1", "2", "3", "4-5", "6-8", "9+"],
        include_lowest=True,
    )
    by_dec = d.groupby("size_decile", as_index=False)["home_legal_mismatch_rate"].mean()
    by_leg = d.groupby("legal_bucket", as_index=False, observed=False)["home_legal_mismatch_rate"].mean()

    fig, ax = plt.subplots(1, 2, figsize=(13.2, 5.2))
    sns.barplot(data=by_dec, x="size_decile", y="home_legal_mismatch_rate", color="#F97316", ax=ax[0])
    ax[0].set_ylim(0, 1)
    ax[0].set_xlabel("Merchant size decile")
    ax[0].set_ylabel("Mean mismatch rate")
    ax[0].set_title("Mismatch by Size Decile")

    sns.barplot(data=by_leg, x="legal_bucket", y="home_legal_mismatch_rate", color="#14B8A6", ax=ax[1])
    ax[1].set_ylim(0, 1)
    ax[1].set_xlabel("Legal-country-count bucket")
    ax[1].set_ylabel("Mean mismatch rate")
    ax[1].set_title("Mismatch by Legal-Spread Bucket")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "16_mismatch_decomposition.png")
    plt.close(fig)


def _plot_17_candidate_realization_ratio(per: pd.DataFrame) -> None:
    d = per.copy()
    d = d[d["candidate_count_foreign"] > 0].copy()
    d["realization_ratio"] = d["membership_count"] / d["candidate_count_foreign"]
    d["realization_ratio"] = d["realization_ratio"].clip(0, 1)

    fig, ax = plt.subplots(1, 2, figsize=(13.0, 5.2))
    sns.histplot(d["realization_ratio"], bins=28, color="#0EA5A4", edgecolor="white", linewidth=0.3, ax=ax[0])
    ax[0].set_xlabel("membership_count / foreign_candidate_count")
    ax[0].set_ylabel("Merchant count")
    ax[0].set_title("Candidate Realization Ratio Distribution")
    ax[0].yaxis.set_major_formatter(FuncFormatter(_fmt_int))

    hb = ax[1].hexbin(
        d["candidate_count_foreign"].to_numpy(),
        d["realization_ratio"].to_numpy(),
        gridsize=28,
        cmap="viridis",
        mincnt=1,
    )
    ax[1].set_xlabel("Foreign candidate countries")
    ax[1].set_ylabel("Realization ratio")
    ax[1].set_ylim(0, 1)
    ax[1].set_title("Realization Ratio vs Candidate Breadth")
    cb = fig.colorbar(hb, ax=ax[1])
    cb.set_label("Merchant count")
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "17_candidate_realization_ratio.png")
    plt.close(fig)


def _plot_18_duplicate_semantics(pair: pd.DataFrame, per: pd.DataFrame) -> None:
    total_pairs = len(pair)
    unique_pairs = int((pair["pair_rows"] == 1).sum())
    cross_country_dup = int(((pair["pair_rows"] > 1) & (pair["legal_country_n"] > 1)).sum())
    same_country_dup_only = int(((pair["pair_rows"] > 1) & (pair["legal_country_n"] == 1)).sum())

    affected = {
        "any_dup": float((per["dup_pair_rate"] > 0).mean()),
        "cross_country_dup": float((per["cross_country_dup_rate"] > 0).mean()),
        "same_country_dup_only": float((per["same_country_dup_only_rate"] > 0).mean()),
    }

    fig, ax = plt.subplots(1, 2, figsize=(13.5, 5.1))
    b = pd.DataFrame(
        {
            "bucket": ["unique pair", "cross-country dup", "same-country dup-only"],
            "count": [unique_pairs, cross_country_dup, same_country_dup_only],
        }
    )
    b["share"] = b["count"] / max(total_pairs, 1)
    sns.barplot(
        data=b,
        x="bucket",
        y="share",
        hue="bucket",
        palette=["#64748B", "#2563EB", "#F59E0B"],
        dodge=False,
        legend=False,
        ax=ax[0],
    )
    ax[0].set_ylim(0, 1)
    ax[0].set_xlabel("")
    ax[0].set_ylabel("Share of merchant-site pairs")
    ax[0].set_title("Duplicate Pair Semantics")
    ax[0].tick_params(axis="x", rotation=18)
    for i, r in b.reset_index(drop=True).iterrows():
        ax[0].text(i, r["share"], f"{r['share']*100:.1f}%\n(n={int(r['count']):,})", ha="center", va="bottom", fontsize=8)

    m = pd.DataFrame(
        {
            "bucket": ["any dup", "cross-country dup", "same-country dup-only"],
            "share": [affected["any_dup"], affected["cross_country_dup"], affected["same_country_dup_only"]],
        }
    )
    sns.barplot(
        data=m,
        x="bucket",
        y="share",
        hue="bucket",
        palette=["#334155", "#1D4ED8", "#D97706"],
        dodge=False,
        legend=False,
        ax=ax[1],
    )
    ax[1].set_ylim(0, 1)
    ax[1].set_xlabel("")
    ax[1].set_ylabel("Share of merchants")
    ax[1].set_title("Merchant-Level Exposure to Dup Semantics")
    ax[1].tick_params(axis="x", rotation=18)
    for i, r in m.reset_index(drop=True).iterrows():
        ax[1].text(i, r["share"], f"{r['share']*100:.1f}%", ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "18_duplicate_semantics_breakdown.png")
    plt.close(fig)


def _plot_19_outlet_pyramid(per: pd.DataFrame) -> None:
    d = per.copy()
    bins = [0, 1, 3, 10, 50, np.inf]
    labels = ["1", "2-3", "4-10", "11-50", "51+"]
    d["bucket"] = pd.cut(d["outlet_count"], bins=bins, labels=labels, include_lowest=True)
    s = d.groupby("bucket", as_index=False, observed=False).size().rename(columns={"size": "merchant_count"})
    total = max(float(s["merchant_count"].sum()), 1.0)
    s["share"] = s["merchant_count"] / total

    fig, ax = plt.subplots(1, 2, figsize=(12.6, 4.9))
    sns.barplot(data=s, x="bucket", y="merchant_count", color="#4B5563", ax=ax[0])
    ax[0].set_xlabel("Outlets per merchant bucket")
    ax[0].set_ylabel("Merchant count")
    ax[0].set_title("Merchant Pyramid by Outlet Count")
    ax[0].yaxis.set_major_formatter(FuncFormatter(_fmt_int))

    sns.barplot(data=s, x="bucket", y="share", color="#2563EB", ax=ax[1])
    ax[1].set_xlabel("Outlets per merchant bucket")
    ax[1].set_ylabel("Share of merchants")
    ax[1].set_ylim(0, 1)
    ax[1].set_title("Merchant Pyramid Share")
    for i, r in s.reset_index(drop=True).iterrows():
        ax[1].text(i, r["share"], f"{r['share']*100:.1f}%", ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT_PLOTS / "19_outlet_pyramid.png")
    plt.close(fig)


def _write_metrics(per: pd.DataFrame, outlets: pd.DataFrame, gini: float) -> None:
    outlet_counts = per["outlet_count"].to_numpy()
    legal_counts = per["legal_country_count"].to_numpy()
    mismatch_rates = per["home_legal_mismatch_rate"].to_numpy()
    candidate_counts = per["candidate_count_foreign"].to_numpy()
    membership_counts = per["membership_count"].to_numpy()
    dup_pair_rate = per["dup_pair_rate"].to_numpy()

    metrics = {
        "outlet_count_quantiles": {
            "min": int(np.min(outlet_counts)),
            "median": float(np.median(outlet_counts)),
            "p90": float(np.quantile(outlet_counts, 0.9)),
            "p99": float(np.quantile(outlet_counts, 0.99)),
            "max": int(np.max(outlet_counts)),
        },
        "gini_outlet_count": gini,
        "home_legal_mismatch_overall": float(np.mean(outlets["home_country_iso"] != outlets["legal_country_iso"])),
        "legal_country_quantiles": {
            "min": int(np.min(legal_counts)),
            "median": float(np.median(legal_counts)),
            "p90": float(np.quantile(legal_counts, 0.9)),
            "max": int(np.max(legal_counts)),
        },
        "single_vs_multi_counts": {
            "true": int(np.sum(per["single_vs_multi_flag"] == True)),  # noqa: E712
            "false": int(np.sum(per["single_vs_multi_flag"] == False)),  # noqa: E712
        },
        "candidate_membership": {
            "candidate_all_median": float(np.median(per["candidate_count_all"])),
            "candidate_foreign_median": float(np.median(candidate_counts)),
            "membership_median": float(np.median(membership_counts)),
            "membership_share": float(np.mean(membership_counts > 0)),
            "corr": float(np.corrcoef(candidate_counts, membership_counts)[0, 1]),
            "realization_ratio_median": float(
                np.median(
                    np.divide(
                        membership_counts,
                        np.clip(candidate_counts, 1, None),
                    )
                )
            ),
        },
        "dup_pair_rate": {
            "mean": float(np.mean(dup_pair_rate)),
            "p90": float(np.quantile(dup_pair_rate, 0.9)),
            "share_with_dups": float(np.mean(dup_pair_rate > 0)),
            "share_with_cross_country_dups": float(np.mean(per["cross_country_dup_rate"] > 0)),
            "share_with_same_country_dup_only": float(np.mean(per["same_country_dup_only_rate"] > 0)),
        },
    }
    with open(OUT_PLOTS / "plot_metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)


def main() -> None:
    OUT_PLOTS.mkdir(parents=True, exist_ok=True)
    _set_theme()
    outlets, cand, mem = _load_data()
    per, pair, _pair_legal = _build_features(outlets, cand, mem)

    _plot_1_outlet_hist(per)
    _plot_2_ccdf(per)
    gini = _plot_3_lorenz(per)
    _plot_4_topk(per)
    _plot_5_mismatch_hex(per)
    _plot_6_mismatch_decile(per)
    _plot_7_legal_ecdf(per)
    _plot_8_size_vs_legal_hex(per)
    _plot_9_flag_replacement(per)
    _plot_10_flag_jitter_fixed(per)
    _plot_11_candidate_vs_membership(per)
    _plot_12_candidate_gap_ecdf(per)
    _plot_13_duplicate_heatmap_fixed(per, pair)
    _plot_14_dup_rate_ecdf(per)
    _plot_15_flag_coverage_bar(per)
    _plot_16_mismatch_decomposition(per)
    _plot_17_candidate_realization_ratio(per)
    _plot_18_duplicate_semantics(pair, per)
    _plot_19_outlet_pyramid(per)
    _write_metrics(per, outlets, gini)

    print("plots_written")
    for p in sorted(OUT_PLOTS.glob("*.png")):
        print(p.name)


if __name__ == "__main__":
    main()
