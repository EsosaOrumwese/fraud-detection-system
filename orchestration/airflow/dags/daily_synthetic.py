"""
DAG: daily_synthetic
Author: Esosa Orumwese
Schedule: 02:00 UTC daily
Purpose: Generate 1 M synthetic transactions, upload Parquet to raw S3,
         and clean up local temp files.
"""

from __future__ import annotations

import sys
import subprocess
import shutil
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from airflow.decorators import dag, task
from airflow.providers.amazon.aws.hooks.s3 import S3Hook

from fraud_detection.simulator.generate import generate_dataset  # type: ignore
from fraud_detection.utils.param_store import get_param  # type: ignore
from fraud_detection.simulator.config import load_config

# 1. Default/task‐level retry & alert settings
default_args = {
    "owner": "mlops",
    "depends_on_past": False,
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,
}


# 2. DAG decorator — using 'schedule' (cron) per Airflow 3 docs
@dag(
    dag_id="daily_synthetic",
    default_args=default_args,
    schedule="0 2 * * *",  # 02:00 UTC daily
    start_date=datetime(2025, 6, 20),
    catchup=False,
    max_active_runs=1,
    tags=["data_generation", "synthetic"],
)
def daily_synthetic():
    @task
    def fetch_bucket_name() -> str:
        """Retrieve the S3 raw-bucket name from SSM via your Param Store helper."""
        bucket = get_param("/fraud/raw_bucket_name")
        if not bucket:
            raise RuntimeError("SSM param '/fraud/raw_bucket_name' is empty")
        return bucket

    @task(multiple_outputs=True)
    def run_generator() -> dict[str, str]:
        """Run your generator and return the local Parquet file path & temp_dir."""
        base_dir = Path(__file__).parents[1]  # Dag is located in ./dags/ in Docker container
        config_path = base_dir / "project_config" / "generator_config.yaml"

        cfg = load_config(config_path)
        tmp_dir = Path(tempfile.mkdtemp())

        cfg.out_dir = tmp_dir
        out_file = generate_dataset(cfg)
        return {
            "local_path": str(out_file),
            "tmp_dir": str(tmp_dir),
            "config_path": str(config_path),
        }

    @task
    def validate_file(local_path: str) -> None:
        """Validate via your existing GE script — production via subprocess"""
        script = Path("/opt/airflow/scripts/ge_validate.py")
        if not script.exists():
            raise FileNotFoundError(f"Validation script missing at {script}")
        subprocess.run([sys.executable, str(script), local_path], check=True)

    @task
    def upload_to_s3(local_path: str, bucket: str, execution_date: str, config_path: str) -> str:
        """
        Upload the generated Parquet to S3 under:
          s3://{bucket}/payments/year=YYYY/month=MM/{filename}
        """
        # ds == 'YYYY-MM-DD'
        cfg = load_config(Path(config_path))
        date = datetime.fromisoformat(execution_date)
        key = (
            f"payments/"
            f"year={date.year}/month={date.month:02d}/"
            f"payments_{cfg.total_rows:_}_{execution_date}.parquet"
        )
        hook = S3Hook(aws_conn_id=None)
        hook.load_file(
            filename=local_path,
            key=key,
            bucket_name=bucket,
            replace=True,
        )
        return f"s3://{bucket}/{key}"

    @task(trigger_rule="all_done")
    def cleanup_tmp(tmp_dir: str) -> None:
        """Ensure the temp file is removed even if upstream fails."""
        shutil.rmtree(tmp_dir, ignore_errors=True)

    # Define dependencies
    bucket = fetch_bucket_name()
    gen = run_generator()
    validation = validate_file(gen["local_path"])
    upload = upload_to_s3(gen["local_path"], bucket, "{{ ds }}", gen["config_path"])
    cleanup = cleanup_tmp(gen["tmp_dir"])

    bucket >> gen >> validation >> upload >> cleanup  # type: ignore[list-item]


# instantiate the DAG
daily_synthetic = daily_synthetic()  # type: ignore
