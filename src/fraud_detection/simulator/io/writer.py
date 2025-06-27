import logging
from pathlib import Path
from datetime import date
from typing import Union
import pyarrow as pa  # type: ignore
import pyarrow.parquet as pq  # type: ignore
from botocore.exceptions import ClientError  # type: ignore
import boto3  # type: ignore

class ParquetWriter:
    def __init__(self, output_dir: Union[str, Path], start_date: date):
        self.output_dir = Path(output_dir)
        self.start_date = start_date

    def write(self, table: pa.Table):
        file_name = f"transactions_{self.start_date.isoformat()}.parquet"
        out_path = self.output_dir / file_name
        out_path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(table, str(out_path))
        logging.info(f"Wrote Parquet file to {out_path}")

class S3ParquetWriter(ParquetWriter):
    def __init__(self, output_dir: Union[str, Path], start_date: date, bucket: str):
        super().__init__(output_dir, start_date)
        self.bucket = bucket
        self.s3 = boto3.client("s3")

    def write(self, table: pa.Table):
        file_name = f"transactions_{self.start_date.isoformat()}.parquet"
        key = file_name
        try:
            # Check if already exists
            self.s3.head_object(Bucket=self.bucket, Key=key)
            logging.info(f"s3://{self.bucket}/{key} exists → skipping upload")
            return
        except ClientError as e:
            # 404 means not found → proceed
            if e.response.get("Error", {}).get("Code") != "404":
                raise
        # Write locally then upload
        local_path = self.output_dir / file_name
        local_path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(table, str(local_path))
        self.s3.upload_file(str(local_path), self.bucket, key)
        logging.info(f"Uploaded to s3://{self.bucket}/{key}")
