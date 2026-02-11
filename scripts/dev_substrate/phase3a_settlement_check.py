#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


REQUIRED_SETTLEMENT_KEYS = [
    "version",
    "settlement_id",
    "scope",
    "policy",
    "storage",
    "ig_durability_prerequisites",
    "auth_capability_boundary",
    "validation_ladder",
    "performance_targets",
    "cost_targets",
]


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


def run(settlement_path: Path, profile_path: Path, output_root: Path) -> int:
    checks: list[dict[str, str]] = []
    started = _now_utc()

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
        decision = "FAIL_CLOSED"
        return _write_and_exit(started, checks, decision, output_root, "phase3a_settlement_check")

    all_ok = True

    for key in REQUIRED_SETTLEMENT_KEYS:
        all_ok &= _check(
            key in settlement,
            f"settlement_key_{key}",
            "present" if key in settlement else "missing",
            checks,
        )

    wiring = profile.get("wiring", {})
    event_bus = wiring.get("event_bus", {})
    settlement_policy = settlement.get("policy", {})

    all_ok &= _check(
        wiring.get("event_bus_kind") == "kafka",
        "profile_event_bus_kind",
        f"event_bus_kind={wiring.get('event_bus_kind')}",
        checks,
    )

    all_ok &= _check(
        settlement_policy.get("partitioning_profile_id")
        == profile.get("policy", {}).get("partitioning_profile_id"),
        "partitioning_profile_alignment",
        "settlement and profile partitioning_profile_id aligned",
        checks,
    )

    all_ok &= _check(
        bool(settlement_policy.get("require_gate_pass")) == bool(profile.get("policy", {}).get("require_gate_pass")),
        "require_gate_pass_alignment",
        "settlement and profile require_gate_pass aligned",
        checks,
    )

    corridor_topics = {
        str(topic.get("name")): topic
        for topic in settlement_policy.get("topic_corridor", {}).get("topics", [])
        if isinstance(topic, dict)
    }

    profile_topic_values = {
        str(event_bus.get("topic_control", "")),
        str(event_bus.get("topic_audit", "")),
        str(event_bus.get("topic_traffic_fraud", "")),
        str(event_bus.get("topic_context_arrival_events", "")),
        str(event_bus.get("topic_context_arrival_entities", "")),
        str(event_bus.get("topic_context_flow_anchor_fraud", "")),
    }
    profile_topic_values.discard("")

    all_ok &= _check(
        profile_topic_values.issubset(set(corridor_topics.keys())),
        "topic_corridor_alignment",
        "all dev_min profile topics are present in settlement topic corridor",
        checks,
    )

    storage = settlement.get("storage", {})
    all_ok &= _check(
        storage.get("evidence_store", {}).get("prefix") == wiring.get("evidence_store", {}).get("prefix"),
        "evidence_prefix_alignment",
        "settlement/profile evidence prefix alignment",
        checks,
    )
    all_ok &= _check(
        storage.get("quarantine_store", {}).get("prefix") == wiring.get("quarantine_store", {}).get("prefix"),
        "quarantine_prefix_alignment",
        "settlement/profile quarantine prefix alignment",
        checks,
    )
    all_ok &= _check(
        storage.get("archive_store", {}).get("prefix") == wiring.get("archive_store", {}).get("prefix"),
        "archive_prefix_alignment",
        "settlement/profile archive prefix alignment",
        checks,
    )

    carry_forward = settlement.get("local_parity_carry_forward_refs", [])
    carry_ok = True
    for ref in carry_forward:
        if not Path(ref).exists():
            carry_ok = False
            checks.append(
                {
                    "name": "local_parity_carry_forward_ref",
                    "status": "FAIL",
                    "detail": f"missing ref: {ref}",
                }
            )
    if carry_ok:
        checks.append(
            {
                "name": "local_parity_carry_forward_ref",
                "status": "PASS",
                "detail": f"{len(carry_forward)} refs present",
            }
        )
    all_ok &= carry_ok

    decision = "PASS" if all_ok else "FAIL_CLOSED"
    return _write_and_exit(started, checks, decision, output_root, "phase3a_settlement_check")


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 3.A settlement conformance check")
    parser.add_argument(
        "--settlement",
        default="config/platform/dev_substrate/phase3/control_ingress_settlement_v0.yaml",
        help="Path to settlement yaml",
    )
    parser.add_argument(
        "--profile",
        default="config/platform/profiles/dev_min.yaml",
        help="Path to dev_min profile",
    )
    parser.add_argument(
        "--output-root",
        default="runs/fraud-platform/dev_substrate/phase3",
        help="Output root for evidence json",
    )
    args = parser.parse_args()

    return run(Path(args.settlement), Path(args.profile), Path(args.output_root))


if __name__ == "__main__":
    raise SystemExit(main())
