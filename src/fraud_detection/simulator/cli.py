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
import json
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
    """
    Entry point for the fraud simulator CLI.

    Parses command-line arguments for:
      --config      Path to generator_config.yaml
      --s3          Flag to upload outputs (transactions & catalogs) to S3
      --log-level   Logging level (e.g. INFO, DEBUG)
      --num-workers Override number of parallel workers
      --batch-size  Override number of rows per chunk
      --realism     Sampling mode: "v1" or "v2"

    Workflow:
      1. Load and validate configuration via config.load_config()
      2. Invoke core.generate_dataframe(cfg) to build the DataFrame
      3. Write partitioned Parquet under out_dir/payments/year=…/month=…
      4. If --s3:
         • upload transactions to the raw-data bucket
         • if realism="v2", upload catalog Parquets to the artifacts bucket
    """
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
        choices=["v1", "v2"],
        default="v1",
        help="Override sampling mode (v1 = rebuild per chunk; v2 = pre-load catalogs)",
    )
    # ── SD-02 temporal overrides ───────────────────────────────────────────────
    parser.add_argument(
        "--weekday-weights",
        type=str,
        help="JSON string containing weekday-to-weight map",
    )
    parser.add_argument(
        "--time-components",
        type=str,
        help="JSON string containing list of time-component objects",
    )
    parser.add_argument(
        "--seed",
        type=str,
        help="Override RNG seed (int or string) for reproducibility",
    )
    parser.add_argument(
        "--distribution-type",
        type=str,
        choices=["gaussian"],
        help="Override temporal distribution type",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        help="Override max rows per sampling batch (chunk_size)",
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
        # allow CLI to override performance & temporal knobs
        if args.num_workers is not None:
            cfg.num_workers = args.num_workers
        if args.batch_size is not None:
            cfg.batch_size = args.batch_size
        if args.realism:
            cfg.realism = args.realism

        # ── CLI overrides for temporal settings ─────────────────────────────────
        # weekday_weights (inline JSON only)
        if args.weekday_weights is not None:
            # 1) Load JSON
            try:
                raw = json.loads(args.weekday_weights)
            except json.JSONDecodeError as e:
                logger.error("Invalid JSON for --weekday-weights: %s", e)
                sys.exit(1)

            # 2) Must be a dict
            if not isinstance(raw, dict):
                logger.error("--weekday-weights must be a JSON object")
                sys.exit(1)

            # 3) Coerce & validate entries
            override_w: dict[int, float] = {}
            for k, v in raw.items():
                try:
                    ik = int(k)
                    fv = float(v)
                except Exception:
                    logger.error("Invalid entry in --weekday-weights: key %r→int, value %r→float", k, v)
                    sys.exit(1)
                if ik < 0 or ik > 6:
                    logger.error("Weekday index %d out of range [0,6]", ik)
                    sys.exit(1)
                if fv <= 0:
                    logger.error("Weekday weight for %d must be > 0; got %s", ik, v)
                    sys.exit(1)
                override_w[ik] = fv

            # 4) Empty dict → uniform weights
            if not override_w:
                override_w = {i: 1.0 for i in range(7)}

            # 5) Ensure weights sum > 0
            total = sum(override_w.values())
            if total <= 0:
                logger.error("Sum of weekday-weights must be > 0; got %s", total)
                sys.exit(1)

            # 6) Merge non-mutatively with file or defaults
            existing = cfg.temporal.weekday_weights or {}
            merged = {**existing, **override_w}
            cfg.temporal.weekday_weights = merged

        # time_components (inline JSON only)
        if args.time_components is not None:
            try:
                tc_list = json.loads(args.time_components)
            except json.JSONDecodeError as e:
                logger.error("Malformed JSON for --time-components: %s", e)
                sys.exit(1)
            try:
                from fraud_detection.simulator.config import TimeComponentConfig
                cfg.temporal.time_components = [
                    TimeComponentConfig(**c) for c in tc_list
                ]
            except ValidationError as e:
                logger.error("Invalid entry in --time-components: %s", e)
                sys.exit(1)

        # seed override (int or string)
        if args.seed is not None:
            try:
                cfg.seed = int(args.seed)
            except ValueError:
                logger.error("--seed must be an integer")
                sys.exit(1)

        # distribution_type override
        if args.distribution_type:
            cfg.temporal.distribution_type = args.distribution_type

        # chunk_size override
        if args.chunk_size is not None:
            if args.chunk_size <= 0:
                logger.error("--chunk-size must be > 0")
                sys.exit(1)
            cfg.temporal.chunk_size = args.chunk_size
        # ── Observability: dump final temporal settings ───────────────────────────
        logger.info(
            "Resolved temporal settings: weekday_weights=%s, time_components=%s, "
            "distribution_type=%s, chunk_size=%s",
            cfg.temporal.weekday_weights,
            cfg.temporal.time_components,
            cfg.temporal.distribution_type,
            cfg.temporal.chunk_size,
        )
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
        start = time.perf_counter()
        df = generate_dataframe(cfg)
        elapsed = time.perf_counter() - start
        logger.info(
            "Generation complete: %d rows in %.2f s (%.0f rows/s)",
            len(df),
            elapsed,
            len(df) / elapsed,
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
            s3 = boto3.client("s3")

            bucket = get_param("/fraud/raw_bucket_name")
            key = f"payments/year={year}/month={month}/{filename}"
            logger.info("Uploading to S3: s3://%s/%s", bucket, key)
            s3.upload_file(str(local_path), bucket, key)
            logger.info("Upload complete: s3://%s/%s", bucket, key)

            # Upload catalogs (v2) to artifacts bucket
            if cfg.realism == "v2":
                bucket_art = get_param("/fraud/artifacts_bucket_name")
                catalog_dir = Path(cfg.out_dir) / "catalog"
                for parquet_file in catalog_dir.glob("*.parquet"):
                    key_cat = f"catalogues/{parquet_file.name}"
                    logger.info(
                        f"Uploading catalog {parquet_file.name} to s3://{bucket_art}/{key_cat}"
                    )
                    s3.upload_file(str(parquet_file), bucket_art, key_cat)

    except ClientError as e:
        logger.error("S3 upload failed: %s", e, exc_info=True)
        sys.exit(2)
    except Exception:
        logger.exception("Generator failed unexpectedly")
        sys.exit(1)


if __name__ == "__main__":
    main()
