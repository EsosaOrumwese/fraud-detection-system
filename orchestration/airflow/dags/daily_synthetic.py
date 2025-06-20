"""
DAG: daily_synthetic
Author: Esosa Orumwese
Schedule: 02:00 UTC daily
Purpose: Generate 1 M synthetic transactions, upload Parquet to raw S3,
         and clean up local temp files.
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import boto3  # type: ignore
from airflow.decorators import dag, task
from airflow.models.param import Param
from airflow.utils.trigger_rule import TriggerRule

from fraud_detection.simulator.generate import generate_dataset  # type: ignore # signature: (total_rows, out_dir) → Path
from fraud_detection.utils.param_store import get_param  # type: ignore


# ─────────────────────────── DAG definition ────────────────────────────── #
@dag(
    schedule="0 2 * * *",  # 02:00 UTC daily
    start_date=datetime(2025, 6, 12),  # first valid run
    catchup=True,
    default_args={
        "owner": "mlops",
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
        "email_on_failure": False,
    },
    max_active_runs=1,  # no overlapping runs
    tags=["data-gen"],
    params={
        "rows": Param(1_000_000, type="integer", description="Total rows to generate"),
    },
)
def daily_synthetic():
    @task
    def fetch_bucket() -> str:
        """Retrieve the S3 raw-bucket name from SSM via your Param Store helper."""
        bucket = get_param("/fraud/raw_bucket_name")
        if not bucket:
            raise RuntimeError("SSM param '/fraud/raw_bucket_name' is empty")
        return bucket

    @task
    def generate(rows: int) -> str:
        """Run your generator and return the local Parquet file path."""
        tmp_dir = Path(tempfile.mkdtemp())
        out_path = generate_dataset(rows, tmp_dir)
        return str(out_path)

    @task
    def upload(local_path: str, bucket: str, ds: str) -> str:
        """
        Upload the generated Parquet to S3 under:
          s3://{bucket}/payments/year=YYYY/month=MM/{filename}
        """
        # parse execution date (ds is an ISO string)
        exec_dt = datetime.fromisoformat(ds)
        part = exec_dt.date()
        key = (
            f"payments/"
            f"year={part.year}/"
            f"month={part:%m}/"
            f"{Path(local_path).name}"
        )

        s3 = boto3.client(
            "s3",
            region_name=os.getenv("AWS_DEFAULT_REGION", "eu-west-2"),
        )
        s3.upload_file(local_path, bucket, key)
        return f"s3://{bucket}/{key}"

    @task(trigger_rule=TriggerRule.ALL_DONE)
    def cleanup(local_path: str):
        """Ensure the temp file is removed even if upstream fails."""
        try:
            Path(local_path).unlink(missing_ok=True)
        except Exception as e:
            # Log a warning but don’t fail the DAG
            print(f"Cleanup warning: {e}")

    # ─────────────────────── Compose task graph ───────────────────────── #
    bucket = fetch_bucket()
    file_path = generate("{{ params.rows }}")
    s3_uri = upload(file_path, bucket, "{{ ds }}")
    cleanup(file_path)



# instantiate the DAG
daily_synthetic = daily_synthetic()
