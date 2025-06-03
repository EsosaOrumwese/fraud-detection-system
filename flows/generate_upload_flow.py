"""
flows/generate_upload_flow.py

Prefect 3 flow that:
  1. Generates N synthetic rows to a local Parquet.
  2. Validates via Great Expectations suite (by running scripts/ge_validate.py).
  3. Uploads to S3 (RAW_BUCKET).
  4. Runs a DuckDB SQL check on the S3 object via a presigned URL.

To create/update a deployment:
    poetry run python flows/generate_upload_flow.py deploy
To run the deployment locally:
    prefect run --deployment generate-upload/generate-upload
"""

from pathlib import Path
from datetime import datetime
import os
import tempfile
import subprocess

from prefect import flow, task, get_run_logger
from prefect.deployments import Deployment  # Prefect 3.x

from fraud_detection.simulator.generate import generate_dataset, _upload_to_s3  # noqa: E402

# Fallback bucket if RAW_BUCKET not set
RAW_BUCKET = os.getenv("RAW_BUCKET", "fraud-raw-placeholder")


@task(retries=2, retry_delay_seconds=10, log_prints=True)
def create(rows: int) -> Path:
    """
    1) Make a temporary directory.
    2) Generate `rows` synthetic records into a Parquet under that directory.
    3) Return the Path to the generated Parquet.
    """
    out_dir = Path(tempfile.mkdtemp(prefix="simgen_"))
    return generate_dataset(rows, out_dir)


@task(retries=1, retry_delay_seconds=5, log_prints=True)
def ge_validate(file_path: Path):
    """
    Run the Great Expectations validation script as a subprocess.
    Invokes: scripts/ge_validate.py <file_path>.
    Exits with nonzero if validation fails.
    """
    logger = get_run_logger()
    logger.info(f"Running Great Expectations validation on {file_path} …")

    # Call the existing script directly, since it has no main() function.
    result = subprocess.run(
        ["python", "scripts/ge_validate.py", str(file_path)],
        capture_output=True,
    )

    # Log stdout and stderr for debugging
    if result.stdout:
        logger.info(result.stdout.decode().strip())
    if result.stderr:
        logger.error(result.stderr.decode().strip())

    # If the script exited with non-zero, raise to trigger a retry/failure
    if result.returncode != 0:
        raise RuntimeError(f"GE validation failed for {file_path}")


@task(retries=2, retry_delay_seconds=10, log_prints=True)
def upload(file_path: Path) -> str:
    """
    Upload the given Parquet to S3 (RAW_BUCKET). Returns the actual S3 URI.
    """
    logger = get_run_logger()
    logger.info(f"Uploading {file_path} to s3://{RAW_BUCKET} …")
    s3_uri = _upload_to_s3(file_path, RAW_BUCKET)
    logger.info(f"Uploaded → {s3_uri}")
    return s3_uri


@task(log_prints=True)
def duckdb_check(s3_uri: str):
    """
    Connect to DuckDB, run a simple SQL check (COUNT, AVG(amount)), and log the results.
    Uses a presigned URL (valid 1 hour) for parquet_scan.
    """
    import duckdb
    import boto3
    import botocore

    logger = get_run_logger()
    assert s3_uri.startswith("s3://"), "duckdb_check: s3_uri must start with s3://"
    parts = s3_uri[5:].split("/", 1)
    bucket, key = parts[0], parts[1]

    # Generate a presigned URL valid for 1 hour
    s3_client = boto3.client("s3", config=botocore.client.Config(signature_version="s3v4"))
    presigned = s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=3600,
    )
    logger.info(f"Using presigned URL (expires in 1h) for DuckDB: {presigned}")

    # Run a simple SQL query in DuckDB
    con = duckdb.connect()
    df = (
        con.execute(
            f"""
            SELECT
                COUNT(*) AS row_count,
                MIN(amount) AS min_amount,
                MAX(amount) AS max_amount,
                AVG(amount) AS avg_amount
            FROM parquet_scan('{presigned}')
            """
        )
        .fetchdf()
    )
    logger.info("DuckDB validation results:")
    logger.info(df.to_markdown(tablefmt="grid"))


@flow(name="generate-upload")
def main(rows: int = 1_000_000):
    """
    Orchestration flow:
      1. create(rows)        → file_path
      2. ge_validate(file_path)
      3. s3_uri = upload(file_path)
      4. duckdb_check(s3_uri)
    """
    logger = get_run_logger()
    logger.info(f"Flow start: generating {rows} rows …")
    file_path = create(rows)
    ge_validate(file_path)
    s3_uri = upload(file_path)
    duckdb_check(s3_uri)
    logger.info("Flow completed successfully.")


def deploy():
    """
    Build (or update) a Prefect deployment for this flow, using the Python SDK.
    This replaces the old 'prefect deployment build' CLI.
    """
    Deployment.build_from_flow(
        flow=main,
        name="generate-upload",
        work_pool_name="default",
        apply=True,
        parameters={"rows": 1_000_000},
        tags=["production", "etl"],
        # Optionally, specify image/entrypoint if needed:
        # image="ghcr.io/<owner>/simgen:latest",
        # entrypoint=["python", "-m", "fraud_detection.simulator.generate"],
    )


if __name__ == "__main__":
    """
    Two modes:
      1) `poetry run python flows/generate_upload_flow.py deploy`
         → creates/updates the deployment on Prefect via Deployment.build_from_flow.
      2) `poetry run python flows/generate_upload_flow.py`
         → runs the flow locally in debug mode (default rows=1_000_000).
    """
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "deploy":
        deploy()
    else:
        main()
