#!/usr/bin/env python3
"""
Command‐line interface for the fraud simulator, now driven by config including risk priors.

Handles:
 1. Argument parsing (rows, fraud_rate, seed, out_dir, S3 flag)
 2. Invoking core.generate_dataframe & write_parquet
 3. Optional S3 upload using boto3==1.35.49
 4. Clear exit codes and messages for any failures

Workflow:
 1. Parse --config and --s3 override
 2. Load & validate config via model_validate
 3. Generate DataFrame with correlated fraud via risk catalogs
 4. Write partitioned Parquet and optionally upload to S3
 5. Structured logs & clear exit codes
"""

import sys
import argparse
import logging
from pathlib import Path
from datetime import date
import time

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
    parser.add_argument(
        "--num-workers",
        type=int,
        help="Number of parallel worker processes to use (overrides config.num_workers)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        help="Number of rows to generate in each batch (overrides config.batch_size)",
    )
    parser.add_argument(
        "--realism",
        type=str,
        choices=["v1","v2"],
        default="v1",
        help="Override sampling mode (v1 = rebuild per chunk; v2 = pre-load catalogs)",
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
        # allow CLI to override performance knobs
        if args.num_workers is not None:
            cfg.num_workers = args.num_workers
        if args.batch_size is not None:
            cfg.batch_size = args.batch_size
        if args.realism:
            cfg.realism = args.realism
    except (FileNotFoundError, ValueError, ValidationError) as e:
        logger.error("Config error: %s", e)
        sys.exit(1)

    # Final settings (allow --s3 to override config.s3_upload)
    do_upload = args.s3 or cfg.s3_upload

    try:
        # 1) Generate
        logger.info(
            "Starting data generation (rows=%d, fraud_rate=%.4f, seed=%s)",
            cfg.total_rows, cfg.fraud_rate, cfg.seed,
        )
        start = time.perf_counter()
        df = generate_dataframe(cfg)
        elapsed = time.perf_counter() - start
        logger.info(
            "Generation complete: %d rows in %.2f s (%.0f rows/s)",
            len(df), elapsed, len(df) / elapsed,
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
