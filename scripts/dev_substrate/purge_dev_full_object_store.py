from __future__ import annotations

import sys
import time
from pathlib import Path

import boto3
from botocore.config import Config


BUCKET = "fraud-platform-dev-full-object-store"
REGION = "eu-west-2"


def log(msg: str) -> None:
    print(msg, flush=True)


def main() -> int:
    s3 = boto3.client(
        "s3",
        region_name=REGION,
        config=Config(
            retries={"max_attempts": 10, "mode": "standard"},
            max_pool_connections=50,
        ),
    )

    log(f"Starting purge for {BUCKET} in {REGION}")

    total_removed = 0
    batch = 0
    start = time.time()

    while True:
        resp = s3.list_object_versions(Bucket=BUCKET, MaxKeys=1000)
        objs = []
        for v in resp.get("Versions", []):
            objs.append({"Key": v["Key"], "VersionId": v["VersionId"]})
        for m in resp.get("DeleteMarkers", []):
            objs.append({"Key": m["Key"], "VersionId": m["VersionId"]})

        if not objs:
            log("No remaining object versions or delete markers.")
            break

        batch += 1
        s3.delete_objects(Bucket=BUCKET, Delete={"Objects": objs, "Quiet": True})
        total_removed += len(objs)

        if batch == 1 or batch % 25 == 0:
            elapsed = time.time() - start
            log(f"batches={batch} removed={total_removed} elapsed_sec={elapsed:.1f}")

    upload_count = 0
    while True:
        uploads = s3.list_multipart_uploads(Bucket=BUCKET).get("Uploads", [])
        if not uploads:
            break
        for upload in uploads:
            s3.abort_multipart_upload(
                Bucket=BUCKET,
                Key=upload["Key"],
                UploadId=upload["UploadId"],
            )
            upload_count += 1
        log(f"aborted_multipart_uploads={upload_count}")

    elapsed = time.time() - start
    log(f"Finished purge. removed={total_removed} multipart_aborted={upload_count} elapsed_sec={elapsed:.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
