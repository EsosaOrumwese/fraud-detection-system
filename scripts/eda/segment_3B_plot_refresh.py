from __future__ import annotations

import glob
import json
import math
import struct
from pathlib import Path

import geopandas as gpd
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import polars as pl
import seaborn as sns

matplotlib.use("Agg")

RUN_ROOT = Path("runs/local_full_run-5/c25a2675fbfbacd952b13bb594880e92/data/layer1/3B")
OUT_DIR = Path("docs/reports/reports/eda/segment_3B/plots")

MERCHANT_PROFILE_PATH = Path(
    "reference/layer1/transaction_schema_merchant_ids/2026-01-03/transaction_schema_merchant_ids.parquet"
)
OUTLET_PATH = Path(
    "runs/local_full_run-5/c25a2675fbfbacd952b13bb594880e92/data/layer1/1A/"
    "outlet_catalogue/seed=42/manifest_fingerprint="
    "c8fd43cd60ce0ede0c63d2ceb4610f167c9b107e1d59b9b8c7d7b8d0028b05c8"
)
WORLD_COUNTRIES_PATH = Path("reference/spatial/world_countries/2024/world_countries.parquet")
ALIAS_POLICY_PATH = Path("config/layer1/2B/policy/alias_layout_policy_v1.json")


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
            "axes.labelsize": 11,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "legend.fontsize": 10,
            "savefig.dpi": 170,
            "figure.dpi": 170,
        }
    )


def _glob_many(pattern: str) -> list[str]:
    matches = sorted(glob.glob(pattern))
    if not matches:
        raise FileNotFoundError(f"No matches for pattern: {pattern}")
    return matches


def _glob_one(pattern: str) -> str:
    matches = _glob_many(pattern)
    return matches[0]


def _decode_probabilities(prob: np.ndarray, alias: np.ndarray) -> np.ndarray:
    count = prob.size
    if count == 0:
        return np.array([], dtype=np.float64)
    p_hat = prob / float(count)
    residual = (1.0 - prob) / float(count)
    for idx in range(count):
        p_hat[int(alias[idx])] += residual[idx]
    return p_hat


def _read_alias_slice(blob_path: Path, offset: int, length: int, endianness: str) -> tuple[np.ndarray, np.ndarray]:
    endian = "<" if endianness == "little" else ">"
    with blob_path.open("rb") as handle:
        handle.seek(int(offset))
        data = handle.read(int(length))
    if len(data) < 16:
        raise ValueError("Alias slice too short.")
    n_sites, prob_qbits, _, _ = struct.unpack(endian + "IIII", data[:16])
    expected_len = 16 + int(n_sites) * 8
    payload = data[:expected_len]
    prob_q = np.zeros(int(n_sites), dtype=np.float64)
    alias = np.zeros(int(n_sites), dtype=np.int64)
    pos = 16
    for i in range(int(n_sites)):
        q, a = struct.unpack(endian + "II", payload[pos : pos + 8])
        prob_q[i] = q
        alias[i] = a
        pos += 8
    prob = prob_q / float(1 << int(prob_qbits))
    return prob, alias


def _haversine_km(lat1, lon1, lat2, lon2) -> np.ndarray:
    r = 6371.0
    lat1 = np.radians(lat1)
    lon1 = np.radians(lon1)
    lat2 = np.radians(lat2)
    lon2 = np.radians(lon2)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2.0) ** 2
    return 2.0 * r * np.arcsin(np.sqrt(a))


def _merchant_legal_country() -> pl.DataFrame:
    outlet_files = sorted(OUTLET_PATH.glob("*.parquet"))
    if not outlet_files:
        raise FileNotFoundError(f"No outlet parquet found under {OUTLET_PATH}")
    outlet = pl.scan_parquet([str(p) for p in outlet_files]).select(["merchant_id", "legal_country_iso"]).collect()
    legal_mode = (
        outlet.group_by(["merchant_id", "legal_country_iso"])
        .len()
        .sort(["merchant_id", "len"], descending=[False, True])
        .group_by("merchant_id")
        .agg(pl.first("legal_country_iso").alias("legal_country_iso"))
    )
    return legal_mode


def _load_core_frames() -> dict[str, pl.DataFrame]:
    vclass = pl.read_parquet(
        _glob_many(str(RUN_ROOT / "virtual_classification" / "seed=*" / "manifest_fingerprint=*" / "*.parquet"))
    )
    vsettle = pl.read_parquet(
        _glob_many(str(RUN_ROOT / "virtual_settlement" / "seed=*" / "manifest_fingerprint=*" / "*.parquet"))
    )
    edge = pl.read_parquet(_glob_many(str(RUN_ROOT / "edge_catalogue" / "seed=*" / "manifest_fingerprint=*" / "*.parquet")))
    alias_idx = pl.read_parquet(
        _glob_many(str(RUN_ROOT / "edge_alias_index" / "seed=*" / "manifest_fingerprint=*" / "*.parquet"))
    )
    merchant_profile = pl.read_parquet(MERCHANT_PROFILE_PATH)
    legal_country = _merchant_legal_country()

    return {
        "vclass": vclass,
        "vsettle": vsettle,
        "edge": edge,
        "alias_idx": alias_idx,
        "merchant_profile": merchant_profile,
        "legal_country": legal_country,
    }


def _plot_a_series(vclass_enriched: pl.DataFrame) -> None:
    # A1: virtual rate by MCC
    mcc_top = (
        vclass_enriched.group_by("mcc")
        .agg(
            [
                pl.len().alias("n"),
                pl.col("is_virtual").cast(pl.Float64).mean().alias("virtual_rate"),
            ]
        )
        .sort("n", descending=True)
        .head(20)
        .sort("virtual_rate", descending=True)
        .to_pandas()
    )
    fig, ax = plt.subplots(figsize=(8.5, 5.8))
    sns.barplot(data=mcc_top, y="mcc", x="virtual_rate", color="#2E5EAA", ax=ax)
    for idx, row in mcc_top.iterrows():
        ax.text(min(row["virtual_rate"] + 0.01, 0.995), idx, f"n={int(row['n'])}", va="center", fontsize=8)
    ax.set_xlim(0, 1.0)
    ax.set_xlabel("virtual rate")
    ax.set_ylabel("MCC")
    ax.set_title("Virtual Rate by MCC (Top 20 by merchant count)")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "A1_virtual_rate_by_mcc.png")
    plt.close(fig)

    # A2: virtual rate by channel
    by_channel = (
        vclass_enriched.group_by("channel")
        .agg(
            [
                pl.len().alias("n"),
                pl.col("is_virtual").cast(pl.Float64).mean().alias("virtual_rate"),
            ]
        )
        .sort("virtual_rate", descending=True)
        .to_pandas()
    )
    fig, ax = plt.subplots(figsize=(6.8, 4.8))
    sns.barplot(data=by_channel, x="channel", y="virtual_rate", color="#1F7A8C", ax=ax)
    for i, row in by_channel.iterrows():
        ax.text(i, row["virtual_rate"] + 0.02, f"n={int(row['n']):,}", ha="center", fontsize=9)
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("channel")
    ax.set_ylabel("virtual rate")
    ax.set_title("Virtual Rate by Channel")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "A2_virtual_rate_by_channel.png")
    plt.close(fig)

    # A3: virtual rate by legal country
    by_country = (
        vclass_enriched.group_by("legal_country_iso")
        .agg(
            [
                pl.len().alias("n"),
                pl.col("is_virtual").cast(pl.Float64).mean().alias("virtual_rate"),
            ]
        )
        .sort("n", descending=True)
        .head(20)
        .sort("virtual_rate", descending=True)
        .to_pandas()
    )
    fig, ax = plt.subplots(figsize=(9, 5.8))
    sns.barplot(data=by_country, x="legal_country_iso", y="virtual_rate", color="#7B6AA0", ax=ax)
    for i, row in by_country.iterrows():
        ax.text(i, row["virtual_rate"] + 0.01, f"{int(row['n']):,}", ha="center", fontsize=8, rotation=90)
    ax.set_ylim(0, 1.04)
    ax.set_xlabel("legal country")
    ax.set_ylabel("virtual rate")
    ax.set_title("Virtual Rate by Legal Country (Top 20 by merchant count)")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "A3_virtual_rate_by_country.png")
    plt.close(fig)

    # A4: MCC x channel heatmap
    heat = (
        vclass_enriched.group_by(["channel", "mcc"])
        .agg(
            [
                pl.len().alias("n"),
                pl.col("is_virtual").cast(pl.Float64).mean().alias("virtual_rate"),
            ]
        )
        .join(vclass_enriched.group_by("mcc").len().rename({"len": "mcc_n"}), on="mcc", how="left")
        .sort("mcc_n", descending=True)
    )
    top_mcc = heat.select("mcc").unique().head(20).to_series().to_list()
    heat = heat.filter(pl.col("mcc").is_in(top_mcc))
    mat = heat.to_pandas().pivot(index="channel", columns="mcc", values="virtual_rate")
    fig, ax = plt.subplots(figsize=(10.8, 4.8))
    sns.heatmap(mat, cmap="YlOrRd", vmin=0, vmax=1, annot=True, fmt=".2f", linewidths=0.5, ax=ax, cbar_kws={"label": "virtual rate"})
    ax.set_title("Virtual Rate Heatmap: Channel x MCC (Top 20 MCCs)")
    ax.set_xlabel("MCC")
    ax.set_ylabel("channel")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "A4_virtual_rate_mcc_channel_heatmap.png")
    plt.close(fig)


def _plot_b_series(vsettle: pl.DataFrame) -> None:
    settle_pd = vsettle.select(["merchant_id", "lat_deg", "lon_deg", "tzid_settlement"]).to_pandas()

    # B5: settlement density scatter with duplicate marker size
    dup = (
        vsettle.group_by(["lat_deg", "lon_deg"])
        .agg(pl.len().alias("dup_count"))
        .sort("dup_count", descending=True)
        .to_pandas()
    )
    fig, ax = plt.subplots(figsize=(9.2, 5.2))
    sc = ax.scatter(
        dup["lon_deg"],
        dup["lat_deg"],
        s=20 + 18 * dup["dup_count"],
        c=dup["dup_count"],
        cmap="magma",
        alpha=0.85,
        edgecolor="white",
        linewidth=0.3,
    )
    cbar = fig.colorbar(sc, ax=ax)
    cbar.set_label("duplicate merchant count at coordinate")
    ax.set_xlabel("longitude")
    ax.set_ylabel("latitude")
    ax.set_title("Settlement Coordinate Density (size/color = duplicates)")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "B5_settlement_density_hexbin.png")
    plt.close(fig)

    # B6: duplicate counts
    dup_profile = (
        vsettle.group_by(["lat_deg", "lon_deg"])
        .agg(pl.len().alias("dup_count"))
        .group_by("dup_count")
        .agg(pl.len().alias("coord_count"))
        .sort("dup_count")
        .to_pandas()
    )
    fig, ax = plt.subplots(figsize=(7.6, 4.8))
    sns.barplot(data=dup_profile, x="dup_count", y="coord_count", color="#8D6E63", ax=ax)
    for i, row in dup_profile.iterrows():
        ax.text(i, row["coord_count"] + 0.5, f"{int(row['coord_count'])}", ha="center", fontsize=8)
    ax.set_xlabel("merchants sharing exact settlement coordinate")
    ax.set_ylabel("number of distinct coordinates")
    ax.set_title("Settlement Coordinate Duplicate Count Distribution")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "B6_settlement_coord_duplicates.png")
    plt.close(fig)

    # B7: top settlement tzids
    tz_top = (
        vsettle.group_by("tzid_settlement")
        .agg(pl.len().alias("n"))
        .sort("n", descending=True)
        .head(15)
        .to_pandas()
    )
    fig, ax = plt.subplots(figsize=(8.8, 5.2))
    sns.barplot(data=tz_top, y="tzid_settlement", x="n", color="#607D8B", ax=ax)
    ax.set_xlabel("merchant count")
    ax.set_ylabel("settlement tzid")
    ax.set_title("Top 15 Settlement TZIDs")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "B7_settlement_tzid_top15.png")
    plt.close(fig)


def _merchant_country_metrics(edge: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    merchant_country = edge.group_by(["merchant_id", "country_iso"]).agg(pl.len().alias("edge_n"))
    merchant_total = merchant_country.group_by("merchant_id").agg(pl.sum("edge_n").alias("edge_total"))
    shares = merchant_country.join(merchant_total, on="merchant_id", how="left").with_columns(
        (pl.col("edge_n") / pl.col("edge_total")).alias("share")
    )
    # normalized entropy in [0,1]
    ent = (
        shares.group_by("merchant_id")
        .agg(
            [
                pl.max("share").alias("top1_share"),
                pl.len().alias("country_count"),
                ((-pl.col("share") * pl.col("share").log()).sum()).alias("entropy_raw"),
            ]
        )
        .with_columns((pl.col("entropy_raw") / pl.col("country_count").cast(pl.Float64).log()).alias("entropy_norm"))
    )
    return shares, ent


def _plot_c_series(edge: pl.DataFrame, edge_idx: pl.DataFrame) -> None:
    shares, ent = _merchant_country_metrics(edge)
    idx_merch = edge_idx.filter(pl.col("scope") == "MERCHANT")

    merchant_country_count = shares.group_by("merchant_id").agg(pl.len().alias("country_count"))
    uniform_df = (
        idx_merch.select(["merchant_id", "edge_count_total"])
        .join(merchant_country_count, on="merchant_id", how="left")
        .join(ent.select(["merchant_id", "top1_share", "entropy_norm"]), on="merchant_id", how="left")
        .to_pandas()
    )

    # C_uniformity_summary: 2x2 metric distributions
    fig, axes = plt.subplots(2, 2, figsize=(10.8, 7.2))
    metrics = [
        ("edge_count_total", "Edge count per merchant"),
        ("country_count", "Distinct countries per merchant"),
        ("top1_share", "Top-1 country share per merchant"),
        ("entropy_norm", "Normalized country-share entropy"),
    ]
    for ax, (col, title) in zip(axes.flatten(), metrics):
        series = pd.Series(uniform_df[col]).dropna()
        unique_n = int(series.nunique(dropna=True))
        if unique_n <= 1:
            value = float(series.iloc[0]) if len(series) else 0.0
            ax.bar([0], [len(series)], color="#4E79A7", width=0.6)
            ax.set_xticks([0])
            ax.set_xticklabels([f"{value:.6g}"])
            ax.set_xlim(-0.8, 0.8)
        else:
            try:
                sns.histplot(series, bins=min(20, unique_n * 2), color="#4E79A7", ax=ax)
            except ValueError:
                vc = series.value_counts().sort_index()
                ax.bar(range(len(vc)), vc.values, color="#4E79A7", width=0.75)
                ax.set_xticks(range(len(vc)))
                ax.set_xticklabels([f"{v:.6g}" for v in vc.index], rotation=35, ha="right")
        ax.set_title(f"{title} (unique={unique_n})", fontsize=11)
        ax.set_xlabel("")
        ax.set_ylabel("merchant count")
    fig.suptitle("Uniformity Summary (Edge Catalogue Merchant-Level Metrics)", y=0.99)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "C_uniformity_summary.png")
    plt.close(fig)

    # C_country_allocation_profile
    country_profile = edge.group_by("country_iso").agg(pl.len().alias("edge_n")).sort("edge_n", descending=True)
    total_edges = int(country_profile["edge_n"].sum())
    top = country_profile.head(25).to_pandas()
    other_edges = total_edges - int(top["edge_n"].sum())
    top = pd.concat(
        [
            top,
            pd.DataFrame([{"country_iso": "Other", "edge_n": other_edges}]),
        ],
        ignore_index=True,
    )
    fig, ax = plt.subplots(figsize=(11.4, 5.2))
    sns.barplot(data=top, x="country_iso", y="edge_n", color="#7A9E9F", ax=ax)
    plt.setp(ax.get_xticklabels(), rotation=70, ha="right")
    ax.set_xlabel("country")
    ax.set_ylabel("edge count")
    ax.set_title("Edge Allocation by Country (Top 25 + Other)")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "C_country_allocation_profile.png")
    plt.close(fig)

    # C_merchant_country_overlay
    sample_merchants = (
        idx_merch.select("merchant_id").sort("merchant_id").head(5).to_series().to_list()
    )
    top_countries = country_profile.head(20).select("country_iso").to_series().to_list()
    sample = (
        shares.filter(pl.col("merchant_id").is_in(sample_merchants))
        .with_columns(
            pl.when(pl.col("country_iso").is_in(top_countries))
            .then(pl.col("country_iso"))
            .otherwise(pl.lit("Other"))
            .alias("country_bucket")
        )
        .group_by(["merchant_id", "country_bucket"])
        .agg(pl.sum("share").alias("share"))
    )
    order = top_countries + ["Other"]
    sample_pd = sample.to_pandas()
    sample_pd["country_bucket"] = pd.Categorical(sample_pd["country_bucket"], categories=order, ordered=True)
    sample_pd = sample_pd.sort_values(["merchant_id", "country_bucket"])

    fig, ax = plt.subplots(figsize=(11.4, 5.2))
    sns.lineplot(
        data=sample_pd,
        x="country_bucket",
        y="share",
        hue="merchant_id",
        marker="o",
        linewidth=1.6,
        ax=ax,
    )
    plt.setp(ax.get_xticklabels(), rotation=70, ha="right")
    ax.set_xlabel("country bucket")
    ax.set_ylabel("share of merchant edges")
    ax.set_title("Merchant Country-Share Profiles (5 merchant sample)")
    ax.legend(title="merchant_id", ncol=2, fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "C_merchant_country_overlay.png")
    plt.close(fig)

    # C_edge_density_hexbin_log
    edge_pd = edge.select(["lon_deg", "lat_deg"]).to_pandas()
    fig, ax = plt.subplots(figsize=(9.8, 5.6))
    hb = ax.hexbin(edge_pd["lon_deg"], edge_pd["lat_deg"], gridsize=80, bins="log", cmap="viridis", mincnt=1)
    cb = fig.colorbar(hb, ax=ax)
    cb.set_label("edge count (log10)")
    ax.set_xlabel("longitude")
    ax.set_ylabel("latitude")
    ax.set_title("Edge Location Density (Hexbin, Log Scale)")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "C_edge_density_hexbin_log.png")
    plt.close(fig)


def _plot_d_series(alias_idx: pl.DataFrame, edge: pl.DataFrame) -> None:
    policy = json.loads(ALIAS_POLICY_PATH.read_text(encoding="utf-8"))
    endianness = str(policy.get("endianness") or "little")
    blob_path = Path(_glob_one(str(RUN_ROOT / "edge_alias_blob" / "seed=*" / "manifest_fingerprint=*" / "*.bin")))

    alias_merchants = alias_idx.filter(pl.col("scope") == "MERCHANT")

    # D1: alias length vs edge count
    d1 = alias_merchants.select(["merchant_id", "edge_count_total", "alias_table_length"]).to_pandas()
    fig, ax = plt.subplots(figsize=(6.6, 5.2))
    ax.scatter(d1["edge_count_total"], d1["alias_table_length"], s=180, alpha=0.65, color="#4C78A8", edgecolor="white", linewidth=0.8)
    mn = float(min(d1["edge_count_total"].min(), d1["alias_table_length"].min()))
    mx = float(max(d1["edge_count_total"].max(), d1["alias_table_length"].max()))
    ax.plot([mn, mx], [mn, mx], linestyle="--", color="#6B7280", linewidth=1.2)
    mismatch = int((d1["edge_count_total"] != d1["alias_table_length"]).sum())
    uniq_edges = int(d1["edge_count_total"].nunique())
    uniq_alias = int(d1["alias_table_length"].nunique())
    ax.text(
        mn + 1,
        mx - 1,
        f"merchants={len(d1):,}\nlength mismatches={mismatch}\nunique edge_count={uniq_edges}\nunique alias_len={uniq_alias}",
        fontsize=9,
        va="top",
        ha="left",
        bbox=dict(facecolor="white", alpha=0.85, edgecolor="#D1D5DB"),
    )
    ax.set_xlabel("edge count per merchant")
    ax.set_ylabel("alias table length")
    ax.set_title("Alias Table Length vs Edge Count")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "D1_alias_length_vs_edge_count.png")
    plt.close(fig)

    # D2: edge weight vs decoded alias probability
    sample_merchants = alias_merchants.select("merchant_id").sort("merchant_id").head(5).to_series().to_list()
    edge_sample = (
        edge.filter(pl.col("merchant_id").is_in(sample_merchants))
        .select(["merchant_id", "edge_id", "edge_weight"])
        .sort(["merchant_id", "edge_id"])
    )
    points: list[tuple[int, float, float]] = []
    for merchant_id in sample_merchants:
        row = alias_merchants.filter(pl.col("merchant_id") == merchant_id).to_dicts()[0]
        prob, alias = _read_alias_slice(blob_path, int(row["blob_offset_bytes"]), int(row["blob_length_bytes"]), endianness)
        p_hat = _decode_probabilities(prob, alias)
        weights = (
            edge_sample.filter(pl.col("merchant_id") == merchant_id)
            .select("edge_weight")
            .to_series()
            .to_numpy()
        )
        length = min(len(p_hat), len(weights))
        for w, p in zip(weights[:length], p_hat[:length]):
            points.append((merchant_id, float(w), float(p)))

    d2 = pd.DataFrame(points, columns=["merchant_id", "edge_weight", "alias_prob"])
    d2["edge_weight_scaled"] = d2["edge_weight"] * 1000.0
    d2["alias_prob_scaled"] = d2["alias_prob"] * 1000.0
    fig, ax = plt.subplots(figsize=(6.8, 5.2))
    sns.scatterplot(
        data=d2,
        x="edge_weight_scaled",
        y="alias_prob_scaled",
        hue="merchant_id",
        s=22,
        alpha=0.25,
        linewidth=0,
        ax=ax,
    )
    lo = float(min(d2["edge_weight_scaled"].min(), d2["alias_prob_scaled"].min()))
    hi = float(max(d2["edge_weight_scaled"].max(), d2["alias_prob_scaled"].max()))
    ax.plot([lo, hi], [lo, hi], linestyle="--", color="#6B7280", linewidth=1.1)
    max_abs_err = float(np.abs(d2["edge_weight_scaled"] - d2["alias_prob_scaled"]).max())
    ax.text(
        lo + (hi - lo) * 0.02,
        hi - (hi - lo) * 0.06,
        f"max abs error = {max_abs_err:.6f} (x1e-3 scale)",
        fontsize=9,
        bbox=dict(facecolor="white", alpha=0.85, edgecolor="#D1D5DB"),
    )
    ax.set_xlabel("edge weight (x1e-3)")
    ax.set_ylabel("decoded alias probability (x1e-3)")
    ax.set_title("Edge Weight vs Decoded Alias Probability (5-merchant sample)")
    ax.legend(title="merchant_id", fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "D2_edge_weight_vs_alias_prob.png")
    plt.close(fig)


def _plot_e_series(edge: pl.DataFrame, vsettle: pl.DataFrame) -> None:
    joined = edge.select(["merchant_id", "lat_deg", "lon_deg"]).join(
        vsettle.select(["merchant_id", "lat_deg", "lon_deg"]),
        on="merchant_id",
        suffix="_settle",
        how="left",
    )
    dist_km = _haversine_km(
        joined["lat_deg"].to_numpy(),
        joined["lon_deg"].to_numpy(),
        joined["lat_deg_settle"].to_numpy(),
        joined["lon_deg_settle"].to_numpy(),
    )
    dist_log = np.log10(dist_km)
    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    sns.histplot(dist_log, bins=45, color="#4E79A7", ax=ax)
    p50 = float(np.percentile(dist_km, 50))
    p90 = float(np.percentile(dist_km, 90))
    ax.axvline(np.log10(p50), color="#D62728", linestyle="--", linewidth=1.2, label=f"median ~{p50:,.0f} km")
    ax.axvline(np.log10(p90), color="#F28E2B", linestyle=":", linewidth=1.2, label=f"p90 ~{p90:,.0f} km")
    ax.legend(loc="upper right")
    ax.set_xlabel("log10 edge-to-settlement distance (km)")
    ax.set_ylabel("edge count")
    ax.set_title("Edge Distance to Settlement (log10 km)")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "E1_edge_distance_to_settlement.png")
    plt.close(fig)

    # settlement country overlap
    settle_pd = vsettle.select(["merchant_id", "lat_deg", "lon_deg"]).to_pandas()
    settle_gdf = gpd.GeoDataFrame(
        settle_pd,
        geometry=gpd.points_from_xy(settle_pd["lon_deg"], settle_pd["lat_deg"]),
        crs="EPSG:4326",
    )
    world = gpd.read_parquet(WORLD_COUNTRIES_PATH)
    world = world.rename(columns={"country_iso": "settlement_country"})
    settle_join = gpd.sjoin(settle_gdf, world[["settlement_country", "geom"]], how="left", predicate="within")
    settle_join["settlement_country"] = settle_join["settlement_country"].fillna("UNK")
    settle_country = pl.from_pandas(settle_join[["merchant_id", "settlement_country"]])

    by_mc = edge.group_by(["merchant_id", "country_iso"]).agg(pl.len().alias("edge_n"))
    overlap = (
        by_mc.join(settle_country, on="merchant_id", how="left")
        .with_columns((pl.col("country_iso") == pl.col("settlement_country")).alias("is_same"))
        .group_by("settlement_country")
        .agg(
            [
                pl.sum("edge_n").alias("edges_total"),
                (pl.when(pl.col("is_same")).then(pl.col("edge_n")).otherwise(0)).sum().alias("edges_same"),
            ]
        )
        .with_columns((pl.col("edges_same") / pl.col("edges_total")).alias("same_share"))
        .join(settle_country.group_by("settlement_country").agg(pl.len().alias("merchant_count")), on="settlement_country", how="left")
        .sort("merchant_count", descending=True)
    )
    ov = overlap.head(15).to_pandas()
    global_share = float(overlap["edges_same"].sum() / overlap["edges_total"].sum())
    max_share = float(ov["same_share"].max()) if len(ov) else 0.0
    zoom_max = min(0.10, max_share + 0.02) if max_share > 0 else 0.10

    fig, axes = plt.subplots(1, 2, figsize=(11.2, 5.6), sharey=True)
    for ax, xlim, subtitle in [
        (axes[0], (0, zoom_max), f"Zoomed (0-{int(zoom_max*100)}%)"),
        (axes[1], (0, 1.0), "Full scale"),
    ]:
        sns.barplot(data=ov, y="settlement_country", x="same_share", color="#59A14F", ax=ax)
        ax.set_xlim(*xlim)
        ax.axvline(global_share, color="#D62728", linestyle="--", linewidth=1.2, label=f"global={global_share:.3f}")
        ax.set_title(subtitle, fontsize=11)
        ax.set_xlabel("edge share in settlement country")
        if ax is axes[0]:
            ax.set_ylabel("settlement country")
        else:
            ax.set_ylabel("")
        ax.legend(loc="lower right", fontsize=8)

    fig.suptitle("Edge Share in Settlement Country (Top 15 Settlement Countries)", y=0.99)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "E2_settlement_country_overlap.png")
    plt.close(fig)


def main() -> None:
    _set_theme()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    frames = _load_core_frames()
    vclass = frames["vclass"]
    vsettle = frames["vsettle"]
    edge = frames["edge"]
    alias_idx = frames["alias_idx"]
    merchant_profile = frames["merchant_profile"]
    legal_country = frames["legal_country"]

    vclass_enriched = (
        vclass.join(merchant_profile.select(["merchant_id", "mcc", "channel", "home_country_iso"]), on="merchant_id", how="left")
        .join(legal_country, on="merchant_id", how="left")
        .with_columns(pl.coalesce(["legal_country_iso", "home_country_iso"]).alias("legal_country_iso"))
    )

    _plot_a_series(vclass_enriched)
    _plot_b_series(vsettle)
    _plot_c_series(edge, alias_idx)
    _plot_d_series(alias_idx, edge)
    _plot_e_series(edge, vsettle)

    print("3B plot refresh complete. Files written under:", OUT_DIR)


if __name__ == "__main__":
    main()
