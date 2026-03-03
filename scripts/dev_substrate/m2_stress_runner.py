#!/usr/bin/env python3
"""M2 stress runner.

Current scope:
1. M2-ST-S0 Stage-A artifact emission and dispatch hardening.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


M2_PLAN_PATH = Path(
    "docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M2.stress_test.md"
)
DEFAULT_OUTPUT_ROOT = Path("runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control")

REQUIRED_S0_SECTIONS = [
    "## 5) M2 Stress Handle Packet (Pinned)",
    "## 6) Capability-Lane Coverage (Phase-Coverage Law)",
    "## 7) Stress Topology (M2)",
    "## 8) Execution Plan (Execution-Grade Runbook)",
    "## 9) Blocker Taxonomy (M2 Stress)",
]

REQUIRED_HANDLE_KEYS = [
    "M2_STRESS_PROFILE_ID",
    "M2_STRESS_BLOCKER_REGISTER_PATH_PATTERN",
    "M2_STRESS_EXECUTION_SUMMARY_PATH_PATTERN",
    "M2_STRESS_DECISION_LOG_PATH_PATTERN",
    "M2_STRESS_REQUIRED_ARTIFACTS",
    "M2_STRESS_MAX_RUNTIME_MINUTES",
    "M2_STRESS_MAX_SPEND_USD",
    "M2_STRESS_BASELINE_EVENTS_PER_SECOND",
    "M2_STRESS_BURST_EVENTS_PER_SECOND",
    "M2_STRESS_WINDOW_MINUTES",
]


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _ts_token() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _extract_handle_packet(plan_text: str) -> dict[str, Any]:
    packet: dict[str, Any] = {}
    rx = re.compile(r"`([A-Z0-9_]+)\s*=\s*([^`]+)`")
    for key, raw in rx.findall(plan_text):
        value = raw.strip()
        if value.lower() in {"true", "false"}:
            packet[key] = value.lower() == "true"
            continue
        if value.startswith('"') and value.endswith('"'):
            packet[key] = value[1:-1]
            continue
        try:
            packet[key] = int(value) if "." not in value else float(value)
        except ValueError:
            packet[key] = value
    return packet


def _build_stagea_findings(plan_exists: bool, plan_text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    handle_packet = _extract_handle_packet(plan_text) if plan_exists else {}

    missing_sections = [s for s in REQUIRED_S0_SECTIONS if s not in plan_text]
    missing_handles = [k for k in REQUIRED_HANDLE_KEYS if k not in handle_packet]

    f1_closed = bool(plan_exists)
    f2_closed = len(missing_handles) == 0
    f3_closed = len(missing_sections) == 0

    findings = [
        {
            "id": "M2-ST-F1",
            "classification": "PREVENT",
            "finding": "No dedicated M2 stress authority file existed; control file was still inline-only.",
            "required_action": "Create/pin platform.M2.stress_test.md and route active phase to it.",
            "status": "CLOSED" if f1_closed else "OPEN",
            "evidence": {"plan_exists": plan_exists, "path": str(M2_PLAN_PATH)},
        },
        {
            "id": "M2-ST-F2",
            "classification": "PREVENT",
            "finding": "Stress handle packet for M2 is not yet pinned in stress authority.",
            "required_action": "Pin M2 stress handle packet before any managed stress run.",
            "status": "CLOSED" if f2_closed else "OPEN",
            "evidence": {"missing_handle_keys": missing_handles},
        },
        {
            "id": "M2-ST-F3",
            "classification": "PREVENT",
            "finding": "M2 has many coupled lanes and needs deterministic lane matrix/ordering.",
            "required_action": "Pin deterministic lane matrix and execution order.",
            "status": "CLOSED" if f3_closed else "OPEN",
            "evidence": {"missing_sections": missing_sections},
        },
        {
            "id": "M2-ST-F4",
            "classification": "OBSERVE",
            "finding": "Historical M2 closure was provisioning-heavy; load sensitivity requires fresh profiling.",
            "required_action": "Run bounded baseline + burst stress windows with telemetry capture.",
            "status": "OPEN_OBSERVE",
            "evidence": {"next_stage": "M2-ST-S1/M2-ST-S2"},
        },
        {
            "id": "M2-ST-F5",
            "classification": "OBSERVE",
            "finding": "Secret-path readability and API-edge auth are regression-sensitive under concurrent probes.",
            "required_action": "Run concurrency-aware secret/auth probes with strict leak checks.",
            "status": "OPEN_OBSERVE",
            "evidence": {"next_stage": "M2-ST-S1/M2-ST-S3"},
        },
        {
            "id": "M2-ST-F6",
            "classification": "ACCEPT",
            "finding": "M2 build evidence already includes lane decomposition and blocker taxonomy.",
            "required_action": "Reuse as baseline for stress execution and blocker IDs.",
            "status": "ACCEPTED",
            "evidence": {"baseline_source": "platform.M2.build_plan.md (M2.A..M2.J)"},
        },
    ]

    blockers: list[dict[str, Any]] = []
    if not f1_closed:
        blockers.append(
            {
                "id": "M2-ST-B1",
                "severity": "S1",
                "status": "OPEN",
                "source_finding": "M2-ST-F1",
                "message": "Dedicated M2 stress authority file missing.",
            }
        )
    if not f2_closed:
        blockers.append(
            {
                "id": "M2-ST-B1",
                "severity": "S1",
                "status": "OPEN",
                "source_finding": "M2-ST-F2",
                "message": "M2 stress handle packet incomplete.",
                "details": {"missing_handle_keys": missing_handles},
            }
        )
    if not f3_closed:
        blockers.append(
            {
                "id": "M2-ST-B9",
                "severity": "S1",
                "status": "OPEN",
                "source_finding": "M2-ST-F3",
                "message": "M2 lane matrix/ordering sections missing in authority.",
                "details": {"missing_sections": missing_sections},
            }
        )

    return findings, blockers


def _build_lane_matrix() -> dict[str, Any]:
    lane_rows: list[dict[str, Any]] = [
        {
            "lane_id": "M2.A",
            "anchor": "state backend and lock conformance",
            "probe_groups": ["tf_state_backend", "s3_state_posture", "dynamodb_lock_posture"],
            "stages": ["S1", "S2"],
        },
        {
            "lane_id": "M2.B",
            "anchor": "core stack materialization",
            "probe_groups": ["core_outputs", "s3_kms_tag_posture"],
            "stages": ["S1", "S2"],
        },
        {
            "lane_id": "M2.C",
            "anchor": "streaming stack materialization",
            "probe_groups": ["msk_cluster", "bootstrap_path", "glue_registry"],
            "stages": ["S1", "S2"],
        },
        {
            "lane_id": "M2.D",
            "anchor": "topic/schema readiness and SR authority",
            "probe_groups": ["topic_surface", "schema_surface", "sr_commit_authority"],
            "stages": ["S1", "S2", "S3"],
        },
        {
            "lane_id": "M2.E",
            "anchor": "runtime stack and IAM posture",
            "probe_groups": ["runtime_roles", "api_edge_surfaces", "runtime_path_governance"],
            "stages": ["S1", "S2", "S3"],
        },
        {
            "lane_id": "M2.F",
            "anchor": "secret path contract/materialization",
            "probe_groups": ["ssm_presence", "role_path_readability", "plaintext_leak_scan"],
            "stages": ["S1", "S2", "S3"],
        },
        {
            "lane_id": "M2.G",
            "anchor": "data_ml stack materialization",
            "probe_groups": ["data_ml_roles", "data_ml_ssm_paths", "idempotence"],
            "stages": ["S1", "S2"],
        },
        {
            "lane_id": "M2.H",
            "anchor": "ops stack and cost guardrail surfaces",
            "probe_groups": ["ops_role_paths", "cost_guardrail_continuity", "idempotence"],
            "stages": ["S1", "S2"],
        },
        {
            "lane_id": "M2.I",
            "anchor": "destroy/recover and residual scan",
            "probe_groups": ["rehearsal_scope", "post_recover_integrity", "residual_risk_scan"],
            "stages": ["S3", "S4"],
        },
        {
            "lane_id": "M2.J",
            "anchor": "P0 rollup and handoff",
            "probe_groups": ["rollup_completeness", "managed_control_rails", "m3_handoff_readiness"],
            "stages": ["S5"],
        },
    ]

    return {
        "lane_rows": lane_rows,
        "component_sequence": ["M2.A/B/C", "M2.D/E/F", "M2.G/H"],
        "plane_sequence": ["substrate_plane", "control_rail_plane", "safety_plane"],
        "integrated_windows": ["S1_baseline", "S2_burst", "S3_failure_injection"],
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_s0(phase_execution_id: str, output_root: Path) -> int:
    plan_exists = M2_PLAN_PATH.exists()
    plan_text = M2_PLAN_PATH.read_text(encoding="utf-8") if plan_exists else ""
    findings, blockers = _build_stagea_findings(plan_exists, plan_text)
    lane_matrix = _build_lane_matrix()
    handle_packet = _extract_handle_packet(plan_text) if plan_exists else {}

    output_dir = output_root / phase_execution_id / "stress"
    output_dir.mkdir(parents=True, exist_ok=True)

    stagea_findings = {
        "generated_at_utc": _now_utc(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M2-ST-S0",
        "overall_pass": len(blockers) == 0,
        "prevent_open_count": sum(1 for item in findings if item["classification"] == "PREVENT" and item["status"] == "OPEN"),
        "findings": findings,
    }

    lane_matrix_artifact = {
        "generated_at_utc": _now_utc(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M2-ST-S0",
        "lane_matrix": lane_matrix,
        "dispatch_profile": {
            "baseline_eps": handle_packet.get("M2_STRESS_BASELINE_EVENTS_PER_SECOND", 20),
            "burst_eps": handle_packet.get("M2_STRESS_BURST_EVENTS_PER_SECOND", 40),
            "window_minutes": handle_packet.get("M2_STRESS_WINDOW_MINUTES", 10),
            "max_runtime_minutes": handle_packet.get("M2_STRESS_MAX_RUNTIME_MINUTES", 180),
            "max_spend_usd": handle_packet.get("M2_STRESS_MAX_SPEND_USD", 35),
        },
    }

    blocker_register = {
        "generated_at_utc": _now_utc(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M2-ST-S0",
        "overall_pass": len(blockers) == 0,
        "open_blocker_count": len(blockers),
        "blockers": blockers,
    }

    decision_log = {
        "generated_at_utc": _now_utc(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M2-ST-S0",
        "decisions": [
            "Used platform.M2.stress_test.md as single authority for S0 findings and lane matrix.",
            "Closed PREVENT findings only when explicit authority evidence exists.",
            "Kept OBSERVE findings open for S1/S2/S3 execution windows.",
        ],
    }

    execution_summary = {
        "generated_at_utc": _now_utc(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M2-ST-S0",
        "overall_pass": len(blockers) == 0,
        "next_gate": "M2_ST_S1_READY" if len(blockers) == 0 else "BLOCKED",
        "required_artifacts": [
            "m2_stagea_findings.json",
            "m2_lane_matrix.json",
            "m2_blocker_register.json",
            "m2_execution_summary.json",
            "m2_decision_log.json",
        ],
    }

    _write_json(output_dir / "m2_stagea_findings.json", stagea_findings)
    _write_json(output_dir / "m2_lane_matrix.json", lane_matrix_artifact)
    _write_json(output_dir / "m2_blocker_register.json", blocker_register)
    _write_json(output_dir / "m2_decision_log.json", decision_log)
    _write_json(output_dir / "m2_execution_summary.json", execution_summary)

    print(f"[m2_s0] phase_execution_id={phase_execution_id}")
    print(f"[m2_s0] output_dir={output_dir.as_posix()}")
    print(f"[m2_s0] overall_pass={execution_summary['overall_pass']}")
    print(f"[m2_s0] next_gate={execution_summary['next_gate']}")
    print(f"[m2_s0] open_blockers={len(blockers)}")

    return 0 if execution_summary["overall_pass"] else 2


def main() -> int:
    parser = argparse.ArgumentParser(description="M2 stress runner")
    parser.add_argument("--stage", default="S0", choices=["S0"], help="Stress stage to execute.")
    parser.add_argument("--phase-execution-id", default=f"m2_stress_s0_{_ts_token()}")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    args = parser.parse_args()

    if args.stage == "S0":
        return run_s0(args.phase_execution_id, Path(args.output_root))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
