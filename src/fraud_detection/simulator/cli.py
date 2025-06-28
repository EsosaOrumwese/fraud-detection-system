#!/usr/bin/env python3
"""
Command‐line interface for the fraud simulator.

Handles:
 1. Argument parsing (rows, fraud_rate, seed, out_dir, S3 flag)
 2. Invoking core.generate_dataframe & write_parquet
 3. Optional S3 upload using boto3==1.35.49
 4. Clear exit codes and messages for any failures

Workflow:
 1. Parse --config and any override flags
 2. Load & validate config via model_validate
 3. Apply CLI overrides (only for S3 flag)
 4. Generate, write, and optionally upload based on final settings
"""

import sys
import argparse
import logging
from pathlib import Path
from datetime import date

import boto3  # type: ignore
from botocore.exceptions import ClientError  # type: ignore

from pydantic import ValidationError

from fraud_detection.simulator.config import load_config, GeneratorConfig
from fraud_detection.simulator.core import generate_dataframe, write_parquet
from fraud_detection.utils.param_store import get_param


# Module‐level logger
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate synthetic payments matching schema and optionally upload to S3"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("project_config/generator_config.yaml"),
        help="Path to YAML config file",
    )
    parser.add_argument(
        "--s3", action="store_true", help="Upload resulting Parquet to S3"
    )
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Set logging level",
    )
    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s – %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger.debug("Arguments: %s", args)

    # Load & validate config
    try:
        cfg: GeneratorConfig = load_config(args.config)
    except (FileNotFoundError, ValueError, ValidationError) as e:
        logger.error("Config error: %s", e)
        sys.exit(1)

    # Final settings (allow --s3 to override config.s3_upload)
    do_upload = args.s3 or cfg.s3_upload

    try:
        # 1) Generate
        logger.info(
            "Starting data generation (rows=%d, fraud_rate=%.4f, seed=%s)",
            cfg.total_rows,
            cfg.fraud_rate,
            cfg.seed,
        )
        df = generate_dataframe(
            total_rows=cfg.total_rows,
            fraud_rate=cfg.fraud_rate,
            seed=cfg.seed,
            start_date=cfg.temporal.start_date,
            end_date=cfg.temporal.end_date,
        )

        # 2) Write locally
        today = date.today()
        year = today.year
        month = f"{today.month:02d}"
        filename = f"payments_{cfg.total_rows:_}_{today.isoformat()}.parquet"

        # local path: {out_dir}/payments/year=YYYY/month=MM/filename
        local_dir = cfg.out_dir / "payments" / f"year={year}" / f"month={month}"
        local_path = write_parquet(df, local_dir / filename)
        logger.info("Written local file: %s", local_path)

        # 3) Optional S3 upload
        if do_upload:
            bucket = get_param("/fraud/raw_bucket_name")
            key = f"payments/year={year}/month={month}/{filename}"
            logger.info("Uploading to S3: s3://%s/%s", bucket, key)
            boto3.client("s3").upload_file(str(local_path), bucket, key)
            logger.info("Upload complete: s3://%s/%s", bucket, key)

    except ClientError as e:
        logger.error("S3 upload failed: %s", e, exc_info=True)
        sys.exit(2)
    except Exception:
        logger.exception("Generator failed unexpectedly")
        sys.exit(1)


if __name__ == "__main__":
    main()
