from __future__ import annotations

import json
import textwrap
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import statsmodels.api as sm


BASE = Path(
    r"C:\Users\LEGION\Documents\Data Science\Python & R Scripts\fraud-detection-system"
)
ARTEFACT = (
    BASE
    / r"artefacts\analytics_slices\data_scientist\midlands_partnership_nhs_ft\05_governed_explainable_ai"
)
SQL_DIR = ARTEFACT / "sql"
METRICS_DIR = ARTEFACT / "metrics"
EXTRACTS_DIR = ARTEFACT / "extracts"
LOGS_DIR = ARTEFACT / "logs"

SELECTION_PATH = LOGS_DIR / "bounded_file_selection.json"
MODEL_BASE_V1 = EXTRACTS_DIR / "flow_model_ready_slice_v1.parquet"
MODEL_BASE_V2 = EXTRACTS_DIR / "flow_model_ready_slice_v2_encoded.parquet"
SELECTED_VALIDATION_SCORES = EXTRACTS_DIR / "validation_scores_selected_v1.parquet"
SELECTED_TEST_SCORES = EXTRACTS_DIR / "test_scores_selected_v1.parquet"
MODEL_REVIEW_SUMMARY = EXTRACTS_DIR / "flow_model_review_summary_v1.parquet"
RISK_BAND_SUMMARY = EXTRACTS_DIR / "flow_model_risk_band_summary_v1.parquet"

TARGET = "target_is_fraud_truth"
BASELINE_FEATURES = [
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
]
CHALLENGER_FEATURES = BASELINE_FEATURES + [
    "merchant_train_fraud_rate",
    "party_train_fraud_rate",
    "account_train_fraud_rate",
    "instrument_train_fraud_rate",
    "device_train_fraud_rate",
    "ip_train_fraud_rate",
]


def pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def read_sql(name: str) -> str:
    return (SQL_DIR / name).read_text(encoding="utf-8")


def sql_list(paths: list[str]) -> str:
    return ", ".join(f"'{p.replace(chr(92), '/')}'" for p in paths)


def render_sql(sql_text: str, replacements: dict[str, str]) -> str:
    rendered = sql_text
    for key, value in replacements.items():
        rendered = rendered.replace(key, value)
    return rendered


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


def downsample_train(train_df: pd.DataFrame, negative_ratio: int = 5) -> pd.DataFrame:
    positives = train_df[train_df[TARGET] == 1]
    negatives = train_df[train_df[TARGET] == 0]
    sample_size = min(len(negatives), len(positives) * negative_ratio)
    sampled_negatives = negatives.sample(n=sample_size, random_state=42)
    sampled = pd.concat([positives, sampled_negatives], axis=0).sample(
        frac=1.0, random_state=42
    )
    return sampled


def transform_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["log_amount"] = np.log1p(out["amount"])
    out["log_arrival_seq"] = np.log1p(out["arrival_seq"])
    out["log_merchant_flow_count"] = np.log1p(out["merchant_flow_count"])
    out["log_party_flow_count"] = np.log1p(out["party_flow_count"])
    out["log_account_flow_count"] = np.log1p(out["account_flow_count"])
    out["log_instrument_flow_count"] = np.log1p(out["instrument_flow_count"])
    out["log_device_flow_count"] = np.log1p(out["device_flow_count"])
    out["log_ip_flow_count"] = np.log1p(out["ip_flow_count"])
    return out


def fit_glm(train_df: pd.DataFrame, features: list[str]):
    X = sm.add_constant(train_df[features], has_constant="add")
    y = train_df[TARGET].astype(int)
    model = sm.GLM(y, X, family=sm.families.Binomial())
    return model.fit(maxiter=200)


def predict_probabilities(result, df: pd.DataFrame, features: list[str]) -> np.ndarray:
    X = sm.add_constant(df[features], has_constant="add")
    return result.predict(X)


def choose_thresholds(validation_prob: np.ndarray) -> tuple[float, float]:
    return float(np.quantile(validation_prob, 0.95)), float(np.quantile(validation_prob, 0.80))


def score_bands(probabilities: np.ndarray, high_threshold: float, medium_threshold: float) -> np.ndarray:
    return np.where(
        probabilities >= high_threshold,
        "High",
        np.where(probabilities >= medium_threshold, "Medium", "Low"),
    )


def write_md(path: Path, text: str) -> None:
    path.write_text(textwrap.dedent(text).strip() + "\n", encoding="utf-8")


def save_parquet(df: pd.DataFrame, path: Path) -> None:
    con = duckdb.connect()
    con.register("tmp_df", df)
    con.execute(
        f"COPY tmp_df TO '{str(path).replace(chr(92), '/')}' (FORMAT PARQUET, COMPRESSION ZSTD)"
    )
    con.close()


def records_for_json(df: pd.DataFrame) -> list[dict]:
    return json.loads(df.to_json(orient="records", date_format="iso"))


def evaluate_split(
    split_df: pd.DataFrame,
    probabilities: np.ndarray,
    split_name: str,
    model_name: str,
    high_threshold: float,
    medium_threshold: float,
) -> tuple[dict[str, float | int | str], pd.DataFrame, pd.DataFrame]:
    y_true = split_df[TARGET].astype(int).to_numpy()
    scored = split_df[
        [
            "flow_id",
            "flow_ts_utc",
            TARGET,
            "fraud_label",
            "is_fraud_bank_view",
            "bank_label",
            "has_case_opened",
        ]
    ].copy()
    scored["predicted_probability"] = probabilities
    scored["risk_band"] = score_bands(probabilities, high_threshold, medium_threshold)
    overall_rate = float(scored[TARGET].mean())
    positives = int(scored[TARGET].sum())
    metrics = {
        "model_name": model_name,
        "split_role": split_name,
        "rows": int(len(scored)),
        "positives": positives,
        "positive_rate": overall_rate,
        "roc_auc": roc_auc_manual(y_true, probabilities),
        "average_precision": average_precision_manual(y_true, probabilities),
        "high_threshold": float(high_threshold),
        "medium_threshold": float(medium_threshold),
    }
    band_rows: list[dict[str, float | int | str]] = []
    total_positives = max(1, positives)
    for band in ["High", "Medium", "Low"]:
        band_df = scored[scored["risk_band"] == band]
        band_rows.append(
            {
                "model_name": model_name,
                "split_role": split_name,
                "risk_band": band,
                "rows": int(len(band_df)),
                "positives": int(band_df[TARGET].sum()),
                "positive_rate": float(band_df[TARGET].mean()) if len(band_df) else 0.0,
                "capture_rate": float(band_df[TARGET].sum() / total_positives),
                "lift_vs_baseline": float(band_df[TARGET].mean() / overall_rate) if len(band_df) and overall_rate else 0.0,
            }
        )
    return metrics, pd.DataFrame(band_rows), scored


def top_coefficients(result, features: list[str], top_n: int = 8) -> list[dict[str, float]]:
    params = result.params.drop("const")
    ranked = params.abs().sort_values(ascending=False).head(top_n)
    return [
        {"feature": feature, "coefficient": float(params[feature]), "abs_coefficient": float(abs(params[feature]))}
        for feature in ranked.index
    ]


def load_split(split_role: str) -> pd.DataFrame:
    query = f"""
        SELECT *
        FROM parquet_scan('{str(MODEL_BASE_V2).replace(chr(92), '/')}')
        WHERE split_role = '{split_role}'
    """
    return duckdb.sql(query).df()


def main() -> None:
    selection = json.loads(SELECTION_PATH.read_text(encoding="utf-8"))
    replacements = {
        "$flow_anchor_files": sql_list(selection["anchor_files"]),
        "$flow_truth_files": sql_list(selection["truth_files"]),
        "$flow_bank_files": sql_list(selection["bank_files"]),
        "$case_files": sql_list(selection["case_files"]),
        "$model_base_output": f"'{str(MODEL_BASE_V1).replace(chr(92), '/')}'",
        "$model_base_path": f"'{str(MODEL_BASE_V1).replace(chr(92), '/')}'",
        "$model_base_v2_output": f"'{str(MODEL_BASE_V2).replace(chr(92), '/')}'",
    }

    con = duckdb.connect()
    scope_sql = render_sql(read_sql("01_profile_governed_model_scope.sql"), replacements)
    scope_df = con.execute(scope_sql).fetchdf()
    scope_df.to_csv(METRICS_DIR / "01_profile_governed_model_scope.csv", index=False)

    build_v1_sql = render_sql(read_sql("02_build_flow_model_ready_slice.sql"), replacements)
    con.execute(build_v1_sql)
    build_v2_sql = render_sql(read_sql("03_build_flow_model_ready_slice_v2_encoded.sql"), replacements)
    con.execute(build_v2_sql)

    model_profile_df = con.execute(
        f"""
        SELECT
            split_role,
            COUNT(*) AS flow_rows,
            SUM(CASE WHEN {TARGET} THEN 1 ELSE 0 END) AS fraud_truth_rows,
            AVG(CASE WHEN {TARGET} THEN 1.0 ELSE 0.0 END) AS fraud_truth_rate,
            MIN(flow_ts_utc) AS min_flow_ts_utc,
            MAX(flow_ts_utc) AS max_flow_ts_utc
        FROM parquet_scan('{str(MODEL_BASE_V2).replace(chr(92), '/')}')
        GROUP BY split_role
        ORDER BY CASE split_role WHEN 'train' THEN 1 WHEN 'validation' THEN 2 ELSE 3 END
        """
    ).fetchdf()
    model_profile_df.to_csv(METRICS_DIR / "02_profile_model_ready_slice.csv", index=False)

    encoded_nulls_df = con.execute(
        f"""
        SELECT
            AVG(CASE WHEN merchant_train_fraud_rate IS NULL THEN 1.0 ELSE 0.0 END) AS merchant_rate_null_rate,
            AVG(CASE WHEN party_train_fraud_rate IS NULL THEN 1.0 ELSE 0.0 END) AS party_rate_null_rate,
            AVG(CASE WHEN account_train_fraud_rate IS NULL THEN 1.0 ELSE 0.0 END) AS account_rate_null_rate,
            AVG(CASE WHEN instrument_train_fraud_rate IS NULL THEN 1.0 ELSE 0.0 END) AS instrument_rate_null_rate,
            AVG(CASE WHEN device_train_fraud_rate IS NULL THEN 1.0 ELSE 0.0 END) AS device_rate_null_rate,
            AVG(CASE WHEN ip_train_fraud_rate IS NULL THEN 1.0 ELSE 0.0 END) AS ip_rate_null_rate
        FROM parquet_scan('{str(MODEL_BASE_V2).replace(chr(92), '/')}')
        """
    ).fetchdf()
    encoded_nulls_df.to_csv(METRICS_DIR / "03_encoded_feature_null_rates.csv", index=False)
    con.close()

    train_df = transform_features(load_split("train"))
    validation_df = transform_features(load_split("validation"))
    test_df = transform_features(load_split("test"))
    sampled_train = downsample_train(train_df, negative_ratio=5)

    baseline_result = fit_glm(sampled_train, BASELINE_FEATURES)
    challenger_result = fit_glm(sampled_train, CHALLENGER_FEATURES)

    baseline_validation_prob = predict_probabilities(baseline_result, validation_df, BASELINE_FEATURES)
    baseline_test_prob = predict_probabilities(baseline_result, test_df, BASELINE_FEATURES)
    challenger_validation_prob = predict_probabilities(challenger_result, validation_df, CHALLENGER_FEATURES)
    challenger_test_prob = predict_probabilities(challenger_result, test_df, CHALLENGER_FEATURES)

    baseline_high, baseline_medium = choose_thresholds(baseline_validation_prob)
    challenger_high, challenger_medium = choose_thresholds(challenger_validation_prob)

    baseline_val_metrics, baseline_val_bands, baseline_val_scores = evaluate_split(
        validation_df, baseline_validation_prob, "validation", "baseline_logistic_structural", baseline_high, baseline_medium
    )
    baseline_test_metrics, baseline_test_bands, baseline_test_scores = evaluate_split(
        test_df, baseline_test_prob, "test", "baseline_logistic_structural", baseline_high, baseline_medium
    )
    challenger_val_metrics, challenger_val_bands, challenger_val_scores = evaluate_split(
        validation_df, challenger_validation_prob, "validation", "challenger_logistic_encoded_history", challenger_high, challenger_medium
    )
    challenger_test_metrics, challenger_test_bands, challenger_test_scores = evaluate_split(
        test_df, challenger_test_prob, "test", "challenger_logistic_encoded_history", challenger_high, challenger_medium
    )

    metrics_df = pd.DataFrame(
        [baseline_val_metrics, baseline_test_metrics, challenger_val_metrics, challenger_test_metrics]
    )
    metrics_df.to_csv(METRICS_DIR / "04_model_compare_metrics.csv", index=False)

    risk_bands_df = pd.concat(
        [baseline_val_bands, baseline_test_bands, challenger_val_bands, challenger_test_bands],
        ignore_index=True,
    )
    risk_bands_df.to_csv(METRICS_DIR / "05_model_compare_risk_bands.csv", index=False)

    baseline_val_high = baseline_val_bands[baseline_val_bands["risk_band"] == "High"].iloc[0]
    challenger_val_high = challenger_val_bands[challenger_val_bands["risk_band"] == "High"].iloc[0]
    baseline_val_auc = float(baseline_val_metrics["roc_auc"])
    challenger_val_auc = float(challenger_val_metrics["roc_auc"])
    baseline_val_high_rate = float(baseline_val_high["positive_rate"])
    challenger_val_high_rate = float(challenger_val_high["positive_rate"])

    select_challenger = (
        (challenger_val_auc - baseline_val_auc) >= 0.01
        or (challenger_val_high_rate - baseline_val_high_rate) >= 0.01
    )
    selected_model_name = (
        "challenger_logistic_encoded_history" if select_challenger else "baseline_logistic_structural"
    )
    selected_features = CHALLENGER_FEATURES if select_challenger else BASELINE_FEATURES
    selected_result = challenger_result if select_challenger else baseline_result
    selected_validation_scores = challenger_val_scores if select_challenger else baseline_val_scores
    selected_test_scores = challenger_test_scores if select_challenger else baseline_test_scores
    selected_validation_metrics = challenger_val_metrics if select_challenger else baseline_val_metrics
    selected_test_metrics = challenger_test_metrics if select_challenger else baseline_test_metrics
    selected_val_bands = challenger_val_bands if select_challenger else baseline_val_bands
    selected_test_bands = challenger_test_bands if select_challenger else baseline_test_bands
    selected_high = challenger_high if select_challenger else baseline_high
    selected_medium = challenger_medium if select_challenger else baseline_medium

    save_parquet(selected_validation_scores, SELECTED_VALIDATION_SCORES)
    save_parquet(selected_test_scores, SELECTED_TEST_SCORES)

    review_summary_df = pd.DataFrame(
        [
            {
                "selected_model_name": selected_model_name,
                "selected_feature_count": len(selected_features),
                "baseline_validation_auc": baseline_val_auc,
                "challenger_validation_auc": challenger_val_auc,
                "baseline_validation_high_rate": baseline_val_high_rate,
                "challenger_validation_high_rate": challenger_val_high_rate,
                "selected_high_threshold": selected_high,
                "selected_medium_threshold": selected_medium,
            }
        ]
    )
    save_parquet(review_summary_df, MODEL_REVIEW_SUMMARY)
    risk_band_summary_df = pd.concat([selected_val_bands, selected_test_bands], ignore_index=True)
    save_parquet(risk_band_summary_df, RISK_BAND_SUMMARY)

    coeffs_df = pd.DataFrame(
        [
            {
                "model_name": "baseline_logistic_structural",
                "feature": k,
                "coefficient": float(v),
            }
            for k, v in baseline_result.params.drop("const").items()
        ]
        + [
            {
                "model_name": "challenger_logistic_encoded_history",
                "feature": k,
                "coefficient": float(v),
            }
            for k, v in challenger_result.params.drop("const").items()
        ]
    )
    coeffs_df.to_csv(METRICS_DIR / "06_model_coefficients.csv", index=False)

    explanation_pack = {
        "selected_model_name": selected_model_name,
        "selected_features": selected_features,
        "top_coefficients": top_coefficients(selected_result, selected_features),
        "selected_validation_metrics": selected_validation_metrics,
        "selected_test_metrics": selected_test_metrics,
    }
    (METRICS_DIR / "07_explanation_pack.json").write_text(
        json.dumps(explanation_pack, indent=2), encoding="utf-8"
    )

    scope = scope_df.iloc[0]
    reason = (
        "selected because the validation uplift materially exceeded the simpler baseline despite the added governance and explanation burden"
        if select_challenger
        else "selected because the encoded-history challenger did not add enough governed decision value to justify the extra explanation and maintenance burden"
    )
    selected_val_high_row = selected_val_bands[selected_val_bands["risk_band"] == "High"].iloc[0]
    selected_test_high_row = selected_test_bands[selected_test_bands["risk_band"] == "High"].iloc[0]
    selected_val_med_row = selected_val_bands[selected_val_bands["risk_band"] == "Medium"].iloc[0]

    write_md(
        ARTEFACT / "governed_model_use_case_v1.md",
        f"""
        # Governed Model Use Case v1

        Selected bounded use case:
        - predict authoritative fraud truth at `flow_id` level for prioritisation support

        Allowed use:
        - rank or band flows for human-led review prioritisation
        - support decision preparation rather than autonomous adjudication

        Explicit non-use:
        - no standalone automated decisioning
        - no truth-only or post-outcome fields as live-like features
        - no bank-view field as the target

        Bounded governed evidence:
        - `flow_rows`: {int(scope.flow_rows):,}
        - `fraud_truth_rate`: {pct(float(scope.fraud_truth_rate))}
        - `bank_view_rate`: {pct(float(scope.bank_view_rate))}
        - `truth_bank_mismatch_rate`: {pct(float(scope.truth_bank_mismatch_rate))}
        """,
    )

    write_md(
        ARTEFACT / "model_source_rules_v1.md",
        """
        # Model Source Rules v1

        Authoritative target source:
        - `s4_flow_truth_labels_6B`

        Comparison-only operational source:
        - `s4_flow_bank_view_6B`

        Feature-allowed first-pass source:
        - `s2_flow_anchor_baseline_6B`

        Restricted source:
        - `s4_case_timeline_6B` is allowed only for bounded explanatory context and not for post-outcome feature leakage

        Safe-use rule:
        - comparison-only bank-view fields may support explanation or assurance, but they must not override authoritative fraud truth in target logic
        """,
    )

    write_md(
        ARTEFACT / "model_fit_for_use_checks_v1.md",
        f"""
        # Model Fit For Use Checks v1

        Grain:
        - `flow_id` remains the modelling grain

        Coverage:
        - `flow_rows`: {int(scope.flow_rows):,}
        - `distinct_flow_id`: {int(scope.distinct_flow_id):,}
        - case-open coverage: {pct(float(scope.case_open_rate))}

        Governance result:
        - the bounded slice is usable for governed modelling
        - authoritative truth and comparison-only bank view remain materially different and must stay separated
        - the first-pass feature posture should remain anchor-led and leakage-screened
        """,
    )

    write_md(
        ARTEFACT / "model_risk_note_v1.md",
        """
        # Model Risk Note v1

        Main risk if overtrusted:
        - the score could be mistaken for an autonomous fraud adjudication output rather than a prioritisation aid

        Main bounded controls:
        - authoritative truth is the target source
        - comparison-only bank view is excluded from target logic
        - no post-outcome case fields are used as live-like features
        - thresholding is defined for human-led review support only

        Human-in-the-loop posture:
        - High band supports strongest review priority
        - the score should not replace case review or override other governance controls
        """,
    )

    write_md(
        ARTEFACT / "model_lineage_and_join_path_v1.md",
        """
        # Model Lineage And Join Path v1

        Join path:
        - `s2_flow_anchor_baseline_6B` -> `s4_flow_truth_labels_6B` on `flow_id`
        - `s2_flow_anchor_baseline_6B` -> `s4_flow_bank_view_6B` on `flow_id`
        - `s2_flow_anchor_baseline_6B` -> bounded `CASE_OPENED` view from `s4_case_timeline_6B` on `flow_id`

        Modelling posture:
        - anchor supplies the feature backbone
        - truth supplies the authoritative target
        - bank view remains comparison-only
        - case timeline supports bounded explanatory context and governance checks only
        """,
    )

    write_md(
        ARTEFACT / "flow_model_selection_decision_v1.md",
        f"""
        # Flow Model Selection Decision v1

        Selected model:
        - `{selected_model_name}`

        Decision reason:
        - {reason}

        Validation comparison:
        - baseline validation ROC AUC: {baseline_val_auc:.4f}
        - challenger validation ROC AUC: {challenger_val_auc:.4f}
        - baseline validation High-band truth rate: {pct(baseline_val_high_rate)}
        - challenger validation High-band truth rate: {pct(challenger_val_high_rate)}

        Governance interpretation:
        - the baseline remains the more directly explainable option
        - the challenger adds encoded historical-risk features derived from the training window and therefore needs stronger explanation and maintenance discipline
        """,
    )

    write_md(
        ARTEFACT / "flow_model_threshold_note_v1.md",
        f"""
        # Flow Model Threshold Note v1

        Selected threshold posture:
        - `High` band: validation top 5% workload threshold at probability >= {selected_high:.8f}
        - `Medium` band: validation top 20% workload threshold at probability >= {selected_medium:.8f}

        Validation band trade-off:
        - High-band rows: {int(selected_val_high_row.rows):,}
        - High-band truth rate: {pct(float(selected_val_high_row.positive_rate))}
        - High-band lift vs baseline: {float(selected_val_high_row.lift_vs_baseline):.2f}x
        - Medium-band rows: {int(selected_val_med_row.rows):,}
        - Medium-band truth rate: {pct(float(selected_val_med_row.positive_rate))}

        Human review boundary:
        - High band supports strongest review priority
        - Medium band supports secondary review support
        - the score does not replace human adjudication
        """,
    )

    top_features_md = "\n".join(
        [
            f"- `{row['feature']}`: coefficient {row['coefficient']:.4f}"
            for row in explanation_pack["top_coefficients"]
        ]
    )
    write_md(
        ARTEFACT / "flow_model_explanation_pack_v1.md",
        (
            "# Flow Model Explanation Pack v1\n\n"
            f"Selected model:\n- `{selected_model_name}`\n\n"
            "Main score drivers by absolute coefficient:\n"
            f"{top_features_md}\n\n"
            "Explanation reading:\n"
            "- the selected model remains reviewable because it is coefficient-based logistic scoring\n"
            "- if the challenger is selected, the added drivers are encoded historical-risk features rather than opaque tree logic\n"
            "- this keeps the slice explainable enough for challenge while still allowing a governed performance comparison\n"
        ),
    )

    write_md(
        ARTEFACT / "model_definition_pack_v1.md",
        f"""
        # Model Definition Pack v1

        Use case:
        - bounded flow-level fraud-risk prioritisation support

        Selected model:
        - `{selected_model_name}`

        Selected feature count:
        - {len(selected_features)}

        Target meaning:
        - authoritative fraud truth from `s4_flow_truth_labels_6B`
        """,
    )

    write_md(
        ARTEFACT / "model_assumptions_and_limits_v1.md",
        """
        # Model Assumptions And Limits v1

        Key assumptions:
        - the bounded local slice is representative enough for a governed first pass
        - anchor-led structural features are available at scoring time
        - authoritative truth remains the correct target surface

        Limits:
        - this is not a live deployment approval
        - this is not a platform-wide responsible-AI assurance pack
        - the score is bounded to prioritisation support and requires human review
        - no broad fairness claim is made from this bounded slice
        """,
    )

    write_md(
        ARTEFACT / "README_model_regeneration_v1.md",
        """
        # README - Model Regeneration v1

        Regeneration order:
        1. reuse the bounded file selection in `logs/bounded_file_selection.json`
        2. run the SQL governance gate
        3. build `flow_model_ready_slice_v1.parquet`
        4. build `flow_model_ready_slice_v2_encoded.parquet`
        5. run `build_governed_explainable_ai.py`

        Required review before recirculation:
        - confirm source rules still hold
        - confirm leakage boundaries still hold
        - confirm model-choice and threshold notes still match outputs
        """,
    )

    write_md(
        ARTEFACT / "MODEL_CHANGELOG.md",
        """
        # Model Changelog

        ## v1
        - initial governed and explainable AI slice
        - logistic baseline and encoded-history logistic challenger compared
        - model-choice, threshold, explanation, and caveat materials generated
        """,
    )

    write_md(
        ARTEFACT / "model_handover_summary_v1.md",
        f"""
        # Model Handover Summary v1

        Slice:
        - `05_governed_explainable_ai`

        Selected model:
        - `{selected_model_name}`

        Review essentials:
        - read the governed use-case note
        - read the source-rules note
        - read the model-selection decision
        - read the threshold note
        - read the assumptions and limits pack
        """,
    )

    write_md(
        ARTEFACT / "flow_model_decision_brief_v1.md",
        """
        # Flow Model Decision Brief v1

        What the score predicts:
        - bounded authoritative fraud risk at `flow_id` level

        What the score helps with:
        - prioritisation support
        - review ordering

        What it does not replace:
        - human adjudication
        - wider governance controls
        """,
    )

    write_md(
        ARTEFACT / "flow_model_challenge_response_v1.md",
        f"""
        # Flow Model Challenge Response v1

        Why trust this score?
        - the target is authoritative fraud truth
        - feature and target source rules were pinned before training
        - model choice and threshold choice were documented explicitly

        Why not trust it blindly?
        - it is bounded to one governed slice
        - it supports prioritisation, not autonomous decisioning
        - comparison-only bank-view signals remain excluded from target logic

        Why this model?
        - {reason}

        When should humans override it?
        - whenever case context or broader governance signals outweigh the bounded score
        """,
    )

    annotated_summary = pd.DataFrame(
        [
            {
                "selected_model_name": selected_model_name,
                "validation_auc": float(selected_validation_metrics["roc_auc"]),
                "test_auc": float(selected_test_metrics["roc_auc"]),
                "high_threshold": selected_high,
                "medium_threshold": selected_medium,
                "validation_high_band_truth_rate": float(selected_val_high_row.positive_rate),
                "test_high_band_truth_rate": float(selected_test_high_row.positive_rate),
            }
        ]
    )
    annotated_summary.to_csv(ARTEFACT / "flow_model_annotated_summary_v1.csv", index=False)

    write_md(
        ARTEFACT / "flow_model_action_note_v1.md",
        """
        # Flow Model Action Note v1

        Intended action:
        - use the High band for strongest review attention
        - use the Medium band for secondary review support
        - treat all bands as prioritisation support rather than automatic outcome decisions
        """,
    )

    fact_pack = {
        "slice": "midlands_partnership_nhs_ft/05_governed_explainable_ai",
        "governance_gate": records_for_json(scope_df)[0],
        "model_ready_profile": records_for_json(model_profile_df),
        "encoded_feature_null_rates": records_for_json(encoded_nulls_df)[0],
        "comparison_metrics": records_for_json(metrics_df),
        "selected_model_name": selected_model_name,
        "selected_features": selected_features,
        "selected_validation_metrics": selected_validation_metrics,
        "selected_test_metrics": selected_test_metrics,
        "selected_validation_risk_bands": records_for_json(selected_val_bands),
        "selected_test_risk_bands": records_for_json(selected_test_bands),
        "top_coefficients": explanation_pack["top_coefficients"],
        "assets": {
            "model_base_v1": str(MODEL_BASE_V1),
            "model_base_v2": str(MODEL_BASE_V2),
            "validation_scores_selected": str(SELECTED_VALIDATION_SCORES),
            "test_scores_selected": str(SELECTED_TEST_SCORES),
            "risk_band_summary": str(RISK_BAND_SUMMARY),
            "review_summary": str(MODEL_REVIEW_SUMMARY),
        },
    }
    (METRICS_DIR / "execution_fact_pack.json").write_text(
        json.dumps(fact_pack, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
