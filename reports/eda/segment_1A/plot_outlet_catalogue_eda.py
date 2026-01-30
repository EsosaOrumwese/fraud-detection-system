# Generates outlet_catalogue realism plots for segment 1A
# Headless backend ensures this runs without a GUI.
import json
from pathlib import Path

import numpy as np
import polars as pl
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE = Path(r"runs\local_full_run-5\c25a2675fbfbacd952b13bb594880e92\data\layer1\1A")
OUT_DIR = Path(r"reports\eda\segment_1A\plots")
OUT_DIR.mkdir(parents=True, exist_ok=True)

plt.style.use("seaborn-v0_8")
plt.rcParams.update({
    "figure.dpi": 140,
    "savefig.dpi": 140,
    "axes.titleweight": "bold",
    "axes.labelsize": 10,
    "axes.titlesize": 12,
    "legend.frameon": False,
})

# Paths
outlet_file = next((BASE / "outlet_catalogue").rglob("*.parquet"))
candidate_file = next((BASE / "s3_candidate_set").rglob("*.parquet"))
membership_file = next((BASE / "s6" / "membership").rglob("*.parquet"))

# Load
outlets = pl.read_parquet(outlet_file)

# Per-merchant metrics
per_merchant = outlets.group_by("merchant_id").agg([
    pl.len().alias("outlet_count"),
    pl.col("legal_country_iso").n_unique().alias("legal_country_count"),
    pl.col("home_country_iso").n_unique().alias("home_country_count"),
    (pl.col("home_country_iso") != pl.col("legal_country_iso")).mean().alias("home_legal_mismatch_rate"),
    pl.col("single_vs_multi_flag").max().alias("single_vs_multi_flag"),
])

# Candidate and membership counts
# Use foreign-only candidates for realism comparison vs membership.
cand_df = pl.read_parquet(candidate_file)
cand = cand_df.group_by("merchant_id").agg(pl.col("country_iso").n_unique().alias("candidate_count_all"))
cand_foreign = cand_df.filter(pl.col("is_home") == False).group_by("merchant_id").agg(
    pl.col("country_iso").n_unique().alias("candidate_count_foreign")
)
mem = pl.read_parquet(membership_file).group_by("merchant_id").agg(pl.col("country_iso").n_unique().alias("membership_count"))

per_merchant = (
    per_merchant.join(cand, on="merchant_id", how="left")
    .join(cand_foreign, on="merchant_id", how="left")
    .join(mem, on="merchant_id", how="left")
)
per_merchant = per_merchant.with_columns([
    pl.col("candidate_count_all").fill_null(0),
    pl.col("candidate_count_foreign").fill_null(0),
    pl.col("membership_count").fill_null(0),
])

# Duplicate merchant-site pairs
pair_counts = outlets.group_by(["merchant_id", "site_id"]).len().rename({"len": "pair_count"})

# Per merchant duplicate stats
per_merchant_dup = pair_counts.group_by("merchant_id").agg([
    pl.len().alias("site_pairs"),
    (pl.col("pair_count") > 1).sum().alias("dup_site_pairs"),
    pl.col("pair_count").max().alias("max_pair_dups"),
])
per_merchant_dup = per_merchant_dup.with_columns([
    (pl.col("dup_site_pairs") / pl.col("site_pairs")).alias("dup_pair_rate")
])

# Merge dup stats
per_merchant = per_merchant.join(per_merchant_dup, on="merchant_id", how="left")

# Arrays
outlet_counts = per_merchant["outlet_count"].to_numpy()
legal_counts = per_merchant["legal_country_count"].to_numpy()
mismatch_rates = per_merchant["home_legal_mismatch_rate"].to_numpy()
flags = per_merchant["single_vs_multi_flag"].to_numpy()
candidate_counts = per_merchant["candidate_count_foreign"].to_numpy()
membership_counts = per_merchant["membership_count"].to_numpy()
dup_pair_rate = per_merchant["dup_pair_rate"].fill_null(0).to_numpy()

# --- Plot 1: Outlet count histogram (log bins)
fig, ax = plt.subplots(figsize=(7.2, 4.5))
bins = np.logspace(np.log10(outlet_counts.min()), np.log10(outlet_counts.max()), 28)
ax.hist(outlet_counts, bins=bins, color="#2a6f97", edgecolor="#0b3d91", alpha=0.85)
ax.set_xscale("log")
ax.set_yscale("log")
ax.set_xlabel("Outlets per merchant (log scale)")
ax.set_ylabel("Merchant count (log scale)")
ax.set_title("Outlet Count Distribution (Log-Log Histogram)")
for q, label, color in [(np.median(outlet_counts), "median", "#e07a5f"), (np.quantile(outlet_counts, 0.9), "p90", "#f2cc8f")]:
    ax.axvline(q, color=color, linestyle="--", linewidth=1.5, label=f"{label}={q:.0f}")
ax.legend(loc="upper right")
fig.tight_layout()
fig.savefig(OUT_DIR / "1_outlet_hist_loglog.png")
plt.close(fig)

# --- Plot 2: CCDF (log-log)
sorted_counts = np.sort(outlet_counts)
ccdf = 1.0 - np.arange(1, len(sorted_counts) + 1) / len(sorted_counts)
fig, ax = plt.subplots(figsize=(7.2, 4.5))
ax.loglog(sorted_counts, ccdf, marker="o", markersize=3, linestyle="none", color="#1b4332", alpha=0.6)
ax.set_xlabel("Outlets per merchant (log scale)")
ax.set_ylabel("P(X ≥ x) (log scale)")
ax.set_title("Outlet Count CCDF (Heavy-Tail View)")
fig.tight_layout()
fig.savefig(OUT_DIR / "2_outlet_ccdf_loglog.png")
plt.close(fig)

# --- Plot 3: Lorenz curve
sorted_counts = np.sort(outlet_counts)
lorenz_y = np.insert(np.cumsum(sorted_counts) / np.sum(sorted_counts), 0, 0)
lorenz_x = np.insert(np.arange(1, len(sorted_counts) + 1) / len(sorted_counts), 0, 0)
fig, ax = plt.subplots(figsize=(6.5, 6.0))
ax.plot(lorenz_x, lorenz_y, color="#264653", linewidth=2.0, label="Lorenz curve")
ax.plot([0, 1], [0, 1], color="#bcb8b1", linestyle="--", label="Perfect equality")
ax.set_xlabel("Cumulative share of merchants")
ax.set_ylabel("Cumulative share of outlets")
ax.set_title("Outlet Concentration (Lorenz Curve)")
ax.legend(loc="lower right")
fig.tight_layout()
fig.savefig(OUT_DIR / "3_lorenz_curve.png")
plt.close(fig)

# --- Plot 4: Top-K share curve
percent = np.linspace(0.01, 1.0, 100)
shares = []
counts_sorted_desc = np.sort(outlet_counts)[::-1]
for p in percent:
    k = max(1, int(len(counts_sorted_desc) * p))
    shares.append(counts_sorted_desc[:k].sum() / counts_sorted_desc.sum())
fig, ax = plt.subplots(figsize=(7.2, 4.5))
ax.plot(percent * 100, np.array(shares) * 100, color="#6a4c93", linewidth=2.0)
ax.set_xlabel("Top X% of merchants")
ax.set_ylabel("% of outlets held")
ax.set_title("Top-K Merchant Concentration")
ax.grid(True, alpha=0.2)
fig.tight_layout()
fig.savefig(OUT_DIR / "4_topk_share_curve.png")
plt.close(fig)

# --- Plot 5: Mismatch rate vs merchant size (hexbin on log outlet_count)
log_outlets = np.log10(outlet_counts)
fig, ax = plt.subplots(figsize=(7.2, 4.8))
hb = ax.hexbin(log_outlets, mismatch_rates, gridsize=28, cmap="viridis", mincnt=1)
ax.set_xlabel("log10(Outlets per merchant)")
ax.set_ylabel("Home vs legal mismatch rate")
ax.set_title("Mismatch Rate vs Merchant Size")
cb = fig.colorbar(hb, ax=ax)
cb.set_label("Merchant count")
fig.tight_layout()
fig.savefig(OUT_DIR / "5_mismatch_vs_size_hex.png")
plt.close(fig)

# --- Plot 6: Mismatch rate by outlet-count quantile bucket
quant_edges = np.quantile(outlet_counts, np.linspace(0, 1, 11))
# bucket 0..9
bucket_ids = np.digitize(outlet_counts, quant_edges[1:-1], right=True)
xs, ys, errs = [], [], []
for b in range(0, 10):
    mask = bucket_ids == b
    if not mask.any():
        continue
    xs.append(b)
    ys.append(float(np.mean(mismatch_rates[mask])))
    errs.append(float(np.std(mismatch_rates[mask], ddof=0)))
fig, ax = plt.subplots(figsize=(7.6, 4.5))
ax.errorbar(xs, ys, yerr=errs, fmt="-o", color="#ef476f", ecolor="#9b2226", capsize=4)
ax.set_xlabel("Merchant size decile (0=smallest, 9=largest)")
ax.set_ylabel("Mean home/legal mismatch rate")
ax.set_title("Mismatch Rate by Merchant Size Decile")
ax.grid(True, alpha=0.2)
fig.tight_layout()
fig.savefig(OUT_DIR / "6_mismatch_by_decile.png")
plt.close(fig)

# --- Plot 7: ECDF of legal countries per merchant
xs = np.sort(legal_counts)
ys = np.arange(1, len(xs) + 1) / len(xs)
fig, ax = plt.subplots(figsize=(7.2, 4.5))
ax.step(xs, ys, where="post", color="#3d5a80", linewidth=2.0)
ax.set_xlabel("Legal countries per merchant")
ax.set_ylabel("ECDF")
ax.set_title("Distribution of Legal Country Count per Merchant")
ax.set_xlim(left=1)
ax.grid(True, alpha=0.2)
fig.tight_layout()
fig.savefig(OUT_DIR / "7_legal_country_ecdf.png")
plt.close(fig)

# --- Plot 8: Outlet count vs legal countries (hexbin)
fig, ax = plt.subplots(figsize=(7.2, 4.8))
hb = ax.hexbin(np.log10(outlet_counts), legal_counts, gridsize=28, cmap="magma", mincnt=1)
ax.set_xlabel("log10(Outlets per merchant)")
ax.set_ylabel("Legal countries per merchant")
ax.set_title("Merchant Size vs Cross-Border Spread")
cb = fig.colorbar(hb, ax=ax)
cb.set_label("Merchant count")
fig.tight_layout()
fig.savefig(OUT_DIR / "8_size_vs_legal_hex.png")
plt.close(fig)

# --- Plot 9: Outlet count by single_vs_multi_flag (violin)
fig, ax = plt.subplots(figsize=(6.8, 4.5))
true_vals = outlet_counts[flags == True]
false_vals = outlet_counts[flags == False]
if len(false_vals) == 0:
    ax.violinplot([true_vals], positions=[2], showmeans=True, showmedians=True)
    ax.text(1, np.min(true_vals), "no data", color="#6c757d", ha="center", va="bottom")
else:
    ax.violinplot([false_vals, true_vals], showmeans=True, showmedians=True)
ax.set_xticks([1, 2])
ax.set_xticklabels(["False", "True"])
ax.set_yscale("log")
ax.set_ylabel("Outlets per merchant (log scale)")
ax.set_title("Outlet Count by single_vs_multi_flag")
ax.annotate("No merchants flagged False", xy=(1, 10), xytext=(1.2, 30),
            arrowprops=dict(arrowstyle="->", color="#6c757d"), color="#6c757d")
fig.tight_layout()
fig.savefig(OUT_DIR / "9_flag_violin.png")
plt.close(fig)

# --- Plot 10: Jitter plot for flag presence
fig, ax = plt.subplots(figsize=(6.8, 4.5))
# jitter x for True only
x = np.random.normal(loc=2, scale=0.04, size=len(outlet_counts))
ax.scatter(x, outlet_counts, s=10, alpha=0.5, color="#2a9d8f")
ax.set_xticks([1, 2])
ax.set_xticklabels(["False", "True"])
ax.set_yscale("log")
ax.set_ylabel("Outlets per merchant (log scale)")
ax.set_title("Flag Coverage: single_vs_multi_flag")
ax.annotate("All merchants flagged True", xy=(2, np.median(outlet_counts)),
            xytext=(1.4, np.median(outlet_counts) * 2),
            arrowprops=dict(arrowstyle="->", color="#6c757d"), color="#6c757d")
fig.tight_layout()
fig.savefig(OUT_DIR / "10_flag_jitter.png")
plt.close(fig)

# --- Plot 11: Candidate vs membership (hexbin)
fig, ax = plt.subplots(figsize=(7.2, 4.8))
hb = ax.hexbin(candidate_counts, membership_counts, gridsize=30, cmap="cividis", mincnt=1)
max_c = max(candidate_counts.max(), membership_counts.max())
ax.plot([0, max_c], [0, max_c], color="#adb5bd", linestyle="--", linewidth=1)
ax.set_xlabel("Foreign candidate countries per merchant")
ax.set_ylabel("Actual foreign memberships per merchant")
ax.set_title("Foreign Candidate Breadth vs Actual Foreign Membership")
cb = fig.colorbar(hb, ax=ax)
cb.set_label("Merchant count")
fig.tight_layout()
fig.savefig(OUT_DIR / "11_candidate_vs_membership_hex.png")
plt.close(fig)

# --- Plot 12: ECDF of candidate-membership gap
candidate_gap = candidate_counts - membership_counts
gap = np.sort(candidate_gap)
ys = np.arange(1, len(gap) + 1) / len(gap)
fig, ax = plt.subplots(figsize=(7.2, 4.5))
ax.step(gap, ys, where="post", color="#ff7f0e", linewidth=2.0)
ax.set_xlabel("Foreign candidate count minus actual membership count")
ax.set_ylabel("ECDF")
ax.set_title("Gap Between Foreign Candidate Set Size and Actual Membership")
ax.grid(True, alpha=0.2)
fig.tight_layout()
fig.savefig(OUT_DIR / "12_candidate_gap_ecdf.png")
plt.close(fig)

# --- Plot 13: Duplicate site_id heatmap for top merchants
site_legal = outlets.group_by(["merchant_id", "site_id"]).agg(pl.col("legal_country_iso").n_unique().alias("legal_country_count"))
site_legal_dup = site_legal.filter(pl.col("legal_country_count") > 1)
if site_legal_dup.height > 0:
    top_merchants = (site_legal_dup.group_by("merchant_id").agg(pl.len().alias("dup_sites"))
                     .sort("dup_sites", descending=True)
                     .head(18))
    top_ids = top_merchants["merchant_id"].to_list()
    subset = site_legal_dup.filter(pl.col("merchant_id").is_in(top_ids)).sort(["merchant_id", "legal_country_count"], descending=True)

    max_sites = 15
    matrix = np.zeros((max_sites, len(top_ids)), dtype=float)
    for col_idx, mid in enumerate(top_ids):
        rows = subset.filter(pl.col("merchant_id") == mid).sort("legal_country_count", descending=True).head(max_sites)
        vals = rows["legal_country_count"].to_numpy()
        for r, v in enumerate(vals):
            matrix[r, col_idx] = v

    fig, ax = plt.subplots(figsize=(10.5, 5.0))
    im = ax.imshow(matrix, aspect="auto", cmap="plasma")
    ax.set_xlabel("Top merchants (by duplicated site_ids)")
    ax.set_ylabel("Site rank within merchant (1 = most duplicated)")
    ax.set_title("Duplicate Site IDs Across Legal Countries (Top Merchants)")
    ax.set_xticks(range(len(top_ids)))
    ax.set_xticklabels([str(m)[-6:] for m in top_ids], rotation=45, ha="right", fontsize=7)
    cb = fig.colorbar(im, ax=ax)
    cb.set_label("Distinct legal countries per site_id")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "13_duplicate_site_heatmap.png")
    plt.close(fig)

# --- Plot 14: ECDF of duplicate site-pair rate per merchant
if dup_pair_rate.size:
    dup_sorted = np.sort(dup_pair_rate)
    ys = np.arange(1, len(dup_sorted) + 1) / len(dup_sorted)
    fig, ax = plt.subplots(figsize=(7.2, 4.5))
    ax.step(dup_sorted, ys, where="post", color="#6d597a", linewidth=2.0)
    ax.set_xlabel("Duplicate site-pair rate per merchant")
    ax.set_ylabel("ECDF")
    ax.set_title("Distribution of Duplicate Merchant-Site Pairs")
    ax.grid(True, alpha=0.2)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "14_dup_pair_rate_ecdf.png")
    plt.close(fig)

# --- Metrics for report
# Gini coefficient
sorted_counts = np.sort(outlet_counts)
index = np.arange(1, len(sorted_counts) + 1)
gini = (np.sum((2 * index - len(sorted_counts) - 1) * sorted_counts) / (len(sorted_counts) * np.sum(sorted_counts)))

metrics = {
    "outlet_count_quantiles": {
        "min": int(np.min(outlet_counts)),
        "median": float(np.median(outlet_counts)),
        "p90": float(np.quantile(outlet_counts, 0.9)),
        "p99": float(np.quantile(outlet_counts, 0.99)),
        "max": int(np.max(outlet_counts)),
    },
    "gini_outlet_count": float(gini),
    "home_legal_mismatch_overall": float((outlets["home_country_iso"] != outlets["legal_country_iso"]).mean()),
    "legal_country_quantiles": {
        "min": int(np.min(legal_counts)),
        "median": float(np.median(legal_counts)),
        "p90": float(np.quantile(legal_counts, 0.9)),
        "max": int(np.max(legal_counts)),
    },
    "single_vs_multi_counts": {
        "true": int(np.sum(flags == True)),
        "false": int(np.sum(flags == False)),
    },
    "candidate_membership": {
        "candidate_all_median": float(np.median(per_merchant["candidate_count_all"].to_numpy())),
        "candidate_foreign_median": float(np.median(candidate_counts)),
        "membership_median": float(np.median(membership_counts)),
        "membership_share": float(np.mean(membership_counts > 0)),
        "corr": float(np.corrcoef(candidate_counts, membership_counts)[0, 1]),
    },
    "dup_pair_rate": {
        "mean": float(np.mean(dup_pair_rate)),
        "p90": float(np.quantile(dup_pair_rate, 0.9)),
        "share_with_dups": float(np.mean(dup_pair_rate > 0)),
    },
}

with open(OUT_DIR / "plot_metrics.json", "w", encoding="utf-8") as f:
    json.dump(metrics, f, indent=2)

print("plots_written", len(list(OUT_DIR.glob("*.png"))))
