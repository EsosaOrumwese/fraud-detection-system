from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[5]
EXPORT_ROOT = (
    REPO_ROOT
    / "analysis"
    / "dev_full_offline_investigation"
    / "00_investigation"
    / "watson_workbench"
    / "exports"
    / "interface_world"
    / "behavioural_streams"
    / "branches"
    / "baseline_vs_fraud_overlay_contract"
)
FIGURE_ROOT = EXPORT_ROOT / "figures"

COLORS = {
    "baseline": "#4E79A7",
    "with_fraud": "#F28E2B",
    "fraud": "#E15759",
    "non_fraud": "#59A14F",
    "campaign": "#B07AA1",
    "muted": "#BAB0AC",
    "grid": "#D9DEE7",
    "text": "#2F3A45",
    "ok": "#59A14F",
    "change": "#E15759",
}


def read_csv(name: str) -> pd.DataFrame:
    return pd.read_csv(EXPORT_ROOT / name)


def save_figure(fig: plt.Figure, name: str) -> None:
    FIGURE_ROOT.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURE_ROOT / name, dpi=180, bbox_inches="tight")
    plt.close(fig)


def style_axis(ax: plt.Axes, grid_axis: str = "y") -> None:
    ax.set_axisbelow(True)
    ax.grid(axis=grid_axis, color=COLORS["grid"], linewidth=0.8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#9AA4B2")
    ax.spines["bottom"].set_color("#9AA4B2")
    ax.tick_params(colors=COLORS["text"], labelsize=9)


def add_bar_labels(ax: plt.Axes, bars, fmt="{:,.0f}", pad=3, fontsize=8.5) -> None:
    for bar in bars:
        height = bar.get_height()
        ax.annotate(
            fmt.format(height),
            xy=(bar.get_x() + bar.get_width() / 2, height),
            xytext=(0, pad),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=fontsize,
            color="#111111",
        )


def plot_schema_overlay_contract() -> None:
    schema = read_csv("schema_overlay_contract.csv").copy()
    schema = schema.sort_values(["overlay_added_column", "column"], ascending=[False, True]).reset_index(drop=True)

    y = np.arange(len(schema))
    fig, ax = plt.subplots(figsize=(9.2, 5.8))

    for i, row in schema.iterrows():
        baseline_present = bool(row["in_baseline"])
        with_fraud_present = bool(row["in_with_fraud"])
        color = COLORS["change"] if row["overlay_added_column"] else COLORS["baseline"]

        if baseline_present and with_fraud_present:
            ax.plot([0, 1], [i, i], color="#B8C2CE", linewidth=1.8, zorder=1)
        if baseline_present:
            ax.scatter(0, i, s=72, color=COLORS["baseline"], edgecolor="white", linewidth=0.8, zorder=2)
        else:
            ax.scatter(0, i, s=72, facecolor="white", edgecolor="#C7CED8", linewidth=1.3, zorder=2)
        if with_fraud_present:
            ax.scatter(1, i, s=86 if row["overlay_added_column"] else 72, color=color, edgecolor="white", linewidth=0.8, zorder=2)
        else:
            ax.scatter(1, i, s=72, facecolor="white", edgecolor="#C7CED8", linewidth=1.3, zorder=2)

    ax.set_yticks(y)
    ax.set_yticklabels(schema["column"])
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["baseline", "with_fraud"])
    ax.set_xlim(-0.35, 1.35)
    ax.invert_yaxis()
    ax.set_title("With-Fraud Keeps the Baseline Stream Body and Adds Two Overlay Fields", loc="left")
    ax.text(1.08, 0, "overlay-added", va="center", fontsize=8.8, color=COLORS["change"], fontweight="bold")
    ax.text(1.08, 1, "overlay-added", va="center", fontsize=8.8, color=COLORS["change"], fontweight="bold")
    ax.grid(axis="x", color=COLORS["grid"], linewidth=0.8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#9AA4B2")
    ax.spines["bottom"].set_color("#9AA4B2")
    ax.tick_params(colors=COLORS["text"], labelsize=9)
    save_figure(fig, "01_schema_overlay_contract.png")


def plot_contract_shape_and_amount_delta() -> None:
    delta = read_csv("baseline_with_fraud_contract_delta.csv")

    shape_metrics = delta[delta["metric"].isin(["rows", "event_types"])].copy()
    amount_metrics = delta[delta["metric"].isin(["mean_amount", "median_amount", "p95_amount"])].copy()

    fig, axes = plt.subplots(1, 3, figsize=(14, 4.8), gridspec_kw={"width_ratios": [1.1, 1.2, 1.4]})

    ax = axes[0]
    rows = delta[delta["metric"] == "rows"].iloc[0]
    bars = ax.bar(
        ["baseline", "with_fraud"],
        [rows["baseline"] / 1_000_000, rows["with_fraud"] / 1_000_000],
        color=[COLORS["baseline"], COLORS["with_fraud"]],
        edgecolor="none",
    )
    add_bar_labels(ax, bars, fmt="{:,.1f}M")
    ax.set_ylabel("Event rows (millions)")
    ax.set_title("Traffic volume", loc="left")
    style_axis(ax)

    ax = axes[1]
    event_types = delta[delta["metric"] == "event_types"].iloc[0]
    bars = ax.bar(
        ["baseline", "with_fraud"],
        [event_types["baseline"], event_types["with_fraud"]],
        color=[COLORS["baseline"], COLORS["with_fraud"]],
        edgecolor="none",
    )
    add_bar_labels(ax, bars)
    ax.set_ylim(0, 2.7)
    ax.set_ylabel("Event types")
    ax.set_title("Grammar breadth", loc="left")
    style_axis(ax)

    ax = axes[2]
    labels = ["mean", "median", "p95"]
    x = np.arange(len(labels))
    width = 0.36
    baseline_values = amount_metrics["baseline"].to_numpy()
    with_fraud_values = amount_metrics["with_fraud"].to_numpy()
    ax.bar(x - width / 2, baseline_values, width, color=COLORS["baseline"], label="baseline", edgecolor="none")
    ax.bar(x + width / 2, with_fraud_values, width, color=COLORS["with_fraud"], label="with_fraud", edgecolor="none")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Amount")
    ax.set_title("Global amount surface barely moves", loc="left")
    ax.legend(frameon=False, loc="upper left")
    style_axis(ax)

    fig.suptitle("Overlay Preserves Traffic Shape While Slightly Moving Global Amount Statistics", x=0.06, ha="left")
    save_figure(fig, "02_contract_shape_and_amount_delta.png")


def plot_fraud_sparsity_and_amount_contrast() -> None:
    overlay = read_csv("with_fraud_overlay_summary.csv")
    overlay["label"] = overlay["fraud_flag"].map({False: "non-fraud", True: "fraud"})

    fig, axes = plt.subplots(1, 3, figsize=(14, 4.8), gridspec_kw={"width_ratios": [1.2, 1.3, 1.5]})

    ax = axes[0]
    share = overlay.set_index("label")["row_share"]
    bars = ax.bar(["non-fraud", "fraud"], share.loc[["non-fraud", "fraud"]] * 100, color=[COLORS["non_fraud"], COLORS["fraud"]], edgecolor="none")
    ax.set_yscale("log")
    ax.set_ylabel("Event-row share (%) log scale")
    ax.set_title("Fraud is sparse", loc="left")
    for bar, label in zip(bars, ["99.996987%", "0.003013%"]):
        ax.annotate(label, (bar.get_x() + bar.get_width() / 2, bar.get_height()), xytext=(0, 4), textcoords="offset points", ha="center", fontsize=8.2)
    style_axis(ax)

    ax = axes[1]
    amount_cols = ["mean_amount", "median_amount"]
    labels = ["mean", "median"]
    x = np.arange(len(labels))
    width = 0.36
    nf = overlay[overlay["label"] == "non-fraud"].iloc[0]
    fr = overlay[overlay["label"] == "fraud"].iloc[0]
    ax.bar(x - width / 2, [nf[c] for c in amount_cols], width, color=COLORS["non_fraud"], label="non-fraud", edgecolor="none")
    ax.bar(x + width / 2, [fr[c] for c in amount_cols], width, color=COLORS["fraud"], label="fraud", edgecolor="none")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Amount")
    ax.set_title("Marked rows are amount-elevated", loc="left")
    ax.legend(frameon=False)
    style_axis(ax)

    ax = axes[2]
    total_delta = read_csv("baseline_with_fraud_contract_delta.csv")
    total_row = total_delta[total_delta["metric"] == "total_amount"].iloc[0]
    bars = ax.bar(["baseline total", "overlay increase"], [total_row["baseline"], total_row["delta"]], color=[COLORS["baseline"], COLORS["change"]], edgecolor="none")
    ax.set_yscale("log")
    ax.set_ylabel("Total amount contribution (log scale)")
    ax.set_title("Large absolute total, tiny overlay lift", loc="left")
    ax.text(0, total_row["baseline"] * 1.12, "$11.509B", ha="center", fontsize=8.5)
    ax.text(1, total_row["delta"] * 1.18, "$437.5K", ha="center", fontsize=8.5)
    style_axis(ax)

    fig.suptitle("Fraud Is Rare at Row Grain but Economically Different Where Marked", x=0.06, ha="left")
    save_figure(fig, "03_fraud_sparsity_and_amount_contrast.png")


def plot_fraud_event_side_balance() -> None:
    by_event = read_csv("fraud_flag_by_event_type.csv")
    fraud = by_event[by_event["fraud_flag"] == True].copy()

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8))

    ax = axes[0]
    bars = ax.bar(fraud["event_type"], fraud["rows"], color=[COLORS["baseline"], COLORS["fraud"]], edgecolor="none")
    add_bar_labels(ax, bars)
    ax.set_ylabel("Fraud-marked event rows")
    ax.set_title("Fraud rows split evenly by event side", loc="left")
    ax.set_ylim(0, 8_000)
    style_axis(ax)

    ax = axes[1]
    flow = read_csv("fraud_flow_shape.csv").iloc[0]
    values = [flow["min_events_per_flow"], flow["median_events_per_flow"], flow["max_events_per_flow"], flow["nonstandard_flow_shapes"]]
    labels = ["min events\nper flow", "median events\nper flow", "max events\nper flow", "nonstandard\nflow shapes"]
    bars = ax.bar(labels, values, color=[COLORS["ok"], COLORS["ok"], COLORS["ok"], COLORS["change"]], edgecolor="none")
    add_bar_labels(ax, bars)
    ax.set_ylim(0, 2.6)
    ax.set_title("Fraud flows preserve two-event grammar", loc="left")
    style_axis(ax)

    fig.suptitle("Fraud Marking Is Flow-Consistent, Not One-Sided", x=0.06, ha="left")
    save_figure(fig, "04_fraud_event_side_balance.png")


def plot_fraud_row_preservation_and_mutation() -> None:
    comparison = read_csv("fraud_rows_vs_baseline.csv").iloc[0]

    preserved_labels = ["matched\nbaseline", "same\nevent type", "same\ntimestamp", "same\namount"]
    preserved_values = [
        comparison["matched_baseline_rows"],
        comparison["same_event_type_rows"],
        comparison["same_ts_rows"],
        comparison["same_amount_rows"],
    ]

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), gridspec_kw={"width_ratios": [1.35, 1]})

    ax = axes[0]
    bars = ax.bar(preserved_labels, preserved_values, color=[COLORS["ok"], COLORS["ok"], COLORS["ok"], COLORS["change"]], edgecolor="none")
    add_bar_labels(ax, bars)
    ax.set_ylim(0, 15_500)
    ax.set_ylabel("Fraud-marked rows")
    ax.set_title("Identity and timing preserved; amount changed", loc="left")
    style_axis(ax)

    ax = axes[1]
    delta_labels = ["min", "mean", "max"]
    delta_values = [comparison["min_amount_delta"], comparison["mean_amount_delta"], comparison["max_amount_delta"]]
    bars = ax.bar(delta_labels, delta_values, color=[COLORS["muted"], COLORS["campaign"], COLORS["change"]], edgecolor="none")
    add_bar_labels(ax, bars, fmt="{:,.2f}")
    ax.set_ylabel("Amount delta vs baseline")
    ax.set_title("Fraud-row amount mutation", loc="left")
    style_axis(ax)

    fig.suptitle("Marked Rows Match Baseline Keys and Timestamps, Then Mutate Amount", x=0.06, ha="left")
    save_figure(fig, "05_fraud_row_preservation_and_mutation.png")


def plot_campaign_overlay_footprint() -> None:
    campaigns = read_csv("campaign_overlay_summary.csv").copy()
    campaigns["rank"] = np.arange(1, len(campaigns) + 1)

    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.8), gridspec_kw={"width_ratios": [1.25, 1]})

    ax = axes[0]
    bars = ax.bar(campaigns["rank"], campaigns["flows"], color=COLORS["campaign"], edgecolor="none")
    add_bar_labels(ax, bars)
    ax.set_xlabel("Campaign rank by row footprint")
    ax.set_ylabel("Fraud flows")
    ax.set_title("Campaign footprint is uneven", loc="left")
    ax.set_xticks(campaigns["rank"])
    style_axis(ax)

    ax = axes[1]
    ax.scatter(campaigns["flows"], campaigns["mean_amount"], s=campaigns["rows"] / 12, color=COLORS["campaign"], alpha=0.85, edgecolor="white", linewidth=0.8)
    for _, row in campaigns.iterrows():
        ax.text(row["flows"], row["mean_amount"] + 0.08, f"#{int(row['rank'])}", ha="center", fontsize=8)
    ax.set_xlabel("Fraud flows")
    ax.set_ylabel("Mean amount")
    ax.set_title("Footprint vs amount posture", loc="left")
    style_axis(ax, grid_axis="both")

    fig.suptitle("Campaign IDs Expose Footprint, Not Meaning", x=0.06, ha="left")
    save_figure(fig, "06_campaign_overlay_footprint.png")


def plot_null_semantics() -> None:
    nulls = read_csv("with_fraud_nulls.csv")
    rows = int(nulls.loc[nulls["column"] == "campaign_id", "null_count"].iloc[0])
    overlay = read_csv("with_fraud_overlay_summary.csv")
    non_fraud_rows = int(overlay[overlay["fraud_flag"] == False]["rows"].iloc[0])
    fraud_rows = int(overlay[overlay["fraud_flag"] == True]["rows"].iloc[0])

    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    labels = ["campaign_id\nnull rows", "non-fraud\nrows", "fraud\nrows"]
    values = [rows, non_fraud_rows, fraud_rows]
    colors = [COLORS["muted"], COLORS["non_fraud"], COLORS["fraud"]]
    bars = ax.bar(labels, values, color=colors, edgecolor="none")
    ax.set_yscale("log")
    ax.set_ylabel("Rows (log scale)")
    ax.set_title("campaign_id Nullness Matches the Non-Fraud State", loc="left")
    ax.text(0, rows * 1.18, f"{rows:,}", ha="center", fontsize=8.5)
    ax.text(1, non_fraud_rows * 1.18, f"{non_fraud_rows:,}", ha="center", fontsize=8.5)
    ax.text(2, fraud_rows * 1.18, f"{fraud_rows:,}", ha="center", fontsize=8.5)
    style_axis(ax)
    save_figure(fig, "07_campaign_id_null_semantics.png")


def plot_stream_profile_preservation_evidence() -> None:
    profile = read_csv("stream_contract_profile.csv").set_index("stream")
    fingerprint = read_csv("stream_key_fingerprint.csv").set_index("stream_name")

    ratio_metrics = pd.DataFrame(
        {
            "metric": ["event rows", "approx flows", "event types", "key fingerprint"],
            "ratio": [
                profile.loc["with_fraud", "rows"] / profile.loc["baseline", "rows"],
                profile.loc["with_fraud", "approx_flows"] / profile.loc["baseline", "approx_flows"],
                profile.loc["with_fraud", "event_types"] / profile.loc["baseline", "event_types"],
                fingerprint.loc["with_fraud", "key_hash_sum"] / fingerprint.loc["baseline", "key_hash_sum"],
            ],
        }
    )

    horizon = pd.DataFrame(
        {
            "stream": ["baseline", "with_fraud"],
            "min_ts": [
                pd.to_datetime(profile.loc["baseline", "min_ts_utc"], utc=True).tz_convert(None),
                pd.to_datetime(profile.loc["with_fraud", "min_ts_utc"], utc=True).tz_convert(None),
            ],
            "max_ts": [
                pd.to_datetime(profile.loc["baseline", "max_ts_utc"], utc=True).tz_convert(None),
                pd.to_datetime(profile.loc["with_fraud", "max_ts_utc"], utc=True).tz_convert(None),
            ],
        }
    )

    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.8), gridspec_kw={"width_ratios": [1.05, 1.35]})

    ax = axes[0]
    y = np.arange(len(ratio_metrics))
    ax.axvline(1.0, color=COLORS["ok"], linestyle="--", linewidth=1.2, label="perfect preservation")
    ax.scatter(ratio_metrics["ratio"], y, s=90, color=COLORS["baseline"], edgecolor="white", linewidth=0.8, zorder=3)
    ax.set_yticks(y)
    ax.set_yticklabels(ratio_metrics["metric"])
    ax.set_xlim(0.995, 1.005)
    ax.set_xlabel("with_fraud / baseline")
    ax.set_title("Profile signals sit exactly at parity", loc="left")
    ax.legend(frameon=False, loc="lower right")
    style_axis(ax, grid_axis="x")

    ax = axes[1]
    y = np.arange(len(horizon))
    colors = [COLORS["baseline"], COLORS["with_fraud"]]
    for i, row in horizon.iterrows():
        ax.hlines(i, row["min_ts"], row["max_ts"], color=colors[i], linewidth=7, alpha=0.85)
        ax.scatter(row["min_ts"], i, color=colors[i], s=42, edgecolor="white", linewidth=0.8, zorder=3)
        ax.scatter(row["max_ts"], i, color=colors[i], s=42, edgecolor="white", linewidth=0.8, zorder=3)
    ax.set_yticks(y)
    ax.set_yticklabels(horizon["stream"])
    ax.set_xlim(horizon["min_ts"].min() - pd.Timedelta(days=3), horizon["max_ts"].max() + pd.Timedelta(days=3))
    ax.set_xlabel("UTC date")
    ax.set_title("Both streams occupy the same operating horizon", loc="left")
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    style_axis(ax, grid_axis="x")

    fig.suptitle("Full-Stream Preservation Evidence Is Profile-and-Fingerprint Based", x=0.06, ha="left")
    save_figure(fig, "08_stream_profile_preservation_evidence.png")


def plot_campaign_grammar_and_time_span() -> None:
    campaigns = read_csv("campaign_overlay_summary.csv").copy()
    campaigns["rank"] = np.arange(1, len(campaigns) + 1)
    campaigns["rows_per_flow"] = campaigns["rows"] / campaigns["flows"]
    campaigns["min_ts"] = pd.to_datetime(campaigns["min_ts_utc"], utc=True).dt.tz_convert(None)
    campaigns["max_ts"] = pd.to_datetime(campaigns["max_ts_utc"], utc=True).dt.tz_convert(None)

    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.8), gridspec_kw={"width_ratios": [1, 1.35]})

    ax = axes[0]
    ax.plot(campaigns["rank"], campaigns["rows_per_flow"], marker="o", color=COLORS["campaign"], label="rows per flow")
    ax.plot(campaigns["rank"], campaigns["event_types"], marker="s", color=COLORS["baseline"], label="event types")
    ax.axhline(2, color=COLORS["ok"], linestyle="--", linewidth=1.2, label="two-event contract")
    ax.set_xticks(campaigns["rank"])
    ax.set_xlabel("Campaign rank by row footprint")
    ax.set_ylabel("Count")
    ax.set_ylim(1.7, 2.3)
    ax.set_title("Each campaign keeps the two-event grammar", loc="left")
    ax.legend(frameon=False, loc="upper right")
    style_axis(ax)

    ax = axes[1]
    y = campaigns["rank"]
    ax.hlines(y, campaigns["min_ts"], campaigns["max_ts"], color=COLORS["campaign"], linewidth=5, alpha=0.8)
    ax.scatter(campaigns["min_ts"], y, color=COLORS["baseline"], s=34, zorder=3, label="first fraud row")
    ax.scatter(campaigns["max_ts"], y, color=COLORS["fraud"], s=34, zorder=3, label="last fraud row")
    ax.set_yticks(y)
    ax.set_yticklabels([f"#{int(rank)}" for rank in campaigns["rank"]])
    ax.invert_yaxis()
    ax.set_xlim(campaigns["min_ts"].min() - pd.Timedelta(days=3), campaigns["max_ts"].max() + pd.Timedelta(days=3))
    ax.set_xlabel("UTC date")
    ax.set_ylabel("Campaign rank")
    ax.set_title("Campaign footprints span the operating window", loc="left")
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=2)
    style_axis(ax, grid_axis="x")

    fig.suptitle("Campaign IDs Preserve Stream Grammar While Exposing Uneven Footprints", x=0.06, ha="left")
    save_figure(fig, "09_campaign_grammar_and_time_span.png")


def main() -> None:
    plot_schema_overlay_contract()
    plot_contract_shape_and_amount_delta()
    plot_fraud_sparsity_and_amount_contrast()
    plot_fraud_event_side_balance()
    plot_fraud_row_preservation_and_mutation()
    plot_campaign_overlay_footprint()
    plot_null_semantics()
    plot_stream_profile_preservation_evidence()
    plot_campaign_grammar_and_time_span()


if __name__ == "__main__":
    main()
