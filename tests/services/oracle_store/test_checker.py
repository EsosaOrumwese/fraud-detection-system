from __future__ import annotations

from fraud_detection.oracle_store import checker


def test_resolve_oracle_path_relative() -> None:
    resolved = checker._resolve_oracle_path(
        "data/layer2/5B/arrival_events/part-000.parquet",
        "runs/local_full_run-5/c25a",
    )
    assert resolved.replace("\\", "/").endswith(
        "runs/local_full_run-5/c25a/data/layer2/5B/arrival_events/part-000.parquet"
    )


def test_pack_root_from_locator_alias() -> None:
    root = "runs/local_full_run-5/c25a"
    path = f"{root}/data/layer2/5B/arrival_events/seed=42/part-000.parquet"
    pack_root = checker._pack_root_from_locator(path, root)
    assert pack_root.replace("\\", "/").endswith("runs/local_full_run-5/c25a")


def test_s3_path_exists_head(monkeypatch) -> None:
    class StubClient:
        def head_object(self, Bucket: str, Key: str) -> None:  # noqa: N802
            if Key != "exists.json":
                raise Exception("NotFound")

    monkeypatch.setattr(checker, "_s3_client", lambda *args, **kwargs: StubClient())
    assert checker._path_exists("s3://bucket/exists.json", endpoint=None, region=None, path_style=None) is True
    assert checker._path_exists("s3://bucket/missing.json", endpoint=None, region=None, path_style=None) is False


def test_s3_path_exists_glob(monkeypatch) -> None:
    class StubPaginator:
        def paginate(self, Bucket: str, Prefix: str):  # noqa: N802
            return [{"Contents": [{"Key": "data/part-000.parquet"}]}]

    class StubClient:
        def get_paginator(self, name: str):  # noqa: D401
            return StubPaginator()

    monkeypatch.setattr(checker, "_s3_client", lambda *args, **kwargs: StubClient())
    assert (
        checker._path_exists(
            "s3://bucket/data/part-*.parquet", endpoint=None, region=None, path_style=None
        )
        is True
    )
