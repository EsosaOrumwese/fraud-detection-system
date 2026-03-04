#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PLAN = Path("docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M8.stress_test.md")
REG = Path("docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md")
OUT_ROOT = Path("runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control")

PLAN_KEYS = [
    "M8_STRESS_PROFILE_ID",
    "M8_STRESS_BLOCKER_REGISTER_PATH_PATTERN",
    "M8_STRESS_EXECUTION_SUMMARY_PATH_PATTERN",
    "M8_STRESS_DECISION_LOG_PATH_PATTERN",
    "M8_STRESS_REQUIRED_ARTIFACTS",
    "M8_STRESS_MAX_RUNTIME_MINUTES",
    "M8_STRESS_MAX_SPEND_USD",
    "M8_STRESS_EXPECTED_VERDICT_ON_PASS",
    "M8_STRESS_EXPECTED_NEXT_GATE_ON_PASS",
    "M8_STRESS_TARGETED_RERUN_ONLY",
    "M8_STRESS_STALE_EVIDENCE_CUTOFF_UTC",
    "M8_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY",
    "M8_STRESS_REQUIRE_ORACLE_EVIDENCE_ONLY",
    "M8_STRESS_DISALLOW_WAIVED_THROUGHPUT",
]

REQ_HANDLES = [
    "SPINE_RUN_REPORT_PATH_PATTERN",
    "SPINE_RECONCILIATION_PATH_PATTERN",
    "SPINE_NON_REGRESSION_PACK_PATTERN",
    "GOV_APPEND_LOG_PATH_PATTERN",
    "GOV_RUN_CLOSE_MARKER_PATH_PATTERN",
    "REPORTER_LOCK_BACKEND",
    "REPORTER_LOCK_KEY_PATTERN",
    "ROLE_EKS_IRSA_OBS_GOV",
    "EKS_CLUSTER_NAME",
    "EKS_NAMESPACE_OBS_GOV",
    "S3_EVIDENCE_BUCKET",
    "S3_EVIDENCE_RUN_ROOT_PATTERN",
    "PHASE_BUDGET_ENVELOPE_PATH_PATTERN",
    "PHASE_COST_OUTCOME_RECEIPT_PATH_PATTERN",
    "M7_HANDOFF_PACK_PATH_PATTERN",
    "RECEIPT_SUMMARY_PATH_PATTERN",
    "KAFKA_OFFSETS_SNAPSHOT_PATH_PATTERN",
    "QUARANTINE_SUMMARY_PATH_PATTERN",
]

EXPECTED_LANE_STAGE = {
    "A": "S0",
    "B": "S1",
    "C": "S1",
    "D": "S2",
    "E": "S2",
    "F": "S3",
    "G": "S3",
    "H": "S4",
    "I": "S4",
    "J": "S5",
}

S0_ARTIFACTS = [
    "m8_stagea_findings.json",
    "m8_lane_matrix.json",
    "m8a_handle_closure_snapshot.json",
    "m8_runtime_locality_guard_snapshot.json",
    "m8_source_authority_guard_snapshot.json",
    "m8_realism_guard_snapshot.json",
    "m8_blocker_register.json",
    "m8_execution_summary.json",
    "m8_decision_log.json",
    "m8_gate_verdict.json",
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def tok() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_scalar(v: str) -> Any:
    s = v.strip()
    if s.lower() in {"true", "false"}:
        return s.lower() == "true"
    if s.startswith('"') and s.endswith('"'):
        return s[1:-1]
    try:
        return int(s) if "." not in s else float(s)
    except ValueError:
        return s


def parse_bt_map(text: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in re.findall(r"`([A-Z0-9_]+)\s*=\s*([^`]+)`", text):
        out[k] = parse_scalar(v)
    return out


def parse_registry(path: Path) -> dict[str, Any]:
    out: dict[str, Any] = {}
    rx = re.compile(r"^\* `([^`]+)`(?:\s.*)?$")
    for raw in path.read_text(encoding="utf-8").splitlines():
        m = rx.match(raw.strip())
        if not m:
            continue
        body = m.group(1).strip()
        if "=" not in body:
            continue
        k, v = body.split("=", 1)
        out[k.strip()] = parse_scalar(v.strip())
    return out


def parse_strict_authority_ids(plan_text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for label, exec_id in re.findall(r"`(M7P8-ST-S5|M7P9-ST-S5|M7P10-ST-S5)`:\s*`([^`]+)`", plan_text):
        out[label] = exec_id.strip()
    m_parent = re.search(r"Parent `M7-ST-S5`:\s*`([^`]+)`", plan_text)
    if m_parent:
        out["M7-ST-S5"] = m_parent.group(1).strip()
    return out


def parse_lane_matrix(plan_text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    rx = re.compile(r"^\|\s*[^|]+\|\s*`([A-J])`\s*\|\s*`(S[0-5])`\s*\|")
    for raw in plan_text.splitlines():
        m = rx.match(raw.strip())
        if m:
            out[m.group(1)] = m.group(2)
    return out


def loadj(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except Exception:
        return {}


def dumpj(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def is_placeholder(v: Any) -> bool:
    s = str(v or "").strip()
    lower = s.lower()
    if not s:
        return True
    if lower in {"tbd", "todo", "none", "null", "unset"}:
        return True
    if "placeholder" in lower or "to_pin" in lower:
        return True
    if "<" in s and ">" in s:
        return True
    return False


def is_local_path(v: str) -> bool:
    s = str(v or "").strip()
    if not s:
        return False
    if s.startswith("runs/") or s.startswith("./runs/"):
        return True
    if re.match(r"^[A-Za-z]:[\\/]", s):
        return True
    return False


def parse_utc(ts: Any) -> datetime | None:
    s = str(ts or "").strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def dedupe_blockers(blockers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for b in blockers:
        sig = f"{b.get('id','')}|{json.dumps(b.get('details', {}), sort_keys=True, default=str)}"
        if sig in seen:
            continue
        seen.add(sig)
        out.append(b)
    return out


def add_blocker(blockers: list[dict[str, Any]], blocker_id: str, severity: str, details: dict[str, Any]) -> None:
    blockers.append({"id": blocker_id, "severity": severity, "status": "OPEN", "details": details})


def check_required_files(paths: list[Path], blockers: list[dict[str, Any]]) -> None:
    missing = [p.as_posix() for p in paths if not p.exists()]
    if missing:
        add_blocker(blockers, "M8-ST-B14", "S0", {"reason": "required_input_missing", "missing_paths": missing})


def run_s0(phase_execution_id: str, upstream_m7_execution: str) -> int:
    t_start = datetime.now(timezone.utc)
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)

    blockers: list[dict[str, Any]] = []
    decisions: list[str] = []
    advisories: list[str] = []
    captured = now()

    check_required_files([PLAN, REG], blockers)
    plan_text = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    registry = parse_registry(REG) if REG.exists() else {}
    plan_packet = parse_bt_map(plan_text)

    unresolved_plan_keys = [k for k in PLAN_KEYS if k not in plan_packet]
    if unresolved_plan_keys:
        add_blocker(
            blockers,
            "M8-ST-B14",
            "S0",
            {"reason": "unresolved_plan_packet_keys", "missing_keys": unresolved_plan_keys},
        )
    else:
        decisions.append("Resolved full M8 stress plan-packet keys from authority doc.")

    strict_parent = parse_strict_authority_ids(plan_text)
    expected_parent = strict_parent.get("M7-ST-S5", "").strip()
    if not expected_parent:
        add_blocker(
            blockers,
            "M8-ST-B14",
            "S0",
            {"reason": "strict_parent_unresolved", "expected_key": "M7-ST-S5"},
        )
    elif expected_parent != upstream_m7_execution:
        add_blocker(
            blockers,
            "M8-ST-B13",
            "S0",
            {
                "reason": "strict_parent_mismatch",
                "expected_parent_execution": expected_parent,
                "provided_upstream_execution": upstream_m7_execution,
            },
        )

    lane_matrix = parse_lane_matrix(plan_text)
    missing_lanes = sorted([lane for lane in EXPECTED_LANE_STAGE if lane not in lane_matrix])
    mismatched_lanes = sorted(
        [
            lane
            for lane, expected_stage in EXPECTED_LANE_STAGE.items()
            if lane in lane_matrix and lane_matrix[lane] != expected_stage
        ]
    )
    if missing_lanes or mismatched_lanes:
        add_blocker(
            blockers,
            "M8-ST-B15",
            "S0",
            {
                "reason": "lane_coverage_hole",
                "missing_lanes": missing_lanes,
                "mismatched_lanes": [
                    {"lane": lane, "expected_stage": EXPECTED_LANE_STAGE[lane], "actual_stage": lane_matrix.get(lane)}
                    for lane in mismatched_lanes
                ],
            },
        )
    else:
        decisions.append("Phase-coverage lane ownership A..J is complete and stage-aligned.")

    required_true_flags = [
        "M8_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY",
        "M8_STRESS_REQUIRE_ORACLE_EVIDENCE_ONLY",
        "M8_STRESS_DISALLOW_WAIVED_THROUGHPUT",
    ]
    false_flags = [k for k in required_true_flags if plan_packet.get(k) is not True]
    if false_flags:
        add_blocker(
            blockers,
            "M8-ST-B14",
            "S0",
            {"reason": "anti_hole_flags_not_true", "flags": false_flags},
        )
    else:
        decisions.append("Anti-hole policy flags are explicitly pinned true.")

    missing_handles: list[str] = []
    placeholder_handles: list[str] = []
    resolved_handles: dict[str, Any] = {}
    for key in REQ_HANDLES:
        if key not in registry:
            missing_handles.append(key)
            continue
        value = registry.get(key)
        resolved_handles[key] = value
        if is_placeholder(value):
            placeholder_handles.append(key)
    if missing_handles or placeholder_handles:
        add_blocker(
            blockers,
            "M8-ST-B1",
            "S0",
            {
                "reason": "required_handles_unresolved",
                "missing_handles": missing_handles,
                "placeholder_handles": placeholder_handles,
            },
        )
    else:
        decisions.append("Required M8 S0 handle matrix is complete and non-placeholder.")

    m7_dir = OUT_ROOT / upstream_m7_execution / "stress"
    m7_summary_path = m7_dir / "m7_execution_summary.json"
    m8_handoff_path = m7_dir / "m8_handoff_pack.json"
    m7_summary = loadj(m7_summary_path)
    m8_handoff = loadj(m8_handoff_path)

    if not m7_summary:
        add_blocker(
            blockers,
            "M8-ST-B1",
            "S0",
            {"reason": "m7_summary_unreadable", "path": m7_summary_path.as_posix()},
        )
    else:
        if not bool(m7_summary.get("overall_pass")):
            add_blocker(
                blockers,
                "M8-ST-B1",
                "S0",
                {"reason": "m7_summary_not_pass", "path": m7_summary_path.as_posix()},
            )
        if str(m7_summary.get("next_gate", "")).strip() != "M8_READY":
            add_blocker(
                blockers,
                "M8-ST-B1",
                "S0",
                {
                    "reason": "m7_next_gate_mismatch",
                    "expected_next_gate": "M8_READY",
                    "actual_next_gate": m7_summary.get("next_gate"),
                },
            )

    if not m8_handoff:
        add_blocker(
            blockers,
            "M8-ST-B1",
            "S0",
            {"reason": "m8_handoff_unreadable", "path": m8_handoff_path.as_posix()},
        )
    else:
        if str(m8_handoff.get("next_gate", "")).strip() != "M8_READY":
            add_blocker(
                blockers,
                "M8-ST-B1",
                "S0",
                {
                    "reason": "m8_handoff_next_gate_mismatch",
                    "expected_next_gate": "M8_READY",
                    "actual_next_gate": m8_handoff.get("next_gate"),
                },
            )
        if str(m8_handoff.get("verdict", "")).strip() not in {"GO", "ADVANCE_TO_M8"}:
            add_blocker(
                blockers,
                "M8-ST-B1",
                "S0",
                {"reason": "m8_handoff_verdict_not_green", "actual_verdict": m8_handoff.get("verdict")},
            )

    stale_cutoff = parse_utc(plan_packet.get("M8_STRESS_STALE_EVIDENCE_CUTOFF_UTC"))
    summary_ts = parse_utc(m7_summary.get("generated_at_utc")) if m7_summary else None
    handoff_ts = parse_utc(m8_handoff.get("generated_at_utc")) if m8_handoff else None
    if stale_cutoff is None:
        add_blocker(blockers, "M8-ST-B14", "S0", {"reason": "stale_cutoff_unparseable"})
    else:
        if summary_ts is None or summary_ts < stale_cutoff:
            add_blocker(
                blockers,
                "M8-ST-B13",
                "S0",
                {
                    "reason": "m7_summary_stale_or_unparseable",
                    "cutoff_utc": plan_packet.get("M8_STRESS_STALE_EVIDENCE_CUTOFF_UTC"),
                    "generated_at_utc": m7_summary.get("generated_at_utc") if m7_summary else "",
                },
            )
        if handoff_ts is None or handoff_ts < stale_cutoff:
            add_blocker(
                blockers,
                "M8-ST-B13",
                "S0",
                {
                    "reason": "m8_handoff_stale_or_unparseable",
                    "cutoff_utc": plan_packet.get("M8_STRESS_STALE_EVIDENCE_CUTOFF_UTC"),
                    "generated_at_utc": m8_handoff.get("generated_at_utc") if m8_handoff else "",
                },
            )

    strict_p8 = strict_parent.get("M7P8-ST-S5", "").strip()
    strict_p9 = strict_parent.get("M7P9-ST-S5", "").strip()
    strict_p10 = strict_parent.get("M7P10-ST-S5", "").strip()
    if not (strict_p8 and strict_p9 and strict_p10):
        add_blocker(
            blockers,
            "M8-ST-B14",
            "S0",
            {"reason": "strict_subphase_ids_unresolved", "strict_parent_map": strict_parent},
        )
    else:
        subphase_rows = m8_handoff.get("subphase_rows", []) if m8_handoff else []
        subphase_map = {str(r.get("label", "")).strip(): r for r in subphase_rows if isinstance(r, dict)}
        expected_subphase = {"P8": strict_p8, "P9": strict_p9, "P10": strict_p10}
        mismatches: list[dict[str, Any]] = []
        for label, expected_exec in expected_subphase.items():
            row = subphase_map.get(label, {})
            if not row:
                mismatches.append({"label": label, "reason": "missing_row"})
                continue
            actual_exec = str(row.get("phase_execution_id", "")).strip()
            if actual_exec != expected_exec:
                mismatches.append(
                    {
                        "label": label,
                        "reason": "phase_execution_mismatch",
                        "expected": expected_exec,
                        "actual": actual_exec,
                    }
                )
            if not bool(row.get("ok")):
                mismatches.append({"label": label, "reason": "subphase_not_ok"})
        if mismatches:
            add_blocker(
                blockers,
                "M8-ST-B13",
                "S0",
                {"reason": "strict_subphase_authority_mismatch", "mismatches": mismatches},
            )
        else:
            decisions.append("Strict M7 P8/P9/P10 authority chain matches pinned execution IDs.")

    platform_run_id = str(m8_handoff.get("platform_run_id", "")).strip()
    if not platform_run_id:
        platform_run_id = str(m7_summary.get("platform_run_id", "")).strip() if m7_summary else ""
    if not platform_run_id:
        add_blocker(
            blockers,
            "M8-ST-B14",
            "S0",
            {"reason": "platform_run_id_unresolved"},
        )

    run_scope_refs = [
        str(m8_handoff.get("receipt_summary_ref", "")).strip() if m8_handoff else "",
        str(m8_handoff.get("offsets_snapshot_ref", "")).strip() if m8_handoff else "",
        str(m8_handoff.get("quarantine_summary_ref", "")).strip() if m8_handoff else "",
        str(m8_handoff.get("decision_evidence_ref", "")).strip() if m8_handoff else "",
        str(m8_handoff.get("case_labels_evidence_ref", "")).strip() if m8_handoff else "",
        str(m8_handoff.get("rtdl_evidence_ref", "")).strip() if m8_handoff else "",
    ]
    empty_refs = [r for r in run_scope_refs if not r]
    local_refs = [r for r in run_scope_refs if is_local_path(r)]
    if empty_refs:
        add_blocker(
            blockers,
            "M8-ST-B17",
            "S0",
            {"reason": "empty_authoritative_refs", "empty_ref_count": len(empty_refs)},
        )
    if local_refs:
        add_blocker(
            blockers,
            "M8-ST-B17",
            "S0",
            {"reason": "non_authoritative_local_refs", "refs": local_refs},
        )

    runtime_locality_guard = {
        "generated_at_utc": captured,
        "phase_execution_id": phase_execution_id,
        "stage_id": "M8-ST-S0",
        "require_remote_runtime_only": bool(plan_packet.get("M8_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY")),
        "runtime_execution_attempted": False,
        "runtime_execution_mode": "none_in_s0_preflight",
        "overall_pass": True,
        "details": ["S0 performs authority preflight only; runtime execution lanes start at S2."],
    }
    if runtime_locality_guard["require_remote_runtime_only"] is not True:
        runtime_locality_guard["overall_pass"] = False
        add_blocker(
            blockers,
            "M8-ST-B16",
            "S0",
            {"reason": "runtime_locality_policy_not_pinned_true"},
        )

    source_authority_guard = {
        "generated_at_utc": captured,
        "phase_execution_id": phase_execution_id,
        "stage_id": "M8-ST-S0",
        "require_oracle_evidence_only": bool(plan_packet.get("M8_STRESS_REQUIRE_ORACLE_EVIDENCE_ONLY")),
        "upstream_summary_path": m7_summary_path.as_posix(),
        "upstream_handoff_path": m8_handoff_path.as_posix(),
        "authoritative_refs": run_scope_refs,
        "local_ref_count": len(local_refs),
        "empty_ref_count": len(empty_refs),
        "overall_pass": len(local_refs) == 0 and len(empty_refs) == 0,
    }
    if source_authority_guard["require_oracle_evidence_only"] is not True:
        source_authority_guard["overall_pass"] = False
        add_blocker(
            blockers,
            "M8-ST-B17",
            "S0",
            {"reason": "source_authority_policy_not_pinned_true"},
        )

    addendum_status = m8_handoff.get("addendum_lane_status", {}) if m8_handoff else {}
    realism_guard = {
        "generated_at_utc": captured,
        "phase_execution_id": phase_execution_id,
        "stage_id": "M8-ST-S0",
        "disallow_waived_throughput": bool(plan_packet.get("M8_STRESS_DISALLOW_WAIVED_THROUGHPUT")),
        "addendum_lane_status": addendum_status,
        "addendum_open_blocker_count": int(m8_handoff.get("addendum_open_blocker_count", -1)) if m8_handoff else -1,
        "overall_pass": False,
    }
    realism_green = (
        bool(addendum_status)
        and all(bool(addendum_status.get(k)) for k in ("A1", "A2", "A3", "A4"))
        and int(m8_handoff.get("addendum_open_blocker_count", -1)) == 0
    )
    realism_guard["overall_pass"] = bool(plan_packet.get("M8_STRESS_DISALLOW_WAIVED_THROUGHPUT")) and realism_green
    if not realism_guard["overall_pass"]:
        add_blocker(
            blockers,
            "M8-ST-B18",
            "S0",
            {
                "reason": "non_toy_realism_guard_not_satisfied",
                "addendum_lane_status": addendum_status,
                "addendum_open_blocker_count": realism_guard["addendum_open_blocker_count"],
            },
        )
    else:
        decisions.append("Non-toy realism prerequisite is green via strict M7 addendum closure.")

    stagea_findings = {
        "generated_at_utc": captured,
        "phase_execution_id": phase_execution_id,
        "stage_id": "M8-ST-S0",
        "findings": [
            {"id": "M8-ST-F1", "classification": "PREVENT", "status": "CLOSED_IN_PLAN"},
            {"id": "M8-ST-F2", "classification": "PREVENT", "status": "CLOSED_IN_PLAN"},
            {"id": "M8-ST-F3", "classification": "PREVENT", "status": "CLOSED_IN_PLAN"},
            {"id": "M8-ST-F4", "classification": "PREVENT", "status": "CLOSED_IN_STAGE"},
            {"id": "M8-ST-F5", "classification": "PREVENT", "status": "OPEN_FOR_S1_PLUS"},
            {"id": "M8-ST-F6", "classification": "OBSERVE", "status": "OPEN_FOR_S2"},
            {"id": "M8-ST-F7", "classification": "OBSERVE", "status": "CLOSED_IN_STAGE"},
            {"id": "M8-ST-F8", "classification": "ACCEPT", "status": "CLOSED_IN_STAGE"},
            {"id": "M8-ST-F9", "classification": "PREVENT", "status": "CLOSED_IN_STAGE"},
            {"id": "M8-ST-F10", "classification": "PREVENT", "status": "CLOSED_IN_STAGE"},
            {"id": "M8-ST-F11", "classification": "PREVENT", "status": "CLOSED_IN_STAGE"},
        ],
    }

    lane_matrix_artifact = {
        "generated_at_utc": captured,
        "phase_execution_id": phase_execution_id,
        "stage_id": "M8-ST-S0",
        "expected_lane_stage_map": EXPECTED_LANE_STAGE,
        "parsed_lane_stage_map": lane_matrix,
        "missing_lanes": missing_lanes,
        "mismatched_lanes": mismatched_lanes,
        "overall_pass": len(missing_lanes) == 0 and len(mismatched_lanes) == 0,
    }

    handle_snapshot = {
        "generated_at_utc": captured,
        "phase_execution_id": phase_execution_id,
        "stage_id": "M8-ST-S0",
        "platform_run_id": platform_run_id,
        "upstream_m7_execution": upstream_m7_execution,
        "upstream_m7_summary_path": m7_summary_path.as_posix(),
        "upstream_m8_handoff_path": m8_handoff_path.as_posix(),
        "required_handle_count": len(REQ_HANDLES),
        "resolved_handle_count": len(REQ_HANDLES) - len(missing_handles),
        "missing_handles": missing_handles,
        "placeholder_handles": placeholder_handles,
        "resolved_handles": resolved_handles,
        "strict_parent_execution_expected": expected_parent,
        "strict_subphase_expected": {
            "P8": strict_p8,
            "P9": strict_p9,
            "P10": strict_p10,
        },
    }

    blockers = dedupe_blockers(blockers)
    overall_pass = len(blockers) == 0
    next_gate = "M8_ST_S1_READY" if overall_pass else "BLOCKED"
    verdict = "GO" if overall_pass else "HOLD_REMEDIATE"
    elapsed_seconds = round((datetime.now(timezone.utc) - t_start).total_seconds(), 3)

    blocker_register = {
        "generated_at_utc": captured,
        "phase_execution_id": phase_execution_id,
        "stage_id": "M8-ST-S0",
        "overall_pass": overall_pass,
        "open_blocker_count": len(blockers),
        "blockers": blockers,
    }
    execution_summary = {
        "generated_at_utc": captured,
        "phase_execution_id": phase_execution_id,
        "stage_id": "M8-ST-S0",
        "platform_run_id": platform_run_id,
        "overall_pass": overall_pass,
        "open_blocker_count": len(blockers),
        "next_gate": next_gate,
        "verdict": verdict,
        "elapsed_seconds": elapsed_seconds,
        "required_artifacts": S0_ARTIFACTS,
        "upstream_m7_execution": upstream_m7_execution,
        "strict_parent_execution_expected": expected_parent,
    }
    decision_log = {
        "generated_at_utc": captured,
        "phase_execution_id": phase_execution_id,
        "stage_id": "M8-ST-S0",
        "decisions": decisions,
        "advisories": advisories,
    }
    gate_verdict = {
        "generated_at_utc": captured,
        "phase_execution_id": phase_execution_id,
        "stage_id": "M8-ST-S0",
        "overall_pass": overall_pass,
        "verdict": verdict,
        "next_gate": next_gate,
        "expected_next_gate_on_pass": "M8_ST_S1_READY",
        "open_blocker_count": len(blockers),
    }

    artifacts: dict[str, dict[str, Any]] = {
        "m8_stagea_findings.json": stagea_findings,
        "m8_lane_matrix.json": lane_matrix_artifact,
        "m8a_handle_closure_snapshot.json": handle_snapshot,
        "m8_runtime_locality_guard_snapshot.json": runtime_locality_guard,
        "m8_source_authority_guard_snapshot.json": source_authority_guard,
        "m8_realism_guard_snapshot.json": realism_guard,
        "m8_blocker_register.json": blocker_register,
        "m8_execution_summary.json": execution_summary,
        "m8_decision_log.json": decision_log,
        "m8_gate_verdict.json": gate_verdict,
    }
    for name, payload in artifacts.items():
        dumpj(out / name, payload)

    missing_outputs = [name for name in S0_ARTIFACTS if not (out / name).exists()]
    if missing_outputs:
        add_blocker(
            blockers,
            "M8-ST-B12",
            "S0",
            {"reason": "artifact_contract_incomplete", "missing_outputs": missing_outputs},
        )
        blockers = dedupe_blockers(blockers)
        overall_pass = False
        next_gate = "BLOCKED"
        verdict = "HOLD_REMEDIATE"
        blocker_register["overall_pass"] = overall_pass
        blocker_register["open_blocker_count"] = len(blockers)
        blocker_register["blockers"] = blockers
        execution_summary["overall_pass"] = overall_pass
        execution_summary["open_blocker_count"] = len(blockers)
        execution_summary["next_gate"] = next_gate
        execution_summary["verdict"] = verdict
        gate_verdict["overall_pass"] = overall_pass
        gate_verdict["verdict"] = verdict
        gate_verdict["next_gate"] = next_gate
        gate_verdict["open_blocker_count"] = len(blockers)
        dumpj(out / "m8_blocker_register.json", blocker_register)
        dumpj(out / "m8_execution_summary.json", execution_summary)
        dumpj(out / "m8_gate_verdict.json", gate_verdict)

    print(
        json.dumps(
            {
                "phase_execution_id": phase_execution_id,
                "stage_id": "M8-ST-S0",
                "overall_pass": execution_summary.get("overall_pass"),
                "open_blocker_count": execution_summary.get("open_blocker_count"),
                "next_gate": execution_summary.get("next_gate"),
                "output_dir": out.as_posix(),
            },
            ensure_ascii=True,
        )
    )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="M8 parent stress runner")
    ap.add_argument("--stage", required=True, choices=["S0", "S1", "S2", "S3", "S4", "S5"])
    ap.add_argument("--phase-execution-id", default="")
    ap.add_argument("--upstream-m7-execution", default="m7_stress_s5_20260304T212520Z")
    args = ap.parse_args()

    phase_execution_id = args.phase_execution_id.strip() or f"m8_stress_{args.stage.lower()}_{tok()}"
    if args.stage != "S0":
        raise SystemExit("Only S0 is implemented in this runner. Execute S0 first and continue sequentially.")
    return run_s0(phase_execution_id=phase_execution_id, upstream_m7_execution=args.upstream_m7_execution.strip())


if __name__ == "__main__":
    raise SystemExit(main())

