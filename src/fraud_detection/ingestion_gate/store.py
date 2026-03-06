"""Object-store utilities for IG receipts/quarantine (local + S3-compatible)."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Protocol
from urllib.parse import urlparse


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class ArtifactRef:
    path: str
    digest: str | None = None


@dataclass(frozen=True)
class StoreHealthSnapshot:
    last_success_at_utc: str | None = None
    last_failure_at_utc: str | None = None
    last_failure_operation: str | None = None
    last_failure_error: str | None = None
    consecutive_failures: int = 0
    last_benign_conflict_at_utc: str | None = None
    last_benign_conflict_operation: str | None = None
    last_benign_conflict_error: str | None = None


class ObjectStore(Protocol):
    def write_json(self, relative_path: str, payload: dict[str, Any]) -> ArtifactRef:
        ...

    def write_json_if_absent(self, relative_path: str, payload: dict[str, Any]) -> ArtifactRef:
        ...

    def read_json(self, relative_path: str) -> dict[str, Any]:
        ...

    def write_text(self, relative_path: str, content: str) -> ArtifactRef:
        ...

    def append_jsonl(self, relative_path: str, records: Iterable[dict[str, Any]]) -> ArtifactRef:
        ...

    def exists(self, relative_path: str) -> bool:
        ...


class ObservedObjectStore:
    def __init__(self, inner: ObjectStore) -> None:
        self.inner = inner
        self._last_success_at_utc: str | None = None
        self._last_failure_at_utc: str | None = None
        self._last_failure_operation: str | None = None
        self._last_failure_error: str | None = None
        self._consecutive_failures = 0
        self._last_benign_conflict_at_utc: str | None = None
        self._last_benign_conflict_operation: str | None = None
        self._last_benign_conflict_error: str | None = None

    def write_json(self, relative_path: str, payload: dict[str, Any]) -> ArtifactRef:
        return self._observe("write_json", lambda: self.inner.write_json(relative_path, payload))

    def write_json_if_absent(self, relative_path: str, payload: dict[str, Any]) -> ArtifactRef:
        return self._observe("write_json_if_absent", lambda: self.inner.write_json_if_absent(relative_path, payload))

    def read_json(self, relative_path: str) -> dict[str, Any]:
        return self._observe("read_json", lambda: self.inner.read_json(relative_path))

    def write_text(self, relative_path: str, content: str) -> ArtifactRef:
        return self._observe("write_text", lambda: self.inner.write_text(relative_path, content))

    def append_jsonl(self, relative_path: str, records: Iterable[dict[str, Any]]) -> ArtifactRef:
        buffered = list(records)
        return self._observe("append_jsonl", lambda: self.inner.append_jsonl(relative_path, buffered))

    def exists(self, relative_path: str) -> bool:
        return self._observe("exists", lambda: self.inner.exists(relative_path))

    def health_snapshot(self) -> StoreHealthSnapshot:
        return StoreHealthSnapshot(
            last_success_at_utc=self._last_success_at_utc,
            last_failure_at_utc=self._last_failure_at_utc,
            last_failure_operation=self._last_failure_operation,
            last_failure_error=self._last_failure_error,
            consecutive_failures=self._consecutive_failures,
            last_benign_conflict_at_utc=self._last_benign_conflict_at_utc,
            last_benign_conflict_operation=self._last_benign_conflict_operation,
            last_benign_conflict_error=self._last_benign_conflict_error,
        )

    def _observe(self, operation: str, fn: Any) -> Any:
        try:
            value = fn()
        except FileExistsError as exc:
            if operation == "write_json_if_absent":
                self._record_benign_conflict(operation, exc)
                raise
            self._record_failure(operation, exc)
            raise
        except Exception as exc:
            self._record_failure(operation, exc)
            raise
        self._record_success()
        return value

    def _record_success(self) -> None:
        self._last_success_at_utc = datetime.now(tz=timezone.utc).isoformat()
        self._consecutive_failures = 0

    def _record_failure(self, operation: str, exc: Exception) -> None:
        self._last_failure_at_utc = datetime.now(tz=timezone.utc).isoformat()
        self._last_failure_operation = operation
        self._last_failure_error = f"{type(exc).__name__}:{exc}"
        self._consecutive_failures += 1

    def _record_benign_conflict(self, operation: str, exc: Exception) -> None:
        now = datetime.now(tz=timezone.utc).isoformat()
        self._last_success_at_utc = now
        self._last_benign_conflict_at_utc = now
        self._last_benign_conflict_operation = operation
        self._last_benign_conflict_error = f"{type(exc).__name__}:{exc}"
        self._consecutive_failures = 0

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)


class LocalObjectStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def _full_path(self, relative_path: str) -> Path:
        return self.root / relative_path

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
        return json.loads(self._read_text_with_retry(path))

    def write_text(self, relative_path: str, content: str) -> ArtifactRef:
        path = self._full_path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(content, encoding="utf-8")
        os.replace(tmp_path, path)
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

    def _read_text_with_retry(self, path: Path) -> str:
        last_err: Exception | None = None
        for _ in range(5):
            try:
                return path.read_text(encoding="utf-8")
            except (PermissionError, FileNotFoundError) as exc:
                last_err = exc
                time.sleep(0.05)
        if last_err:
            raise last_err
        return path.read_text(encoding="utf-8")


class S3ObjectStore:
    def __init__(
        self,
        bucket: str,
        prefix: str = "",
        endpoint_url: str | None = None,
        region_name: str | None = None,
        path_style: bool | None = None,
    ) -> None:
        import boto3
        from botocore.config import Config

        self.bucket = bucket
        self.prefix = prefix.strip("/")
        config = None
        if path_style:
            config = Config(s3={"addressing_style": "path"})
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            region_name=region_name,
            config=config,
        )

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

    def append_jsonl(self, relative_path: str, records: Iterable[dict[str, Any]]) -> ArtifactRef:
        from botocore.exceptions import ClientError

        key = self._key(relative_path)
        lines = []
        for record in records:
            line = json.dumps(record, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
            lines.append(line)
        append_block = "".join(line + "\n" for line in lines)
        max_attempts = max(1, _env_int("IG_OBJECT_STORE_APPEND_MAX_ATTEMPTS", 5))
        sleep_seconds = max(0.0, _env_int("IG_OBJECT_STORE_APPEND_BACKOFF_MS", 50) / 1000.0)
        last_conflict: ClientError | None = None
        for attempt in range(1, max_attempts + 1):
            existing = ""
            etag = None
            if self.exists(relative_path):
                response = self._client.get_object(Bucket=self.bucket, Key=key)
                existing = response["Body"].read().decode("utf-8")
                etag = response.get("ETag")
            content = existing + append_block
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
                return ArtifactRef(path=f"s3://{self.bucket}/{key}")
            except ClientError as exc:
                error_code = exc.response.get("Error", {}).get("Code")
                if error_code not in {"PreconditionFailed", "412"}:
                    raise
                last_conflict = exc
                if attempt >= max_attempts:
                    break
                time.sleep(sleep_seconds * attempt)
        if last_conflict is not None:
            raise RuntimeError("S3_APPEND_CONFLICT") from last_conflict
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


def build_object_store(
    root: str,
    s3_endpoint_url: str | None = None,
    s3_region: str | None = None,
    s3_path_style: bool | None = None,
) -> ObjectStore:
    if root.startswith("s3://"):
        parsed = urlparse(root)
        bucket = parsed.netloc
        prefix = parsed.path.lstrip("/")
        if not bucket:
            raise ValueError("S3 object_store_root missing bucket")
        endpoint = s3_endpoint_url or os.getenv("IG_S3_ENDPOINT_URL") or os.getenv("AWS_ENDPOINT_URL")
        region = s3_region or os.getenv("IG_S3_REGION") or os.getenv("AWS_DEFAULT_REGION")
        path_style_env = os.getenv("IG_S3_PATH_STYLE")
        path_style = s3_path_style if s3_path_style is not None else (path_style_env == "true")
        return S3ObjectStore(
            bucket=bucket,
            prefix=prefix,
            endpoint_url=endpoint,
            region_name=region,
            path_style=path_style,
        )
    return LocalObjectStore(Path(root))


def observe_object_store(store: ObjectStore) -> ObservedObjectStore:
    if isinstance(store, ObservedObjectStore):
        return store
    return ObservedObjectStore(store)


def unwrap_object_store(store: ObjectStore) -> ObjectStore:
    if isinstance(store, ObservedObjectStore):
        return store.inner
    return store
