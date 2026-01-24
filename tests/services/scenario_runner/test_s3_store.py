from __future__ import annotations

import os
import uuid

import pytest
from botocore.exceptions import ClientError

from fraud_detection.scenario_runner.storage import S3ObjectStore, build_object_store


def test_s3_append_conflict_raises() -> None:
    store = S3ObjectStore("bucket", "prefix")

    class FakeBody:
        def __init__(self, content: str) -> None:
            self._content = content

        def read(self) -> bytes:
            return self._content.encode("utf-8")

    class FakeClient:
        def __init__(self) -> None:
            self.put_calls: list[dict[str, str]] = []

        def head_object(self, Bucket: str, Key: str) -> dict:
            return {}

        def get_object(self, Bucket: str, Key: str) -> dict:
            return {"Body": FakeBody(""), "ETag": '"etag1"'}

        def put_object(self, **kwargs):
            self.put_calls.append(kwargs)
            raise ClientError({"Error": {"Code": "PreconditionFailed"}}, "PutObject")

    fake = FakeClient()
    store._client = fake  # type: ignore[attr-defined]

    with pytest.raises(RuntimeError, match="S3_APPEND_CONFLICT"):
        store.append_jsonl("run_record/test.jsonl", [{"a": 1}])

    assert fake.put_calls
    assert fake.put_calls[0].get("IfMatch") == '"etag1"'


def test_s3_integration_write_once_and_append() -> None:
    bucket = os.getenv("SR_TEST_S3_BUCKET")
    if not bucket:
        pytest.skip("SR_TEST_S3_BUCKET not set")
    prefix = os.getenv("SR_TEST_S3_PREFIX", "sr-test")
    unique = uuid.uuid4().hex
    root = f"s3://{bucket}/{prefix}/{unique}"
    store = build_object_store(root)

    key = f"immutable/{unique}.json"
    store.write_json_if_absent(key, {"hello": "world"})
    with pytest.raises(FileExistsError):
        store.write_json_if_absent(key, {"hello": "again"})

    record_key = f"record/{unique}.jsonl"
    store.append_jsonl(record_key, [{"id": 1}, {"id": 2}])
    content = store.read_text(record_key)
    assert "\"id\":1" in content
    assert "\"id\":2" in content
