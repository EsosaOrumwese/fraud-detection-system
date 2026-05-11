from __future__ import annotations

from pathlib import Path

import duckdb
import matplotlib
import numpy as np
import pandas as pd


matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[5]
RUN_ROOT = ROOT / "runs" / "local_full_run-7" / "a3bd8cac9a4284cd36072c6b9624a0c1"
ARRIVAL_ROOT = RUN_ROOT / "data" / "layer2" / "5B" / "arrival_events"
EXPORT_DIR = (
    ROOT
    / "analysis"
    / "dev_full_offline_investigation"
    / "00_investigation"
    / "watson_workbench"
    / "exports"
    / "interface_world"
    / "traffic_primitives"
    / "branches"
    / "grain_and_identity"
)
FIGURE_DIR = EXPORT_DIR / "figures"


def parquet_pattern(path: Path) -> str:
    return str(path / "**" / "*.parquet").replace("\\", "/")


def savefig(name: str) -> None:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    plt.savefig(FIGURE_DIR / name, dpi=180, bbox_inches="tight")
    plt.close()


def style_axes(ax: plt.Axes) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", color="#d9d2c3", linewidth=0.8, alpha=0.65)
    ax.set_axisbelow(True)


def compact_int(value: float) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return f"{value:,.0f}"


def load_or_build_summaries() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    merchant_path = EXPORT_DIR / "merchant_arrival_counts.csv"
    bucket_path = EXPORT_DIR / "bucket_index_summary.csv"
    selected_path = EXPORT_DIR / "selected_merchant_bucket_progression.csv"
    selected_sample_path = EXPORT_DIR / "selected_merchant_sequence_sample.csv"
    grain_path = EXPORT_DIR / "grain_scale_summary.csv"

    if merchant_path.exists() and bucket_path.exists() and selected_path.exists() and selected_sample_path.exists() and grain_path.exists():
        return (
            pd.read_csv(merchant_path),
            pd.read_csv(bucket_path),
            pd.read_csv(selected_path),
            pd.read_csv(selected_sample_path),
            pd.read_csv(grain_path),
        )

    con = duckdb.connect()
    con.execute("SET threads TO 8")
    con.execute(
        f"""
        CREATE OR REPLACE VIEW arrivals AS
        SELECT *
        FROM read_parquet('{parquet_pattern(ARRIVAL_ROOT)}', hive_partitioning=true)
        """
    )

    merchant_df = con.execute(
        """
        SELECT
            merchant_id,
            COUNT(*)::UBIGINT AS arrival_rows,
            MIN(arrival_seq)::BIGINT AS min_arrival_seq,
            MAX(arrival_seq)::BIGINT AS max_arrival_seq,
            MIN(ts_utc) AS first_ts_utc,
            MAX(ts_utc) AS last_ts_utc,
            COUNT(DISTINCT channel_group)::UBIGINT AS channel_groups,
            COUNT(DISTINCT zone_representation)::UBIGINT AS zones
        FROM arrivals
        GROUP BY merchant_id
        ORDER BY arrival_rows DESC, merchant_id
        """
    ).fetchdf()
    merchant_df.to_csv(merchant_path, index=False)

    bucket_df = con.execute(
        """
        SELECT
            bucket_index,
            COUNT(*)::UBIGINT AS arrival_rows,
            COUNT(DISTINCT merchant_id)::UBIGINT AS merchants,
            MIN(ts_utc) AS first_ts_utc,
            MAX(ts_utc) AS last_ts_utc
        FROM arrivals
        GROUP BY bucket_index
        ORDER BY bucket_index
        """
    ).fetchdf()
    bucket_df.to_csv(bucket_path, index=False)

    selected_ids = {
        "lowest-volume merchant": merchant_df.sort_values(["arrival_rows", "merchant_id"]).iloc[0]["merchant_id"],
        "median-volume merchant": merchant_df.iloc[(merchant_df["arrival_rows"] - merchant_df["arrival_rows"].median()).abs().argsort().iloc[0]][
            "merchant_id"
        ],
        "highest-volume merchant": merchant_df.iloc[0]["merchant_id"],
    }
    label_map = {merchant_id: label for label, merchant_id in selected_ids.items()}
    selected_values = ", ".join(f"'{merchant_id}'" for merchant_id in selected_ids.values())

    selected_df = con.execute(
        f"""
        SELECT
            merchant_id,
            bucket_index,
            COUNT(*)::UBIGINT AS arrivals_in_bucket,
            MIN(arrival_seq)::BIGINT AS min_arrival_seq,
            MAX(arrival_seq)::BIGINT AS max_arrival_seq,
            MIN(ts_utc) AS first_ts_utc,
            MAX(ts_utc) AS last_ts_utc
        FROM arrivals
        WHERE merchant_id IN ({selected_values})
        GROUP BY merchant_id, bucket_index
        ORDER BY merchant_id, bucket_index
        """
    ).fetchdf()
    selected_df["volume_case"] = selected_df["merchant_id"].map(label_map)
    selected_df.to_csv(selected_path, index=False)

    selected_sample_df = con.execute(
        f"""
        WITH selected AS (
            SELECT
                merchant_id,
                bucket_index,
                arrival_seq,
                ts_utc,
                COUNT(*) OVER (PARTITION BY merchant_id) AS merchant_rows,
                ROW_NUMBER() OVER (PARTITION BY merchant_id ORDER BY arrival_seq) AS rn
            FROM arrivals
            WHERE merchant_id IN ({selected_values})
        ),
        sampled AS (
            SELECT
                merchant_id,
                bucket_index,
                arrival_seq,
                ts_utc
            FROM selected
            WHERE rn = 1
               OR rn = merchant_rows
               OR rn % GREATEST(1, CAST(FLOOR(merchant_rows / 650.0) AS BIGINT)) = 0
        )
        SELECT *
        FROM sampled
        ORDER BY merchant_id, arrival_seq
        """
    ).fetchdf()
    selected_sample_df["volume_case"] = selected_sample_df["merchant_id"].map(label_map)
    selected_sample_df.to_csv(selected_sample_path, index=False)

    grain_df = con.execute(
        """
        SELECT 'arrival rows' AS measure, COUNT(*)::DOUBLE AS value FROM arrivals
        UNION ALL
        SELECT 'merchants', COUNT(DISTINCT merchant_id)::DOUBLE FROM arrivals
        UNION ALL
        SELECT 'bucket indexes', COUNT(DISTINCT bucket_index)::DOUBLE FROM arrivals
        UNION ALL
        SELECT 'physical sites', COUNT(DISTINCT site_id)::DOUBLE FROM arrivals WHERE site_id IS NOT NULL
        UNION ALL
        SELECT 'virtual edges', COUNT(DISTINCT edge_id)::DOUBLE FROM arrivals WHERE edge_id IS NOT NULL
        """
    ).fetchdf()
    grain_df.to_csv(grain_path, index=False)

    return merchant_df, bucket_df, selected_df, selected_sample_df, grain_df


def plot_grain_scale(grain_df: pd.DataFrame) -> None:
    order = ["arrival rows", "physical sites", "virtual edges", "merchants", "bucket indexes"]
    data = grain_df.set_index("measure").loc[order].reset_index()
    colors = ["#1f4e5f", "#6d8f71", "#b86b42", "#c9a227", "#5d6d7e"]

    fig, ax = plt.subplots(figsize=(10.5, 5.6))
    bars = ax.bar(data["measure"], data["value"], color=colors, edgecolor="none")
    ax.set_yscale("log")
    ax.set_title("Arrival Surface Grain: Observation Volume vs Actor and Context Counts", fontsize=14, weight="bold")
    ax.set_ylabel("Count (log scale)")
    ax.set_xlabel("")
    style_axes(ax)
    for bar, value in zip(bars, data["value"]):
        ax.text(bar.get_x() + bar.get_width() / 2, value * 1.08, compact_int(value), ha="center", va="bottom", fontsize=10)
    savefig("01_grain_scale_observations_vs_context.png")


def plot_bucket_coverage(bucket_df: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True, gridspec_kw={"height_ratios": [1, 2.4]})

    expected = np.arange(int(bucket_df["bucket_index"].min()), int(bucket_df["bucket_index"].max()) + 1)
    present = np.isin(expected, bucket_df["bucket_index"].to_numpy())
    present_count = int(present.sum())
    axes[0].barh([0], [len(expected)], left=[expected.min()], height=0.42, color="#e7decf", edgecolor="none")
    axes[0].barh([0], [present_count], left=[expected.min()], height=0.42, color="#6d8f71", edgecolor="none")
    if present_count < len(expected):
        missing = expected[~present]
        axes[0].scatter(missing, np.zeros_like(missing), color="#b86b42", s=12, zorder=3, label="missing bucket")
        axes[0].legend(frameon=False, loc="upper right")
    axes[0].text(
        expected.min() + len(expected) / 2,
        0,
        f"{present_count:,} / {len(expected):,} bucket indexes present",
        ha="center",
        va="center",
        fontsize=12,
        weight="bold",
    )
    axes[0].set_yticks([])
    axes[0].set_ylim(-0.7, 0.7)
    axes[0].set_title("Bucket Index Coverage: 2,160 Hourly Slots Across the 90-Day Horizon", fontsize=14, weight="bold")
    axes[0].spines[["top", "right", "left"]].set_visible(False)

    axes[1].plot(bucket_df["bucket_index"], bucket_df["arrival_rows"], color="#1f4e5f", linewidth=1.2)
    axes[1].set_ylabel("Arrival rows")
    axes[1].set_xlabel("bucket_index")
    axes[1].set_title("Traffic Intensity by Canonical Horizon Bucket", fontsize=12, weight="bold")
    style_axes(axes[1])
    savefig("02_bucket_index_coverage_and_traffic.png")


def plot_merchant_distribution(merchant_df: pd.DataFrame) -> None:
    values = merchant_df["arrival_rows"].to_numpy()
    median = np.median(values)
    mean = np.mean(values)
    p95 = np.quantile(values, 0.95)
    max_value = np.max(values)

    fig, ax = plt.subplots(figsize=(11, 6))
    bins = np.geomspace(values.min(), values.max(), 42)
    ax.hist(values, bins=bins, color="#1f4e5f", alpha=0.88, edgecolor="none")
    ax.set_xscale("log")
    ax.set_title("Merchant Arrival-Volume Distribution", fontsize=14, weight="bold")
    ax.set_xlabel("Arrival rows per merchant (log scale)")
    ax.set_ylabel("Merchant count")
    style_axes(ax)
    markers = [
        ("median", median, "#c9a227"),
        ("mean", mean, "#b86b42"),
        ("p95", p95, "#6d8f71"),
        ("max", max_value, "#7b3f61"),
    ]
    ymax = ax.get_ylim()[1]
    for label, value, color in markers:
        ax.axvline(value, color=color, linewidth=2)
        ax.text(value, ymax * 0.92, f"{label}\n{compact_int(value)}", rotation=90, ha="right", va="top", color=color, fontsize=9)
    savefig("03_merchant_arrival_volume_distribution.png")


def plot_merchant_cumulative_share(merchant_df: pd.DataFrame) -> None:
    ranked = merchant_df.sort_values("arrival_rows", ascending=False).reset_index(drop=True)
    ranked["merchant_rank_share"] = (ranked.index + 1) / len(ranked)
    ranked["arrival_cume_share"] = ranked["arrival_rows"].cumsum() / ranked["arrival_rows"].sum()

    checkpoints = [0.01, 0.05, 0.10, 0.20]
    fig, ax = plt.subplots(figsize=(10.5, 6))
    ax.plot(ranked["merchant_rank_share"] * 100, ranked["arrival_cume_share"] * 100, color="#1f4e5f", linewidth=2.4)
    ax.plot([0, 100], [0, 100], color="#b8ad9a", linestyle="--", linewidth=1.2, label="equal contribution reference")
    for share in checkpoints:
        idx = max(0, int(np.ceil(share * len(ranked))) - 1)
        y = ranked.loc[idx, "arrival_cume_share"] * 100
        ax.scatter([share * 100], [y], color="#b86b42", s=44, zorder=5)
        ax.text(share * 100 + 1.2, y, f"top {share:.0%}: {y:.1f}%", va="center", fontsize=9)
    ax.set_title("Cumulative Arrival Share by Ranked Merchants", fontsize=14, weight="bold")
    ax.set_xlabel("Top merchants included (%)")
    ax.set_ylabel("Cumulative arrival rows (%)")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.legend(frameon=False, loc="lower right")
    style_axes(ax)
    savefig("04_ranked_merchants_cumulative_arrival_share.png")


def plot_arrival_seq_validation(merchant_df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8.5, 7.5))
    ax.scatter(merchant_df["arrival_rows"], merchant_df["max_arrival_seq"], s=20, color="#1f4e5f", alpha=0.55, edgecolors="none")
    limit = merchant_df[["arrival_rows", "max_arrival_seq"]].to_numpy().max()
    ax.plot([0, limit], [0, limit], color="#b86b42", linewidth=2, label="max arrival_seq = row count")
    ax.set_title("Merchant-Local Sequence Check", fontsize=14, weight="bold")
    ax.set_xlabel("Arrival rows per merchant")
    ax.set_ylabel("Max arrival_seq per merchant")
    ax.legend(frameon=False, loc="upper left")
    style_axes(ax)
    savefig("05_arrival_seq_matches_merchant_row_count.png")


def plot_selected_merchant_progression(selected_sample_df: pd.DataFrame) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
    colors = {
        "lowest-volume merchant": "#c9a227",
        "median-volume merchant": "#6d8f71",
        "highest-volume merchant": "#1f4e5f",
    }
    ordered_labels = ["lowest-volume merchant", "median-volume merchant", "highest-volume merchant"]
    for ax, label in zip(axes, ordered_labels):
        group = selected_sample_df[selected_sample_df["volume_case"] == label]
        ax.scatter(
            group["bucket_index"],
            group["arrival_seq"],
            s=10,
            color=colors.get(label, "#555555"),
            alpha=0.62,
            edgecolors="none",
        )
        ax.set_title(label, fontsize=11, weight="bold", loc="left")
        ax.set_ylabel("arrival_seq")
        style_axes(ax)
    axes[-1].set_xlabel("bucket_index")
    fig.suptitle("Selected Merchants: arrival_seq Is Merchant-Local Identity, Not a Shared Time Axis", fontsize=14, weight="bold", y=0.995)
    savefig("06_selected_merchants_arrival_seq_vs_bucket.png")


def plot_channel_and_route_context() -> None:
    traffic_dir = EXPORT_DIR.parents[1]
    channel_df = pd.read_csv(traffic_dir / "arrival_events_channel_summary.csv")
    virtual_df = pd.read_csv(traffic_dir / "arrival_events_virtual_summary.csv")

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.6))

    channel_df = channel_df.sort_values("rows", ascending=False)
    x = np.arange(len(channel_df))
    width = 0.36
    axes[0].bar(x - width / 2, channel_df["row_share"] * 100, width=width, color="#1f4e5f", edgecolor="none", label="arrival rows")
    axes[0].bar(
        x + width / 2,
        channel_df["merchants"] / channel_df["merchants"].sum() * 100,
        width=width,
        color="#c9a227",
        edgecolor="none",
        label="merchants",
    )
    axes[0].set_xticks(x, channel_df["channel_group"], rotation=10)
    axes[0].set_ylabel("Share (%)")
    axes[0].set_title("Channel Exposure: Row Share vs Merchant Participation", fontsize=12, weight="bold")
    axes[0].legend(frameon=False)
    style_axes(axes[0])

    virtual_df["route_lane"] = np.where(virtual_df["is_virtual"].astype(str).str.lower() == "true", "virtual", "physical")
    virtual_df = virtual_df.sort_values("route_lane")
    x = np.arange(len(virtual_df))
    axes[1].bar(x - width / 2, virtual_df["row_share"] * 100, width=width, color="#1f4e5f", edgecolor="none", label="arrival rows")
    axes[1].bar(
        x + width / 2,
        virtual_df["merchants"] / virtual_df["merchants"].sum() * 100,
        width=width,
        color="#b86b42",
        edgecolor="none",
        label="merchants",
    )
    axes[1].set_xticks(x, virtual_df["route_lane"])
    axes[1].set_ylabel("Share (%)")
    axes[1].set_title("Route Lane: Physical/Virtual Split", fontsize=12, weight="bold")
    axes[1].legend(frameon=False)
    style_axes(axes[1])

    fig.suptitle("Context Fields Change the Meaning of the Same Arrival Grain", fontsize=14, weight="bold", y=1.03)
    savefig("07_channel_and_route_context_at_arrival_grain.png")


def main() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "figure.facecolor": "#fbf7ef",
            "axes.facecolor": "#fbf7ef",
            "axes.edgecolor": "#3c3a36",
            "axes.labelcolor": "#292724",
            "xtick.color": "#292724",
            "ytick.color": "#292724",
            "text.color": "#292724",
        }
    )

    merchant_df, bucket_df, selected_df, selected_sample_df, grain_df = load_or_build_summaries()
    plot_grain_scale(grain_df)
    plot_bucket_coverage(bucket_df)
    plot_merchant_distribution(merchant_df)
    plot_merchant_cumulative_share(merchant_df)
    plot_arrival_seq_validation(merchant_df)
    plot_selected_merchant_progression(selected_sample_df)
    plot_channel_and_route_context()

    print(f"Wrote figures to {FIGURE_DIR}")


if __name__ == "__main__":
    main()
