"""Engine pull ingestion: frame engine outputs into canonical envelopes."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import pyarrow.parquet as pq

from .catalogue import OutputCatalogue
from .errors import IngestionError
from .ids import derive_engine_event_id
from .retry import with_retry

logger = logging.getLogger(__name__)

@dataclass
class EnginePuller:
    run_facts_view_path: Path | None
    catalogue: OutputCatalogue
    run_facts_payload: dict[str, Any] | None = None
    retry_attempts: int = 3
    retry_backoff_seconds: float = 0.2
    retry_max_seconds: float = 2.0
    _facts: dict[str, Any] | None = None

    def iter_events(self, output_ids: list[str] | None = None) -> Iterable[dict[str, Any]]:
        facts = self._load_facts()
        pins = facts.get("pins", {})
        output_roles = facts.get("output_roles", {})
        locators = facts.get("locators", [])
        locator_by_output = {loc["output_id"]: loc["path"] for loc in locators}
        for output_id, role in output_roles.items():
            if role != "business_traffic":
                continue
            if output_ids and output_id not in output_ids:
                continue
            if output_id not in locator_by_output:
                continue
            logger.info("IG engine_pull output_id=%s path=%s", output_id, locator_by_output[output_id])
            yield from self._events_from_output(output_id, locator_by_output[output_id], pins)

    def list_outputs(self) -> list[str]:
        facts = self._load_facts()
        output_roles = facts.get("output_roles", {})
        locators = facts.get("locators", [])
        locator_by_output = {loc["output_id"]: loc["path"] for loc in locators}
        outputs: list[str] = []
        for output_id, role in output_roles.items():
            if role != "business_traffic":
                continue
            if output_id not in locator_by_output:
                continue
            outputs.append(output_id)
        return outputs

    def list_locator_paths(self, output_id: str) -> list[str]:
        locator = self._locator_for_output(output_id)
        if not locator:
            return []
        return self._expand_paths(locator)

    def iter_events_for_paths(self, output_id: str, paths: list[str]) -> Iterable[dict[str, Any]]:
        facts = self._load_facts()
        pins = facts.get("pins", {})
        locator = self._locator_for_output(output_id)
        if not locator:
            return
        yield from self._events_from_output(output_id, locator, pins, paths_override=paths)

    def _load_facts(self) -> dict[str, Any]:
        if self._facts is None:
            if self.run_facts_payload is not None:
                self._facts = self.run_facts_payload
            elif self.run_facts_view_path is not None:
                self._facts = json.loads(self.run_facts_view_path.read_text(encoding="utf-8"))
            else:
                raise IngestionError("RUN_FACTS_MISSING")
        return self._facts

    def _events_from_output(
        self,
        output_id: str,
        path: str,
        pins: dict[str, Any],
        paths_override: list[str] | None = None,
    ) -> Iterable[dict[str, Any]]:
        entry = self.catalogue.get(output_id)
        files = paths_override or self._expand_paths(path)
        for file_path in files:
            for row in self._read_rows(file_path):
                event_id = derive_engine_event_id(output_id, entry.primary_key, row, pins)
                ts_utc = row.get("ts_utc")
                if ts_utc is None:
                    raise IngestionError("MISSING_EVENT_TIME")
                envelope = {
                    "event_id": event_id,
                    "event_type": output_id,
                    "ts_utc": ts_utc,
                    "manifest_fingerprint": pins.get("manifest_fingerprint"),
                    "parameter_hash": pins.get("parameter_hash"),
                    "seed": pins.get("seed"),
                    "scenario_id": pins.get("scenario_id"),
                    "run_id": pins.get("run_id"),
                    "producer": "engine",
                    "payload": row,
                }
                yield envelope

    def _locator_for_output(self, output_id: str) -> str | None:
        facts = self._load_facts()
        locators = facts.get("locators", [])
        for locator in locators:
            if locator.get("output_id") == output_id:
                return locator.get("path")
        return None

    def _expand_paths(self, path: str) -> list[str]:
        if path.startswith("s3://"):
            return _expand_s3_paths(
                path,
                attempts=self.retry_attempts,
                base_delay_seconds=self.retry_backoff_seconds,
                max_delay_seconds=self.retry_max_seconds,
            )
        local = Path(path)
        if "*" in local.name:
            return [str(item) for item in local.parent.glob(local.name)]
        return [path]

    def _read_rows(self, path: str) -> Iterable[dict[str, Any]]:
        if path.startswith("s3://"):
            yield from _read_rows_s3(
                path,
                attempts=self.retry_attempts,
                base_delay_seconds=self.retry_backoff_seconds,
                max_delay_seconds=self.retry_max_seconds,
            )
            return
        local = Path(path)
        if local.suffix == ".parquet":
            table = pq.read_table(local)
            for row in table.to_pylist():
                yield row
        elif local.suffix in (".jsonl", ".json"):
            if local.suffix == ".json":
                data = json.loads(local.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    for row in data:
                        yield row
                elif isinstance(data, dict):
                    yield data
            else:
                with local.open("r", encoding="utf-8") as handle:
                    for line in handle:
                        if line.strip():
                            yield json.loads(line)
        else:
            raise ValueError("UNSUPPORTED_OUTPUT_FORMAT")


def _expand_s3_paths(
    path: str,
    *,
    attempts: int,
    base_delay_seconds: float,
    max_delay_seconds: float,
) -> list[str]:
    from fnmatch import fnmatch
    from urllib.parse import urlparse

    parsed = urlparse(path)
    bucket = parsed.netloc
    key = parsed.path.lstrip("/")
    if "*" not in key:
        return [path]
    prefix = key.split("*", 1)[0]
    client = _s3_client()
    paginator = client.get_paginator("list_objects_v2")
    results: list[str] = []
    pages = with_retry(
        lambda: list(paginator.paginate(Bucket=bucket, Prefix=prefix)),
        attempts=attempts,
        base_delay_seconds=base_delay_seconds,
        max_delay_seconds=max_delay_seconds,
    )
    for page in pages:
        for item in page.get("Contents", []):
            candidate = item["Key"]
            if fnmatch(candidate, key):
                results.append(f"s3://{bucket}/{candidate}")
    return results


def _read_rows_s3(
    path: str,
    *,
    attempts: int,
    base_delay_seconds: float,
    max_delay_seconds: float,
) -> Iterable[dict[str, Any]]:
    from urllib.parse import urlparse

    import pyarrow as pa

    parsed = urlparse(path)
    bucket = parsed.netloc
    key = parsed.path.lstrip("/")
    client = _s3_client()
    response = with_retry(
        lambda: client.get_object(Bucket=bucket, Key=key),
        attempts=attempts,
        base_delay_seconds=base_delay_seconds,
        max_delay_seconds=max_delay_seconds,
    )
    data = response["Body"].read()
    if key.endswith(".parquet"):
        table = pq.read_table(pa.BufferReader(data))
        for row in table.to_pylist():
            yield row
        return
    text = data.decode("utf-8")
    if key.endswith(".json"):
        payload = json.loads(text)
        if isinstance(payload, list):
            for row in payload:
                yield row
        elif isinstance(payload, dict):
            yield payload
        return
    if key.endswith(".jsonl"):
        for line in text.splitlines():
            if line.strip():
                yield json.loads(line)
        return
    raise ValueError("UNSUPPORTED_OUTPUT_FORMAT")


def _s3_client():
    import os

    import boto3
    from botocore.config import Config

    endpoint = os.getenv("IG_S3_ENDPOINT_URL") or os.getenv("AWS_ENDPOINT_URL")
    region = os.getenv("IG_S3_REGION") or os.getenv("AWS_DEFAULT_REGION")
    path_style_env = os.getenv("IG_S3_PATH_STYLE")
    config = None
    if path_style_env == "true":
        config = Config(s3={"addressing_style": "path"})
    return boto3.client("s3", region_name=region, endpoint_url=endpoint, config=config)
