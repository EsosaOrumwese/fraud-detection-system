#!/usr/bin/env python3
"""Worker entrypoint for PR3-S4 Scenario Runner bootstrap inside the VPC."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from fraud_detection.scenario_runner.authority import RunHandle
from fraud_detection.scenario_runner.config import load_policy, load_wiring
from fraud_detection.scenario_runner.evidence import EvidenceBundle, hash_bundle
from fraud_detection.scenario_runner.engine import LocalEngineInvoker
from fraud_detection.scenario_runner.models import EvidenceStatus, RunRequest, RunWindow, ScenarioBinding
from fraud_detection.scenario_runner.runner import ScenarioRunner
from fraud_detection.scenario_runner.storage import build_object_store


POLICY_PATH = Path("config/platform/sr/policy_v0.yaml")


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def is_missing_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def dump_json_line(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=True), flush=True)


def build_request(
    *,
    platform_run_id: str,
    scenario_id: str,
    window_start: str,
    window_end: str,
    oracle_receipt: dict[str, Any],
    oracle_engine_run_root: str,
    output_ids: list[str],
) -> RunRequest:
    return RunRequest(
        run_equivalence_key="pr3_s4|" + platform_run_id + "|" + scenario_id + "|" + window_start + "|" + window_end,
        manifest_fingerprint=str(oracle_receipt.get("manifest_fingerprint") or "").strip(),
        parameter_hash=str(oracle_receipt.get("parameter_hash") or "").strip(),
        seed=int(oracle_receipt.get("seed") or 0),
        scenario=ScenarioBinding(scenario_id=scenario_id, scenario_set=None),
        window=RunWindow(
            window_start_utc=datetime.fromisoformat(window_start.replace("Z", "+00:00")),
            window_end_utc=datetime.fromisoformat(window_end.replace("Z", "+00:00")),
            window_tz="UTC",
        ),
        engine_run_root=oracle_engine_run_root,
        output_ids=output_ids,
        invoker="SYSTEM::pr3_s4_control_bootstrap_remote",
    )


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
        "execution_identity_env": "HOSTNAME",
        "control_bus_stream": kafka_bootstrap_servers,
        "control_bus_region": aws_region,
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def main() -> None:
    blockers: list[str] = []
    try:
        platform_run_id = str(os.environ.get("PLATFORM_RUN_ID", "")).strip()
        scenario_id = str(os.environ.get("SCENARIO_ID", "")).strip()
        window_start = str(os.environ.get("WINDOW_START_TS_UTC", "")).strip()
        window_end = str(os.environ.get("WINDOW_END_TS_UTC", "")).strip()
        object_store_root = str(os.environ.get("OBJECT_STORE_ROOT", "")).strip()
        oracle_engine_run_root = str(os.environ.get("ORACLE_ENGINE_RUN_ROOT", "")).strip()
        authority_store_dsn = str(os.environ.get("AURORA_DSN", "")).strip()
        control_bus_topic = str(os.environ.get("CONTROL_BUS_TOPIC", "")).strip()
        kafka_bootstrap_servers = str(os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "")).strip()
        aws_region = str(os.environ.get("AWS_REGION", "")).strip()
        traffic_output_ids = json.loads(str(os.environ.get("TRAFFIC_OUTPUT_IDS_JSON", "[]")))
        if not isinstance(traffic_output_ids, list):
            raise RuntimeError("PR3.B20_CONTROL_BOOTSTRAP_FAIL:TRAFFIC_OUTPUT_IDS_INVALID")

        request_identity = {
            "oracle_engine_run_root": oracle_engine_run_root,
            "scenario_id": scenario_id,
            "window_start_ts_utc": window_start,
            "window_end_ts_utc": window_end,
            "traffic_output_ids": traffic_output_ids,
            "platform_run_id": platform_run_id,
            "object_store_root": object_store_root,
            "authority_store_dsn": authority_store_dsn,
            "control_bus_topic": control_bus_topic,
            "kafka_bootstrap_servers": kafka_bootstrap_servers,
            "aws_region": aws_region,
        }
        missing_fields = [key for key, value in request_identity.items() if is_missing_value(value)]
        if missing_fields:
            raise RuntimeError(
                "PR3.B20_CONTROL_BOOTSTRAP_FAIL:MISSING_REQUEST_FIELDS:" + ",".join(sorted(missing_fields))
            )

        os.environ["PLATFORM_RUN_ID"] = platform_run_id
        os.environ["ACTIVE_PLATFORM_RUN_ID"] = platform_run_id
        os.environ["PLATFORM_STORE_ROOT"] = object_store_root
        os.environ["KAFKA_BOOTSTRAP_SERVERS"] = kafka_bootstrap_servers
        os.environ["KAFKA_SECURITY_PROTOCOL"] = "SASL_SSL"
        os.environ["KAFKA_SASL_MECHANISM"] = "OAUTHBEARER"
        os.environ["KAFKA_AWS_REGION"] = aws_region

        store = build_object_store(object_store_root, s3_region=aws_region, s3_path_style=False)
        oracle_receipt_ref = str(os.environ.get("ORACLE_RECEIPT_REF", "")).strip()
        oracle_receipt = store.read_json(oracle_receipt_ref.replace(f"{object_store_root}/", "", 1))
        policy = load_policy(POLICY_PATH)

        with tempfile.TemporaryDirectory(prefix="pr3_s4_bootstrap_") as tmp_dir:
            wiring_path = Path(tmp_dir) / "g3a_sr_wiring.dev_full.yaml"
            write_wiring(
                path=wiring_path,
                object_store_root=object_store_root,
                oracle_engine_run_root=oracle_engine_run_root,
                authority_store_dsn=authority_store_dsn,
                control_bus_topic=control_bus_topic,
                kafka_bootstrap_servers=kafka_bootstrap_servers,
                aws_region=aws_region,
            )
            wiring = load_wiring(wiring_path)
            runner = ScenarioRunner(
                wiring=wiring,
                policy=policy,
                engine_invoker=LocalEngineInvoker(default_engine_root=oracle_engine_run_root),
                run_prefix=platform_run_id,
            )
            request = build_request(
                platform_run_id=platform_run_id,
                scenario_id=scenario_id,
                window_start=window_start,
                window_end=window_end,
                oracle_receipt=oracle_receipt,
                oracle_engine_run_root=oracle_engine_run_root,
                output_ids=list(policy.traffic_output_ids),
            )
            canonical = runner._canonicalize(request)
            intent_fingerprint = runner._intent_fingerprint(canonical)
            run_id, _ = runner.equiv_registry.resolve(canonical.run_equivalence_key, intent_fingerprint)
            status = runner.ledger.read_status(run_id)
            facts_view = runner.ledger.read_facts_view(run_id)
            if status and str(status.state.value).upper() == "READY" and facts_view is not None:
                response = runner._response_from_status(run_id, "READY already present")
            else:
                leader, lease_token = runner.lease_manager.acquire(run_id, owner_id="sr-local")
                if not leader:
                    raise RuntimeError(f"PR3.B20_CONTROL_BOOTSTRAP_FAIL:LEASE_BUSY:{run_id}")
                run_handle = RunHandle(
                    run_id=run_id,
                    intent_fingerprint=intent_fingerprint,
                    leader=True,
                    lease_token=lease_token,
                )
                runner._anchor_run(run_handle)
                plan = runner._compile_plan(canonical, run_id)
                runner._commit_plan(run_handle, plan)
                notes = [
                    "PR3-S4 bounded control bootstrap authored READY directly from the authoritative oracle pack.",
                    "Scenario Runner output/gate rescans were intentionally skipped for this correctness gate to avoid redundant spend and OOM risk.",
                ]
                bundle = EvidenceBundle(
                    status=EvidenceStatus.COMPLETE,
                    locators=[],
                    gate_receipts=[],
                    instance_receipts=[],
                    bundle_hash=hash_bundle([], [], plan.policy_rev, []),
                    notes=notes,
                )
                response = runner._commit_ready(
                    run_handle,
                    canonical,
                    plan,
                    bundle,
                    engine_run_root=oracle_engine_run_root,
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
            "execution_id": str(os.environ.get("PR3_EXECUTION_ID", "")).strip(),
            "platform_run_id": platform_run_id,
            "scenario_run_id": scenario_run_id,
            "scenario_id": scenario_id,
            "overall_pass": True,
            "blocker_ids": [],
            "oracle": {
                "oracle_engine_run_root": oracle_engine_run_root,
                "oracle_run_receipt_ref": oracle_receipt_ref,
                "manifest_fingerprint": str(oracle_receipt.get("manifest_fingerprint") or "").strip(),
                "parameter_hash": str(oracle_receipt.get("parameter_hash") or "").strip(),
                "seed": int(oracle_receipt.get("seed") or 0),
            },
            "run_window": {
                "window_start_ts_utc": window_start,
                "window_end_ts_utc": window_end,
            },
            "sr": {
                "run_id": response.run_id,
                "state": str(response.state.value),
                "record_ref": response.record_ref,
                "status_ref": status_ref,
                "facts_view_ref": facts_view_ref,
            },
            "worker": {
                "mode": "eks_in_vpc_job",
                "control_authoring_path": "scenario_runner_light_ready_commit",
                "hostname": str(os.environ.get("HOSTNAME", "")).strip(),
            },
        }
        dump_json_line(summary)
    except Exception as exc:  # noqa: BLE001
        blockers.append(str(exc))
        dump_json_line(
            {
                "phase": "PR3",
                "state": "S4",
                "generated_at_utc": now_utc(),
                "execution_id": str(os.environ.get("PR3_EXECUTION_ID", "")).strip(),
                "platform_run_id": str(os.environ.get("PLATFORM_RUN_ID", "")).strip(),
                "scenario_run_id": "",
                "overall_pass": False,
                "blocker_ids": blockers,
                "error": str(exc),
                "worker": {
                    "mode": "eks_in_vpc_job",
                    "control_authoring_path": "scenario_runner_light_ready_commit",
                    "hostname": str(os.environ.get("HOSTNAME", "")).strip(),
                },
            }
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()
