#!/usr/bin/env python3
"""
M2.F Kafka/Confluent topic readiness verification.

Fail-closed checks:
1. Resolve bootstrap/key/secret from pinned SSM paths.
2. Authenticate to Kafka using SASL_SSL/PLAIN.
3. Fetch topic metadata and verify required topic set.
4. Emit non-secret evidence snapshot.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import subprocess
import sys
from typing import Any

DEFAULT_REQUIRED_TOPICS = [
    "fp.bus.control.v1",
    "fp.bus.traffic.fraud.v1",
    "fp.bus.context.arrival_events.v1",
    "fp.bus.context.arrival_entities.v1",
    "fp.bus.context.flow_anchor.fraud.v1",
    "fp.bus.rtdl.v1",
    "fp.bus.audit.v1",
    "fp.bus.case.triggers.v1",
    "fp.bus.labels.events.v1",
]


def run_json(cmd: list[str]) -> dict[str, Any]:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"Command failed ({proc.returncode}): {' '.join(cmd)}\n{proc.stderr.strip()}"
        )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Command returned non-JSON output: {' '.join(cmd)}\n{proc.stdout[:300]}"
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"Unexpected JSON shape from command: {' '.join(cmd)}")
    return payload


def get_ssm_parameter(name: str, region: str) -> tuple[str, int]:
    payload = run_json(
        [
            "aws",
            "ssm",
            "get-parameter",
            "--name",
            name,
            "--with-decryption",
            "--region",
            region,
            "--output",
            "json",
        ]
    )
    parameter = payload.get("Parameter", {})
    value = str(parameter.get("Value", ""))
    version = int(parameter.get("Version", 0))
    if not value:
        raise RuntimeError(f"SSM parameter is empty: {name}")
    return value, version


def normalize_required_topics(raw: str) -> list[str]:
    if not raw.strip():
        return DEFAULT_REQUIRED_TOPICS.copy()
    out = [item.strip() for item in raw.split(",") if item.strip()]
    if not out:
        raise ValueError("required_topics parsed to empty list")
    return out


def upload_if_requested(local_path: pathlib.Path, s3_uri: str) -> None:
    if not s3_uri:
        return
    proc = subprocess.run(
        ["aws", "s3", "cp", str(local_path), s3_uri], capture_output=True, text=True
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"Failed to upload evidence to S3 ({proc.returncode}): {proc.stderr.strip()}"
        )


def read_topics_with_confluent_kafka(
    bootstrap: str, api_key: str, api_secret: str, timeout_sec: int = 10
) -> set[str]:
    from confluent_kafka import admin  # type: ignore[import-not-found]

    client = admin.AdminClient(
        {
            "bootstrap.servers": bootstrap,
            "security.protocol": "SASL_SSL",
            "sasl.mechanism": "PLAIN",
            "sasl.username": api_key,
            "sasl.password": api_secret,
            "socket.timeout.ms": timeout_sec * 1000,
        }
    )
    metadata = client.list_topics(timeout=timeout_sec)
    return set(metadata.topics.keys())


def read_topics_with_kafka_python(
    bootstrap: str, api_key: str, api_secret: str, timeout_sec: int = 10
) -> set[str]:
    from kafka import KafkaAdminClient

    client = KafkaAdminClient(
        bootstrap_servers=[bootstrap],
        security_protocol="SASL_SSL",
        sasl_mechanism="PLAIN",
        sasl_plain_username=api_key,
        sasl_plain_password=api_secret,
        request_timeout_ms=timeout_sec * 1000,
        api_version_auto_timeout_ms=7000,
    )
    try:
        return set(client.list_topics())
    finally:
        client.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aws-region", default="eu-west-2")
    parser.add_argument(
        "--bootstrap-ssm-path",
        default="/fraud-platform/dev_min/confluent/bootstrap",
    )
    parser.add_argument(
        "--api-key-ssm-path",
        default="/fraud-platform/dev_min/confluent/api_key",
    )
    parser.add_argument(
        "--api-secret-ssm-path",
        default="/fraud-platform/dev_min/confluent/api_secret",
    )
    parser.add_argument(
        "--required-topics",
        default="",
        help="Comma-separated list. Default: Spine Green v0 required topics.",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Default: runs/dev_substrate/m2_f/<timestamp>/topic_readiness_snapshot.json",
    )
    parser.add_argument(
        "--evidence-s3-uri",
        default="",
        help="Optional s3:// URI for uploading the generated snapshot.",
    )
    args = parser.parse_args()

    now = dt.datetime.now(dt.timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    required_topics = normalize_required_topics(args.required_topics)

    output_path = (
        pathlib.Path(args.output)
        if args.output
        else pathlib.Path(f"runs/dev_substrate/m2_f/{stamp}/topic_readiness_snapshot.json")
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    snapshot: dict[str, Any] = {
        "phase": "M2.F",
        "captured_at_utc": now.isoformat(),
        "lane": "",
        "ssm_paths": {
            "bootstrap": args.bootstrap_ssm_path,
            "api_key": args.api_key_ssm_path,
            "api_secret": args.api_secret_ssm_path,
        },
        "ssm_versions": {},
        "bootstrap_present": False,
        "auth_present": False,
        "connectivity_pass": False,
        "topics_required": required_topics,
        "topics_present": [],
        "topics_missing": [],
        "acl_readiness_mode": "metadata_visibility_via_authenticated_admin_client",
        "errors": [],
        "overall_pass": False,
    }

    try:
        bootstrap, bootstrap_version = get_ssm_parameter(
            args.bootstrap_ssm_path, args.aws_region
        )
        api_key, api_key_version = get_ssm_parameter(args.api_key_ssm_path, args.aws_region)
        api_secret, api_secret_version = get_ssm_parameter(
            args.api_secret_ssm_path, args.aws_region
        )
        snapshot["ssm_versions"] = {
            "bootstrap": bootstrap_version,
            "api_key": api_key_version,
            "api_secret": api_secret_version,
        }
        snapshot["bootstrap_present"] = True
        snapshot["auth_present"] = True
    except Exception as exc:  # noqa: BLE001
        snapshot["errors"].append(f"ssm_resolution_failed: {exc}")
        output_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
        print(str(output_path))
        return 2

    try:
        topics = read_topics_with_confluent_kafka(bootstrap, api_key, api_secret)
        snapshot["lane"] = "kafka_admin_protocol_python_confluent_kafka"
        snapshot["connectivity_pass"] = True
        snapshot["topics_present"] = [t for t in required_topics if t in topics]
        snapshot["topics_missing"] = [t for t in required_topics if t not in topics]
    except Exception as exc:  # noqa: BLE001
        snapshot["errors"].append(f"confluent_kafka_failed: {exc}")
        try:
            topics = read_topics_with_kafka_python(bootstrap, api_key, api_secret)
            snapshot["lane"] = "kafka_admin_protocol_python_kafka_python_fallback"
            snapshot["connectivity_pass"] = True
            snapshot["topics_present"] = [t for t in required_topics if t in topics]
            snapshot["topics_missing"] = [t for t in required_topics if t not in topics]
        except Exception as fallback_exc:  # noqa: BLE001
            snapshot["errors"].append(f"kafka_python_fallback_failed: {fallback_exc}")

    snapshot["overall_pass"] = bool(
        snapshot["bootstrap_present"]
        and snapshot["auth_present"]
        and snapshot["connectivity_pass"]
        and not snapshot["topics_missing"]
    )

    output_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")

    if args.evidence_s3_uri:
        try:
            upload_if_requested(output_path, args.evidence_s3_uri)
        except Exception as exc:  # noqa: BLE001
            snapshot["errors"].append(f"evidence_upload_failed: {exc}")
            snapshot["overall_pass"] = False
            output_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
            print(str(output_path))
            print("overall_pass=false")
            return 3

    print(str(output_path))
    print(f"overall_pass={'true' if snapshot['overall_pass'] else 'false'}")
    return 0 if snapshot["overall_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
