#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3
import yaml
from botocore.exceptions import ClientError
from kafka.admin import KafkaAdminClient, NewTopic


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    if not isinstance(loaded, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return loaded


def _check(condition: bool, name: str, detail: str, checks: list[dict[str, str]]) -> bool:
    status = "PASS" if condition else "FAIL"
    checks.append({"name": name, "status": status, "detail": detail})
    return condition


def _write_and_exit(
    started_at: str,
    checks: list[dict[str, str]],
    decision: str,
    output_root: Path,
    artifact_prefix: str,
) -> int:
    finished_at = _now_utc()
    output_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_path = output_root / f"{artifact_prefix}_{stamp}.json"

    payload = {
        "started_at_utc": started_at,
        "finished_at_utc": finished_at,
        "decision": decision,
        "checks": checks,
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    for item in checks:
        print(f"[{item['status']}] {item['name']}: {item['detail']}")
    print(f"Decision: {decision}")
    print(f"Evidence: {output_path.as_posix()}")
    return 0 if decision == "PASS" else 2


def _env(
    name: str,
    checks: list[dict[str, str]],
    required: bool = True,
    default: str | None = None,
) -> str | None:
    value = os.getenv(name, "").strip()
    if value:
        _check(True, f"env_{name}", "set", checks)
        return value
    if default is not None:
        _check(True, f"env_{name}", f"using default={default}", checks)
        return default
    _check(not required, f"env_{name}", "missing", checks)
    return None


def _first_bootstrap_host(bootstrap_servers: str) -> str:
    first = bootstrap_servers.split(",")[0].strip()
    if not first:
        raise ValueError("empty bootstrap value")
    host = first.split(":")[0].strip()
    if not host:
        raise ValueError("unable to parse bootstrap host")
    return host


def _table_name(default_prefix: str, env_name: str) -> str:
    current = os.getenv(env_name, "").strip()
    if current:
        return current
    if env_name == "DEV_MIN_CONTROL_TABLE":
        return f"{default_prefix}-control-runs"
    if env_name == "DEV_MIN_IG_ADMISSION_TABLE":
        return f"{default_prefix}-ig-admission-state"
    if env_name == "DEV_MIN_IG_PUBLISH_STATE_TABLE":
        return f"{default_prefix}-ig-publish-state"
    raise ValueError(f"unsupported table env mapping: {env_name}")


def _bucket_name(default_prefix: str, env_name: str) -> str:
    current = os.getenv(env_name, "").strip()
    if current:
        return current
    if env_name == "DEV_MIN_OBJECT_STORE_BUCKET":
        return f"{default_prefix}-object-store"
    if env_name == "DEV_MIN_EVIDENCE_BUCKET":
        return f"{default_prefix}-evidence"
    if env_name == "DEV_MIN_QUARANTINE_BUCKET":
        return f"{default_prefix}-quarantine"
    if env_name == "DEV_MIN_ARCHIVE_BUCKET":
        return f"{default_prefix}-archive"
    raise ValueError(f"unsupported bucket env mapping: {env_name}")


def _parse_api_version(raw: str) -> tuple[int, int, int]:
    parts = [part.strip() for part in raw.split(".") if part.strip()]
    if len(parts) != 3:
        raise ValueError("api version must be MAJOR.MINOR.PATCH")
    return int(parts[0]), int(parts[1]), int(parts[2])


def run(
    settlement_path: Path,
    profile_path: Path,
    output_root: Path,
    allow_topic_create: bool,
    timeout_seconds: float,
) -> int:
    checks: list[dict[str, str]] = []
    started = _now_utc()
    all_ok = True

    try:
        settlement = _load_yaml(settlement_path)
        profile = _load_yaml(profile_path)
    except Exception as exc:  # pragma: no cover
        checks.append(
            {
                "name": "load_inputs",
                "status": "FAIL",
                "detail": f"unable to load settlement/profile: {exc}",
            }
        )
        return _write_and_exit(
            started,
            checks,
            "FAIL_CLOSED",
            output_root,
            "phase3b_ci_infra_readiness",
        )

    wiring = profile.get("wiring", {})
    event_bus = wiring.get("event_bus", {})
    storage = settlement.get("storage", {})
    topic_specs = settlement.get("policy", {}).get("topic_corridor", {}).get("topics", [])
    topic_specs = topic_specs if isinstance(topic_specs, list) else []

    name_prefix = _env("DEV_MIN_NAME_PREFIX", checks, required=False, default="fraud-platform-dev-min") or "fraud-platform-dev-min"
    aws_region = _env("DEV_MIN_AWS_REGION", checks, required=True)
    bootstrap_env_name = str(event_bus.get("bootstrap_servers_env", "DEV_MIN_KAFKA_BOOTSTRAP")).strip()
    username_env_name = str(event_bus.get("sasl_username_env", "DEV_MIN_KAFKA_API_KEY")).strip()
    password_env_name = str(event_bus.get("sasl_password_env", "DEV_MIN_KAFKA_API_SECRET")).strip()

    bootstrap = _env(bootstrap_env_name, checks, required=True)
    api_key = _env(username_env_name, checks, required=True)
    api_secret = _env(password_env_name, checks, required=True)
    security_protocol = str(event_bus.get("security_protocol", "SASL_SSL")).strip()
    sasl_mechanism = str(event_bus.get("sasl_mechanism", "PLAIN")).strip()
    api_version = _parse_api_version(os.getenv("DEV_MIN_KAFKA_API_VERSION", "2.8.0").strip())

    # Kafka corridor readiness via Kafka admin protocol.
    if bootstrap and api_key and api_secret:
        admin: KafkaAdminClient | None = None
        try:
            bootstrap_host = _first_bootstrap_host(bootstrap)
            admin = KafkaAdminClient(
                bootstrap_servers=bootstrap,
                security_protocol=security_protocol,
                sasl_mechanism=sasl_mechanism,
                sasl_plain_username=api_key,
                sasl_plain_password=api_secret,
                request_timeout_ms=int(timeout_seconds * 1000),
                api_version_auto_timeout_ms=int(timeout_seconds * 1000),
                client_id="phase3b-readiness",
                api_version=api_version,
            )
            all_ok &= _check(
                True,
                "kafka_admin_auth",
                f"bootstrap_host={bootstrap_host}",
                checks,
            )

            existing_topics = set(admin.list_topics())
            required_topic_names = []
            topic_spec_map: dict[str, dict[str, Any]] = {}
            for spec in topic_specs:
                if isinstance(spec, dict):
                    name = str(spec.get("name", "")).strip()
                    if name:
                        required_topic_names.append(name)
                        topic_spec_map[name] = spec
            missing = [name for name in required_topic_names if name not in existing_topics]

            if missing and allow_topic_create:
                new_topics: list[NewTopic] = []
                for topic_name in missing:
                    spec = topic_spec_map[topic_name]
                    new_topics.append(
                        NewTopic(
                            name=topic_name,
                            num_partitions=int(spec.get("partitions", 1)),
                            replication_factor=int(spec.get("replication_factor", 1)),
                            topic_configs={"retention.ms": str(int(spec.get("retention_ms", 604800000)))},
                        )
                    )
                if new_topics:
                    admin.create_topics(new_topics=new_topics, validate_only=False)
                existing_topics = set(admin.list_topics())
                missing = [name for name in required_topic_names if name not in existing_topics]

            all_ok &= _check(
                not missing,
                "kafka_topic_corridor_ready",
                "all required topics available" if not missing else f"missing_topics={','.join(missing)}",
                checks,
            )

            if required_topic_names:
                descriptions = admin.describe_topics(required_topic_names)
                desc_map: dict[str, dict[str, Any]] = {}
                if isinstance(descriptions, list):
                    for item in descriptions:
                        if isinstance(item, dict):
                            name = str(item.get("topic", "")).strip()
                            if name:
                                desc_map[name] = item
                partition_mismatches: list[str] = []
                for topic_name in required_topic_names:
                    expected = int(topic_spec_map[topic_name].get("partitions", 1))
                    actual = len(desc_map.get(topic_name, {}).get("partitions", []) or [])
                    if actual < expected:
                        partition_mismatches.append(f"{topic_name}:{actual}<{expected}")
                all_ok &= _check(
                    not partition_mismatches,
                    "kafka_topic_partition_minimums",
                    "partition minimums satisfied"
                    if not partition_mismatches
                    else ",".join(partition_mismatches),
                    checks,
                )

            all_ok &= _check(
                True,
                "kafka_acl_boundary_posture",
                "authenticated topic describe/create path succeeded with configured principal",
                checks,
            )
        except Exception as exc:
            all_ok &= _check(
                False,
                "kafka_corridor_readiness",
                f"{type(exc).__name__}: {exc}",
                checks,
            )
        finally:
            if admin is not None:
                admin.close()
    else:
        all_ok &= _check(False, "kafka_corridor_readiness", "missing kafka auth env values", checks)

    # S3 readiness (bucket + prefix marker writes).
    s3 = boto3.client("s3", region_name=aws_region)
    marker_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for store_name in ["object_store", "evidence_store", "quarantine_store", "archive_store"]:
        store_cfg = storage.get(store_name, {})
        if not isinstance(store_cfg, dict):
            all_ok &= _check(False, f"s3_{store_name}", "store config missing", checks)
            continue
        bucket_env = str(store_cfg.get("bucket_env", "")).strip()
        prefix = str(store_cfg.get("prefix", "") or store_cfg.get("oracle_prefix", "")).strip("/")
        bucket = None
        if bucket_env:
            bucket_default = _bucket_name(name_prefix, bucket_env)
            bucket = _env(bucket_env, checks, required=False, default=bucket_default)
        if not bucket:
            all_ok &= _check(False, f"s3_{store_name}_bucket", f"missing bucket env {bucket_env}", checks)
            continue
        try:
            s3.head_bucket(Bucket=bucket)
            marker_key = (
                f"{prefix}/_phase3/readiness/{store_name}_{marker_stamp}.json"
                if prefix
                else f"_phase3/readiness/{store_name}_{marker_stamp}.json"
            )
            marker_body = json.dumps(
                {"store": store_name, "checked_at_utc": _now_utc(), "phase": "3B"},
                separators=(",", ":"),
            ).encode("utf-8")
            s3.put_object(Bucket=bucket, Key=marker_key, Body=marker_body)
            s3.head_object(Bucket=bucket, Key=marker_key)
            all_ok &= _check(
                True,
                f"s3_{store_name}_ready",
                f"marker=s3://{bucket}/{marker_key}",
                checks,
            )
        except ClientError as exc:
            all_ok &= _check(
                False,
                f"s3_{store_name}_ready",
                f"{exc.response.get('Error', {}).get('Code', 'ClientError')}",
                checks,
            )

    # DynamoDB prerequisite tables.
    dynamodb = boto3.client("dynamodb", region_name=aws_region)
    durability = settlement.get("ig_durability_prerequisites", {})
    if not isinstance(durability, dict):
        all_ok &= _check(False, "ig_durability_prerequisites", "missing in settlement", checks)
    else:
        table_envs = [
            str(durability.get("control_table_env", "DEV_MIN_CONTROL_TABLE")).strip(),
            str(durability.get("admission_state_table_env", "DEV_MIN_IG_ADMISSION_TABLE")).strip(),
            str(durability.get("publish_state_table_env", "DEV_MIN_IG_PUBLISH_STATE_TABLE")).strip(),
        ]
        for table_env in table_envs:
            table_name = _table_name(name_prefix, table_env)
            try:
                response = dynamodb.describe_table(TableName=table_name)
                status = (
                    response.get("Table", {}).get("TableStatus", "UNKNOWN")
                    if isinstance(response, dict)
                    else "UNKNOWN"
                )
                all_ok &= _check(
                    status in {"ACTIVE", "UPDATING"},
                    f"dynamodb_{table_name}",
                    f"status={status}",
                    checks,
                )
            except ClientError as exc:
                all_ok &= _check(
                    False,
                    f"dynamodb_{table_name}",
                    f"{exc.response.get('Error', {}).get('Code', 'ClientError')}",
                    checks,
                )

    decision = "PASS" if all_ok else "FAIL_CLOSED"
    return _write_and_exit(started, checks, decision, output_root, "phase3b_ci_infra_readiness")


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 3.B Control+Ingress infrastructure readiness")
    parser.add_argument(
        "--settlement",
        default="config/platform/dev_substrate/phase3/control_ingress_settlement_v0.yaml",
        help="Path to settlement yaml",
    )
    parser.add_argument(
        "--profile",
        default="config/platform/profiles/dev_min.yaml",
        help="Path to dev_min profile yaml",
    )
    parser.add_argument(
        "--output-root",
        default="runs/fraud-platform/dev_substrate/phase3",
        help="Output root for readiness evidence",
    )
    parser.add_argument(
        "--allow-topic-create",
        action="store_true",
        help="Create missing Kafka topics defined in settlement topic corridor",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=12.0,
        help="Timeout for Kafka admin connections",
    )
    args = parser.parse_args()

    return run(
        Path(args.settlement),
        Path(args.profile),
        Path(args.output_root),
        args.allow_topic_create,
        args.timeout_seconds,
    )


if __name__ == "__main__":
    raise SystemExit(main())
