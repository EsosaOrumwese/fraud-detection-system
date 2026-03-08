#!/usr/bin/env python3
"""Author PR3-S4 run-scoped SR artifacts on the active platform run."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import boto3
import yaml

from fraud_detection.scenario_runner.config import load_policy, load_wiring
from fraud_detection.scenario_runner.engine import LocalEngineInvoker
from fraud_detection.scenario_runner.models import RunRequest, RunWindow, ScenarioBinding
from fraud_detection.scenario_runner.runner import ScenarioRunner
from fraud_detection.scenario_runner.storage import build_object_store


REGISTRY_PATH = Path("docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md")
POLICY_PATH = Path("config/platform/sr/policy_v0.yaml")


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def parse_registry(path: Path) -> dict[str, str]:
    payload: dict[str, str] = {}
    pattern = re.compile(r"^\*\s*`([^`]+)`")
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(raw_line.strip())
        if not match:
            continue
        body = match.group(1)
        if "=" not in body:
            continue
        key, value = body.split("=", 1)
        payload[key.strip()] = value.strip().strip('"')
    return payload


def resolve_ssm(region: str, names: list[str]) -> dict[str, str]:
    ssm = boto3.client("ssm", region_name=region)
    response = ssm.get_parameters(Names=names, WithDecryption=True)
    values = {
        str(row.get("Name", "")).strip(): str(row.get("Value", "")).strip()
        for row in response.get("Parameters", [])
    }
    missing = [name for name in names if not values.get(name)]
    if missing:
        raise RuntimeError(f"PR3.B20_CONTROL_BOOTSTRAP_FAIL:MISSING_SSM:{','.join(missing)}")
    return values


def build_aurora_dsn(*, endpoint: str, username: str, password: str, db_name: str, port: int) -> str:
    return (
        f"postgresql://{quote_plus(username)}:{quote_plus(password)}@"
        f"{endpoint}:{int(port)}/{db_name}?sslmode=require"
    )


def sha256_json(payload: dict[str, Any]) -> str:
    data = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def resolve_scenario_id(root: Path, fallback: str) -> str:
    for name in (
        "g3a_correctness_wsp_runtime_manifest.json",
        "g3a_s3_wsp_runtime_manifest.json",
        "g3a_s2_wsp_runtime_manifest.json",
        "g3a_s1_wsp_runtime_manifest.json",
    ):
        path = root / name
        if not path.exists():
            continue
        try:
            payload = load_json(path)
            value = str((((payload.get("identity") or {}).get("scenario_id")) or "")).strip()
            if value:
                return value
        except Exception:
            continue
    return fallback


def write_wiring(
    *,
    path: Path,
    object_store_root: str,
    oracle_engine_run_root: str,
    authority_store_dsn: str,
    control_bus_topic: str,
    kafka_bootstrap_servers: str,
    aws_region: str,
) -> None:
    payload = {
        "profile_id": "dev_full_pr3_control_bootstrap",
        "object_store_root": object_store_root,
        "control_bus_topic": control_bus_topic,
        "control_bus_root": "runs/fraud-platform/control_bus",
        "control_bus_kind": "kafka",
        "engine_catalogue_path": "docs/model_spec/data-engine/interface_pack/engine_outputs.catalogue.yaml",
        "gate_map_path": "docs/model_spec/data-engine/interface_pack/engine_gates.map.yaml",
        "schema_root": "docs/model_spec/platform/contracts/scenario_runner",
        "engine_contracts_root": "docs/model_spec/data-engine/interface_pack/contracts",
        "oracle_engine_run_root": oracle_engine_run_root,
        "authority_store_dsn": authority_store_dsn,
        "s3_region": aws_region,
        "s3_path_style": False,
        "auth_mode": "disabled",
        "acceptance_mode": "dev_full",
        "execution_mode": "managed",
        "state_mode": "managed",
        "execution_identity_env": "GITHUB_RUN_ID",
        "control_bus_stream": kafka_bootstrap_servers,
        "control_bus_region": aws_region,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pr3-execution-id", required=True)
    parser.add_argument("--platform-run-id", required=True)
    parser.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/road_to_prod/run_control")
    parser.add_argument("--aws-region", default="eu-west-2")
    parser.add_argument("--scenario-id", default="baseline_v1")
    parser.add_argument("--bootstrap-summary-name", default="g3a_control_plane_bootstrap.json")
    parser.add_argument("--wiring-name", default="g3a_sr_wiring.dev_full.yaml")
    args = parser.parse_args()

    run_root = Path(args.run_control_root) / args.pr3_execution_id
    summary_path = run_root / args.bootstrap_summary_name
    wiring_path = run_root / args.wiring_name
    blockers: list[str] = []

    try:
        registry = parse_registry(REGISTRY_PATH)
        charter = load_json(run_root / "g3a_run_charter.active.json")
        ssm_values = resolve_ssm(
            args.aws_region,
            [
                str(registry["SSM_AURORA_ENDPOINT_PATH"]).strip(),
                str(registry["SSM_AURORA_USERNAME_PATH"]).strip(),
                str(registry["SSM_AURORA_PASSWORD_PATH"]).strip(),
            ],
        )
        object_store_root = f"s3://{str(registry['S3_OBJECT_STORE_BUCKET']).strip()}"
        oracle_engine_run_root = (
            f"{object_store_root}/"
            f"{str(registry['S3_ORACLE_RUN_PREFIX_PATTERN']).strip().format(oracle_source_namespace=registry['ORACLE_SOURCE_NAMESPACE'], oracle_engine_run_id=registry['ORACLE_ENGINE_RUN_ID'])}"
        ).rstrip("/")
        oracle_receipt_ref = f"{oracle_engine_run_root}/run_receipt.json"
        store = build_object_store(object_store_root, s3_region=args.aws_region, s3_path_style=False)
        oracle_receipt = store.read_json(oracle_receipt_ref.replace(f"{object_store_root}/", "", 1))
        scenario_id = resolve_scenario_id(run_root, args.scenario_id)
        authority_store_dsn = build_aurora_dsn(
            endpoint=ssm_values[str(registry["SSM_AURORA_ENDPOINT_PATH"]).strip()],
            username=ssm_values[str(registry["SSM_AURORA_USERNAME_PATH"]).strip()],
            password=ssm_values[str(registry["SSM_AURORA_PASSWORD_PATH"]).strip()],
            db_name=str(registry.get("AURORA_DB_NAME", "fraud_platform")).strip() or "fraud_platform",
            port=int(str(registry.get("AURORA_PORT", "5432")).strip() or "5432"),
        )
        write_wiring(
            path=wiring_path,
            object_store_root=object_store_root,
            oracle_engine_run_root=oracle_engine_run_root,
            authority_store_dsn=authority_store_dsn,
            control_bus_topic=str(registry["FP_BUS_CONTROL_V1"]).strip(),
            kafka_bootstrap_servers=str(registry["MSK_BOOTSTRAP_BROKERS_SASL_IAM"]).strip(),
            aws_region=args.aws_region,
        )

        request_identity = {
            "oracle_engine_run_root": oracle_engine_run_root,
            "manifest_fingerprint": str(oracle_receipt.get("manifest_fingerprint") or "").strip(),
            "parameter_hash": str(oracle_receipt.get("parameter_hash") or "").strip(),
            "seed": int(oracle_receipt.get("seed") or 0),
            "scenario_id": scenario_id,
            "window_start_ts_utc": str(((charter.get("mission_binding") or {}).get("window_start_ts_utc")) or "").strip(),
            "window_end_ts_utc": str(((charter.get("mission_binding") or {}).get("window_end_ts_utc")) or "").strip(),
            "traffic_output_ids": list((load_policy(POLICY_PATH).traffic_output_ids)),
        }
        missing_request_fields = [key for key, value in request_identity.items() if value in {"", [], None}]
        if missing_request_fields:
            raise RuntimeError(
                "PR3.B20_CONTROL_BOOTSTRAP_FAIL:MISSING_REQUEST_FIELDS:" + ",".join(sorted(missing_request_fields))
            )
        run_equivalence_key = sha256_json(request_identity)

        os.environ["PLATFORM_RUN_ID"] = str(args.platform_run_id).strip()
        os.environ["ACTIVE_PLATFORM_RUN_ID"] = str(args.platform_run_id).strip()
        os.environ["PLATFORM_STORE_ROOT"] = object_store_root
        os.environ["KAFKA_BOOTSTRAP_SERVERS"] = str(registry["MSK_BOOTSTRAP_BROKERS_SASL_IAM"]).strip()
        os.environ["KAFKA_SECURITY_PROTOCOL"] = "SASL_SSL"
        os.environ["KAFKA_SASL_MECHANISM"] = "OAUTHBEARER"
        os.environ["KAFKA_AWS_REGION"] = args.aws_region

        wiring = load_wiring(wiring_path)
        policy = load_policy(POLICY_PATH)
        runner = ScenarioRunner(
            wiring=wiring,
            policy=policy,
            engine_invoker=LocalEngineInvoker(default_engine_root=oracle_engine_run_root),
            run_prefix=str(args.platform_run_id).strip(),
        )
        response = runner.submit_run(
            RunRequest(
                run_equivalence_key=run_equivalence_key,
                manifest_fingerprint=str(request_identity["manifest_fingerprint"]),
                parameter_hash=str(request_identity["parameter_hash"]),
                seed=int(request_identity["seed"]),
                scenario=ScenarioBinding(scenario_id=scenario_id, scenario_set=None),
                window=RunWindow(
                    window_start_utc=datetime.fromisoformat(str(request_identity["window_start_ts_utc"]).replace("Z", "+00:00")),
                    window_end_utc=datetime.fromisoformat(str(request_identity["window_end_ts_utc"]).replace("Z", "+00:00")),
                    window_tz="UTC",
                ),
                engine_run_root=oracle_engine_run_root,
                output_ids=list(policy.traffic_output_ids),
                invoker="SYSTEM::pr3_s4_control_bootstrap",
            )
        )
        facts_view_ref = str(response.facts_view_ref or "").strip()
        status_ref = str(response.status_ref or "").strip()
        if not facts_view_ref or not status_ref:
            raise RuntimeError("PR3.B20_CONTROL_BOOTSTRAP_FAIL:SR_OUTPUT_REFS_MISSING")
        relative_facts_ref = facts_view_ref.replace(f"{object_store_root}/", "", 1)
        relative_status_ref = status_ref.replace(f"{object_store_root}/", "", 1)
        status_payload = store.read_json(relative_status_ref)
        facts_payload = store.read_json(relative_facts_ref)
        if str(status_payload.get("state") or "").strip().upper() != "READY":
            raise RuntimeError(f"PR3.B20_CONTROL_BOOTSTRAP_FAIL:SR_NOT_READY:{status_payload.get('state')}")
        scenario_run_id = str(facts_payload.get("run_id") or response.run_id or "").strip()
        if not scenario_run_id:
            raise RuntimeError("PR3.B20_CONTROL_BOOTSTRAP_FAIL:SCENARIO_RUN_ID_EMPTY")

        summary = {
            "phase": "PR3",
            "state": "S4",
            "generated_at_utc": now_utc(),
            "execution_id": args.pr3_execution_id,
            "platform_run_id": str(args.platform_run_id).strip(),
            "scenario_run_id": scenario_run_id,
            "scenario_id": scenario_id,
            "overall_pass": True,
            "blocker_ids": [],
            "wiring_ref": str(wiring_path),
            "oracle": {
                "oracle_engine_run_root": oracle_engine_run_root,
                "oracle_run_receipt_ref": oracle_receipt_ref,
                "manifest_fingerprint": request_identity["manifest_fingerprint"],
                "parameter_hash": request_identity["parameter_hash"],
                "seed": request_identity["seed"],
            },
            "run_window": {
                "window_start_ts_utc": request_identity["window_start_ts_utc"],
                "window_end_ts_utc": request_identity["window_end_ts_utc"],
            },
            "sr": {
                "run_equivalence_key": run_equivalence_key,
                "run_id": response.run_id,
                "state": str(response.state.value),
                "record_ref": response.record_ref,
                "status_ref": status_ref,
                "facts_view_ref": facts_view_ref,
            },
        }
    except Exception as exc:  # noqa: BLE001
        blockers.append(str(exc))
        summary = {
            "phase": "PR3",
            "state": "S4",
            "generated_at_utc": now_utc(),
            "execution_id": args.pr3_execution_id,
            "platform_run_id": str(args.platform_run_id).strip(),
            "scenario_run_id": "",
            "overall_pass": False,
            "blocker_ids": blockers,
            "error": str(exc),
        }
        dump_json(summary_path, summary)
        raise SystemExit(1)

    dump_json(summary_path, summary)


if __name__ == "__main__":
    main()
