from __future__ import annotations

import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd


def mean_absolute_percentage_error(actual: pd.Series, predicted: pd.Series) -> float:
    denom = actual.replace(0, np.nan)
    pct = (actual - predicted).abs() / denom
    return float(pct.dropna().mean())


def rmse(actual: pd.Series, predicted: pd.Series) -> float:
    return float(np.sqrt(np.mean(np.square(actual - predicted))))


def mae(actual: pd.Series, predicted: pd.Series) -> float:
    return float(np.mean(np.abs(actual - predicted)))


def seasonal_naive(train: pd.Series, future_index: pd.DatetimeIndex, seasonal_lag: int = 7) -> pd.Series:
    history = train.copy()
    preds = []
    for date in future_index:
        anchor_date = date - pd.Timedelta(days=seasonal_lag)
        if anchor_date in history.index:
            pred = float(history.loc[anchor_date])
        else:
            pred = float(history.iloc[-seasonal_lag:].mean())
        preds.append(pred)
    return pd.Series(preds, index=future_index, name="seasonal_naive_7d")


def rolling_mean_forecast(train: pd.Series, future_index: pd.DatetimeIndex, window: int = 7) -> pd.Series:
    history = train.copy()
    preds = []
    for _ in future_index:
        pred = float(history.iloc[-window:].mean())
        preds.append(pred)
        history = pd.concat([history, pd.Series([pred], index=[history.index[-1] + pd.Timedelta(days=1)])])
    return pd.Series(preds, index=future_index, name=f"rolling_mean_{window}d")


def weekday_mean_forecast(train: pd.Series, future_index: pd.DatetimeIndex) -> pd.Series:
    weekday_means = train.groupby(train.index.dayofweek).mean()
    overall_mean = float(train.mean())
    preds = [float(weekday_means.get(date.dayofweek, overall_mean)) for date in future_index]
    return pd.Series(preds, index=future_index, name="weekday_mean")


def evaluate(actual: pd.Series, predicted: pd.Series) -> dict[str, float]:
    return {
        "mae": mae(actual, predicted),
        "rmse": rmse(actual, predicted),
        "mape": mean_absolute_percentage_error(actual, predicted),
    }


def main() -> None:
    repo = Path(r"c:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system")
    artefact_root = (
        repo
        / "artefacts"
        / "analytics_slices"
        / "data_scientist"
        / "midlands_partnership_nhs_ft"
        / "01_predictive_modelling"
    )

    series_path = artefact_root / "extracts" / "daily_case_opens_v1.parquet"
    model_base_path = artefact_root / "extracts" / "flow_model_base_v2.parquet"
    forecast_output_path = artefact_root / "extracts" / "case_demand_forecasts_v1.parquet"
    metrics_csv_path = artefact_root / "metrics" / "case_demand_forecast_metrics.csv"
    summary_json_path = artefact_root / "metrics" / "case_demand_forecast_summary.json"

    con = duckdb.connect()
    split_dates = con.execute(
        """
        WITH day_counts AS (
            SELECT
                flow_date_utc,
                split_role,
                COUNT(*) AS row_count
            FROM parquet_scan(?)
            GROUP BY 1, 2
        ),
        dominant_split AS (
            SELECT
                flow_date_utc,
                split_role,
                row_count,
                ROW_NUMBER() OVER (
                    PARTITION BY flow_date_utc
                    ORDER BY row_count DESC, split_role
                ) AS dominance_rank
            FROM day_counts
        )
        SELECT
            flow_date_utc,
            split_role
        FROM dominant_split
        WHERE dominance_rank = 1
        ORDER BY flow_date_utc
        """,
        [str(model_base_path)],
    ).fetchdf()

    split_dates["flow_date_utc"] = pd.to_datetime(split_dates["flow_date_utc"])

    series = con.execute(
        """
        SELECT
            CAST(case_open_date_utc AS DATE) AS case_open_date_utc,
            distinct_cases AS daily_case_opens
        FROM parquet_scan(?)
        ORDER BY case_open_date_utc
        """,
        [str(series_path)],
    ).fetchdf()
    series["case_open_date_utc"] = pd.to_datetime(series["case_open_date_utc"])
    ts = series.set_index("case_open_date_utc")["daily_case_opens"].astype(float)

    split_date_sets = {
        split_role: set(group["flow_date_utc"])
        for split_role, group in split_dates.groupby("split_role")
    }

    train = ts.loc[ts.index.isin(split_date_sets["train"])]
    validation = ts.loc[ts.index.isin(split_date_sets["validation"])]
    test = ts.loc[ts.index.isin(split_date_sets["test"])]

    train_start, train_end = train.index.min(), train.index.max()
    validation_start, validation_end = validation.index.min(), validation.index.max()
    test_start, test_end = test.index.min(), test.index.max()

    validation_candidates = {
        "seasonal_naive_7d": seasonal_naive(train, validation.index),
        "rolling_mean_7d": rolling_mean_forecast(train, validation.index, window=7),
        "weekday_mean": weekday_mean_forecast(train, validation.index),
    }

    validation_metrics_rows = []
    for model_name, preds in validation_candidates.items():
        metrics = evaluate(validation, preds)
        validation_metrics_rows.append(
            {
                "model_name": model_name,
                "evaluation_split": "validation",
                **metrics,
            }
        )

    validation_metrics = pd.DataFrame(validation_metrics_rows).sort_values(["rmse", "mae", "mape"])
    best_model_name = str(validation_metrics.iloc[0]["model_name"])

    train_plus_validation = ts.loc[ts.index.isin(split_date_sets["train"] | split_date_sets["validation"])]
    test_candidates = {
        "seasonal_naive_7d": seasonal_naive(train_plus_validation, test.index),
        "rolling_mean_7d": rolling_mean_forecast(train_plus_validation, test.index, window=7),
        "weekday_mean": weekday_mean_forecast(train_plus_validation, test.index),
    }
    best_test_forecast = test_candidates[best_model_name]
    test_metrics = evaluate(test, best_test_forecast)

    metrics_df = pd.concat(
        [
            validation_metrics,
            pd.DataFrame(
                [
                    {
                        "model_name": best_model_name,
                        "evaluation_split": "test",
                        **test_metrics,
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    metrics_df.to_csv(metrics_csv_path, index=False)

    validation_forecast = validation_candidates[best_model_name]
    forecast_df = pd.DataFrame(
        {
            "case_open_date_utc": list(validation.index) + list(test.index),
            "evaluation_split": ["validation"] * len(validation) + ["test"] * len(test),
            "actual_daily_case_opens": list(validation.values) + list(test.values),
            "predicted_daily_case_opens": list(validation_forecast.values) + list(best_test_forecast.values),
            "forecast_error": list((validation - validation_forecast).values)
            + list((test - best_test_forecast).values),
            "abs_forecast_error": list((validation - validation_forecast).abs().values)
            + list((test - best_test_forecast).abs().values),
            "model_name": [best_model_name] * (len(validation) + len(test)),
        }
    )
    con.register("forecast_df", forecast_df)
    con.execute(
        """
        COPY forecast_df
        TO ?
        (FORMAT PARQUET, COMPRESSION ZSTD)
        """,
        [str(forecast_output_path)],
    )

    summary = {
        "train_window": {"start": str(train_start.date()), "end": str(train_end.date()), "rows": int(len(train))},
        "validation_window": {
            "start": str(validation_start.date()),
            "end": str(validation_end.date()),
            "rows": int(len(validation)),
        },
        "test_window": {"start": str(test_start.date()), "end": str(test_end.date()), "rows": int(len(test))},
        "selected_model": best_model_name,
        "validation_metrics": {
            row["model_name"]: {
                "mae": float(row["mae"]),
                "rmse": float(row["rmse"]),
                "mape": float(row["mape"]),
            }
            for _, row in validation_metrics.iterrows()
        },
        "test_metrics": {
            "mae": float(test_metrics["mae"]),
            "rmse": float(test_metrics["rmse"]),
            "mape": float(test_metrics["mape"]),
        },
    }
    summary_json_path.write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
