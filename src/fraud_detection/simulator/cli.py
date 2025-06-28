#!/usr/bin/env python3
"""
Command‐line interface for the fraud simulator.

Handles:
 1. Argument parsing (rows, fraud_rate, seed, out_dir, S3 flag)
 2. Invoking core.generate_dataframe & write_parquet
 3. Optional S3 upload using boto3==1.35.49
 4. Clear exit codes and messages for any failures
"""

import sys
import argparse
import logging
from pathlib import Path
from datetime import date

import boto3  # type: ignore
from botocore.exceptions import ClientError  # type: ignore

from fraud_detection.simulator.core import generate_dataframe, write_parquet
from fraud_detection.utils.param_store import get_param


# Module‐level logger
logger = logging.getLogger(__name__)

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate synthetic payments matching schema and optionally upload to S3"
    )
    parser.add_argument("--rows",       type=int,    default=1_000_000, help="Number of transactions")
    parser.add_argument("--fraud-rate", type=float,  default=0.01,     help="Overall fraud prevalence")
    parser.add_argument("--seed",       type=int,    default=None,     help="RNG seed for reproducibility")
    parser.add_argument("--out-dir",    type=Path,   default=Path("outputs"), help="Local output directory")
    parser.add_argument("--s3",         action="store_true",           help="Upload resulting Parquet to S3")
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Set logging level"
    )
    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s – %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger.debug("Arguments: %s", args)

    try:
        # 1) Generate
        logger.info("Starting data generation (rows=%s, fraud_rate=%s)", args.rows, args.fraud_rate)
        df = generate_dataframe(total_rows=args.rows, fraud_rate=args.fraud_rate, seed=args.seed)

        # 2) Write locally
        today = date.today()
        year = today.year
        month = f"{today.month:02d}"
        filename = f"payments_{args.rows:_}_{today.isoformat()}.parquet"

        # local path: {out_dir}/payments/year=YYYY/month=MM/filename
        local_dir = args.out_dir / "payments" / f"year={year}" / f"month={month}"
        local_path = write_parquet(df, local_dir / filename)
        logger.info("Written local file: %s", local_path)

        # 3) Optional S3 upload
        if args.s3:
            bucket = get_param("/fraud/raw_bucket_name")
            key = f"payments/year={year}/month={month}/{filename}"
            logger.info("Uploading to S3: s3://%s/%s", bucket, key)
            boto3.client("s3").upload_file(str(local_path), bucket, key)
            logger.info("Upload complete: s3://%s/%s", bucket, key)

    except ClientError as e:
        logger.error("S3 upload failed: %s", e, exc_info=True)
        sys.exit(2)
    except Exception as e:
        logger.exception("Generator failed unexpectedly")
        sys.exit(1)

if __name__ == "__main__":
    main()
