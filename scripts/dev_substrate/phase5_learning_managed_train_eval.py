#!/usr/bin/env python3
"""Run rebuilt Phase 5.C/D on the admitted Phase 5.B basis."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import statistics
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3
import pandas as pd
import pyarrow.dataset as ds
import pyarrow.fs as pafs
import yaml
from sagemaker import image_uris

from fraud_detection.learning_registry.contracts import (
    DatasetManifestContract,
    EvalReportContract,
    RegistryLifecycleEventContract,
)
from fraud_detection.learning_registry.worker import (
    LearningRegistryWorker,
    load_worker_config as load_mpr_worker_config,
)
from fraud_detection.model_factory.contracts import MfTrainBuildRequest, TargetScope
from fraud_detection.model_factory.phase3 import MfTrainPlanResolver, MfTrainPlanResolverConfig
from fraud_detection.model_factory.phase4 import MfTrainEvalReceipt
from fraud_detection.model_factory.phase5 import MfGatePolicyConfig, MfGatePolicyEvaluator
from fraud_detection.model_factory.phase6 import MfBundlePublisher, MfBundlePublisherConfig
from fraud_detection.offline_feature_plane.ids import dataset_fingerprint, deterministic_dataset_manifest_id


REGISTRY_PATH = Path("docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md")


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def parse_registry(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line.startswith("* `") or "`" not in line[3:]:
            continue
        body = line[3:].split("`", 1)[0]
        if "=" not in body:
            continue
        key, value = body.split("=", 1)
        out[key.strip()] = value.strip().strip('"')
    return out


def parse_s3_uri(uri: str) -> tuple[str, str]:
    value = str(uri or "").strip()
    if not value.startswith("s3://"):
        raise ValueError(f"invalid_s3_uri:{value}")
    bucket, _, key = value[5:].partition("/")
    if not bucket or not key:
        raise ValueError(f"invalid_s3_uri:{value}")
    return bucket, key


def s3_read_json(s3: Any, uri: str) -> dict[str, Any]:
    bucket, key = parse_s3_uri(uri)
    payload = json.loads(s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("json_not_object")
    return payload


def s3_read_text(s3: Any, uri: str) -> str:
    bucket, key = parse_s3_uri(uri)
    return s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8")


def s3_write_bytes(s3: Any, uri: str, body: bytes, content_type: str) -> None:
    bucket, key = parse_s3_uri(uri)
    s3.put_object(Bucket=bucket, Key=key, Body=body, ContentType=content_type)


def s3_write_json(s3: Any, uri: str, payload: dict[str, Any]) -> None:
    s3_write_bytes(s3, uri, json.dumps(payload, indent=2, ensure_ascii=True).encode("utf-8"), "application/json")


def read_ssm(ssm: Any, name: str, *, decrypt: bool) -> str:
    return str(ssm.get_parameter(Name=name, WithDecryption=decrypt)["Parameter"]["Value"]).strip()


def dbx_request_json(
    base_url: str,
    token: str,
    method: str,
    path: str,
    *,
    query: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    qs = "?" + urllib.parse.urlencode(query, doseq=True) if query else ""
    data = None if payload is None else json.dumps(payload, ensure_ascii=True).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}{qs}",
        method=method,
        data=data,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        raw = response.read().decode("utf-8")
    if not raw:
        return {}
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("json_not_object")
    return parsed


def dbx_find_experiment_id(base_url: str, token: str, experiment_path: str) -> str:
    quoted = urllib.parse.quote(experiment_path, safe="")
    try:
        payload = dbx_request_json(base_url, token, "GET", f"/api/2.0/mlflow/experiments/get-by-name?experiment_name={quoted}")
        experiment = payload.get("experiment") or {}
        experiment_id = str(experiment.get("experiment_id") or "").strip()
        if experiment_id:
            return experiment_id
    except Exception:
        pass
    page = ""
    while True:
        body: dict[str, Any] = {"max_results": 200}
        if page:
            body["page_token"] = page
        payload = dbx_request_json(base_url, token, "POST", "/api/2.0/mlflow/experiments/search", payload=body)
        for row in payload.get("experiments", []) or []:
            if str((row or {}).get("name") or "").strip() == experiment_path:
                experiment_id = str((row or {}).get("experiment_id") or "").strip()
                if experiment_id:
                    return experiment_id
        page = str(payload.get("next_page_token") or "").strip()
        if not page:
            break
    created = dbx_request_json(base_url, token, "POST", "/api/2.0/mlflow/experiments/create", payload={"name": experiment_path})
    experiment_id = str(created.get("experiment_id") or "").strip()
    if not experiment_id:
        raise RuntimeError("phase5c_mlflow_experiment_unresolved")
    return experiment_id


def dbx_create_run(base_url: str, token: str, experiment_id: str, tags: list[dict[str, str]]) -> str:
    created = dbx_request_json(
        base_url,
        token,
        "POST",
        "/api/2.0/mlflow/runs/create",
        payload={"experiment_id": experiment_id, "start_time": int(time.time() * 1000), "tags": tags},
    )
    run_id = str((((created.get("run") or {}).get("info") or {}).get("run_id")) or "").strip()
    if not run_id:
        raise RuntimeError("phase5c_mlflow_run_id_unresolved")
    return run_id


def dbx_log_batch(
    base_url: str,
    token: str,
    run_id: str,
    *,
    metrics: dict[str, float],
    params: dict[str, str],
    tags: dict[str, str],
) -> None:
    ts_ms = int(time.time() * 1000)
    payload = {
        "run_id": run_id,
        "metrics": [{"key": key, "value": float(value), "timestamp": ts_ms, "step": 0} for key, value in metrics.items()],
        "params": [{"key": key, "value": str(value)} for key, value in params.items()],
        "tags": [{"key": key, "value": str(value)} for key, value in tags.items()],
    }
    dbx_request_json(base_url, token, "POST", "/api/2.0/mlflow/runs/log-batch", payload=payload)


def dbx_finish_run(base_url: str, token: str, run_id: str) -> dict[str, Any]:
    dbx_request_json(
        base_url,
        token,
        "POST",
        "/api/2.0/mlflow/runs/update",
        payload={"run_id": run_id, "status": "FINISHED", "end_time": int(time.time() * 1000)},
    )
    return dbx_request_json(base_url, token, "GET", f"/api/2.0/mlflow/runs/get?run_id={urllib.parse.quote(run_id, safe='')}")


def make_s3_dataset(uri: str, region: str) -> ds.Dataset:
    bucket, key = parse_s3_uri(uri)
    filesystem = pafs.S3FileSystem(region=region)
    return ds.dataset(f"{bucket}/{key}", filesystem=filesystem, format="parquet")


def collect_label_rows(
    *,
    label_uri: str,
    feature_asof_utc: str,
    region: str,
    positive_target: int,
    negative_target: int,
    batch_size: int,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    dataset = make_s3_dataset(label_uri, region)
    scanner = dataset.scanner(columns=["flow_id", "event_seq", "is_fraud_truth"], batch_size=batch_size)
    rows: list[dict[str, Any]] = []
    requested_pos = max(int(positive_target), 1)
    requested_neg = max(int(negative_target), 1)
    buffered_pos = requested_pos * 4
    buffered_neg = requested_neg * 4
    pos = 0
    neg = 0
    row_index = 0
    for batch in scanner.to_batches():
        pdf = batch.to_pandas()
        for row in pdf.itertuples(index=False):
            label = 1 if bool(row.is_fraud_truth) else 0
            if label == 1 and pos >= buffered_pos:
                row_index += 1
                continue
            if label == 0 and neg >= buffered_neg:
                row_index += 1
                continue
            rows.append(
                {
                    "flow_id": int(row.flow_id),
                    "event_seq": int(row.event_seq),
                    "label": label,
                    "source_row_index": row_index,
                    "feature_asof_utc": feature_asof_utc,
                }
            )
            if label == 1:
                pos += 1
            else:
                neg += 1
            row_index += 1
            if pos >= buffered_pos and neg >= buffered_neg:
                break
        if pos >= buffered_pos and neg >= buffered_neg:
            break
    if pos < buffered_pos or neg < buffered_neg:
        raise RuntimeError(f"phase5c_sample_shortfall:pos={pos}/{buffered_pos}:neg={neg}/{buffered_neg}")
    sample = pd.DataFrame(rows)
    return sample, {
        "positive_rows": int(pos),
        "negative_rows": int(neg),
        "requested_positive_rows": int(requested_pos),
        "requested_negative_rows": int(requested_neg),
        "total_rows": int(len(sample)),
        "min_source_row_index": int(sample["source_row_index"].min()),
        "max_source_row_index": int(sample["source_row_index"].max()),
    }


def enrich_events(
    *,
    events_uri: str,
    sample: pd.DataFrame,
    region: str,
    batch_size: int,
    feature_asof_utc: str,
    positive_target: int,
    negative_target: int,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    dataset = make_s3_dataset(events_uri, region)
    need = {(int(row.flow_id), int(row.event_seq)): row.label for row in sample.itertuples(index=False)}
    rows: list[dict[str, Any]] = []
    scanner = dataset.scanner(
        columns=["flow_id", "event_seq", "amount", "ts_utc", "campaign_id", "event_type"],
        batch_size=batch_size,
    )
    for batch in scanner.to_batches():
        pdf = batch.to_pandas()
        pdf["lookup_key"] = list(zip(pdf["flow_id"].astype("int64"), pdf["event_seq"].astype("int64")))
        hit = pdf[pdf["lookup_key"].isin(need.keys())]
        if hit.empty:
            continue
        for row in hit.itertuples(index=False):
            key = (int(row.flow_id), int(row.event_seq))
            rows.append(
                {
                    "flow_id": key[0],
                    "event_seq": key[1],
                    "amount": float(row.amount),
                    "ts_utc": str(row.ts_utc),
                    "campaign_id": None if pd.isna(row.campaign_id) else str(row.campaign_id),
                    "event_type": str(row.event_type),
                    "label": int(need[key]),
                }
            )
        if len(rows) >= len(need):
            break
    frame = pd.DataFrame(rows).drop_duplicates(subset=["flow_id", "event_seq"], keep="first")
    if len(frame) != len(sample):
        raise RuntimeError(f"phase5c_event_match_shortfall:{len(frame)}<{len(sample)}")
    frame["ts_utc"] = pd.to_datetime(frame["ts_utc"], utc=True)
    frame["hour_utc"] = frame["ts_utc"].dt.hour.astype("int64")
    frame["weekday_utc"] = frame["ts_utc"].dt.weekday.astype("int64")
    frame["has_campaign"] = frame["campaign_id"].notna().astype("int64")
    frame["amount_log1p"] = frame["amount"].map(lambda value: math.log1p(max(float(value), 0.0)))
    frame["campaign_hash_bucket"] = frame["campaign_id"].fillna("").map(lambda value: int(hashlib.sha256(value.encode("utf-8")).hexdigest()[:8], 16) % 17 if value else 0)
    frame["event_type_auth"] = (frame["event_type"] == "AUTH_REQUEST").astype("int64")
    ordered = frame.sort_values(["ts_utc", "flow_id", "event_seq"]).reset_index(drop=True)
    feature_asof_dt = pd.Timestamp(feature_asof_utc)
    bounded = ordered[ordered["ts_utc"] <= feature_asof_dt].copy()
    campaign_rows = bounded[bounded["has_campaign"] == 1].copy()
    selected_parts: list[pd.DataFrame] = []
    if not campaign_rows.empty:
        selected_parts.append(campaign_rows)
    remaining = bounded[~bounded.index.isin(campaign_rows.index)].copy()
    selected_pos = int(campaign_rows["label"].sum()) if not campaign_rows.empty else 0
    selected_neg = int(len(campaign_rows) - selected_pos) if not campaign_rows.empty else 0
    remaining_pos_target = max(int(positive_target) - selected_pos, 0)
    remaining_neg_target = max(int(negative_target) - selected_neg, 0)
    pos_pool = remaining[remaining["label"] == 1].sort_values(["ts_utc", "flow_id", "event_seq"])
    neg_pool = remaining[remaining["label"] == 0].sort_values(["ts_utc", "flow_id", "event_seq"])
    if len(pos_pool) < remaining_pos_target or len(neg_pool) < remaining_neg_target:
        raise RuntimeError(
            f"phase5c_bounded_sample_shortfall:pos={selected_pos + len(pos_pool)}/{positive_target}:neg={selected_neg + len(neg_pool)}/{negative_target}"
        )
    if remaining_pos_target > 0:
        selected_parts.append(select_evenly(pos_pool, remaining_pos_target))
    if remaining_neg_target > 0:
        selected_parts.append(select_evenly(neg_pool, remaining_neg_target))
    selected = pd.concat(selected_parts, axis=0).drop_duplicates(subset=["flow_id", "event_seq"], keep="first")
    if len(selected) != positive_target + negative_target:
        raise RuntimeError(f"phase5c_selected_row_count_invalid:{len(selected)}!={positive_target + negative_target}")
    selected = selected.sort_values(["ts_utc", "flow_id", "event_seq"]).reset_index(drop=True)
    return selected, {
        "matched_rows": int(len(ordered)),
        "bounded_rows": int(len(bounded)),
        "selected_rows": int(len(selected)),
        "fraud_rows": int(selected["label"].sum()),
        "campaign_present_rows": int(selected["has_campaign"].sum()),
        "bounded_campaign_rows": int(campaign_rows.shape[0]),
        "event_type_counts": selected["event_type"].value_counts().to_dict(),
        "ts_min_utc": selected["ts_utc"].min().isoformat().replace("+00:00", "Z"),
        "ts_max_utc": selected["ts_utc"].max().isoformat().replace("+00:00", "Z"),
        "feature_asof_utc": feature_asof_utc,
    }


def split_time_based(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    total = len(frame)
    if total < 100:
        raise RuntimeError(f"phase5c_dataset_too_small:{total}")
    train_end = max(int(total * 0.6), 1)
    valid_end = max(int(total * 0.8), train_end + 1)
    train = frame.iloc[:train_end].copy()
    valid = frame.iloc[train_end:valid_end].copy()
    test = frame.iloc[valid_end:].copy()
    for name, part in (("train", train), ("validation", valid), ("test", test)):
        labels = set(part["label"].astype(int).tolist())
        if labels != {0, 1}:
            raise RuntimeError(f"phase5c_split_not_bimodal:{name}:{sorted(labels)}")
    return train, valid, test


def encode_csv_rows(frame: pd.DataFrame, *, include_label: bool) -> str:
    cols = ["amount", "amount_log1p", "hour_utc", "weekday_utc", "has_campaign", "campaign_hash_bucket", "event_type_auth"]
    if include_label:
        cols = ["label"] + cols
    buffer = io.StringIO()
    frame.loc[:, cols].to_csv(buffer, index=False, header=False)
    return buffer.getvalue()


def write_sample_artifacts(
    *,
    run_root: Path,
    s3: Any,
    object_store_root: str,
    platform_run_id: str,
    execution_id: str,
    train: pd.DataFrame,
    valid: pd.DataFrame,
    test: pd.DataFrame,
) -> dict[str, str]:
    prefix = f"{object_store_root.rstrip('/')}/{platform_run_id}/learning/phase5/{execution_id}"
    refs = {
        "train_csv_ref": f"{prefix}/dataset/train/train.csv",
        "validation_csv_ref": f"{prefix}/dataset/validation/validation.csv",
        "test_features_csv_ref": f"{prefix}/dataset/test/test_features.csv",
        "test_labels_ref": f"{prefix}/dataset/test/test_labels.json",
        "dataset_basis_ref": f"{prefix}/dataset/dataset_basis.json",
        "sample_rows_ref": f"{prefix}/dataset/sample_rows.json",
    }
    s3_write_bytes(s3, refs["train_csv_ref"], encode_csv_rows(train, include_label=True).encode("utf-8"), "text/csv")
    s3_write_bytes(s3, refs["validation_csv_ref"], encode_csv_rows(valid, include_label=True).encode("utf-8"), "text/csv")
    s3_write_bytes(s3, refs["test_features_csv_ref"], encode_csv_rows(test, include_label=False).encode("utf-8"), "text/csv")
    s3_write_json(
        s3,
        refs["test_labels_ref"],
        {
            "schema_version": "phase5.test_labels.v0",
            "labels": [int(value) for value in test["label"].tolist()],
            "campaign_present": [int(value) for value in test["has_campaign"].tolist()],
            "weekday_utc": [int(value) for value in test["weekday_utc"].tolist()],
            "ts_utc": [value.isoformat().replace("+00:00", "Z") for value in test["ts_utc"].tolist()],
        },
    )
    sample_rows = pd.concat([train, valid, test], axis=0).reset_index(drop=True)
    basis_payload = {
        "schema_version": "phase5.dataset_basis.v0",
        "rows_total": int(len(sample_rows)),
        "train_rows": int(len(train)),
        "validation_rows": int(len(valid)),
        "test_rows": int(len(test)),
        "label_counts": {str(key): int(value) for key, value in sample_rows["label"].value_counts().to_dict().items()},
        "time_bounds": {
            "min_ts_utc": sample_rows["ts_utc"].min().isoformat().replace("+00:00", "Z"),
            "max_ts_utc": sample_rows["ts_utc"].max().isoformat().replace("+00:00", "Z"),
        },
        "feature_columns": ["amount", "amount_log1p", "hour_utc", "weekday_utc", "has_campaign", "campaign_hash_bucket", "event_type_auth"],
    }
    s3_write_json(s3, refs["dataset_basis_ref"], basis_payload)
    s3_write_json(
        s3,
        refs["sample_rows_ref"],
        {
            "schema_version": "phase5.dataset_sample_rows.v0",
            "rows": [
                {
                    "flow_id": int(row.flow_id),
                    "event_seq": int(row.event_seq),
                    "label": int(row.label),
                    "amount": float(row.amount),
                    "ts_utc": row.ts_utc.isoformat().replace("+00:00", "Z"),
                    "has_campaign": int(row.has_campaign),
                    "campaign_id": row.campaign_id,
                }
                for row in sample_rows.itertuples(index=False)
            ],
        },
    )
    dump_json(run_root / "phase5c_dataset_basis.local.json", basis_payload)
    return refs


def build_manifest_payload(
    *,
    platform_run_id: str,
    scenario_run_id: str,
    label_asof_utc: str,
    label_maturity_days: int,
    replay_start: int,
    replay_end: int,
) -> dict[str, Any]:
    identity = {
        "platform_run_id": platform_run_id,
        "scenario_run_ids": [scenario_run_id],
        "replay_basis": [{"topic": "s3_event_stream_with_fraud_6B", "partition": 0, "offset_kind": "oracle_row_span", "start_offset": str(replay_start), "end_offset": str(replay_end)}],
        "label_basis": {"label_asof_utc": label_asof_utc, "resolution_rule": "observed_time<=label_asof_utc", "maturity_days": int(label_maturity_days)},
        "feature_definition_set": {"feature_set_id": "core_features", "feature_set_version": "v1"},
        "join_scope": {"subject_key": "flow_id,event_seq", "required_output_ids": ["s3_event_stream_with_fraud_6B", "s4_event_labels_6B"]},
        "filters": {"phase": "phase5_managed_bound"},
        "policy_revision": "ofs-policy-v0",
        "config_revision": "dev-full-phase5-managed",
        "ofs_code_release_id": "git:phase5_learning_managed_train_eval",
    }
    fingerprint = dataset_fingerprint(identity)
    manifest_id = deterministic_dataset_manifest_id(fingerprint)
    payload = {
        "schema_version": "learning.dataset_manifest.v0",
        "dataset_manifest_id": manifest_id,
        "dataset_fingerprint": fingerprint,
        "platform_run_id": platform_run_id,
        "scenario_run_ids": [scenario_run_id],
        "replay_basis": identity["replay_basis"],
        "label_basis": identity["label_basis"],
        "feature_definition_set": identity["feature_definition_set"],
        "provenance": {"ofs_code_release_id": identity["ofs_code_release_id"], "config_revision": identity["config_revision"], "run_config_digest": identity["policy_revision"]},
    }
    DatasetManifestContract.from_payload(payload)
    return payload


def wait_training(sm: Any, job_name: str, timeout_seconds: int, poll_seconds: int) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        payload = sm.describe_training_job(TrainingJobName=job_name)
        status = str(payload.get("TrainingJobStatus") or "")
        if status in {"Completed", "Failed", "Stopped"}:
            return payload
        time.sleep(poll_seconds)
    raise TimeoutError("phase5c_training_timeout")


def wait_transform(sm: Any, job_name: str, timeout_seconds: int, poll_seconds: int) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        payload = sm.describe_transform_job(TransformJobName=job_name)
        status = str(payload.get("TransformJobStatus") or "")
        if status in {"Completed", "Failed", "Stopped"}:
            return payload
        time.sleep(poll_seconds)
    raise TimeoutError("phase5c_transform_timeout")


def normalize_job_name(prefix: str, suffix: str) -> str:
    base = f"{prefix}-{suffix}"
    safe = "".join(ch if ch.isalnum() or ch == "-" else "-" for ch in base).strip("-")
    return safe[:63].rstrip("-")


def auc_roc(y_true: list[int], y_score: list[float]) -> float:
    pos_n = sum(y_true)
    neg_n = len(y_true) - pos_n
    if pos_n <= 0 or neg_n <= 0:
        return 0.0
    ranks = sorted([(score, idx) for idx, score in enumerate(y_score)], key=lambda item: item[0])
    rank_sum = 0.0
    rank = 1
    i = 0
    while i < len(ranks):
        j = i
        while j < len(ranks) and ranks[j][0] == ranks[i][0]:
            j += 1
        avg_rank = (rank + (rank + (j - i) - 1)) / 2.0
        for _, idx in ranks[i:j]:
            if y_true[idx] == 1:
                rank_sum += avg_rank
        rank += j - i
        i = j
    return float((rank_sum - (pos_n * (pos_n + 1) / 2.0)) / (pos_n * neg_n))


def precision_at_k(y_true: list[int], y_score: list[float], k: int) -> float:
    if not y_true:
        return 0.0
    order = sorted(range(len(y_score)), key=lambda idx: y_score[idx], reverse=True)[: max(1, min(k, len(y_score)))]
    return float(sum(y_true[idx] for idx in order) / len(order))


def log_loss(y_true: list[int], y_score: list[float]) -> float:
    eps = 1e-15
    total = 0.0
    for label, score in zip(y_true, y_score):
        p = min(max(float(score), eps), 1.0 - eps)
        total += -(label * math.log(p) + (1 - label) * math.log(1.0 - p))
    return float(total / max(len(y_true), 1))


def compute_eval_metrics(test: pd.DataFrame, scores: list[float]) -> dict[str, Any]:
    labels = [int(value) for value in test["label"].tolist()]
    overall = {
        "auc_roc": auc_roc(labels, scores),
        "precision_at_50": precision_at_k(labels, scores, 50),
        "log_loss": log_loss(labels, scores),
        "score_mean": float(statistics.fmean(scores)) if scores else 0.0,
        "rows": int(len(labels)),
        "positives": int(sum(labels)),
        "negatives": int(len(labels) - sum(labels)),
    }
    cohorts: dict[str, Any] = {}
    for cohort_name, mask in (
        ("campaign_present", test["has_campaign"] == 1),
        ("campaign_absent", test["has_campaign"] == 0),
        ("weekday_lt_5", test["weekday_utc"] < 5),
        ("weekday_ge_5", test["weekday_utc"] >= 5),
    ):
        indexes = [idx for idx, keep in enumerate(mask.tolist()) if keep]
        if len(indexes) < 20:
            continue
        sub_y = [labels[idx] for idx in indexes]
        sub_s = [scores[idx] for idx in indexes]
        cohorts[cohort_name] = {
            "rows": int(len(indexes)),
            "positives": int(sum(sub_y)),
            "auc_roc": auc_roc(sub_y, sub_s),
            "precision_at_50": precision_at_k(sub_y, sub_s, min(50, len(sub_s))),
        }
    return {"overall": overall, "cohorts": cohorts}


def select_evenly(frame: pd.DataFrame, count: int) -> pd.DataFrame:
    if count <= 0 or frame.empty:
        return frame.iloc[0:0].copy()
    if len(frame) <= count:
        return frame.copy()
    if count == 1:
        return frame.iloc[[len(frame) // 2]].copy()
    positions = []
    upper = len(frame) - 1
    for idx in range(count):
        pos = round(idx * upper / (count - 1))
        positions.append(int(pos))
    unique_positions = sorted(set(positions))
    selected = frame.iloc[unique_positions].copy()
    cursor = 0
    while len(selected) < count:
        if cursor not in unique_positions:
            unique_positions.append(cursor)
            selected = frame.iloc[sorted(unique_positions)].copy()
        cursor += 1
    return selected.iloc[:count].copy()


def create_rollback_event(
    *,
    run_root: Path,
    platform_run_id: str,
    execution_id: str,
    previous_bundle: dict[str, Any],
    target_scope: dict[str, str],
    evidence_refs: list[dict[str, str]],
) -> Path:
    payload = {
        "schema_version": "learning.registry_lifecycle.v0",
        "registry_event_id": hashlib.sha256(
            json.dumps(
                {"phase": "phase5_rollback_drill", "platform_run_id": platform_run_id, "execution_id": execution_id, "bundle": previous_bundle},
                sort_keys=True,
                ensure_ascii=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest(),
        "event_type": "BUNDLE_ROLLED_BACK",
        "scope_key": target_scope,
        "bundle_ref": previous_bundle,
        "actor": {"actor_id": "SYSTEM::phase5_learning_managed_train_eval", "source_type": "SYSTEM"},
        "ts_utc": now_utc(),
        "evidence_refs": evidence_refs,
    }
    RegistryLifecycleEventContract.from_payload(payload)
    path = run_root / "phase5_rollback_event.json"
    dump_json(path, payload)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase 5.C/D on the admitted managed basis.")
    parser.add_argument("--execution-id", required=True)
    parser.add_argument("--source-execution-id", required=True)
    parser.add_argument("--phase5a-execution-id", required=True)
    parser.add_argument("--phase5b-execution-id", required=True)
    parser.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/proving_plane/run_control")
    parser.add_argument("--summary-name", default="phase5_learning_managed_summary.json")
    parser.add_argument("--receipt-name", default="phase5_learning_managed_receipt.json")
    parser.add_argument("--aws-region", default="eu-west-2")
    parser.add_argument("--positive-target", type=int, default=1000)
    parser.add_argument("--negative-target", type=int, default=2000)
    parser.add_argument("--scan-batch-size", type=int, default=200000)
    parser.add_argument("--training-instance-type", default="ml.m5.large")
    parser.add_argument("--transform-instance-type", default="ml.m5.large")
    parser.add_argument("--max-runtime-seconds", type=int, default=2400)
    parser.add_argument("--poll-seconds", type=int, default=20)
    args = parser.parse_args()

    run_root = Path(args.run_control_root) / args.execution_id
    summary_path = run_root / args.summary_name
    receipt_path = run_root / args.receipt_name
    blockers: list[str] = []
    notes: list[str] = []

    try:
        registry = parse_registry(REGISTRY_PATH)
        object_store_bucket = str(registry["S3_OBJECT_STORE_BUCKET"]).strip()
        object_store_root = f"s3://{object_store_bucket}"
        source_root = Path(args.run_control_root) / args.source_execution_id
        phase5a_root = Path(args.run_control_root) / args.phase5a_execution_id
        phase5b_root = Path(args.run_control_root) / args.phase5b_execution_id

        source_receipt = load_json(source_root / "phase4_coupled_readiness_receipt.json")
        bootstrap = load_json(source_root / "phase4_control_plane_bootstrap.json")
        phase5a_summary = load_json(phase5a_root / "phase5_learning_surface_summary.json")
        phase5b_summary = load_json(phase5b_root / "phase5_ofs_dataset_basis_summary.json")
        phase5b_receipt = load_json(phase5b_root / "phase5_ofs_dataset_basis_receipt.json")

        if str(source_receipt.get("verdict") or "").strip().upper() != "PHASE4_READY":
            raise RuntimeError("phase5c_source_phase4_not_green")
        if not bool(bootstrap.get("overall_pass")):
            raise RuntimeError("phase5c_source_bootstrap_not_green")
        if str(phase5b_receipt.get("verdict") or "").strip().upper() != "PHASE5B_READY":
            raise RuntimeError("phase5c_phase5b_not_green")

        platform_run_id = str(phase5b_summary.get("platform_run_id") or bootstrap.get("platform_run_id") or "").strip()
        scenario_run_id = str(phase5b_summary.get("scenario_run_id") or bootstrap.get("scenario_run_id") or "").strip()
        if not platform_run_id or not scenario_run_id:
            raise RuntimeError("phase5c_run_scope_unresolved")

        feature_asof_utc = str((((phase5a_summary.get("upstream_truth") or {}).get("feature_asof_utc")) or "")).strip()
        label_asof_utc = str((((phase5a_summary.get("upstream_truth") or {}).get("label_asof_utc")) or "")).strip()
        label_maturity_days = int((((phase5a_summary.get("upstream_truth") or {}).get("label_maturity_days")) or 0))
        if not feature_asof_utc or not label_asof_utc or label_maturity_days <= 0:
            raise RuntimeError("phase5c_temporal_law_unresolved")

        s3 = boto3.client("s3", region_name=args.aws_region)
        build_snapshot = s3_read_json(s3, str(phase5b_summary.get("build_snapshot_ref") or ""))
        slice_files = dict(build_snapshot.get("slice_files") or {})
        events_uri = str(slice_files.get("events") or "").strip()
        event_labels_uri = str(slice_files.get("event_labels") or "").strip()
        if not events_uri or not event_labels_uri:
            raise RuntimeError("phase5c_slice_files_unresolved")

        ssm = boto3.client("ssm", region_name=args.aws_region)
        sm = boto3.client("sagemaker", region_name=args.aws_region)
        workspace_url = read_ssm(ssm, str(registry["SSM_DATABRICKS_WORKSPACE_URL_PATH"]).strip(), decrypt=False)
        databricks_token = read_ssm(ssm, str(registry["SSM_DATABRICKS_TOKEN_PATH"]).strip(), decrypt=True)
        tracking_uri = read_ssm(ssm, str(registry["SSM_MLFLOW_TRACKING_URI_PATH"]).strip(), decrypt=False)
        sagemaker_role_arn = read_ssm(ssm, str(registry["SSM_SAGEMAKER_MODEL_EXEC_ROLE_ARN_PATH"]).strip(), decrypt=False)
        model_package_group_name = str(registry["SM_MODEL_PACKAGE_GROUP_NAME"]).strip()
        train_prefix = str(registry.get("SM_TRAINING_JOB_NAME_PREFIX", "fraud-platform-dev-full-mtrain")).strip()
        batch_prefix = str(registry.get("SM_BATCH_TRANSFORM_JOB_NAME_PREFIX", "fraud-platform-dev-full-mbatch")).strip()
        mlflow_experiment_path = str(registry["MLFLOW_EXPERIMENT_PATH"]).strip()
        mlflow_model_name = str(registry["MLFLOW_MODEL_NAME"]).strip()

        label_sample, label_scan = collect_label_rows(
            label_uri=event_labels_uri,
            feature_asof_utc=feature_asof_utc,
            region=args.aws_region,
            positive_target=args.positive_target,
            negative_target=args.negative_target,
            batch_size=args.scan_batch_size,
        )
        sampled, event_scan = enrich_events(
            events_uri=events_uri,
            sample=label_sample,
            region=args.aws_region,
            batch_size=args.scan_batch_size,
            feature_asof_utc=feature_asof_utc,
            positive_target=args.positive_target,
            negative_target=args.negative_target,
        )
        train, valid, test = split_time_based(sampled)
        if pd.Timestamp(sampled["ts_utc"].max()) > pd.Timestamp(feature_asof_utc):
            raise RuntimeError("phase5c_feature_horizon_exceeds_asof")
        sample_refs = write_sample_artifacts(
            run_root=run_root,
            s3=s3,
            object_store_root=object_store_root,
            platform_run_id=platform_run_id,
            execution_id=args.execution_id,
            train=train,
            valid=valid,
            test=test,
        )

        manifest_payload = build_manifest_payload(
            platform_run_id=platform_run_id,
            scenario_run_id=scenario_run_id,
            label_asof_utc=label_asof_utc,
            label_maturity_days=label_maturity_days,
            replay_start=label_scan["min_source_row_index"],
            replay_end=label_scan["max_source_row_index"],
        )
        manifest_ref = f"{object_store_root.rstrip('/')}/{platform_run_id}/learning/phase5/{args.execution_id}/dataset_manifest.json"
        s3_write_json(s3, manifest_ref, manifest_payload)

        request = MfTrainBuildRequest(
            request_id=f"phase5.mf.{args.execution_id}",
            intent_kind="baseline_train",
            platform_run_id=platform_run_id,
            dataset_manifest_refs=(manifest_ref,),
            training_config_ref="config/platform/mf/training_profile_v0.yaml",
            governance_profile_ref="config/platform/mf/governance_profile_v0.yaml",
            requester_principal="SYSTEM::phase5_learning_managed_train_eval",
            target_scope=TargetScope(environment="dev_full", mode="fraud", bundle_slot="primary"),
            policy_revision="mf-policy-v0",
            config_revision="dev-full-phase5-managed",
            mf_code_release_id="git:phase5_learning_managed_train_eval",
            publish_allowed=True,
        )
        resolver = MfTrainPlanResolver(
            config=MfTrainPlanResolverConfig(
                object_store_root=object_store_root,
                object_store_region=args.aws_region,
                object_store_path_style=False,
            )
        )
        plan = resolver.resolve(request=request)
        resolved_plan_ref = resolver.emit_immutable(plan=plan)

        training_suffix = hashlib.sha256(f"{args.execution_id}|{plan.run_key}".encode("utf-8")).hexdigest()[:10]
        training_job_name = normalize_job_name(train_prefix or "fraud-platform-dev-full-mtrain", training_suffix)
        model_name = normalize_job_name(f"{train_prefix or 'fraud-platform-dev-full-mtrain'}-model", training_suffix)
        transform_job_name = normalize_job_name(batch_prefix or "fraud-platform-dev-full-mbatch", training_suffix)
        image_uri = image_uris.retrieve(
            framework="xgboost",
            region=args.aws_region,
            version="1.7-1",
            image_scope="training",
            instance_type=args.training_instance_type,
        )
        train_prefix_uri = sample_refs["train_csv_ref"].rsplit("/", 1)[0] + "/"
        valid_prefix_uri = sample_refs["validation_csv_ref"].rsplit("/", 1)[0] + "/"
        transform_output_ref = f"{object_store_root.rstrip('/')}/{platform_run_id}/learning/phase5/{args.execution_id}/sagemaker/transform_output/"
        train_output_ref = f"{object_store_root.rstrip('/')}/{platform_run_id}/learning/phase5/{args.execution_id}/sagemaker/train_output/"

        execution_started = now_utc()
        sm.create_training_job(
            TrainingJobName=training_job_name,
            AlgorithmSpecification={"TrainingImage": image_uri, "TrainingInputMode": "File"},
            RoleArn=sagemaker_role_arn,
            InputDataConfig=[
                {
                    "ChannelName": "train",
                    "DataSource": {"S3DataSource": {"S3DataType": "S3Prefix", "S3Uri": train_prefix_uri, "S3DataDistributionType": "FullyReplicated"}},
                    "ContentType": "text/csv",
                },
                {
                    "ChannelName": "validation",
                    "DataSource": {"S3DataSource": {"S3DataType": "S3Prefix", "S3Uri": valid_prefix_uri, "S3DataDistributionType": "FullyReplicated"}},
                    "ContentType": "text/csv",
                },
            ],
            OutputDataConfig={"S3OutputPath": train_output_ref},
            ResourceConfig={"InstanceType": args.training_instance_type, "InstanceCount": 1, "VolumeSizeInGB": 30},
            StoppingCondition={"MaxRuntimeInSeconds": int(args.max_runtime_seconds)},
            HyperParameters={
                "objective": "binary:logistic",
                "eval_metric": "auc",
                "num_round": "40",
                "max_depth": "4",
                "eta": "0.2",
                "subsample": "0.9",
                "verbosity": "0",
            },
        )
        training_desc = wait_training(sm, training_job_name, args.max_runtime_seconds + 600, args.poll_seconds)
        if str(training_desc.get("TrainingJobStatus") or "") != "Completed":
            raise RuntimeError(
                f"phase5c_training_failed:{training_desc.get('TrainingJobStatus')}:{str(training_desc.get('FailureReason') or '')[:500]}"
            )
        model_data_url = str((((training_desc.get("ModelArtifacts") or {}).get("S3ModelArtifacts")) or "")).strip()
        if not model_data_url:
            raise RuntimeError("phase5c_model_artifact_missing")

        sm.create_model(
            ModelName=model_name,
            ExecutionRoleArn=sagemaker_role_arn,
            PrimaryContainer={"Image": image_uri, "ModelDataUrl": model_data_url},
        )
        sm.create_transform_job(
            TransformJobName=transform_job_name,
            ModelName=model_name,
            TransformInput={
                "DataSource": {"S3DataSource": {"S3DataType": "S3Prefix", "S3Uri": sample_refs["test_features_csv_ref"]}},
                "ContentType": "text/csv",
                "SplitType": "Line",
            },
            TransformOutput={"S3OutputPath": transform_output_ref, "AssembleWith": "Line"},
            TransformResources={"InstanceType": args.transform_instance_type, "InstanceCount": 1},
        )
        transform_desc = wait_transform(sm, transform_job_name, args.max_runtime_seconds + 600, args.poll_seconds)
        if str(transform_desc.get("TransformJobStatus") or "") != "Completed":
            raise RuntimeError(
                f"phase5c_transform_failed:{transform_desc.get('TransformJobStatus')}:{str(transform_desc.get('FailureReason') or '')[:500]}"
            )

        test_output_uri = f"{transform_output_ref.rstrip('/')}/{Path(parse_s3_uri(sample_refs['test_features_csv_ref'])[1]).name}.out"
        prediction_lines = [line.strip() for line in s3_read_text(s3, test_output_uri).splitlines() if line.strip()]
        scores = [float(line.split(",")[0]) for line in prediction_lines]
        if len(scores) != len(test):
            raise RuntimeError(f"phase5c_prediction_count_mismatch:{len(scores)}!={len(test)}")
        metrics = compute_eval_metrics(test, scores)
        governance_profile = yaml.safe_load(Path("config/platform/mf/governance_profile_v0.yaml").read_text(encoding="utf-8")) or {}
        gate_thresholds = dict(governance_profile.get("eval_thresholds") or {})
        gate_decision = (
            "PASS"
            if metrics["overall"]["auc_roc"] >= float(gate_thresholds["min_auc_roc"])
            and metrics["overall"]["precision_at_50"] >= float(gate_thresholds["min_precision_at_50"])
            else "FAIL"
        )

        experiment_id = dbx_find_experiment_id(workspace_url, databricks_token, mlflow_experiment_path)
        mlflow_tags = [
            {"key": "mlflow.runName", "value": f"{platform_run_id}:{args.execution_id}"},
            {"key": "platform_run_id", "value": platform_run_id},
            {"key": "scenario_run_id", "value": scenario_run_id},
            {"key": "phase5_execution_id", "value": args.execution_id},
            {"key": "phase5b_execution_id", "value": args.phase5b_execution_id},
            {"key": "dataset_manifest_ref", "value": manifest_ref},
            {"key": "mf_model_name", "value": mlflow_model_name},
            {"key": "tracking_uri", "value": tracking_uri},
        ]
        mlflow_run_id = dbx_create_run(workspace_url, databricks_token, experiment_id, mlflow_tags)

        eval_report_id = hashlib.sha256(f"{plan.run_key}|{args.execution_id}|eval".encode("utf-8")).hexdigest()[:24]
        execution_record_payload = {
            "schema_version": "learning.mf_execution_record.v0",
            "run_key": plan.run_key,
            "request_id": request.request_id,
            "platform_run_id": platform_run_id,
            "execution_started_at_utc": execution_started,
            "execution_completed_at_utc": now_utc(),
            "split_strategy": "time_based",
            "seed_policy": {"recipe": "phase5.managed.sample.v0", "base_seed": 0},
            "stage_seed": 0,
            "training_profile_revision": "mf.train.policy.v0@r7",
            "governance_profile_revision": "mf.governance.policy.v0@r12",
            "dataset_manifest_refs": [manifest_ref],
            "dataset_manifest_digests": [manifest_payload["dataset_fingerprint"]],
            "managed_runtime": {
                "training_job_name": training_job_name,
                "transform_job_name": transform_job_name,
                "model_name": model_name,
                "training_instance_type": args.training_instance_type,
                "transform_instance_type": args.transform_instance_type,
            },
        }
        train_artifact_payload = {
            "schema_version": "learning.mf_train_artifact.v0",
            "run_key": plan.run_key,
            "platform_run_id": platform_run_id,
            "algorithm_id": "xgboost_managed_v1",
            "model_fingerprint": hashlib.sha256(
                json.dumps(
                    {"model_data_url": model_data_url, "training_job_name": training_job_name, "dataset_manifest_id": manifest_payload["dataset_manifest_id"]},
                    sort_keys=True,
                    ensure_ascii=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest(),
            "input_refs": {
                **plan.input_refs,
                "dataset_basis_ref": sample_refs["dataset_basis_ref"],
                "train_csv_ref": sample_refs["train_csv_ref"],
                "validation_csv_ref": sample_refs["validation_csv_ref"],
                "test_features_csv_ref": sample_refs["test_features_csv_ref"],
                "test_predictions_ref": test_output_uri,
                "mlflow_run_id": mlflow_run_id,
            },
            "managed_runtime": {
                "model_data_url": model_data_url,
                "training_job_name": training_job_name,
                "transform_job_name": transform_job_name,
                "model_name": model_name,
                "model_package_group_name": model_package_group_name,
            },
        }
        eval_report_payload = {
            "schema_version": "learning.eval_report.v0",
            "eval_report_id": eval_report_id,
            "dataset_manifest_ref": manifest_ref,
            "gate_decision": gate_decision,
            "metrics": {
                "scores": {
                    "auc_roc": metrics["overall"]["auc_roc"],
                    "precision_at_50": metrics["overall"]["precision_at_50"],
                    "log_loss": metrics["overall"]["log_loss"],
                },
                "thresholds": gate_thresholds,
                "dataset_summary": {
                    "train_rows": int(len(train)),
                    "validation_rows": int(len(valid)),
                    "test_rows": int(len(test)),
                    "positives_total": int(sampled["label"].sum()),
                    "negatives_total": int(len(sampled) - sampled["label"].sum()),
                },
                "cohort_metrics": metrics["cohorts"],
                "time_contract": {"feature_asof_utc": feature_asof_utc, "label_asof_utc": label_asof_utc, "label_maturity_days": label_maturity_days},
                "reproducibility_basis": {
                    "dataset_manifest_id": manifest_payload["dataset_manifest_id"],
                    "dataset_fingerprint": manifest_payload["dataset_fingerprint"],
                    "resolved_plan_ref": resolved_plan_ref,
                    "train_artifact_ref_pending": True,
                },
            },
            "provenance": {
                "mf_code_release_id": "git:phase5_learning_managed_train_eval",
                "config_revision": "dev-full-phase5-managed",
                "run_config_digest": "mf-policy-v0",
            },
        }
        EvalReportContract.from_payload(eval_report_payload)

        evidence_prefix = f"{object_store_root.rstrip('/')}/{platform_run_id}/mf/train_runs/{plan.run_key}"
        execution_record_ref = f"{evidence_prefix}/execution_record.json"
        train_artifact_ref = f"{evidence_prefix}/artifacts/model_artifact.json"
        eval_report_ref = f"{evidence_prefix}/eval_report/{eval_report_id}.json"
        evidence_pack_ref = f"{evidence_prefix}/evidence/evidence_pack.json"
        evidence_pack_payload = {
            "schema_version": "learning.mf_training_evidence_pack.v0",
            "run_key": plan.run_key,
            "platform_run_id": platform_run_id,
            "execution_record_ref": execution_record_ref,
            "train_artifact_ref": train_artifact_ref,
            "eval_report_ref": eval_report_ref,
            "evidence_pack_fingerprint": hashlib.sha256(
                json.dumps(
                    {
                        "execution_record_ref": execution_record_ref,
                        "train_artifact_ref": train_artifact_ref,
                        "eval_report_ref": eval_report_ref,
                        "dataset_manifest_ref": manifest_ref,
                    },
                    sort_keys=True,
                    ensure_ascii=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest(),
            "managed_runtime_refs": {
                "training_job_name": training_job_name,
                "transform_job_name": transform_job_name,
                "model_name": model_name,
                "model_data_url": model_data_url,
                "test_predictions_ref": test_output_uri,
                "mlflow_run_id": mlflow_run_id,
            },
        }
        for ref, payload in (
            (execution_record_ref, execution_record_payload),
            (train_artifact_ref, train_artifact_payload),
            (eval_report_ref, eval_report_payload),
            (evidence_pack_ref, evidence_pack_payload),
        ):
            s3_write_json(s3, ref, payload)

        train_eval_receipt = MfTrainEvalReceipt(
            run_key=plan.run_key,
            request_id=request.request_id,
            platform_run_id=platform_run_id,
            execution_started_at_utc=execution_started,
            execution_completed_at_utc=now_utc(),
            split_strategy="time_based",
            seed_policy={"recipe": "phase5.managed.sample.v0", "base_seed": 0},
            stage_seed=0,
            eval_report_id=eval_report_id,
            gate_decision=gate_decision,
            train_artifact_ref=train_artifact_ref,
            eval_report_ref=eval_report_ref,
            execution_record_ref=execution_record_ref,
            evidence_pack_ref=evidence_pack_ref,
            metrics=metrics["overall"],
        )

        gate_evaluator = MfGatePolicyEvaluator(
            config=MfGatePolicyConfig(object_store_root=object_store_root, object_store_region=args.aws_region, object_store_path_style=False)
        )
        phase5_gate = gate_evaluator.evaluate(plan=plan, train_eval_receipt=train_eval_receipt, evaluated_at_utc=now_utc())
        publisher = MfBundlePublisher(
            config=MfBundlePublisherConfig(object_store_root=object_store_root, object_store_region=args.aws_region, object_store_path_style=False)
        )
        publish_result = publisher.publish(plan=plan, phase5_result=phase5_gate, published_at_utc=now_utc())

        snapshot_payload = yaml.safe_load(Path("config/platform/df/registry_snapshot_dev_full_v0.yaml").read_text(encoding="utf-8")) or {}
        previous_bundle = dict((((snapshot_payload.get("records") or [])[0]).get("bundle_ref")) or {})
        rollback_path = create_rollback_event(
            run_root=run_root,
            platform_run_id=platform_run_id,
            execution_id=args.execution_id,
            previous_bundle=previous_bundle,
            target_scope={"environment": "dev_full", "mode": "fraud", "bundle_slot": "primary"},
            evidence_refs=[
                {"ref_type": "mf_bundle_publication", "ref_id": publish_result.bundle_publication.bundle_publication_ref},
                {"ref_type": "mf_publish_receipt", "ref_id": publish_result.publish_receipt_ref},
            ],
        )
        mpr_worker = LearningRegistryWorker(load_mpr_worker_config(profile_path=Path("config/platform/profiles/dev_full.yaml"), poll_seconds=5.0))
        rollback_validation = mpr_worker.validate_rollback_event(rollback_path)

        dbx_log_batch(
            workspace_url,
            databricks_token,
            mlflow_run_id,
            metrics={
                "auc_roc": metrics["overall"]["auc_roc"],
                "precision_at_50": metrics["overall"]["precision_at_50"],
                "log_loss": metrics["overall"]["log_loss"],
            },
            params={
                "dataset_manifest_id": manifest_payload["dataset_manifest_id"],
                "training_job_name": training_job_name,
                "transform_job_name": transform_job_name,
                "model_name": model_name,
                "bundle_id": publish_result.bundle_publication.bundle_id,
                "bundle_version": publish_result.bundle_publication.bundle_version,
            },
            tags={
                "eval_report_ref": eval_report_ref,
                "gate_receipt_ref": phase5_gate.gate_receipt_ref,
                "publish_receipt_ref": publish_result.publish_receipt_ref,
                "registry_event_ref": publish_result.publish_receipt.registry_lifecycle_event_ref,
                "rollback_drill_status": rollback_validation.status,
            },
        )
        mlflow_run = dbx_finish_run(workspace_url, databricks_token, mlflow_run_id)

        overall_pass = gate_decision == "PASS"
        summary = {
            "phase": "PHASE5",
            "subphase": "PHASE5C_D",
            "generated_at_utc": now_utc(),
            "execution_id": args.execution_id,
            "source_execution_id": args.source_execution_id,
            "phase5a_execution_id": args.phase5a_execution_id,
            "phase5b_execution_id": args.phase5b_execution_id,
            "platform_run_id": platform_run_id,
            "scenario_run_id": scenario_run_id,
            "overall_pass": overall_pass,
            "blocker_ids": blockers,
            "dataset_sampling": {
                "label_scan": label_scan,
                "event_scan": event_scan,
                "train_rows": int(len(train)),
                "validation_rows": int(len(valid)),
                "test_rows": int(len(test)),
            },
            "managed_train_eval": {
                "training_job_name": training_job_name,
                "training_job_status": str(training_desc.get("TrainingJobStatus") or ""),
                "transform_job_name": transform_job_name,
                "transform_job_status": str(transform_desc.get("TransformJobStatus") or ""),
                "model_name": model_name,
                "model_data_url": model_data_url,
            },
            "metrics": metrics,
            "governance": {
                "gate_decision": gate_decision,
                "publish_decision": phase5_gate.publish_eligibility.decision,
                "bundle_id": publish_result.bundle_publication.bundle_id,
                "bundle_version": publish_result.bundle_publication.bundle_version,
                "publication_status": publish_result.publish_receipt.publication_status,
                "rollback_validation_status": rollback_validation.status,
                "previous_active_bundle": previous_bundle,
            },
            "lineage": {
                "tracking_uri": tracking_uri,
                "mlflow_experiment_path": mlflow_experiment_path,
                "mlflow_run_id": mlflow_run_id,
                "mlflow_run_status": str((((mlflow_run.get("run") or {}).get("info") or {}).get("status")) or ""),
            },
            "refs": {
                **sample_refs,
                "dataset_manifest_ref": manifest_ref,
                "resolved_plan_ref": resolved_plan_ref,
                "execution_record_ref": execution_record_ref,
                "train_artifact_ref": train_artifact_ref,
                "eval_report_ref": eval_report_ref,
                "evidence_pack_ref": evidence_pack_ref,
                "gate_receipt_ref": phase5_gate.gate_receipt_ref,
                "publish_eligibility_ref": phase5_gate.publish_eligibility_ref,
                "bundle_publication_ref": publish_result.bundle_publication.bundle_publication_ref,
                "publish_receipt_ref": publish_result.publish_receipt_ref,
                "registry_bundle_ref": publish_result.publish_receipt.registry_bundle_ref,
                "registry_lifecycle_event_ref": publish_result.publish_receipt.registry_lifecycle_event_ref,
                "rollback_event_ref": str(rollback_path),
            },
            "notes": [
                "Phase 5.C now uses the admitted Phase 5.B basis directly instead of the old fingerprint-seeded convenience workflow lane.",
                "Train/eval ran on real SageMaker managed surfaces, while lineage was committed to the Databricks-backed MLflow surface.",
                "Phase 5.D stayed non-destructive: candidate publication is real, and rollback proof is validated as a bounded drill instead of changing active runtime resolution ahead of Phase 6.",
            ],
            "assessment": "Phase 5.C/D are green on the rebuilt standard if and only if the managed train/eval result, MLflow lineage, gate/publication chain, and rollback drill all stay attributable to the same admitted bounded basis.",
        }
        receipt = {
            "phase": "PHASE5",
            "generated_at_utc": now_utc(),
            "execution_id": args.execution_id,
            "platform_run_id": platform_run_id,
            "verdict": "PHASE5_READY" if overall_pass else "HOLD_REMEDIATE",
            "next_phase": "PHASE6" if overall_pass else "PHASE5_REMEDIATE",
            "open_blockers": 0 if overall_pass else len(blockers),
            "blocker_ids": blockers,
        }
    except Exception as exc:  # noqa: BLE001
        blockers.append(str(exc))
        summary = {
            "phase": "PHASE5",
            "subphase": "PHASE5C_D",
            "generated_at_utc": now_utc(),
            "execution_id": args.execution_id,
            "overall_pass": False,
            "blocker_ids": blockers,
            "notes": notes,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        receipt = {
            "phase": "PHASE5",
            "generated_at_utc": now_utc(),
            "execution_id": args.execution_id,
            "verdict": "HOLD_REMEDIATE",
            "next_phase": "PHASE5_REMEDIATE",
            "open_blockers": len(blockers),
            "blocker_ids": blockers,
        }
        dump_json(summary_path, summary)
        dump_json(receipt_path, receipt)
        raise SystemExit(1)

    dump_json(summary_path, summary)
    dump_json(receipt_path, receipt)


if __name__ == "__main__":
    main()
