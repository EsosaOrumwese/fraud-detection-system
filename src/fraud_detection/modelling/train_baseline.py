"""
Baseline fraud classifier: XGBoost + sklearn ColumnTransformer.

Usage (as a CLI):
    poetry run python -m fraud_detection.modelling.train_baseline \
        --rows 500000 \
        --parquet outputs/payments_1_000_000.parquet \
        --n-est 300 \
        --max-depth 6 \
        --learning-rate 0.1 \
        --max-categories 100 \
        --seed 42

This module is organized so that:
  - Helper functions (data loading, pipeline building, MLflow setup) are
    type-annotated, fully documented, and raise descriptive exceptions.
  - The `main()` function handles CLI parsing, MLflow context, and high-level logging.
  - Errors at any step are caught and logged before propagating.
"""

from __future__ import annotations

import argparse
import datetime
import logging
import os
import pathlib
import sys
import yaml  # type: ignore
from typing import Any

import mlflow
import mlflow.sklearn
from mlflow.models.signature import infer_signature
import pandas as pd  # type: ignore
import polars as pl
from sklearn.compose import ColumnTransformer  # type: ignore
from sklearn.metrics import average_precision_score  # type: ignore
from sklearn.model_selection import train_test_split  # type: ignore
from sklearn.pipeline import Pipeline  # type: ignore
from sklearn.preprocessing import OneHotEncoder  # type: ignore
from xgboost import XGBClassifier
import boto3  # type: ignore

from fraud_detection.utils.datetime_featurizer import DateTimeFeaturizer

import warnings

### Although my pipeline is fit, it still throws this error. So I'll ignore it for now till it's fixed
warnings.filterwarnings(
    "ignore",
    message="This Pipeline instance is not fitted yet.*",
    category=FutureWarning,
)


# ─── MODULE-LEVEL CONSTANTS ──────────────────────────────────────────────────

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

SCHEMA_PATH = pathlib.Path("schema/transaction_schema.yaml")


# Load & validate schema on import
def load_schema(schema_path: pathlib.Path) -> dict[str, Any]:
    """Read and parse the transaction_schema.yaml file. Raise if missing/invalid."""
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema not found at {schema_path.resolve()}")
    try:
        return yaml.safe_load(schema_path.read_text())
    except yaml.YAMLError as e:
        raise RuntimeError(f"Unable to parse YAML schema file: {e}") from e


# ─── DEFINING IMPORTANT VARIABLES ─────────────────────────────────────

SCHEMA = load_schema(SCHEMA_PATH)
TARGET = "label_fraud"

# Extract columns by dtype
CATEGORICAL: list[str] = [
    f["name"]
    for f in SCHEMA["fields"]
    if f.get("dtype") in ("enum", "string", "bool") and f["name"] != TARGET
]
NUMERIC: list[str] = [
    f["name"] for f in SCHEMA["fields"] if f.get("dtype") in ("int", "float")
]
INTEGER: list[str] = [f["name"] for f in SCHEMA["fields"] if f.get("dtype") == "int"]

# I am just expecting on datetime column
DATETIME: list[str] = [
    f["name"] for f in SCHEMA["fields"] if f.get("dtype") == "datetime"
]

# ─── DATA LOADING & PREPROCESSING HELPERS ─────────────────────────────────────


def load_data(
    rows: int,
    parquet_path: pathlib.Path,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Load up to `rows` records from the given Parquet file, sampled without replacement.

    Args:
        rows: Number of rows to sample. Must be <= total rows in file.
        parquet_path: Path to a single Parquet file conforming to SCHEMA.
        seed: Random seed for reproducibility.

    Returns:
        A pandas.DataFrame of shape (rows, n_columns) where n_columns == len(SCHEMA["fields"]).
    """
    if not parquet_path.exists():
        raise FileNotFoundError(f"Parquet file not found at {parquet_path.resolve()}")
    # Count total rows in Parquet
    total_rows_df = pl.scan_parquet(parquet_path).select(pl.len()).collect()
    total_rows = int(total_rows_df["len"][0])
    if rows > total_rows:
        raise ValueError(f"Requested {rows} rows but file has only {total_rows} rows.")

    # Sample without replacement (deterministic)
    # df_polars = pl.read_parquet(parquet_path).sample(
    #     n=rows, seed=seed, with_replacement=False
    # )
    # Wrap reads & sampling in the global cache:
    with pl.StringCache():
        df_polars = pl.read_parquet(parquet_path).sample(
            n=rows, seed=seed, with_replacement=False
        )
    df = df_polars.to_pandas()
    logger.info("Loaded %d rows from %s", rows, parquet_path.name)
    return df


def calc_class_weight(y: pd.Series) -> float:
    """
    Compute `scale_pos_weight = negative_count / positive_count` for XGBoost.

    Args:
        y: pd.Series of binary labels (0/1), where 1 indicates fraud.

    Returns:
        A float to assign to `scale_pos_weight`.
    """
    pos = int(y.sum())
    neg = int(len(y) - pos)
    if pos == 0:
        raise ValueError(
            "No positive examples in training set; cannot compute scale_pos_weight."
        )
    return neg / pos


def build_pipeline(
    max_categories: int,
    n_estimators: int,
    max_depth: int,
    learning_rate: float,
    tree_method: str = "hist",
) -> Pipeline:
    """
    Construct a scikit-learn pipeline: DateTimeFeaturizer → OneHotEncoder → passthrough numerics → XGBoost.

    Args:
        max_categories: `max_categories` argument for OneHotEncoder (sklearn ≥1.4).
        n_estimators: Number of XGBoost trees.
        max_depth: Maximum depth per tree.
        learning_rate: XGBoost learning rate.
        tree_method: XGBoost `tree_method` (e.g. "hist" for fast CPU training).

    Returns:
        A sklearn Pipeline that accepts raw DataFrame (with SCHEMA columns) and yields a fitted XGBClassifier.
    """
    dt_pipe = Pipeline(
        [
            ("featurize", DateTimeFeaturizer(fields=DATETIME, cyclical=True)),
        ]
    )

    one_hot = OneHotEncoder(
        handle_unknown="ignore",
        sparse_output=True,
        drop="first",
        max_categories=max_categories,
    )
    ct = ColumnTransformer(
        transformers=[
            ("dt", dt_pipe, DATETIME),
            ("cat", one_hot, CATEGORICAL),
            ("num", "passthrough", NUMERIC),
        ],
        remainder="drop",  # drop any unexpected columns
        sparse_threshold=0.0,  # ensure output is sparse if any transformer is sparse
    )
    model = XGBClassifier(
        tree_method=tree_method,
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=learning_rate,
        objective="binary:logistic",
        eval_metric="aucpr",
        use_label_encoder=False,
        verbosity=0,
    )
    pipeline = Pipeline(steps=[("prep", ct), ("clf", model)])
    return pipeline


# ─── MLflow SETUP ────────────────────────────────────────────────────────────────


def setup_mlflow(
    experiment_name: str,
    tracking_uri: str = "file:./outputs/mlruns",
) -> None:
    """
    Configure MLflow to use a local `outputs/mlruns/` directory and set up the experiment.

    If the experiment does not exist, it will be created (no error if it already exists).

    Args:
        experiment_name: Name of the MLflow experiment (e.g. "baseline_fraud").
        tracking_uri: Tracking URI (default: local folder "outputs/mlruns").
    """
    mlflow.set_tracking_uri(tracking_uri)
    try:
        mlflow.create_experiment(experiment_name)
    except mlflow.exceptions.MlflowException:
        # Experiment already exists; safe to ignore
        pass
    mlflow.set_experiment(experiment_name)
    logger.info("MLflow experiment set to '%s' at '%s'", experiment_name, tracking_uri)


def _upload_folder(run_id: str, artifact_path: str, bucket: str):
    """
    Recursively upload all artifacts from a given MLflow run path into an S3 bucket.

    This function traverses the MLflow artifact directory structure for the specified
    run and artifact path. It lists each entry using the MLflowClient API; if the entry
    is a directory, it recurses into that directory, and if it is a file, it downloads
    that file locally and uploads it to the given S3 bucket under the key
    `models/{run_id}/{artifact_relative_path}`. Logs a warning if the starting path
    contains no artifacts, and logs an info message for each successful upload.

    Args:
        run_id (str):
            The MLflow run identifier whose artifacts should be uploaded.
        artifact_path (str):
            The root artifact subdirectory (e.g. "pipeline_artifact") within the run
            from which to begin uploading.
        bucket (str):
            The name of the target S3 bucket where artifacts will be stored.

    Returns:
        None
    """
    from mlflow.tracking import MlflowClient

    client = MlflowClient()
    items = client.list_artifacts(run_id, artifact_path)
    if not items:
        logger.warning("No artifacts found at '%s' for run %s", artifact_path, run_id)
        return

    for item in items:
        # item.path is already like "pipeline_artifact/MLmodel" or deeper
        path_in_repo = item.path
        if item.is_dir:
            _upload_folder(run_id, path_in_repo, bucket)
        else:
            # this will pull down exactly that artifact file
            local_path = client.download_artifacts(run_id, path_in_repo)
            # put it under models/<run_id>/<relative_path>
            key = f"models/{run_id}/{path_in_repo}"
            boto3.client("s3").upload_file(str(local_path), bucket, key)
            logger.info("Uploaded %s → s3://%s/%s", path_in_repo, bucket, key)


# ─── QUICK-TRAIN FUNCTION FOR UNIT TESTS ─────────────────────────────────────────


def quick_train(
    rows: int,
    parquet_path: pathlib.Path,
    *,
    save_model: bool = False,
    out_dir: pathlib.Path | None = None,
    seed: int = 42,
    max_categories: int = 100,
    n_estimators: int = 50,
    max_depth: int = 3,
    learning_rate: float = 0.1,
) -> tuple[float, pathlib.Path] | float:  # type: ignore
    """
    A fast, in-memory train/test pass (used by unit tests).

    Steps:
      1. Load `rows` from `parquet_path` (random sample).
      2. Split 80/20 stratified.
      3. Build pipeline (OneHot + XGB) with small hyperparameters.
      4. Fit, predict, compute avg. precision (AUC-PR).
      5. If save_model=True, persist the fitted Pipeline to out_dir/baseline_xgb.pkl.

    Args:
        rows: Number of rows to sample for training+eval.
        parquet_path: Path to a small Parquet that matches SCHEMA.
        save_model: If True, pickle the fitted Pipeline into out_dir.
        out_dir: Directory to save model if save_model=True.
        seed: Random seed for reproducibility.
        max_categories: Maximum distinct categories passed to OneHotEncoder.
        n_estimators: Small number of XGB trees for a quick sanity check.
        max_depth: Depth for each tree.
        learning_rate: XGB learning rate.

    Returns:
        If save_model=False, returns only `auc_pr: float`.
        If save_model=True, returns `(auc_pr: float, model_path: pathlib.Path)`.
    """
    df = load_data(rows, parquet_path, seed=seed)
    if TARGET not in df.columns:
        raise KeyError(f"Target column '{TARGET}' missing from data.")

    X = df.drop(columns=[TARGET])
    # convert int to float to avoid MLFlow warnings about NULL and ints breaking schema
    X[INTEGER] = X[INTEGER].astype(float)

    # Cast label_fraud (bool) → int (0/1) for XGBoost
    y = df[TARGET].astype(int)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=seed
    )

    pipe = build_pipeline(
        max_categories=max_categories,
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=learning_rate,
    )
    spw = calc_class_weight(y_train)
    pipe.set_params(clf__scale_pos_weight=spw)
    pipe.fit(X_train, y_train)

    preds = pipe.predict_proba(X_test)[:, 1]
    auc_pr = average_precision_score(y_test, preds)

    if save_model:
        if out_dir is None:
            raise ValueError("out_dir must be provided if save_model=True.")
        out_dir.mkdir(parents=True, exist_ok=True)
        model_path = out_dir / "baseline_xgb.pkl"
        import joblib  # type: ignore

        joblib.dump(pipe, model_path)
        logger.info("Saved quick-test model to %s", model_path)
        return auc_pr, model_path

    return auc_pr


# ─── CLI ENTRYPOINT ─────────────────────────────────────────────────────────────


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for full training run."""
    parser = argparse.ArgumentParser(description="Train baseline XGBoost fraud model.")
    parser.add_argument(
        "--rows",
        type=int,
        default=500_000,
        help="Number of rows to sample from Parquet for train+test.",
    )
    parser.add_argument(
        "--parquet",
        type=pathlib.Path,
        default=None,
        help="Path to a single Parquet with 1_000_000 or N simulated payments (24 columns).",
    )
    parser.add_argument("--n-est", type=int, default=300, help="Number of XGB trees.")
    parser.add_argument(
        "--max-depth", type=int, default=6, help="Max depth per XGB tree."
    )
    parser.add_argument(
        "--learning-rate", type=float, default=0.1, help="XGB learning rate."
    )
    parser.add_argument(
        "--max-categories",
        type=int,
        default=150,
        help="Max distinct categories per feature for OneHotEncoder.",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    parser.add_argument(
        "--tree-method",
        type=str,
        default="hist",
        choices=["hist", "approx", "auto"],
        help="XGBoost `tree_method`.",
    )
    parser.add_argument(
        "--mlflow-experiment",
        type=str,
        default="baseline_fraud",
        help="Name of the MLflow experiment to log under.",
    )
    parser.add_argument(
        "--upload-artifacts",
        default="no",
        choices=["yes", "no"],
        help="Whether to push the trained pipeline to the artifacts S3 bucket",
    )
    return parser.parse_args(args)


def main() -> None:
    """
    Main CLI function to train on up to --rows samples from a Parquet, fit XGB,
    compute AUC-PR, log everything to MLflow, and register the model as 'fraud_xgb'.
    """
    args = parse_args()
    try:
        # Resolve Parquet path if not provided
        if args.parquet is None:
            args.parquet = resolve_single_parquet(pathlib.Path("outputs/"), args.rows)
        logger.info("Using Parquet: %s", args.parquet)

        # Load data
        df = load_data(args.rows, args.parquet, seed=args.seed)
        if TARGET not in df.columns:
            raise KeyError(f"Target column '{TARGET}' missing from data.")
        X = df.drop(columns=[TARGET])
        # convert int to float to avoid MLFlow warnings about NULL and ints breaking schema
        X[INTEGER] = X[INTEGER].astype(float)
        y = df[TARGET].astype(int)

        # Split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, stratify=y, random_state=args.seed
        )
        logger.info(
            "Train/test split: %d training rows, %d test rows; fraud rate: %.4f%% → %.4f%%",
            len(y_train),
            len(y_test),
            100 * (y.sum() / len(y)),
            100 * (y_test.sum() / len(y_test)),
        )

        # Build pipeline with user-specified hyperparameters
        pipeline = build_pipeline(
            max_categories=args.max_categories,
            n_estimators=args.n_est,
            max_depth=args.max_depth,
            learning_rate=args.learning_rate,
            tree_method=args.tree_method,
        )
        spw = calc_class_weight(y_train)
        pipeline.set_params(clf__scale_pos_weight=spw)

        # Set up MLflow
        setup_mlflow(args.mlflow_experiment, tracking_uri="file:./outputs/mlruns")
        with mlflow.start_run(run_name="baseline_xgb") as run:
            # Log parameters & tags
            mlflow.log_params(
                {
                    "rows": str(args.rows),
                    "n_estimators": str(args.n_est),
                    "max_depth": str(args.max_depth),
                    "learning_rate": str(args.learning_rate),
                    "scale_pos_weight": str(spw),
                    "train_timestamp": datetime.datetime.now(
                        datetime.timezone.utc
                    ).isoformat(),
                    "seed": str(args.seed),
                }
            )
            mlflow.set_tag("schema_version", SCHEMA.get("version", "unknown"))
            mlflow.set_tag("git_commit", os.getenv("GIT_SHA", "local"))

            # Fit & evaluate
            pipeline.fit(X_train, y_train)
            preds = pipeline.predict_proba(X_test)[:, 1]
            auc_pr = average_precision_score(y_test, preds)
            mlflow.log_metric("auc_pr_test", auc_pr)
            logger.info("Test AUC-PR: %.4f", auc_pr)

            # Log pipeline (preprocessing + model) as a single sklearn artifact
            sig = infer_signature(X_train, preds)
            mlflow.sklearn.log_model(
                sk_model=pipeline,
                artifact_path="pipeline_artifact",
                registered_model_name="fraud_xgb",
                signature=sig,
            )

            # optional S3‐upload of model artifacts
            if args.upload_artifacts == "yes":
                from fraud_detection.utils.param_store import get_param

                bucket = get_param("/fraud/artifacts_bucket_name")
                logger.info("Artifacts‐upload enabled; bucket from SSM: %r", bucket)
                if not bucket:
                    logger.error("No artifacts bucket in SSM—skipping upload")
                else:
                    run_id = run.info.run_id
                    base_artifact_path = "pipeline_artifact"

                    # kick it off
                    _upload_folder(run_id, base_artifact_path, bucket)

            # Log a small sample (1%) of the source data for traceability
            sample_df = df.sample(frac=0.01, random_state=args.seed)
            # sample_path = BASE_DIR / "mlruns" / "tmp_sample.csv"
            sample_path = pathlib.Path("outputs/mlruns/tmp_sample.csv")
            sample_df.to_csv(sample_path, index=False)
            mlflow.log_artifact(str(sample_path), artifact_path="sample_source")
            sample_path.unlink()
            logger.info(
                "Run finished. AUC-PR=%.4f; run_id=%s",
                auc_pr,
                run.info.run_id,
            )
    except Exception as e:
        logger.exception("Training failed: %s", e)
        sys.exit(1)


def resolve_single_parquet(outputs_dir: pathlib.Path, rows: int) -> pathlib.Path:
    """
    Search for exactly one 'payments_{rows}_*.parquet' under outputs_dir.
    Raise if zero or >1 matches.
    """
    if not outputs_dir.exists() or not outputs_dir.is_dir():
        raise FileNotFoundError(f"Expected a directory at {outputs_dir}")
    pattern = f"payments_{rows:_}_*.parquet"
    candidates = list(outputs_dir.glob(pattern))
    if len(candidates) == 0:
        raise FileNotFoundError(f"No matching Parquet files under {outputs_dir}")
    if len(candidates) > 1:
        names = ", ".join(p.name for p in candidates)
        raise RuntimeError(f"Multiple candidate Parquets found: {names}")
    return candidates[0]


if __name__ == "__main__":
    main()
