from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "docs" / "experience_lake" / "outward-facing-assets" / "portfolio" / "_assets"
DEFAULT_SRC_CSV = ROOT / "scratch_files" / "costs.csv"

BG = "#F7F4ED"
TEXT = "#161514"
MUTED = "#5E5A55"
GRID = "#D9D1C7"
LINE = "#3A3632"
ACCENT = "#B5653A"
HEAT_LOW = "#F2E7DE"
HEAT_HIGH = "#204B57"


def _money(x: float) -> str:
    return f"${x:,.2f}"


def resolve_path(raw_path: str, *, default: Path, label: str) -> Path:
    candidate = Path(raw_path).expanduser() if raw_path else default
    if not candidate.is_absolute():
        candidate = (ROOT / candidate).resolve()
    if not candidate.exists():
        raise FileNotFoundError(f"missing_{label}:{candidate}")
    return candidate


def resolve_output_dir(raw_path: str, *, default: Path) -> Path:
    candidate = Path(raw_path).expanduser() if raw_path else default
    if not candidate.is_absolute():
        candidate = (ROOT / candidate).resolve()
    return candidate


def load_cost_data(src_csv: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = pd.read_csv(src_csv)
    metric_cols = [c for c in raw.columns if c != "Service"]

    totals_row = raw.loc[raw["Service"] == "Service total"].copy()
    if totals_row.empty:
        raise RuntimeError("Missing `Service total` row in costs.csv")

    daily_rows = raw.loc[raw["Service"] != "Service total"].copy()
    daily_rows["date"] = pd.to_datetime(daily_rows["Service"])
    daily_rows = daily_rows.sort_values("date").reset_index(drop=True)

    service_cols = [c for c in metric_cols if c != "Total costs($)"]
    daily_long = daily_rows.melt(
        id_vars=["Service", "date", "Total costs($)"],
        value_vars=service_cols,
        var_name="service_col",
        value_name="daily_cost",
    )
    daily_long["daily_cost"] = pd.to_numeric(daily_long["daily_cost"], errors="coerce").fillna(0.0)

    totals_long = totals_row.melt(
        id_vars=["Service"],
        value_vars=service_cols,
        var_name="service_col",
        value_name="window_total",
    )
    totals_long["window_total"] = pd.to_numeric(totals_long["window_total"], errors="coerce").fillna(0.0)

    merged = daily_long.merge(totals_long[["service_col", "window_total"]], on="service_col", how="left")
    merged["service"] = merged["service_col"].str.replace(r"\(\$\)$", "", regex=True)
    merged["service"] = merged["service"].replace(
        {
            "Relational Database Service": "RDS / Aurora",
            "Managed Streaming for Apache Kafka": "MSK",
            "Elastic Container Service": "ECS",
            "Elastic Container Service for Kubernetes": "EKS",
            "EC2 Container Registry (ECR)": "ECR",
            "Key Management Service": "KMS",
        }
    )

    daily_totals = daily_rows[["date", "Total costs($)"]].rename(columns={"Total costs($)": "daily_total"})
    return merged, daily_totals


def style_axes(ax: plt.Axes) -> None:
    ax.set_facecolor(BG)
    for spine in ax.spines.values():
        spine.set_color(GRID)
    ax.tick_params(colors=MUTED)
    ax.xaxis.label.set_color(MUTED)
    ax.yaxis.label.set_color(MUTED)
    ax.title.set_color(TEXT)


def save(fig: plt.Figure, stem: str, asset_dir: Path) -> None:
    asset_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(asset_dir / f"{stem}.png", dpi=300, bbox_inches="tight", facecolor=BG)
    fig.savefig(asset_dir / f"{stem}.svg", bbox_inches="tight", facecolor=BG)
    plt.close(fig)


def build_cost_window_panel(*, asset_dir: Path, src_csv: Path) -> None:
    asset_dir.mkdir(parents=True, exist_ok=True)
    merged, daily_totals = load_cost_data(src_csv)

    top_n = 10
    service_rank = (
        merged.groupby("service", as_index=False)["window_total"]
        .max()
        .sort_values("window_total", ascending=False)
        .reset_index(drop=True)
    )
    top_services = service_rank.head(top_n)["service"].tolist()

    top_df = merged.loc[merged["service"].isin(top_services)].copy()
    tail_total = service_rank.loc[~service_rank["service"].isin(top_services), "window_total"].sum()
    tail_daily = (
        merged.loc[~merged["service"].isin(top_services)]
        .groupby("date", as_index=False)["daily_cost"]
        .sum()
        .assign(service="Remaining low-cost services", window_total=tail_total)
    )
    top_df = pd.concat(
        [top_df[["date", "service", "daily_cost", "window_total"]], tail_daily],
        ignore_index=True,
    )

    order = top_services + ["Remaining low-cost services"]
    heat = (
        top_df.pivot_table(index="service", columns="date", values="daily_cost", aggfunc="sum")
        .reindex(order)
        .fillna(0.0)
    )
    totals = (
        top_df.groupby("service", as_index=False)["window_total"]
        .max()
        .set_index("service")
        .reindex(order)["window_total"]
    )

    export = heat.copy()
    export["window_total"] = totals
    export = export.reset_index().rename(columns={"service": "service"})
    export.to_csv(asset_dir / "appendix_g_cost_window_daily_breakdown.source.csv", index=False)

    cmap = LinearSegmentedColormap.from_list("cost_heat", [HEAT_LOW, "#D6C6B6", ACCENT, HEAT_HIGH])

    fig = plt.figure(figsize=(14.5, 10.0), facecolor=BG)
    gs = fig.add_gridspec(2, 1, height_ratios=[0.9, 1.45], hspace=0.26)
    ax_top = fig.add_subplot(gs[0, 0])
    ax_heat = fig.add_subplot(gs[1, 0])

    for ax in (ax_top, ax_heat):
        style_axes(ax)

    fig.suptitle(
        "Appendix G — Daily Cost Movement Inside the Accepted Proving Window",
        x=0.055,
        y=0.98,
        ha="left",
        fontsize=19,
        color=TEXT,
        fontweight="bold",
    )
    fig.text(
        0.055,
        0.94,
        "The line shows daily total spend across 10–13 March; the matrix below shows where that spend sat by service family.",
        ha="left",
        va="top",
        fontsize=11.5,
        color=MUTED,
    )

    ax_top.grid(axis="y", color=GRID, linewidth=0.8, alpha=0.7)
    ax_top.plot(daily_totals["date"], daily_totals["daily_total"], color=LINE, linewidth=2.8, marker="o", markersize=6)
    ax_top.fill_between(daily_totals["date"], daily_totals["daily_total"], color=ACCENT, alpha=0.10)
    ax_top.set_title("Daily total", loc="left", fontsize=12.5, pad=10, fontweight="bold")
    ax_top.set_ylabel("Daily total (USD)", fontsize=10.5)
    ax_top.set_ylim(0, daily_totals["daily_total"].max() * 1.16)
    ax_top.xaxis.set_major_locator(mdates.DayLocator(interval=1))
    ax_top.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))

    peak = daily_totals.loc[daily_totals["daily_total"].idxmax()]
    ax_top.annotate(
        f"Peak day: {peak['date']:%d %b}  {_money(float(peak['daily_total']))}",
        xy=(peak["date"], peak["daily_total"]),
        xytext=(14, 14),
        textcoords="offset points",
        fontsize=9.5,
        color=TEXT,
        arrowprops={"arrowstyle": "->", "color": MUTED, "lw": 1},
    )

    mat = heat.to_numpy()
    im = ax_heat.imshow(mat, cmap=cmap, aspect="auto")
    ax_heat.set_title("Service-family daily breakdown", loc="left", fontsize=12.5, pad=10, fontweight="bold")
    ax_heat.set_xticks(np.arange(heat.shape[1]))
    ax_heat.set_xticklabels([pd.Timestamp(c).strftime("%d %b") for c in heat.columns], fontsize=10, color=MUTED)
    ax_heat.set_yticks(np.arange(heat.shape[0]))
    ax_heat.set_yticklabels(heat.index.tolist(), fontsize=10, color=TEXT)

    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            val = float(mat[i, j])
            color = "white" if val >= 70 else TEXT
            ax_heat.text(j, i, f"{val:.2f}", ha="center", va="center", fontsize=8.8, color=color)

    # Right-side total column as aligned text, not a second heatmap scale.
    ax_heat.set_xlim(-0.5, heat.shape[1] + 1.25)
    ax_heat.axvline(heat.shape[1] - 0.5, color=GRID, linewidth=1.0)
    ax_heat.text(heat.shape[1] + 0.25, -1.0, "Window total", fontsize=10, color=MUTED, fontweight="bold")
    for i, total in enumerate(totals.tolist()):
        ax_heat.text(heat.shape[1] + 0.25, i, _money(float(total)), va="center", fontsize=9.2, color=TEXT)

    ax_heat.set_xlabel("Accepted proving window days", fontsize=10.5)
    for spine in ax_heat.spines.values():
        spine.set_color(GRID)
    ax_heat.set_xticks(np.arange(-0.5, heat.shape[1], 1), minor=True)
    ax_heat.set_yticks(np.arange(-0.5, heat.shape[0], 1), minor=True)
    ax_heat.grid(which="minor", color=BG, linewidth=1.2)
    ax_heat.tick_params(which="minor", bottom=False, left=False)

    cbar = fig.colorbar(im, ax=ax_heat, fraction=0.025, pad=0.03)
    cbar.outline.set_edgecolor(GRID)
    cbar.ax.tick_params(colors=MUTED, labelsize=9)
    cbar.set_label("Daily service cost (USD)", color=MUTED, fontsize=9.5)

    save(fig, "appendix_g_cost_window_daily_breakdown", asset_dir)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the outward-facing Appendix G cost movement panel from a cost CSV input."
    )
    parser.add_argument("--src-csv", default=str(DEFAULT_SRC_CSV))
    parser.add_argument("--asset-dir", default=str(ASSET_DIR))
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    build_cost_window_panel(
        asset_dir=resolve_output_dir(args.asset_dir, default=ASSET_DIR),
        src_csv=resolve_path(args.src_csv, default=DEFAULT_SRC_CSV, label="cost_csv"),
    )
