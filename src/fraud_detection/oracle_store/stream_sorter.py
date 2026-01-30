"""Oracle Store stream sorter (per-output ts_utc order, bucket partitions, S3-native)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from fnmatch import fnmatch
import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, TYPE_CHECKING
from urllib.parse import urlparse

import yaml

from fraud_detection.ingestion_gate.catalogue import OutputCatalogue
from fraud_detection.scenario_runner.storage import LocalObjectStore, S3ObjectStore

from .config import OracleProfile
from .engine_reader import join_engine_path, read_run_receipt

logger = logging.getLogger(__name__)

if TYPE_CHECKING:  # pragma: no cover - typing only
    import duckdb


@dataclass(frozen=True)
class StreamSortStats:
    row_count: int
    hash_sum: str
    hash_sum2: str
    min_ts_utc: str | None
    max_ts_utc: str | None


@dataclass(frozen=True)
class StreamSortReceipt:
    stream_view_id: str
    engine_run_root: str
    stream_view_root: str
    output_id: str
    output_ids: list[str]
    sort_keys: list[str]
    partition_granularity: str
    source_locator_digest: str
    raw_stats: StreamSortStats
    sorted_stats: StreamSortStats
    created_utc: str
    status: str = "OK"


class StreamSortError(RuntimeError):
    pass


def compute_stream_view_id(
    *,
    engine_run_root: str,
    scenario_id: str,
    output_id: str,
    sort_keys: list[str],
    partition_granularity: str,
) -> str:
    payload = {
        "engine_run_root": engine_run_root,
        "scenario_id": scenario_id,
        "output_id": output_id,
        "sort_keys": list(sort_keys),
        "partition_granularity": partition_granularity,
    }
    data = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def load_output_ids(ref_path: str) -> list[str]:
    payload = yaml.safe_load(Path(ref_path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        items = payload.get("output_ids") or []
    else:
        items = payload or []
    return [str(item) for item in items if str(item).strip()]


def build_stream_view(
    *,
    profile: OracleProfile,
    engine_run_root: str,
    scenario_id: str,
    output_id: str,
    stream_view_root: str,
    stream_view_id: str,
    partition_granularity: str = "bucket",
) -> StreamSortReceipt:
    output_id = str(output_id)
    stream_root = stream_view_root.rstrip("/")
    receipt_path = f"{stream_root}/_stream_sort_receipt.json"
    manifest_path = f"{stream_root}/_stream_view_manifest.json"

    store = _build_store(stream_view_root, profile)
    logger.info(
        "Oracle stream view start root=%s engine_root=%s scenario_id=%s output_id=%s",
        stream_root,
        engine_run_root,
        scenario_id,
        output_id,
    )
    source_locator_digest, locators = _source_locator_digest(
        profile, engine_run_root, scenario_id, [output_id]
    )
    receipt_rel = _relative_path(stream_view_root, receipt_path)
    manifest_rel = _relative_path(stream_view_root, manifest_path)
    if store.exists(manifest_rel) and not store.exists(receipt_rel):
        raise StreamSortError("STREAM_RECEIPT_MISSING")
    if store.exists(receipt_rel):
        existing = store.read_json(receipt_rel)
        if _receipt_matches(existing, source_locator_digest, output_id, stream_view_id, partition_granularity):
            logger.info("Oracle stream view already built; receipt valid. Skipping.")
            return _receipt_from_payload(existing)
        raise StreamSortError("STREAM_RECEIPT_MISMATCH")
    existing_parquet = _list_existing_parquet(store)
    if existing_parquet:
        logger.warning(
            "Oracle stream view found existing parquet without receipt root=%s files=%s",
            stream_root,
            len(existing_parquet),
        )
        raise StreamSortError("STREAM_VIEW_PARTIAL_EXISTS")

    con = _duckdb_connect(profile)
    try:
        logger.info("Oracle stream view computing source stats")
        stats_start = time.monotonic()
        raw_query = _build_raw_query_for_output(con, locators[0])
        raw_stats = _compute_stats(con, raw_query)
        stats_seconds = time.monotonic() - stats_start
        progress_time = os.getenv("STREAM_SORT_PROGRESS_SECONDS")
        eta_seconds = None
        if not progress_time:
            multiplier = float(os.getenv("STREAM_SORT_SORT_MULTIPLIER", "2.0"))
            eta_seconds = max(1.0, stats_seconds * multiplier)
            eta_at = datetime.now(tz=timezone.utc) + timedelta(seconds=eta_seconds)
            logger.info(
                "Oracle stream view ETA sort_completion~%ss (%s UTC) scan_seconds=%.1f multiplier=%.2f rows=%s",
                f"{eta_seconds:.0f}",
                eta_at.isoformat(),
                stats_seconds,
                multiplier,
                raw_stats.row_count,
            )

        out_path = stream_root
        logger.info("Oracle stream view sorting + writing partitions (single pass)")
        sort_start = time.monotonic()
        _write_sorted(con, raw_query, out_path, partition_granularity)
        sort_seconds = time.monotonic() - sort_start
        logger.info(
            "Oracle stream view sort completed seconds=%.1f%s",
            sort_seconds,
            f\" (eta_seconds={eta_seconds:.0f})\" if eta_seconds is not None else "",
        )

        logger.info("Oracle stream view computing sorted stats")
        sorted_query = _build_stats_query_for_parquet(con, f\"{out_path}/**/*.parquet\")
        sorted_stats = _compute_stats(con, sorted_query)
    finally:
        try:
            con.close()
        except Exception:
            pass

    if not _stats_match(raw_stats, sorted_stats):
        raise StreamSortError("STREAM_SORT_VALIDATION_FAILED")

    receipt = StreamSortReceipt(
        stream_view_id=stream_view_id,
        engine_run_root=engine_run_root,
        stream_view_root=stream_view_root,
        output_id=output_id,
        output_ids=[output_id],
        sort_keys=["ts_utc", "filename", "file_row_number"],
        partition_granularity=partition_granularity,
        source_locator_digest=source_locator_digest,
        raw_stats=raw_stats,
        sorted_stats=sorted_stats,
        created_utc=datetime.now(tz=timezone.utc).isoformat(),
    )
    logger.info("Oracle stream view writing receipt + manifest")
    store.write_json(receipt_rel, _receipt_to_payload(receipt))
    store.write_json(
        manifest_rel,
        _manifest_payload(
            profile=profile,
            engine_run_root=engine_run_root,
            stream_view_root=stream_view_root,
            stream_view_id=stream_view_id,
            output_ids=[output_id],
            scenario_id=scenario_id,
            receipt=receipt,
        ),
    )
    logger.info("Oracle stream view built root=%s stream_view_id=%s", stream_view_root, stream_view_id)
    return receipt


def _manifest_payload(
    *,
    profile: OracleProfile,
    engine_run_root: str,
    stream_view_root: str,
    stream_view_id: str,
    output_ids: list[str],
    scenario_id: str,
    receipt: StreamSortReceipt,
) -> dict[str, Any]:
    run_receipt = read_run_receipt(engine_run_root, profile=profile)
    return {
        "stream_view_id": stream_view_id,
        "engine_run_root": engine_run_root,
        "stream_view_root": stream_view_root,
        "engine_run_id": run_receipt.get("run_id"),
        "scenario_id": scenario_id,
        "output_id": receipt.output_id,
        "world_key": {
            "manifest_fingerprint": run_receipt.get("manifest_fingerprint"),
            "parameter_hash": run_receipt.get("parameter_hash"),
            "seed": run_receipt.get("seed"),
            "scenario_id": scenario_id,
        },
        "output_ids": output_ids,
        "sort_keys": receipt.sort_keys,
        "partition_granularity": receipt.partition_granularity,
        "created_utc": receipt.created_utc,
    }


def _build_store(stream_view_root: str, profile: OracleProfile):
    if stream_view_root.startswith("s3://"):
        parsed = urlparse(stream_view_root)
        return S3ObjectStore(
            parsed.netloc,
            prefix=parsed.path.lstrip("/"),
            endpoint_url=profile.wiring.object_store_endpoint,
            region_name=profile.wiring.object_store_region,
            path_style=profile.wiring.object_store_path_style,
        )
    return LocalObjectStore(Path(stream_view_root))


def _receipt_matches(
    payload: dict[str, Any],
    source_locator_digest: str,
    output_id: str,
    stream_view_id: str,
    partition_granularity: str,
) -> bool:
    return (
        payload.get("status") == "OK"
        and payload.get("source_locator_digest") == source_locator_digest
        and payload.get("output_id") == output_id
        and payload.get("stream_view_id") == stream_view_id
        and payload.get("partition_granularity") == partition_granularity
    )


def _receipt_to_payload(receipt: StreamSortReceipt) -> dict[str, Any]:
    return {
        "stream_view_id": receipt.stream_view_id,
        "engine_run_root": receipt.engine_run_root,
        "stream_view_root": receipt.stream_view_root,
        "output_id": receipt.output_id,
        "output_ids": receipt.output_ids,
        "sort_keys": receipt.sort_keys,
        "partition_granularity": receipt.partition_granularity,
        "source_locator_digest": receipt.source_locator_digest,
        "raw_stats": _stats_payload(receipt.raw_stats),
        "sorted_stats": _stats_payload(receipt.sorted_stats),
        "created_utc": receipt.created_utc,
        "status": receipt.status,
    }


def _receipt_from_payload(payload: dict[str, Any]) -> StreamSortReceipt:
    return StreamSortReceipt(
        stream_view_id=payload["stream_view_id"],
        engine_run_root=payload["engine_run_root"],
        stream_view_root=payload["stream_view_root"],
        output_id=str(payload.get("output_id") or ""),
        output_ids=list(payload.get("output_ids") or []),
        sort_keys=list(payload.get("sort_keys") or []),
        partition_granularity=payload.get("partition_granularity", "bucket"),
        source_locator_digest=payload.get("source_locator_digest", ""),
        raw_stats=_stats_from_payload(payload.get("raw_stats") or {}),
        sorted_stats=_stats_from_payload(payload.get("sorted_stats") or {}),
        created_utc=payload.get("created_utc", ""),
        status=payload.get("status", "OK"),
    )


def _stats_payload(stats: StreamSortStats) -> dict[str, Any]:
    return {
        "row_count": stats.row_count,
        "hash_sum": stats.hash_sum,
        "hash_sum2": stats.hash_sum2,
        "min_ts_utc": stats.min_ts_utc,
        "max_ts_utc": stats.max_ts_utc,
    }


def _stats_from_payload(payload: dict[str, Any]) -> StreamSortStats:
    return StreamSortStats(
        row_count=int(payload.get("row_count", 0)),
        hash_sum=str(payload.get("hash_sum", "")),
        hash_sum2=str(payload.get("hash_sum2", "")),
        min_ts_utc=payload.get("min_ts_utc"),
        max_ts_utc=payload.get("max_ts_utc"),
    )


def _stats_match(raw: StreamSortStats, sorted_stats: StreamSortStats) -> bool:
    return (
        raw.row_count == sorted_stats.row_count
        and raw.hash_sum == sorted_stats.hash_sum
        and raw.hash_sum2 == sorted_stats.hash_sum2
        and raw.min_ts_utc == sorted_stats.min_ts_utc
        and raw.max_ts_utc == sorted_stats.max_ts_utc
    )


def _source_locator_digest(
    profile: OracleProfile,
    engine_run_root: str,
    scenario_id: str,
    output_ids: list[str],
) -> tuple[str, list[dict[str, Any]]]:
    run_receipt = read_run_receipt(engine_run_root, profile)
    tokens = {
        "manifest_fingerprint": run_receipt.get("manifest_fingerprint"),
        "parameter_hash": run_receipt.get("parameter_hash"),
        "seed": run_receipt.get("seed"),
        "scenario_id": scenario_id,
    }
    catalogue = OutputCatalogue(Path(profile.wiring.engine_catalogue_path))
    locators: list[dict[str, Any]] = []
    all_paths: list[str] = []
    for output_id in output_ids:
        entry = catalogue.get(output_id)
        if not entry.path_template:
            raise StreamSortError(f"OUTPUT_TEMPLATE_MISSING:{output_id}")
        try:
            relative = entry.path_template.strip().format(**tokens)
        except KeyError as exc:
            raise StreamSortError(f"TEMPLATE_TOKEN_MISSING:{output_id}:{exc}") from exc
        locator_path = join_engine_path(engine_run_root, relative)
        paths = _expand_paths(locator_path, profile)
        if not paths:
            raise StreamSortError(f"OUTPUT_PATHS_EMPTY:{output_id}")
        locators.append(
            {"output_id": output_id, "path": locator_path, "paths": paths}
        )
        all_paths.extend(paths)
    digest = hashlib.sha256("\n".join(sorted(all_paths)).encode("utf-8")).hexdigest()
    return digest, locators


def _expand_paths(path: str, profile: OracleProfile) -> list[str]:
    if "*" not in path:
        return [path]
    if path.startswith("s3://"):
        parsed = urlparse(path)
        bucket = parsed.netloc
        key = parsed.path.lstrip("/")
        prefix = key.split("*", 1)[0]
        client = _s3_client(profile)
        paginator = client.get_paginator("list_objects_v2")
        results: list[str] = []
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for item in page.get("Contents", []):
                candidate = item["Key"]
                if fnmatch(candidate, key):
                    results.append(f"s3://{bucket}/{candidate}")
        return results
    local = Path(path)
    return [str(item) for item in local.parent.glob(local.name)]


def _duckdb_connect(profile: OracleProfile) -> "duckdb.DuckDBPyConnection":
    import duckdb

    con = duckdb.connect()
    con.execute("INSTALL httpfs")
    con.execute("LOAD httpfs")
    progress_time = os.getenv("STREAM_SORT_PROGRESS_SECONDS")
    if progress_time:
        con.execute("PRAGMA enable_progress_bar")
        con.execute(f"PRAGMA progress_bar_time={float(progress_time)}")
    memory_limit = os.getenv("STREAM_SORT_MEMORY_LIMIT")
    if memory_limit:
        con.execute(f"PRAGMA memory_limit='{memory_limit}'")
    temp_dir = os.getenv("STREAM_SORT_TEMP_DIR")
    if temp_dir:
        con.execute(f"PRAGMA temp_directory='{temp_dir}'")
    max_temp = os.getenv("STREAM_SORT_MAX_TEMP_SIZE")
    if max_temp:
        con.execute(f"PRAGMA max_temp_directory_size='{max_temp}'")
    if profile.wiring.object_store_endpoint:
        endpoint = profile.wiring.object_store_endpoint
        if "://" in endpoint:
            parsed = urlparse(endpoint)
            endpoint_host = parsed.netloc or endpoint.split("://", 1)[1]
            con.execute(f"SET s3_endpoint='{endpoint_host}'")
            if parsed.scheme == "http":
                con.execute("SET s3_use_ssl=false")
        else:
            con.execute(f"SET s3_endpoint='{endpoint}'")
    if profile.wiring.object_store_region:
        con.execute(f"SET s3_region='{profile.wiring.object_store_region}'")
    access_key = os.getenv("AWS_ACCESS_KEY_ID") or ""
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY") or ""
    if access_key and secret_key:
        con.execute(f"SET s3_access_key_id='{access_key}'")
        con.execute(f"SET s3_secret_access_key='{secret_key}'")
    session_token = os.getenv("AWS_SESSION_TOKEN") or ""
    if session_token:
        con.execute(f"SET s3_session_token='{session_token}'")
    if profile.wiring.object_store_path_style:
        con.execute("SET s3_url_style='path'")
    threads = os.getenv("STREAM_SORT_THREADS")
    if threads:
        con.execute(f"PRAGMA threads={int(threads)}")
    preserve_order = os.getenv("STREAM_SORT_PRESERVE_ORDER", "").lower()
    if preserve_order in {"0", "false", "no", ""}:
        con.execute("PRAGMA preserve_insertion_order=false")
    elif preserve_order in {"1", "true", "yes"}:
        con.execute("PRAGMA preserve_insertion_order=true")
    if logger.isEnabledFor(logging.INFO):
        try:
            current_threads = con.execute("PRAGMA threads").fetchone()[0]
        except Exception:
            current_threads = threads or "default"
        logger.info(
            "Oracle stream view duckdb_config threads=%s progress_bar=%s memory_limit=%s temp_dir=%s max_temp=%s preserve_order=%s",
            current_threads,
            "on" if progress_time else "off",
            os.getenv("STREAM_SORT_MEMORY_LIMIT") or "default",
            os.getenv("STREAM_SORT_TEMP_DIR") or "default",
            os.getenv("STREAM_SORT_MAX_TEMP_SIZE") or "default",
            os.getenv("STREAM_SORT_PRESERVE_ORDER") or "false",
        )
    return con


def _build_raw_query_for_output(con: "duckdb.DuckDBPyConnection", item: dict[str, Any]) -> str:
    output_id = item["output_id"]
    locator = item["path"]
    columns = _duckdb_columns(con, locator, include_file_meta=True)
    columns = [col for col in columns if col not in {"filename", "file_row_number"}]
    if "ts_utc" not in columns:
        raise StreamSortError(f"MISSING_TS_UTC:{output_id}")
    if "bucket_index" not in columns:
        raise StreamSortError(f"MISSING_BUCKET_INDEX:{output_id}")
    select_cols = ", ".join([f'"{col}"' for col in columns])
    pack_expr = ", ".join([f'"{col}" := "{col}"' for col in columns])
    return (
        "SELECT "
        f"{select_cols}, "
        "filename, "
        "file_row_number, "
        "hash(to_json(struct_pack(" + pack_expr + "))) AS payload_hash "
        f"FROM read_parquet('{locator}', filename=true, file_row_number=true)"
    )


def _duckdb_columns(
    con: "duckdb.DuckDBPyConnection",
    locator: str,
    *,
    include_file_meta: bool = False,
) -> list[str]:
    args = "filename=true, file_row_number=true" if include_file_meta else ""
    rows = con.execute(
        f"DESCRIBE SELECT * FROM read_parquet('{locator}'{', ' + args if args else ''})"
    ).fetchall()
    return [row[0] for row in rows]


def _build_stats_query_for_parquet(con: "duckdb.DuckDBPyConnection", locator: str) -> str:
    columns = _duckdb_columns(con, locator)
    if "ts_utc" not in columns:
        raise StreamSortError("MISSING_TS_UTC")
    if "bucket_index" not in columns:
        raise StreamSortError("MISSING_BUCKET_INDEX")
    select_cols = ", ".join([f'"{col}"' for col in columns])
    pack_expr = ", ".join([f'"{col}" := "{col}"' for col in columns])
    return (
        "SELECT "
        f"{select_cols}, "
        "hash(to_json(struct_pack(" + pack_expr + "))) AS payload_hash "
        f"FROM read_parquet('{locator}')"
    )


def _compute_stats(con: "duckdb.DuckDBPyConnection", query: str) -> StreamSortStats:
    stats_sql = f"""
        SELECT
            count(*)::BIGINT AS row_count,
            min(CAST(ts_utc AS TIMESTAMP)) AS min_ts,
            max(CAST(ts_utc AS TIMESTAMP)) AS max_ts,
            sum(CAST(payload_hash AS DOUBLE)) AS hash_sum,
            sum(CAST(payload_hash % 1000000007 AS BIGINT))::BIGINT AS hash_sum2
        FROM ({query})
    """
    row = con.execute(stats_sql).fetchone()
    if not row:
        raise StreamSortError("STREAM_SORT_STATS_EMPTY")
    return StreamSortStats(
        row_count=int(row[0]),
        hash_sum=str(row[3]),
        hash_sum2=str(row[4]),
        min_ts_utc=row[1].isoformat() if row[1] else None,
        max_ts_utc=row[2].isoformat() if row[2] else None,
    )


def _sort_expr(raw_query: str) -> str:
    return f"""
        SELECT
            *
        FROM ({raw_query})
        ORDER BY bucket_index, CAST(ts_utc AS TIMESTAMP), filename, file_row_number
    """


def _write_sorted(
    con: "duckdb.DuckDBPyConnection",
    raw_query: str,
    output_root: str,
    partition_granularity: str,
) -> None:
    if partition_granularity != "bucket":
        raise StreamSortError("PARTITION_GRANULARITY_UNSUPPORTED")
    sort_expr = _sort_expr(raw_query)
    con.execute(
        "COPY ("
        f"SELECT * EXCLUDE(payload_hash, filename, file_row_number) FROM ({sort_expr}) "
        f") TO '{output_root}' (FORMAT PARQUET, PARTITION_BY (bucket_index))"
    )


def _list_bucket_indices(con: "duckdb.DuckDBPyConnection", locator: str) -> list[int]:
    rows = con.execute(
        f"SELECT DISTINCT bucket_index FROM read_parquet('{locator}', filename=true, file_row_number=true) "
        "ORDER BY bucket_index"
    ).fetchall()
    return [int(row[0]) for row in rows if row and row[0] is not None]


def _relative_path(root: str, absolute: str) -> str:
    if absolute.startswith("s3://"):
        parsed = urlparse(absolute)
        key = parsed.path.lstrip("/")
        root_parsed = urlparse(root)
        root_prefix = root_parsed.path.lstrip("/").rstrip("/")
        if root_prefix and key.startswith(root_prefix + "/"):
            return key[len(root_prefix) + 1 :]
        return key
    if absolute.startswith(root):
        return absolute[len(root) + 1 :]
    return absolute


def _list_existing_parquet(store: LocalObjectStore | S3ObjectStore) -> list[str]:
    return [path for path in store.list_files("") if path.endswith(".parquet")]


def _s3_client(profile: OracleProfile):
    import boto3
    from botocore.config import Config

    config = None
    if profile.wiring.object_store_path_style:
        config = Config(s3={"addressing_style": "path"})
    return boto3.client(
        "s3",
        endpoint_url=profile.wiring.object_store_endpoint,
        region_name=profile.wiring.object_store_region,
        config=config,
    )
