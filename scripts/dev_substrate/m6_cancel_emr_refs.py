#!/usr/bin/env python3
"""Cancel one or more EMR on EKS job runs for M6.F bounded windows."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser(description="Cancel EMR lane job refs")
    parser.add_argument("--region", required=True)
    parser.add_argument("--virtual-cluster-id", required=True)
    parser.add_argument("--job-id", action="append", required=True)
    args = parser.parse_args()

    emr = boto3.client("emr-containers", region_name=args.region)

    results: list[dict[str, Any]] = []
    for job_id in args.job_id:
        normalized = str(job_id).strip()
        if not normalized:
            continue
        try:
            resp = emr.cancel_job_run(
                id=normalized,
                virtualClusterId=args.virtual_cluster_id,
            )
            results.append(
                {
                    "job_id": normalized,
                    "status": "cancel_requested",
                    "response_id": resp.get("id"),
                    "virtual_cluster_id": resp.get("virtualClusterId"),
                }
            )
        except (BotoCoreError, ClientError) as exc:
            results.append(
                {
                    "job_id": normalized,
                    "status": "cancel_error",
                    "error": f"{type(exc).__name__}:{exc}",
                }
            )

    payload = {
        "timestamp_utc": _now_utc(),
        "virtual_cluster_id": args.virtual_cluster_id,
        "results": results,
    }
    print(json.dumps(payload, ensure_ascii=True))

    has_error = any(item.get("status") == "cancel_error" for item in results)
    return 1 if has_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
