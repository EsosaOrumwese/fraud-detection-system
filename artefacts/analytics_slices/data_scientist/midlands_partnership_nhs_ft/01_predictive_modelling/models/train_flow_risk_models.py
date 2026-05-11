from __future__ import annotations

import json
import pickle
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import statsmodels.api as sm


BASE = Path(
    r"C:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system"
)
ASSET = (
    BASE
    / r"artefacts\analytics_slices\data_scientist\midlands_partnership_nhs_ft\01_predictive_modelling"
)
EXTRACT_PATH = ASSET / "extracts" / "flow_model_base_v2.parquet"
METRICS_DIR = ASSET / "metrics"
MODELS_DIR = ASSET / "models"
EXTRACTS_DIR = ASSET / "extracts"
EXTRACT_PATH_SQL = str(EXTRACT_PATH).replace("\\", "/")

RAW_FEATURES = [
    "amount",
    "log_amount",
    "arrival_seq",
    "flow_hour_utc",
    "flow_dow_utc",
    "flow_month_utc",
    "merchant_flow_count",
    "party_flow_count",
    "account_flow_count",
    "instrument_flow_count",
    "device_flow_count",
    "ip_flow_count",
]
MODEL_FEATURES = [
    "log_amount",
    "log_arrival_seq",
    "flow_hour_utc",
    "flow_dow_utc",
    "flow_month_utc",
    "log_merchant_flow_count",
    "log_party_flow_count",
    "log_account_flow_count",
    "log_instrument_flow_count",
    "log_device_flow_count",
    "log_ip_flow_count",
    "merchant_train_fraud_rate",
    "party_train_fraud_rate",
    "account_train_fraud_rate",
    "instrument_train_fraud_rate",
    "device_train_fraud_rate",
    "ip_train_fraud_rate",
]
TARGET = "target_is_fraud_truth"


def load_split(split_role: str) -> pd.DataFrame:
    query = f"""
        SELECT
            flow_id,
            flow_ts_utc,
            {", ".join(RAW_FEATURES)},
            merchant_train_fraud_rate,
            party_train_fraud_rate,
            account_train_fraud_rate,
            instrument_train_fraud_rate,
            device_train_fraud_rate,
            ip_train_fraud_rate,
            {TARGET},
            fraud_label,
            is_fraud_bank_view,
            bank_label
        FROM parquet_scan('{EXTRACT_PATH_SQL}')
        WHERE split_role = '{split_role}'
    """
    return duckdb.sql(query).df()


def transform_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["log_arrival_seq"] = np.log1p(out["arrival_seq"])
    out["log_merchant_flow_count"] = np.log1p(out["merchant_flow_count"])
    out["log_party_flow_count"] = np.log1p(out["party_flow_count"])
    out["log_account_flow_count"] = np.log1p(out["account_flow_count"])
    out["log_instrument_flow_count"] = np.log1p(out["instrument_flow_count"])
    out["log_device_flow_count"] = np.log1p(out["device_flow_count"])
    out["log_ip_flow_count"] = np.log1p(out["ip_flow_count"])
    return out


def downsample_train(train_df: pd.DataFrame, negative_ratio: int = 5) -> pd.DataFrame:
    positives = train_df[train_df[TARGET] == 1]
    negatives = train_df[train_df[TARGET] == 0]
    sample_size = min(len(negatives), len(positives) * negative_ratio)
    sampled_negatives = negatives.sample(n=sample_size, random_state=42)
    sampled = pd.concat([positives, sampled_negatives], axis=0).sample(
        frac=1.0, random_state=42
    )
    return sampled


def fit_logistic_model(train_df: pd.DataFrame):
    X = sm.add_constant(train_df[MODEL_FEATURES], has_constant="add")
    y = train_df[TARGET].astype(int)
    model = sm.GLM(y, X, family=sm.families.Binomial())
    result = model.fit(maxiter=200)
    return result


def predict_probabilities(result, df: pd.DataFrame) -> np.ndarray:
    X = sm.add_constant(df[MODEL_FEATURES], has_constant="add")
    return result.predict(X)


def roc_auc_manual(y_true: np.ndarray, y_score: np.ndarray) -> float:
    order = np.argsort(y_score)
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.arange(1, len(y_score) + 1)
    pos = y_true == 1
    n_pos = np.sum(pos)
    n_neg = len(y_true) - n_pos
    if n_pos == 0 or n_neg == 0:
        return 0.5
    rank_sum = np.sum(ranks[pos])
    auc = (rank_sum - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)
    return float(auc)


def average_precision_manual(y_true: np.ndarray, y_score: np.ndarray) -> float:
    order = np.argsort(-y_score)
    y_sorted = y_true[order]
    positives = np.sum(y_sorted)
    if positives == 0:
        return 0.0
    cumulative_tp = np.cumsum(y_sorted)
    precision = cumulative_tp / (np.arange(len(y_sorted)) + 1)
    ap = np.sum(precision * y_sorted) / positives
    return float(ap)


def score_bands(probabilities: np.ndarray, high_threshold: float, medium_threshold: float):
    return np.where(
        probabilities >= high_threshold,
        "High",
        np.where(probabilities >= medium_threshold, "Medium", "Low"),
    )


def evaluate_predictions(
    y_true: pd.Series,
    probabilities: np.ndarray,
    split_name: str,
    high_threshold: float,
    medium_threshold: float,
) -> tuple[dict, pd.DataFrame]:
    scored = pd.DataFrame(
        {
            TARGET: y_true.to_numpy(dtype=int),
            "predicted_probability": probabilities,
        }
    )
    scored["risk_band"] = score_bands(probabilities, high_threshold, medium_threshold)
    metrics = {
        "split": split_name,
        "rows": int(len(scored)),
        "positives": int(scored[TARGET].sum()),
        "positive_rate": float(scored[TARGET].mean()),
        "roc_auc": roc_auc_manual(y_true.to_numpy(dtype=int), probabilities),
        "average_precision": average_precision_manual(
            y_true.to_numpy(dtype=int), probabilities
        ),
        "high_threshold": float(high_threshold),
        "medium_threshold": float(medium_threshold),
    }

    overall_rate = scored[TARGET].mean()
    band_rows = []
    total_positives = max(1, int(scored[TARGET].sum()))
    for band in ["High", "Medium", "Low"]:
        band_df = scored[scored["risk_band"] == band]
        positives = int(band_df[TARGET].sum())
        rows = int(len(band_df))
        rate = float(band_df[TARGET].mean()) if rows else 0.0
        band_rows.append(
            {
                "split": split_name,
                "risk_band": band,
                "rows": rows,
                "positives": positives,
                "positive_rate": rate,
                "capture_rate": float(positives / total_positives),
                "lift_vs_baseline": float(rate / overall_rate) if overall_rate else 0.0,
            }
        )
    return metrics, pd.DataFrame(band_rows)


def save_scores(df: pd.DataFrame, probabilities: np.ndarray, high_threshold: float, medium_threshold: float, output_name: str) -> None:
    scores = df[
        ["flow_id", "flow_ts_utc", TARGET, "fraud_label", "is_fraud_bank_view", "bank_label"]
    ].copy()
    scores["predicted_probability"] = probabilities
    scores["risk_band"] = score_bands(probabilities, high_threshold, medium_threshold)
    duckdb.register("scores_df", scores)
    output_path = str(EXTRACTS_DIR / output_name).replace("\\", "/")
    duckdb.sql(
        f"COPY scores_df TO '{output_path}' (FORMAT PARQUET, COMPRESSION ZSTD)"
    )


def main() -> None:
    train_df = transform_features(load_split("train"))
    validation_df = transform_features(load_split("validation"))
    test_df = transform_features(load_split("test"))

    sampled_train = downsample_train(train_df, negative_ratio=5)
    result = fit_logistic_model(sampled_train)

    validation_prob = predict_probabilities(result, validation_df)
    test_prob = predict_probabilities(result, test_df)

    high_threshold = float(np.quantile(validation_prob, 0.95))
    medium_threshold = float(np.quantile(validation_prob, 0.80))

    validation_metrics, validation_bands = evaluate_predictions(
        validation_df[TARGET],
        validation_prob,
        "validation",
        high_threshold,
        medium_threshold,
    )
    test_metrics, test_bands = evaluate_predictions(
        test_df[TARGET],
        test_prob,
        "test",
        high_threshold,
        medium_threshold,
    )

    metrics_df = pd.DataFrame([validation_metrics, test_metrics])
    metrics_df.to_csv(METRICS_DIR / "model_metrics.csv", index=False)
    validation_bands.to_csv(METRICS_DIR / "validation_risk_band_metrics.csv", index=False)
    test_bands.to_csv(METRICS_DIR / "test_risk_band_metrics.csv", index=False)

    summary = {
        "model": "statsmodels_glm_binomial",
        "train_rows_full": int(len(train_df)),
        "train_rows_sampled": int(len(sampled_train)),
        "validation_rows": int(len(validation_df)),
        "test_rows": int(len(test_df)),
        "features": MODEL_FEATURES,
    }
    (METRICS_DIR / "model_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    (METRICS_DIR / "glm_coefficients.json").write_text(
        result.params.to_json(indent=2), encoding="utf-8"
    )

    with open(MODELS_DIR / "statsmodels_glm_binomial.pkl", "wb") as f:
        pickle.dump(result, f)

    save_scores(
        validation_df,
        validation_prob,
        high_threshold,
        medium_threshold,
        "validation_scores_v1.parquet",
    )
    save_scores(
        test_df,
        test_prob,
        high_threshold,
        medium_threshold,
        "test_scores_v1.parquet",
    )

    print(metrics_df.to_string(index=False))
    print("--- validation bands ---")
    print(validation_bands.to_string(index=False))
    print("--- test bands ---")
    print(test_bands.to_string(index=False))


if __name__ == "__main__":
    main()
