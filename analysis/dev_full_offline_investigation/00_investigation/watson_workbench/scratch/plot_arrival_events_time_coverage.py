from __future__ import annotations

from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd


matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[5]
TRAFFIC_EXPORT_DIR = (
    ROOT
    / "analysis"
    / "dev_full_offline_investigation"
    / "00_investigation"
    / "watson_workbench"
    / "exports"
    / "interface_world"
    / "traffic_primitives"
)
BRANCH_EXPORT_DIR = TRAFFIC_EXPORT_DIR / "branches" / "time_coverage"
FIGURE_DIR = BRANCH_EXPORT_DIR / "figures"
BUCKET_SUMMARY_PATH = TRAFFIC_EXPORT_DIR / "branches" / "grain_and_identity" / "bucket_index_summary.csv"


COLORS = {
    "ink": "#292724",
    "grid": "#d9d2c3",
    "blue": "#1f4e5f",
    "gold": "#c9a227",
    "green": "#6d8f71",
    "rust": "#b86b42",
    "slate": "#5d6d7e",
    "plum": "#7b3f61",
    "paper": "#fbf7ef",
    "soft": "#efe8dc",
}


def apply_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "figure.facecolor": COLORS["paper"],
            "axes.facecolor": COLORS["paper"],
            "axes.edgecolor": COLORS["ink"],
            "axes.labelcolor": COLORS["ink"],
            "xtick.color": COLORS["ink"],
            "ytick.color": COLORS["ink"],
            "text.color": COLORS["ink"],
            "axes.titleweight": "bold",
        }
    )


def style_axes(ax: plt.Axes, grid_axis: str = "y") -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis=grid_axis, color=COLORS["grid"], linewidth=0.8, alpha=0.72)
    ax.set_axisbelow(True)


def compact_int(value: float) -> str:
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    if abs(value) >= 1_000:
        return f"{value / 1_000:.1f}K"
    return f"{value:,.0f}"


def savefig(name: str) -> None:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    plt.savefig(FIGURE_DIR / name, dpi=180, bbox_inches="tight")
    plt.close()


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    BRANCH_EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    identity_df = pd.read_csv(TRAFFIC_EXPORT_DIR / "arrival_events_identity_summary.csv")
    month_df = pd.read_csv(TRAFFIC_EXPORT_DIR / "arrival_events_month_summary.csv")
    daily_df = pd.read_csv(TRAFFIC_EXPORT_DIR / "arrival_events_daily_summary.csv", parse_dates=["utc_date"])
    hour_df = pd.read_csv(TRAFFIC_EXPORT_DIR / "arrival_events_utc_hour_summary.csv")
    bucket_df = pd.read_csv(BUCKET_SUMMARY_PATH)

    month_df["rows_per_active_day"] = month_df["rows"] / month_df["active_days"]
    month_df["row_share"] = month_df["rows"] / month_df["rows"].sum()
    month_df.to_csv(BRANCH_EXPORT_DIR / "month_normalized_summary.csv", index=False)

    daily_df["weekday"] = daily_df["utc_date"].dt.day_name()
    daily_df["month"] = daily_df["utc_date"].dt.strftime("%Y-%m")
    daily_df["day_index"] = np.arange(len(daily_df))
    daily_df.to_csv(BRANCH_EXPORT_DIR / "daily_time_coverage_summary.csv", index=False)

    weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    weekday_df = (
        daily_df.groupby("weekday", observed=True)
        .agg(
            days=("rows", "count"),
            rows=("rows", "sum"),
            mean_rows=("rows", "mean"),
            min_rows=("rows", "min"),
            max_rows=("rows", "max"),
        )
        .reset_index()
    )
    weekday_df["weekday"] = pd.Categorical(weekday_df["weekday"], categories=weekday_order, ordered=True)
    weekday_df = weekday_df.sort_values("weekday")
    weekday_df.to_csv(BRANCH_EXPORT_DIR / "weekday_summary.csv", index=False)

    bucket_df["first_ts_utc"] = pd.to_datetime(bucket_df["first_ts_utc"], utc=True)
    bucket_df["last_ts_utc"] = pd.to_datetime(bucket_df["last_ts_utc"], utc=True)
    bucket_df.to_csv(BRANCH_EXPORT_DIR / "bucket_index_time_coverage_summary.csv", index=False)

    return identity_df, month_df, daily_df, weekday_df, hour_df, bucket_df


def plot_horizon_daily_coverage(identity_df: pd.DataFrame, daily_df: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(12.5, 7.2), sharex=True, gridspec_kw={"height_ratios": [0.9, 2.8]})

    expected_dates = pd.date_range(daily_df["utc_date"].min(), daily_df["utc_date"].max(), freq="D")
    present = expected_dates.isin(daily_df["utc_date"])
    axes[0].bar(expected_dates, np.ones(len(expected_dates)), color=np.where(present, COLORS["green"], COLORS["rust"]), width=0.9, edgecolor="none")
    axes[0].set_yticks([])
    axes[0].set_title("Daily Coverage Across the January-March Operating Horizon", fontsize=14)
    axes[0].text(
        expected_dates[len(expected_dates) // 2],
        0.5,
        f"{present.sum()} / {len(expected_dates)} UTC dates present",
        ha="center",
        va="center",
        fontsize=12,
        weight="bold",
    )
    axes[0].spines[["top", "right", "left"]].set_visible(False)

    axes[1].plot(daily_df["utc_date"], daily_df["rows"], color=COLORS["blue"], linewidth=2)
    axes[1].scatter(daily_df["utc_date"], daily_df["rows"], color=COLORS["blue"], s=18, edgecolors="none", alpha=0.8)
    first_ts = identity_df.loc[0, "min_ts_utc"]
    last_ts = identity_df.loc[0, "max_ts_utc"]
    axes[1].set_title(f"Boundary: {first_ts} to {last_ts}", fontsize=11, loc="left")
    axes[1].set_ylabel("Daily arrival rows")
    axes[1].set_xlabel("UTC date")
    axes[1].yaxis.set_major_formatter(lambda x, _: compact_int(x))
    axes[1].xaxis.set_major_locator(mdates.MonthLocator())
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    style_axes(axes[1])

    for month_start in pd.date_range(daily_df["utc_date"].min(), daily_df["utc_date"].max(), freq="MS"):
        axes[1].axvline(month_start, color=COLORS["grid"], linewidth=1.0, linestyle="--")

    savefig("01_horizon_daily_coverage.png")


def plot_monthly_raw_vs_normalized(month_df: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.6))

    x = np.arange(len(month_df))
    axes[0].bar(x, month_df["rows"], color=COLORS["blue"], edgecolor="none")
    axes[0].set_xticks(x, month_df["utc_month"])
    axes[0].set_title("Raw Monthly Arrival Rows", fontsize=13)
    axes[0].set_ylabel("Rows")
    axes[0].yaxis.set_major_formatter(lambda y, _: compact_int(y))
    for idx, row in month_df.iterrows():
        axes[0].text(idx, row["rows"] * 1.01, compact_int(row["rows"]), ha="center", va="bottom", fontsize=9)
    style_axes(axes[0])

    axes[1].bar(x, month_df["rows_per_active_day"], color=COLORS["green"], edgecolor="none")
    axes[1].set_xticks(x, month_df["utc_month"])
    axes[1].set_title("Rows per Active Day", fontsize=13)
    axes[1].set_ylabel("Rows per day")
    axes[1].yaxis.set_major_formatter(lambda y, _: compact_int(y))
    y_min = month_df["rows_per_active_day"].min() * 0.985
    y_max = month_df["rows_per_active_day"].max() * 1.01
    axes[1].set_ylim(y_min, y_max)
    for idx, row in month_df.iterrows():
        axes[1].text(idx, row["rows_per_active_day"] * 1.001, compact_int(row["rows_per_active_day"]), ha="center", va="bottom", fontsize=9)
    style_axes(axes[1])

    fig.suptitle("February Is Lower in Raw Rows Because It Has Fewer Days, Not Because the Surface Collapses", fontsize=14, weight="bold", y=1.02)
    savefig("02_monthly_raw_vs_daily_normalized.png")


def plot_daily_volume_stability(daily_df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(13, 6.2))

    mean = daily_df["rows"].mean()
    median = daily_df["rows"].median()
    p25 = daily_df["rows"].quantile(0.25)
    p75 = daily_df["rows"].quantile(0.75)
    min_row = daily_df.loc[daily_df["rows"].idxmin()]
    max_row = daily_df.loc[daily_df["rows"].idxmax()]

    ax.fill_between(daily_df["utc_date"], p25, p75, color=COLORS["green"], alpha=0.18, label="daily IQR")
    ax.plot(daily_df["utc_date"], daily_df["rows"], color=COLORS["blue"], linewidth=2.0, label="daily rows")
    ax.axhline(mean, color=COLORS["rust"], linewidth=1.8, label=f"mean {compact_int(mean)}")
    ax.axhline(median, color=COLORS["gold"], linewidth=1.8, linestyle="--", label=f"median {compact_int(median)}")
    ax.scatter([min_row["utc_date"]], [min_row["rows"]], color=COLORS["plum"], s=70, zorder=5)
    ax.scatter([max_row["utc_date"]], [max_row["rows"]], color=COLORS["rust"], s=70, zorder=5)
    ax.annotate(
        f"min\n{min_row['utc_date'].date()}\n{compact_int(min_row['rows'])}",
        (min_row["utc_date"], min_row["rows"]),
        xytext=(-55, 35),
        textcoords="offset points",
        arrowprops={"arrowstyle": "->", "color": COLORS["plum"]},
        fontsize=9,
    )
    ax.annotate(
        f"max\n{max_row['utc_date'].date()}\n{compact_int(max_row['rows'])}",
        (max_row["utc_date"], max_row["rows"]),
        xytext=(18, -62),
        textcoords="offset points",
        arrowprops={"arrowstyle": "->", "color": COLORS["rust"]},
        fontsize=9,
    )
    ax.set_title("Daily Arrival Volume Stays Continuous Within a Stable Operating Band", fontsize=14)
    ax.set_ylabel("Daily arrival rows")
    ax.set_xlabel("UTC date")
    ax.yaxis.set_major_formatter(lambda y, _: compact_int(y))
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.legend(frameon=False, ncol=4, loc="upper left")
    style_axes(ax)
    savefig("03_daily_volume_stability.png")


def plot_daily_distribution(daily_df: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.8), gridspec_kw={"width_ratios": [2.2, 1]})

    values = daily_df["rows"]
    axes[0].hist(values, bins=18, color=COLORS["blue"], edgecolor="none", alpha=0.9)
    axes[0].axvline(values.mean(), color=COLORS["rust"], linewidth=2, label=f"mean {compact_int(values.mean())}")
    axes[0].axvline(values.median(), color=COLORS["gold"], linewidth=2, linestyle="--", label=f"median {compact_int(values.median())}")
    axes[0].set_title("Distribution of Daily Arrival Rows", fontsize=13)
    axes[0].set_xlabel("Daily rows")
    axes[0].set_ylabel("Number of days")
    axes[0].xaxis.set_major_formatter(lambda x, _: compact_int(x))
    axes[0].legend(frameon=False)
    style_axes(axes[0])

    box = axes[1].boxplot(values, vert=True, patch_artist=True, widths=0.42)
    for patch in box["boxes"]:
        patch.set_facecolor(COLORS["green"])
        patch.set_edgecolor("none")
        patch.set_alpha(0.75)
    for key in ["whiskers", "caps", "medians"]:
        for item in box[key]:
            item.set_color(COLORS["ink"])
            item.set_linewidth(1.4)
    axes[1].set_title("Range Check", fontsize=13)
    axes[1].set_xticks([])
    axes[1].set_ylabel("Daily rows")
    axes[1].yaxis.set_major_formatter(lambda y, _: compact_int(y))
    style_axes(axes[1])

    cv = values.std(ddof=1) / values.mean()
    fig.suptitle(f"Daily Variation Is Visible but Modest: CV = {cv:.2%}", fontsize=14, weight="bold", y=1.02)
    savefig("04_daily_volume_distribution_and_range.png")


def plot_daily_merchant_channel_presence(daily_df: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(12.5, 7.4), sharex=True)

    exception = daily_df[daily_df["merchants"] < daily_df["merchants"].max()]
    axes[0].plot(daily_df["utc_date"], daily_df["merchants"], color=COLORS["blue"], linewidth=2)
    axes[0].scatter(daily_df["utc_date"], daily_df["merchants"], color=COLORS["blue"], s=20, edgecolors="none")
    if not exception.empty:
        row = exception.iloc[0]
        axes[0].scatter([row["utc_date"]], [row["merchants"]], color=COLORS["rust"], s=80, zorder=5)
        axes[0].annotate(
            f"{row['utc_date'].date()}: {int(row['merchants']):,} merchants",
            (row["utc_date"], row["merchants"]),
            xytext=(-70, -45),
            textcoords="offset points",
            arrowprops={"arrowstyle": "->", "color": COLORS["rust"]},
            fontsize=9,
        )
    axes[0].set_title("Daily Active Merchant Presence", fontsize=13)
    axes[0].set_ylabel("Merchants")
    axes[0].set_ylim(daily_df["merchants"].min() - 0.5, daily_df["merchants"].max() + 0.5)
    style_axes(axes[0])

    axes[1].plot(daily_df["utc_date"], daily_df["channels"], color=COLORS["green"], linewidth=2)
    axes[1].scatter(daily_df["utc_date"], daily_df["channels"], color=COLORS["green"], s=20, edgecolors="none")
    axes[1].set_title("Daily Channel Presence", fontsize=13)
    axes[1].set_ylabel("Channel groups")
    axes[1].set_xlabel("UTC date")
    axes[1].set_ylim(0, max(3, daily_df["channels"].max() + 0.5))
    axes[1].xaxis.set_major_locator(mdates.MonthLocator())
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    style_axes(axes[1])

    fig.suptitle("Coverage Is Daily-Complete, With One Merchant-Participation Exception", fontsize=14, weight="bold", y=1.02)
    savefig("05_daily_merchant_and_channel_presence.png")


def plot_weekday_shape(weekday_df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(11, 6))
    x = np.arange(len(weekday_df))
    ax.bar(x, weekday_df["mean_rows"], color=COLORS["blue"], edgecolor="none", alpha=0.9)
    ax.vlines(x, weekday_df["min_rows"], weekday_df["max_rows"], color=COLORS["rust"], linewidth=2.2, label="min-max daily range")
    ax.scatter(x, weekday_df["mean_rows"], color=COLORS["gold"], s=46, zorder=5, label="weekday mean")
    ax.set_xticks(x, weekday_df["weekday"].astype(str), rotation=20, ha="right")
    ax.set_title("Weekday Operating Shape in Daily Arrival Volume", fontsize=14)
    ax.set_ylabel("Rows per day")
    ax.yaxis.set_major_formatter(lambda y, _: compact_int(y))
    ax.legend(frameon=False, loc="upper left")
    style_axes(ax)
    savefig("06_weekday_operating_shape.png")


def plot_bucket_grid(bucket_df: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(13, 7.8), sharex=False, gridspec_kw={"height_ratios": [0.9, 2.7]})

    expected = np.arange(int(bucket_df["bucket_index"].min()), int(bucket_df["bucket_index"].max()) + 1)
    present = np.isin(expected, bucket_df["bucket_index"].to_numpy())
    axes[0].barh([0], [len(expected)], left=[expected.min()], height=0.42, color=COLORS["soft"], edgecolor="none")
    axes[0].barh([0], [present.sum()], left=[expected.min()], height=0.42, color=COLORS["green"], edgecolor="none")
    axes[0].text(
        expected.min() + len(expected) / 2,
        0,
        f"{present.sum():,} / {len(expected):,} hourly bucket indexes present",
        ha="center",
        va="center",
        fontsize=12,
        weight="bold",
    )
    axes[0].set_yticks([])
    axes[0].set_ylim(-0.7, 0.7)
    axes[0].spines[["top", "right", "left"]].set_visible(False)
    axes[0].set_title("Hourly Bucket Grid Coverage", fontsize=14)

    axes[1].plot(bucket_df["first_ts_utc"], bucket_df["arrival_rows"], color=COLORS["blue"], linewidth=1.2)
    axes[1].set_title("Arrival Intensity by Hourly Bucket", fontsize=13)
    axes[1].set_ylabel("Arrival rows")
    axes[1].set_xlabel("UTC time")
    axes[1].yaxis.set_major_formatter(lambda y, _: compact_int(y))
    axes[1].xaxis.set_major_locator(mdates.MonthLocator())
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    style_axes(axes[1])
    savefig("07_bucket_grid_coverage_and_intensity.png")


def plot_utc_hour_profile(hour_df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(12, 6))
    shares = hour_df["row_share"] * 100
    colors = [COLORS["blue"]] * len(hour_df)
    min_hours = hour_df.nsmallest(3, "row_share")["utc_hour"].tolist()
    top_hours = hour_df.nlargest(4, "row_share")["utc_hour"].tolist()
    for i, hour in enumerate(hour_df["utc_hour"]):
        if hour in min_hours:
            colors[i] = COLORS["plum"]
        if hour in top_hours:
            colors[i] = COLORS["rust"]

    ax.bar(hour_df["utc_hour"], shares, color=colors, edgecolor="none")
    ax.plot(hour_df["utc_hour"], shares, color=COLORS["ink"], linewidth=1.2, alpha=0.55)
    ax.set_xticks(range(24))
    ax.set_ylim(0, shares.max() + 0.9)
    ax.set_title("UTC Hour Profile: Time-of-Day Structure Is Present", fontsize=14, pad=14)
    ax.set_xlabel("UTC hour")
    ax.set_ylabel("Share of arrival rows (%)")
    for _, row in hour_df[hour_df["utc_hour"].isin(top_hours + min_hours)].iterrows():
        ax.text(row["utc_hour"], row["row_share"] * 100 + 0.08, f"{row['row_share'] * 100:.2f}%", ha="center", va="bottom", fontsize=8, rotation=90)
    style_axes(ax)
    savefig("08_utc_hour_profile.png")


def main() -> None:
    apply_style()
    identity_df, month_df, daily_df, weekday_df, hour_df, bucket_df = load_inputs()
    plot_horizon_daily_coverage(identity_df, daily_df)
    plot_monthly_raw_vs_normalized(month_df)
    plot_daily_volume_stability(daily_df)
    plot_daily_distribution(daily_df)
    plot_daily_merchant_channel_presence(daily_df)
    plot_weekday_shape(weekday_df)
    plot_bucket_grid(bucket_df)
    plot_utc_hour_profile(hour_df)
    print(f"Wrote figures to {FIGURE_DIR}")


if __name__ == "__main__":
    main()
