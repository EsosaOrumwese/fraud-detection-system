from __future__ import annotations

import glob
import json
import math
import struct
from pathlib import Path

import geopandas as gpd
import numpy as np
import polars as pl
import seaborn as sns
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

RUN_ROOT = Path("runs/local_full_run-5/c25a2675fbfbacd952b13bb594880e92/data/layer1/3B")
OUT_DIR = Path("docs/reports/reports/eda/segment_3B/plots")
POLICY_PATH = Path("config/layer1/2B/policy/alias_layout_policy_v1.json")
WORLD_COUNTRIES = Path("reference/spatial/world_countries/2024/world_countries.parquet")

sns.set_theme(
    style="darkgrid",
    rc={
        "axes.facecolor": "#EAEAF2",
        "figure.facecolor": "white",
        "grid.color": "white",
        "grid.linestyle": "-",
        "grid.linewidth": 1.0,
    },
)


def _glob_one(pattern: str) -> str:
    matches = sorted(glob.glob(pattern))
    if not matches:
        raise FileNotFoundError(f"No matches for pattern: {pattern}")
    if len(matches) > 1:
        # deterministic pick if multiple; caller can override by supplying a tighter pattern
        return matches[0]
    return matches[0]


def _glob_many(pattern: str) -> list[str]:
    matches = sorted(glob.glob(pattern))
    if not matches:
        raise FileNotFoundError(f"No matches for pattern: {pattern}")
    return matches


def _decode_probabilities(prob: np.ndarray, alias: np.ndarray) -> np.ndarray:
    count = prob.size
    if count == 0:
        return np.array([], dtype=np.float64)
    p_hat = prob / float(count)
    residual = (1.0 - prob) / float(count)
    for idx in range(count):
        target = int(alias[idx])
        p_hat[target] += residual[idx]
    return p_hat


def _read_alias_slice(blob_path: Path, offset: int, length: int, endianness: str) -> tuple[np.ndarray, np.ndarray, int]:
    endian = "<" if endianness == "little" else ">"
    with blob_path.open("rb") as handle:
        handle.seek(int(offset))
        data = handle.read(int(length))
    if len(data) < 16:
        raise ValueError("Alias slice too short to read header.")
    n_sites, prob_qbits, _r0, _r1 = struct.unpack(endian + "IIII", data[:16])
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
    return prob, alias, int(prob_qbits)


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


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    endianness = str(policy.get("endianness") or "little")

    alias_index_files = _glob_many(str(RUN_ROOT / "edge_alias_index" / "seed=*" / "manifest_fingerprint=*" / "*.parquet"))
    alias_blob_file = _glob_one(str(RUN_ROOT / "edge_alias_blob" / "seed=*" / "manifest_fingerprint=*" / "*.bin"))
    edge_files = _glob_many(str(RUN_ROOT / "edge_catalogue" / "seed=*" / "manifest_fingerprint=*" / "*.parquet"))
    settlement_files = _glob_many(str(RUN_ROOT / "virtual_settlement" / "seed=*" / "manifest_fingerprint=*" / "*.parquet"))

    alias_index = pl.read_parquet(alias_index_files)
    alias_merchants = alias_index.filter(pl.col("scope") == "MERCHANT")

    # D1: Alias table length vs edge count
    d1_df = alias_merchants.select(["merchant_id", "edge_count_total", "alias_table_length"]).to_pandas()
    x = d1_df["edge_count_total"].to_numpy()
    y = d1_df["alias_table_length"].to_numpy()
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.scatter(x, y, s=220, alpha=0.7, color="#4c72b0", edgecolor="white", linewidth=0.8)
    ax.plot([x.min(), x.max()], [x.min(), x.max()], linestyle="--", color="#444", linewidth=1)
    ax.set_title("D1: Alias Table Length vs Edge Count")
    ax.set_xlabel("Edge count per merchant")
    ax.set_ylabel("Alias table length")
    ax.set_xlim(x.min() - 5, x.max() + 5)
    ax.set_ylim(y.min() - 5, y.max() + 5)
    ax.text(x.min() + 1, y.max() - 2, f"n={len(d1_df)} (all overlap)", fontsize=9, color="#444")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "D1_alias_length_vs_edge_count.png", dpi=160)
    plt.close(fig)

    # D2: Edge weight vs alias probability (sample merchants)
    sample_merchants = alias_merchants.select("merchant_id").head(3).to_series().to_list()
    edge_lf = (
        pl.scan_parquet(edge_files)
        .filter(pl.col("merchant_id").is_in(sample_merchants))
        .select(["merchant_id", "edge_id", "edge_weight"])
    )
    edge_df = edge_lf.collect()

    alias_blob_path = Path(alias_blob_file)
    points = []
    for merchant_id in sample_merchants:
        m_edges = (
            edge_df.filter(pl.col("merchant_id") == merchant_id)
            .sort("edge_id")
            .select(["edge_weight"])
            .to_series()
            .to_numpy()
        )
        row = alias_merchants.filter(pl.col("merchant_id") == merchant_id).to_dicts()[0]
        prob, alias, _prob_qbits = _read_alias_slice(
            alias_blob_path, int(row["blob_offset_bytes"]), int(row["blob_length_bytes"]), endianness
        )
        p_hat = _decode_probabilities(prob, alias)
        if len(m_edges) != len(p_hat):
            length = min(len(m_edges), len(p_hat))
            m_edges = m_edges[:length]
            p_hat = p_hat[:length]
        for w, p in zip(m_edges, p_hat):
            points.append((merchant_id, w, p))

    d2_df = pl.DataFrame(points, schema=["merchant_id", "edge_weight", "alias_prob"], orient="row").to_pandas()
    # rescale to avoid unreadable tiny tick labels
    d2_df["edge_weight_scaled"] = d2_df["edge_weight"] * 1e3
    d2_df["alias_prob_scaled"] = d2_df["alias_prob"] * 1e3
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.scatter(
        d2_df["edge_weight_scaled"],
        d2_df["alias_prob_scaled"],
        s=40,
        alpha=0.15,
        color="#4c72b0",
        linewidth=0,
    )
    min_v = min(d2_df["edge_weight_scaled"].min(), d2_df["alias_prob_scaled"].min())
    max_v = max(d2_df["edge_weight_scaled"].max(), d2_df["alias_prob_scaled"].max())
    ax.plot([min_v, max_v], [min_v, max_v], linestyle="--", color="#444", linewidth=1)
    ax.set_title("D2: Edge Weight vs Alias Probability (sample merchants)")
    ax.set_xlabel("Edge weight (×1e-3)")
    ax.set_ylabel("Decoded alias probability (×1e-3)")
    ax.set_xlim(min_v * 0.999, max_v * 1.001)
    ax.set_ylim(min_v * 0.999, max_v * 1.001)
    ax.text(
        min_v * 1.0005,
        max_v * 0.9995,
        f"all points overlap at ~{d2_df['edge_weight_scaled'].iloc[0]:.3f}\n(n={len(d2_df)})",
        fontsize=8,
        color="#444",
        ha="left",
        va="top",
    )
    fig.tight_layout()
    fig.savefig(OUT_DIR / "D2_edge_weight_vs_alias_prob.png", dpi=160)
    plt.close(fig)

    # E1: Edge distance to settlement
    edges_geo = pl.scan_parquet(edge_files).select(["merchant_id", "lat_deg", "lon_deg"]).collect()
    settle_geo = pl.scan_parquet(settlement_files).select(["merchant_id", "lat_deg", "lon_deg"]).collect()
    joined = edges_geo.join(settle_geo, on="merchant_id", suffix="_settle")
    dist_km = _haversine_km(
        joined["lat_deg"].to_numpy(),
        joined["lon_deg"].to_numpy(),
        joined["lat_deg_settle"].to_numpy(),
        joined["lon_deg_settle"].to_numpy(),
    )
    dist_log = np.log10(dist_km)
    fig, ax = plt.subplots(figsize=(7, 4.5))
    sns.histplot(dist_log, bins=40, color="#4c72b0", ax=ax)
    ax.set_title("E1: Edge Distance to Settlement (log10 km)")
    ax.set_xlabel("log10 distance to settlement (km)")
    ax.set_ylabel("Edge count")
    median = float(np.median(dist_km))
    p90 = float(np.percentile(dist_km, 90))
    ax.axvline(np.log10(median), color="#d62728", linestyle="--", linewidth=1, label=f"median ~{median:,.0f} km")
    ax.axvline(np.log10(p90), color="#ff7f0e", linestyle=":", linewidth=1, label=f"p90 ~{p90:,.0f} km")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "E1_edge_distance_to_settlement.png", dpi=160)
    plt.close(fig)

    # E2: Settlement country vs edge country overlap
    settle_pd = settle_geo.to_pandas()
    settle_gdf = gpd.GeoDataFrame(
        settle_pd,
        geometry=gpd.points_from_xy(settle_pd["lon_deg"], settle_pd["lat_deg"]),
        crs="EPSG:4326",
    )
    world = gpd.read_parquet(WORLD_COUNTRIES)
    world = world.rename(columns={"country_iso": "settlement_country"})
    settle_joined = gpd.sjoin(settle_gdf, world[["settlement_country", "geom"]], how="left", predicate="within")
    settle_joined["settlement_country"] = settle_joined["settlement_country"].fillna("UNK")

    settle_country = pl.from_pandas(settle_joined[["merchant_id", "settlement_country"]])
    edges_counts = (
        pl.scan_parquet(edge_files)
        .select(["merchant_id", "country_iso"])
        .group_by(["merchant_id", "country_iso"])
        .len()
        .collect()
    )
    edges_joined = edges_counts.join(settle_country, on="merchant_id", how="left")
    edges_joined = edges_joined.with_columns(
        (pl.col("country_iso") == pl.col("settlement_country")).alias("is_same")
    )
    agg = edges_joined.group_by("settlement_country").agg(
        [
            pl.col("len").sum().alias("edges_total"),
            pl.col("len").filter(pl.col("is_same")).sum().alias("edges_same"),
        ]
    )
    agg = agg.with_columns((pl.col("edges_same") / pl.col("edges_total")).alias("same_share"))
    merch_counts = settle_country.group_by("settlement_country").len().rename({"len": "merchant_count"})
    agg = agg.join(merch_counts, on="settlement_country", how="left")
    agg_pd = agg.to_pandas().sort_values("merchant_count", ascending=False)

    top_n = 15
    plot_df = agg_pd.head(top_n)
    global_share = float(agg_pd["edges_same"].sum() / agg_pd["edges_total"].sum())

    max_share = float(plot_df["same_share"].max()) if not plot_df.empty else 0.0
    zoom_max = min(0.1, max_share + 0.02) if max_share > 0 else 0.1
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 5.5), sharey=True)
    for ax, xlim, title in [
        (axes[0], (0, zoom_max), f"Zoomed (0–{int(zoom_max*100)}%)"),
        (axes[1], (0, 1.0), "Full scale (0–100%)"),
    ]:
        sns.barplot(
            data=plot_df,
            x="same_share",
            y="settlement_country",
            color="#4c72b0",
            ax=ax,
        )
        ax.set_xlim(*xlim)
        ax.set_title(title)
        ax.set_xlabel("Share of edges in settlement country")
        ax.set_ylabel("Settlement country" if ax is axes[0] else "")
        for idx, row in plot_df.iterrows():
            ax.text(
                min(row["same_share"] + 0.01, xlim[1] - 0.01),
                list(plot_df.index).index(idx),
                f"n={int(row['merchant_count'])}",
                va="center",
                fontsize=8,
            )
        ax.axvline(global_share, color="#d62728", linestyle="--", linewidth=1, label=f"global ~{global_share:.2f}")
        ax.legend(fontsize=8, loc="lower right")

    fig.suptitle("E2: Edge Share in Settlement Country (Top Settlement Countries)")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "E2_settlement_country_overlap.png", dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    main()
