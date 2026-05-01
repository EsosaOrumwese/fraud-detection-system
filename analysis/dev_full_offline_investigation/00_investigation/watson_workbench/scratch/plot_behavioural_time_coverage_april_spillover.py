from __future__ import annotations

from pathlib import Path

import matplotlib.dates as mdates
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
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
    / "time_coverage_and_april_spillover"
)
FIGURE_ROOT = EXPORT_ROOT / "figures"

BOUNDARY_TS = pd.Timestamp("2026-04-01T00:00:00Z")

COLORS = {
    "arrival_events_5B": "#4E79A7",
    "baseline": "#59A14F",
    "with_fraud": "#F28E2B",
    "request": "#4E79A7",
    "response": "#E15759",
    "april": "#B07AA1",
    "muted": "#777777",
    "grid": "#D9DEE7",
}


def read_csv(name: str) -> pd.DataFrame:
    return pd.read_csv(EXPORT_ROOT / name)


def save_figure(fig: plt.Figure, name: str) -> None:
    FIGURE_ROOT.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURE_ROOT / name, dpi=180, bbox_inches="tight")
    plt.close(fig)


def format_integer_axis(ax: plt.Axes) -> None:
    ax.get_xaxis().set_major_formatter(
        plt.FuncFormatter(lambda x, _: f"{int(x):,}" if abs(x) >= 1 else f"{x:g}")
    )


def style_axis(ax: plt.Axes) -> None:
    ax.grid(axis="x", color=COLORS["grid"], linewidth=0.8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#9AA4B2")
    ax.spines["bottom"].set_color("#9AA4B2")
    ax.tick_params(colors="#2F3A45", labelsize=9)


def plot_horizon_profile() -> None:
    profile = read_csv("time_horizon_profile.csv")
    profile["min_ts"] = pd.to_datetime(profile["min_ts_utc"], utc=True)
    profile["max_ts"] = pd.to_datetime(profile["max_ts_utc"], utc=True)

    fig, (ax, ax_zoom) = plt.subplots(
        1,
        2,
        figsize=(13.5, 4.8),
        gridspec_kw={"width_ratios": [2.5, 1.35]},
    )
    y_positions = np.arange(len(profile))

    for idx, row in profile.iterrows():
        color = COLORS.get(row["stream"], COLORS["muted"])
        ax.hlines(
            y=idx,
            xmin=row["min_ts"],
            xmax=row["max_ts"],
            color=color,
            linewidth=9,
            alpha=0.9,
        )
        ax.scatter([row["min_ts"], row["max_ts"]], [idx, idx], s=60, color=color, zorder=3)

    ax.axvline(BOUNDARY_TS, color="#222222", linewidth=1.4, linestyle="--")
    ax.text(BOUNDARY_TS, -0.65, "UTC Apr 1 boundary", fontsize=9, color="#222222", va="top")
    ax.set_yticks(y_positions)
    ax.set_yticklabels(profile["stream"])
    ax.set_title("Behavioural Streams Extend Past the Arrival Horizon by Response Time", loc="left")
    ax.set_xlabel("UTC event time")
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.set_ylim(-0.8, len(profile) - 0.2)
    ax.grid(axis="x", color=COLORS["grid"], linewidth=0.8)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color("#9AA4B2")
    ax.tick_params(colors="#2F3A45", labelsize=9)

    zoom_start = pd.Timestamp("2026-03-31T23:57:00Z")
    zoom_end = pd.Timestamp("2026-04-01T00:02:30Z")
    for idx, row in profile.iterrows():
        color = COLORS.get(row["stream"], COLORS["muted"])
        line_start = max(row["min_ts"], zoom_start)
        line_end = min(row["max_ts"], zoom_end)
        ax_zoom.hlines(idx, line_start, line_end, color=color, linewidth=9, alpha=0.9)
        ax_zoom.scatter([row["max_ts"]], [idx], s=55, color=color, zorder=3)
        ax_zoom.text(
            row["max_ts"] + pd.Timedelta(seconds=7),
            idx,
            row["max_ts"].strftime("%H:%M:%S"),
            va="center",
            fontsize=8.5,
            color="#2F3A45",
        )
    ax_zoom.axvline(BOUNDARY_TS, color="#222222", linewidth=1.4, linestyle="--")
    ax_zoom.set_xlim(zoom_start, zoom_end)
    ax_zoom.set_yticks(y_positions)
    ax_zoom.set_yticklabels([])
    ax_zoom.set_title("Boundary zoom", loc="left", fontsize=10)
    ax_zoom.set_xlabel("UTC terminal minutes")
    ax_zoom.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    ax_zoom.grid(axis="x", color=COLORS["grid"], linewidth=0.8)
    ax_zoom.spines[["top", "right", "left"]].set_visible(False)
    ax_zoom.spines["bottom"].set_color("#9AA4B2")
    ax_zoom.tick_params(colors="#2F3A45", labelsize=9)
    save_figure(fig, "01_horizon_profile_boundary.png")


def plot_monthly_counts_with_tail() -> None:
    monthly = read_csv("monthly_boundary_counts.csv")
    behavioural = monthly[monthly["stream"].isin(["baseline", "with_fraud"])].copy()
    behavioural["rows_m"] = behavioural["rows"] / 1_000_000
    behavioural["utc_month"] = pd.Categorical(
        behavioural["utc_month"], ["2026-01", "2026-02", "2026-03", "2026-04"], ordered=True
    )

    fig, (ax_main, ax_tail) = plt.subplots(
        1,
        2,
        figsize=(12, 4.8),
        gridspec_kw={"width_ratios": [3.2, 1]},
    )

    pivot = behavioural.pivot(index="utc_month", columns="stream", values="rows_m")
    x = np.arange(len(pivot.index))
    width = 0.36
    ax_main.bar(
        x - width / 2,
        pivot["baseline"],
        width=width,
        color=COLORS["baseline"],
        label="baseline",
        edgecolor="none",
    )
    ax_main.bar(
        x + width / 2,
        pivot["with_fraud"],
        width=width,
        color=COLORS["with_fraud"],
        label="with_fraud",
        edgecolor="none",
    )
    ax_main.set_xticks(x)
    ax_main.set_xticklabels(pivot.index.astype(str))
    ax_main.set_ylabel("Event rows (millions)")
    ax_main.set_title("Monthly Event Volume Is Jan-Mar Traffic With a Tiny April Tail", loc="left")
    ax_main.legend(frameon=False, loc="upper right")
    style_axis(ax_main)
    ax_main.grid(axis="y", color=COLORS["grid"], linewidth=0.8)
    ax_main.grid(axis="x", visible=False)

    april = behavioural[behavioural["utc_month"].astype(str) == "2026-04"].copy()
    ax_tail.bar(
        april["stream"],
        april["rows"],
        color=[COLORS["baseline"], COLORS["with_fraud"]],
        edgecolor="none",
    )
    for xpos, rows in enumerate(april["rows"]):
        ax_tail.text(xpos, rows + 6, f"{int(rows):,}", ha="center", fontsize=9)
    ax_tail.set_ylim(0, 180)
    ax_tail.set_ylabel("April event rows")
    ax_tail.set_title("April tail only", loc="left", fontsize=10)
    ax_tail.tick_params(axis="x", rotation=20)
    style_axis(ax_tail)
    ax_tail.grid(axis="y", color=COLORS["grid"], linewidth=0.8)
    ax_tail.grid(axis="x", visible=False)

    save_figure(fig, "02_monthly_volume_with_april_tail.png")


def plot_april_event_side() -> None:
    april = read_csv("april_rows_by_event_side.csv")
    streams = ["baseline", "with_fraud"]
    sides = [
        ("AUTH_REQUEST", 0, COLORS["request"]),
        ("AUTH_RESPONSE", 1, COLORS["response"]),
    ]

    rows = []
    for stream in streams:
        for event_type, event_seq, color in sides:
            match = april[
                (april["stream"] == stream)
                & (april["event_type"] == event_type)
                & (april["event_seq"] == event_seq)
            ]
            rows.append(
                {
                    "stream": stream,
                    "event_type": event_type,
                    "rows": int(match["rows"].iloc[0]) if not match.empty else 0,
                    "color": color,
                }
            )
    df = pd.DataFrame(rows)

    fig, ax = plt.subplots(figsize=(8.8, 4.8))
    x = np.arange(len(streams))
    width = 0.34
    for offset, event_type in [(-width / 2, "AUTH_REQUEST"), (width / 2, "AUTH_RESPONSE")]:
        sub = df[df["event_type"] == event_type]
        ax.bar(
            x + offset,
            sub["rows"],
            width=width,
            label=event_type,
            color=sub["color"].iloc[0],
            edgecolor="none",
        )
        for xpos, rows in zip(x + offset, sub["rows"]):
            ax.text(xpos, rows + 5, f"{rows:,}", ha="center", fontsize=9)

    ax.set_xticks(x)
    ax.set_xticklabels(streams)
    ax.set_ylabel("April event rows")
    ax.set_title("April Spillover Is Response-Side Only", loc="left")
    ax.legend(frameon=False, loc="upper left")
    ax.set_ylim(0, 180)
    style_axis(ax)
    ax.grid(axis="y", color=COLORS["grid"], linewidth=0.8)
    ax.grid(axis="x", visible=False)
    save_figure(fig, "03_april_response_side_only.png")


def plot_boundary_minute_profile() -> None:
    minutes = read_csv("boundary_minutes_by_event_side.csv")
    minutes["minute_ts"] = pd.to_datetime(minutes["utc_minute"] + ":00Z", utc=True)

    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5), sharey=True)
    for ax, stream in zip(axes, ["baseline", "with_fraud"]):
        stream_df = minutes[minutes["stream"] == stream].copy()
        for event_type, color in [("AUTH_REQUEST", COLORS["request"]), ("AUTH_RESPONSE", COLORS["response"])]:
            sub = stream_df[stream_df["event_type"] == event_type].sort_values("minute_ts")
            ax.plot(
                sub["minute_ts"],
                sub["rows"],
                marker="o",
                linewidth=2,
                markersize=4.5,
                color=color,
                label=event_type,
            )

        ax.axvline(BOUNDARY_TS, color="#222222", linewidth=1.3, linestyle="--")
        ax.text(
            BOUNDARY_TS + pd.Timedelta(seconds=25),
            ax.get_ylim()[1] * 0.88,
            "Apr 1",
            fontsize=9,
            color="#222222",
        )
        ax.set_title(stream, loc="left")
        ax.set_xlabel("UTC minute around the boundary")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        style_axis(ax)
        ax.grid(axis="y", color=COLORS["grid"], linewidth=0.8)
    axes[0].set_ylabel("Event rows per minute")
    axes[0].legend(frameon=False, loc="lower left")
    fig.suptitle("Only Response Events Continue Into April in Both Streams", x=0.07, ha="left")
    save_figure(fig, "04_boundary_minute_request_response_profile.png")


def plot_april_touched_flow_shape() -> None:
    shape = read_csv("april_touched_flow_shape.csv")

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), sharey=True)
    for ax, (_, row) in zip(axes, shape.iterrows()):
        values = [row["request_rows"], row["response_rows"], row["pre_april_event_rows"], row["april_event_rows"]]
        labels = ["request\nrows", "response\nrows", "pre-April\nevent rows", "April\nevent rows"]
        colors = [COLORS["request"], COLORS["response"], "#8CD17D", COLORS["april"]]
        ax.bar(labels, values, color=colors, edgecolor="none")
        for idx, value in enumerate(values):
            ax.text(idx, value + 4, f"{int(value):,}", ha="center", fontsize=9)
        ax.set_title(row["stream"], loc="left")
        ax.set_ylim(0, 180)
        style_axis(ax)
        ax.grid(axis="y", color=COLORS["grid"], linewidth=0.8)
        ax.grid(axis="x", visible=False)
    axes[0].set_ylabel("Rows among April-touched flows")
    fig.suptitle(
        "Two Readings of the Same 151 Boundary Flows: Event Side and Calendar Side",
        x=0.06,
        ha="left",
    )
    save_figure(fig, "05_april_touched_flow_pair_shape.png")


def plot_latency_summary() -> None:
    latency = read_csv("april_touched_flow_latency_summary.csv")
    # The baseline and with-fraud boundary delay profiles are identical in this extract,
    # so one shared profile communicates the timing evidence without duplicated labels.
    row = latency.iloc[0]
    metrics = [
        ("min_request_to_response_seconds", "min"),
        ("p25_request_to_response_seconds", "p25"),
        ("median_request_to_response_seconds", "median"),
        ("p75_request_to_response_seconds", "p75"),
        ("max_request_to_response_seconds", "max"),
    ]

    metric_values = [row[col] for col, _ in metrics]
    fig, ax = plt.subplots(figsize=(10.5, 3.8))
    y = 0
    ax.hlines(y, metric_values[0], metric_values[-1], color=COLORS["grid"], linewidth=10)
    ax.hlines(y, metric_values[1], metric_values[3], color=COLORS["april"], linewidth=10)
    ax.scatter(metric_values, [y] * len(metric_values), color="#2F3A45", s=46, zorder=3)
    annotation_y = [0.22, -0.24, 0.34, -0.24, 0.22]
    for value, (_, label), y_text in zip(metric_values, metrics, annotation_y):
        ax.vlines(value, 0.02 if y_text > 0 else -0.02, y_text * 0.75, color="#9AA4B2", linewidth=0.8)
        ax.text(
            value,
            y_text,
            f"{label}\n{value:.3g}s",
            ha="center",
            va="center",
            fontsize=8.5,
            color="#2F3A45",
        )

    ax.set_yticks([0])
    ax.set_yticklabels(["baseline and with_fraud"])
    ax.set_xlabel("Request-to-response seconds")
    ax.set_title("Summary Profile of April Boundary Request-to-Response Delay", loc="left")
    ax.set_xlim(-5, 190)
    ax.set_ylim(-0.5, 0.5)
    style_axis(ax)
    save_figure(fig, "06_request_response_latency_profile.png")


def plot_approx_count_caution() -> None:
    monthly = read_csv("monthly_boundary_counts.csv")
    exact = read_csv("april_rows_by_event_side.csv")
    rows = []
    for stream in ["baseline", "with_fraud"]:
        approx_flows = int(
            monthly[(monthly["stream"] == stream) & (monthly["utc_month"] == "2026-04")][
                "approx_flows"
            ].iloc[0]
        )
        exact_flows = int(exact[exact["stream"] == stream]["distinct_flows"].sum())
        rows.extend(
            [
                {"stream": stream, "measure": "approx monthly distinct", "flows": approx_flows},
                {"stream": stream, "measure": "exact April subset", "flows": exact_flows},
            ]
        )
    df = pd.DataFrame(rows)

    fig, ax = plt.subplots(figsize=(9.5, 4.8))
    x = np.arange(2)
    width = 0.34
    colors = ["#BAB0AC", COLORS["april"]]
    for idx, measure in enumerate(["approx monthly distinct", "exact April subset"]):
        sub = df[df["measure"] == measure]
        ax.bar(
            x + (idx - 0.5) * width,
            sub["flows"],
            width=width,
            color=colors[idx],
            label=measure,
            edgecolor="none",
        )
        for xpos, flows in zip(x + (idx - 0.5) * width, sub["flows"]):
            ax.text(xpos, flows + 3, f"{flows:,}", ha="center", fontsize=9)

    ax.set_xticks(x)
    ax.set_xticklabels(["baseline", "with_fraud"])
    ax.set_ylabel("April flow count")
    ax.set_title("Approximate Distinct Counts Overstate the Tiny April Edge", loc="left")
    ax.legend(frameon=False, loc="lower right")
    ax.set_ylim(0, 185)
    style_axis(ax)
    ax.grid(axis="y", color=COLORS["grid"], linewidth=0.8)
    ax.grid(axis="x", visible=False)
    save_figure(fig, "07_approx_distinct_boundary_caution.png")


def main() -> None:
    plot_horizon_profile()
    plot_monthly_counts_with_tail()
    plot_april_event_side()
    plot_boundary_minute_profile()
    plot_april_touched_flow_shape()
    plot_latency_summary()
    plot_approx_count_caution()


if __name__ == "__main__":
    main()
