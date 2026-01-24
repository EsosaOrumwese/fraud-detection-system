"""Object-store utilities for SR artifacts (local + S3-compatible)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Protocol
from urllib.parse import urlparse


@dataclass(frozen=True)
class ArtifactRef:
    path: str
    digest: str | None = None


class ObjectStore(Protocol):
    def write_json(self, relative_path: str, payload: dict[str, Any]) -> ArtifactRef:
        ...

    def write_json_if_absent(self, relative_path: str, payload: dict[str, Any]) -> ArtifactRef:
        ...

    def read_json(self, relative_path: str) -> dict[str, Any]:
        ...

    def write_text(self, relative_path: str, content: str) -> ArtifactRef:
        ...

    def write_text_if_absent(self, relative_path: str, content: str) -> ArtifactRef:
        ...

    def append_jsonl(self, relative_path: str, records: Iterable[dict[str, Any]]) -> ArtifactRef:
        ...

    def exists(self, relative_path: str) -> bool:
        ...

    def read_text(self, relative_path: str) -> str:
        ...

    def list_files(self, relative_dir: str) -> list[str]:
        ...


class LocalObjectStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def _full_path(self, relative_path: str) -> Path:
        return self.root / relative_path

    def ensure_dir(self, relative_path: str) -> Path:
        path = self._full_path(relative_path)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def write_json(self, relative_path: str, payload: dict[str, Any]) -> ArtifactRef:
        path = self._full_path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        data = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
        tmp_path.write_text(data + "\n", encoding="utf-8")
        os.replace(tmp_path, path)
        return ArtifactRef(path=str(path))

    def write_json_if_absent(self, relative_path: str, payload: dict[str, Any]) -> ArtifactRef:
        path = self._full_path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":")) + "\n"
        try:
            with path.open("x", encoding="utf-8") as handle:
                handle.write(data)
        except FileExistsError as exc:
            raise exc
        return ArtifactRef(path=str(path))

    def read_json(self, relative_path: str) -> dict[str, Any]:
        path = self._full_path(relative_path)
        return json.loads(path.read_text(encoding="utf-8"))

    def write_text(self, relative_path: str, content: str) -> ArtifactRef:
        path = self._full_path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(content, encoding="utf-8")
        os.replace(tmp_path, path)
        return ArtifactRef(path=str(path))

    def write_text_if_absent(self, relative_path: str, content: str) -> ArtifactRef:
        path = self._full_path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("x", encoding="utf-8") as handle:
                handle.write(content)
        except FileExistsError as exc:
            raise exc
        return ArtifactRef(path=str(path))

    def append_jsonl(self, relative_path: str, records: Iterable[dict[str, Any]]) -> ArtifactRef:
        path = self._full_path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            for record in records:
                line = json.dumps(record, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
                handle.write(line + "\n")
        return ArtifactRef(path=str(path))

    def exists(self, relative_path: str) -> bool:
        return self._full_path(relative_path).exists()

    def read_text(self, relative_path: str) -> str:
        return self._full_path(relative_path).read_text(encoding="utf-8")

    def list_files(self, relative_dir: str) -> list[str]:
        base = self._full_path(relative_dir)
        if not base.exists():
            return []
        return [str(path) for path in base.rglob("*") if path.is_file()]


class S3ObjectStore:
    def __init__(self, bucket: str, prefix: str = "") -> None:
        import boto3

        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self._client = boto3.client("s3")

    def _key(self, relative_path: str) -> str:
        relative = relative_path.lstrip("/")
        if not self.prefix:
            return relative
        return f"{self.prefix}/{relative}"

    def _put_text(self, key: str, content: str) -> None:
        self._client.put_object(Bucket=self.bucket, Key=key, Body=content.encode("utf-8"))

    def write_json(self, relative_path: str, payload: dict[str, Any]) -> ArtifactRef:
        data = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":")) + "\n"
        key = self._key(relative_path)
        self._put_text(key, data)
        return ArtifactRef(path=f"s3://{self.bucket}/{key}")

    def write_json_if_absent(self, relative_path: str, payload: dict[str, Any]) -> ArtifactRef:
        from botocore.exceptions import ClientError

        data = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":")) + "\n"
        key = self._key(relative_path)
        try:
            self._client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=data.encode("utf-8"),
                IfNoneMatch="*",
            )
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code")
            if error_code in {"PreconditionFailed", "412"}:
                raise FileExistsError(key) from exc
            raise
        return ArtifactRef(path=f"s3://{self.bucket}/{key}")

    def read_json(self, relative_path: str) -> dict[str, Any]:
        key = self._key(relative_path)
        response = self._client.get_object(Bucket=self.bucket, Key=key)
        body = response["Body"].read().decode("utf-8")
        return json.loads(body)

    def write_text(self, relative_path: str, content: str) -> ArtifactRef:
        key = self._key(relative_path)
        self._put_text(key, content)
        return ArtifactRef(path=f"s3://{self.bucket}/{key}")

    def write_text_if_absent(self, relative_path: str, content: str) -> ArtifactRef:
        from botocore.exceptions import ClientError

        key = self._key(relative_path)
        try:
            self._client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=content.encode("utf-8"),
                IfNoneMatch="*",
            )
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code")
            if error_code in {"PreconditionFailed", "412"}:
                raise FileExistsError(key) from exc
            raise
        return ArtifactRef(path=f"s3://{self.bucket}/{key}")

    def append_jsonl(self, relative_path: str, records: Iterable[dict[str, Any]]) -> ArtifactRef:
        from botocore.exceptions import ClientError

        key = self._key(relative_path)
        existing = ""
        etag = None
        if self.exists(relative_path):
            response = self._client.get_object(Bucket=self.bucket, Key=key)
            existing = response["Body"].read().decode("utf-8")
            etag = response.get("ETag")
        lines = []
        for record in records:
            line = json.dumps(record, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
            lines.append(line)
        content = existing + "".join(line + "\n" for line in lines)
        try:
            if etag:
                self._client.put_object(
                    Bucket=self.bucket,
                    Key=key,
                    Body=content.encode("utf-8"),
                    IfMatch=etag,
                )
            else:
                self._client.put_object(
                    Bucket=self.bucket,
                    Key=key,
                    Body=content.encode("utf-8"),
                    IfNoneMatch="*",
                )
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code")
            if error_code in {"PreconditionFailed", "412"}:
                raise RuntimeError("S3_APPEND_CONFLICT") from exc
            raise
        return ArtifactRef(path=f"s3://{self.bucket}/{key}")

    def exists(self, relative_path: str) -> bool:
        from botocore.exceptions import ClientError

        key = self._key(relative_path)
        try:
            self._client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code")
            if error_code in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise

    def read_text(self, relative_path: str) -> str:
        key = self._key(relative_path)
        response = self._client.get_object(Bucket=self.bucket, Key=key)
        return response["Body"].read().decode("utf-8")

    def list_files(self, relative_dir: str) -> list[str]:
        prefix = self._key(relative_dir).rstrip("/") + "/"
        paginator = self._client.get_paginator("list_objects_v2")
        keys: list[str] = []
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for item in page.get("Contents", []):
                keys.append(f"s3://{self.bucket}/{item['Key']}")
        return keys


def build_object_store(root: str) -> ObjectStore:
    if root.startswith("s3://"):
        parsed = urlparse(root)
        bucket = parsed.netloc
        prefix = parsed.path.lstrip("/")
        if not bucket:
            raise ValueError("S3 object_store_root missing bucket")
        return S3ObjectStore(bucket=bucket, prefix=prefix)
    return LocalObjectStore(Path(root))
