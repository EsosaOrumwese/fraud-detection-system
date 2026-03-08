#!/usr/bin/env python3
"""Materialize PR3-S4 schema evolution drill evidence."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from fraud_detection.action_layer.contracts import ActionOutcome
from fraud_detection.action_layer.publish import build_action_outcome_envelope
from fraud_detection.ingestion_gate.config import SchemaPolicy
from fraud_detection.ingestion_gate.schema import SchemaEnforcer
from fraud_detection.ingestion_gate.schemas import SchemaRegistry


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def dump_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="PR3-S4 schema evolution drill")
    ap.add_argument("--run-control-root", default="runs/dev_substrate/dev_full/road_to_prod/run_control")
    ap.add_argument("--pr3-execution-id", required=True)
    ap.add_argument("--state-id", default="S4")
    args = ap.parse_args()

    root = Path(args.run_control_root) / args.pr3_execution_id
    manifest = json.loads((root / "g3a_s4_wsp_runtime_manifest.json").read_text(encoding="utf-8"))
    platform_run_id = str((((manifest.get("identity") or {}).get("platform_run_id")) or "")).strip()
    scenario_run_id = str((((manifest.get("identity") or {}).get("scenario_run_id")) or "")).strip()

    enforcer = SchemaEnforcer(
        envelope_registry=SchemaRegistry(Path("docs/model_spec/data-engine/interface_pack/contracts")),
        payload_registry_root=Path("."),
        policy=SchemaPolicy.load(Path("config/platform/ig/schema_policy_v0.yaml")),
    )

    payload = {
        "outcome_id": "1" * 32,
        "decision_id": "2" * 32,
        "action_id": "3" * 32,
        "action_kind": "txn_disposition_publish",
        "status": "EXECUTED",
        "idempotency_key": "merchant_42:evt_123:publish",
        "actor_principal": "SYSTEM::decision_fabric",
        "origin": "DF",
        "authz_policy_rev": {"policy_id": "al.policy.v0", "revision": "r1"},
        "run_config_digest": "4" * 64,
        "pins": {
            "platform_run_id": platform_run_id,
            "scenario_run_id": scenario_run_id,
            "manifest_fingerprint": "6" * 64,
            "parameter_hash": "7" * 64,
            "scenario_id": "scenario.v0",
            "seed": 9,
            "run_id": "8" * 32,
        },
        "completed_at_utc": "2026-03-08T14:00:00.000000Z",
        "attempt_seq": 1,
        "reason": "EXECUTED",
        "outcome_payload": {"terminal_state": "EXECUTED"},
    }
    compatible = build_action_outcome_envelope(ActionOutcome.from_payload(payload))
    incompatible = dict(compatible)
    incompatible["schema_version"] = "v999"

    compatible_ok = True
    incompatible_blocked = False
    compatible_error = ""
    incompatible_error = ""

    try:
        enforcer.validate_envelope(compatible)
        enforcer.validate_payload(str(compatible["event_type"]), compatible)
    except Exception as exc:  # noqa: BLE001
        compatible_ok = False
        compatible_error = f"{type(exc).__name__}:{str(exc)[:256]}"

    try:
        enforcer.validate_envelope(incompatible)
        enforcer.validate_payload(str(incompatible["event_type"]), incompatible)
    except Exception as exc:  # noqa: BLE001
        incompatible_blocked = True
        incompatible_error = f"{type(exc).__name__}:{str(exc)[:256]}"

    overall_pass = compatible_ok and incompatible_blocked
    payload_out = {
        "drill_id": "schema_evolution",
        "phase": "PR3",
        "state": args.state_id,
        "generated_at_utc": now_utc(),
        "execution_id": args.pr3_execution_id,
        "platform_run_id": platform_run_id,
        "scenario": "Compatible canonical internal event must validate; incompatible schema-version mutation must fail closed.",
        "expected_behavior": "Schema-compatible payload passes IG schema enforcement, incompatible schema-version is blocked before publish.",
        "observed_outcome": {
            "compatible_ok": compatible_ok,
            "compatible_error": compatible_error,
            "incompatible_blocked": incompatible_blocked,
            "incompatible_error": incompatible_error,
            "event_type": compatible["event_type"],
        },
        "overall_pass": overall_pass,
        "blocker_ids": [] if overall_pass else ["PR3.S4.B26_SCHEMA_DRILL_UNEXECUTED"],
    }
    dump_json(root / "g3a_drill_schema_evolution.json", payload_out)
    print(json.dumps(payload_out, indent=2))


if __name__ == "__main__":
    main()
