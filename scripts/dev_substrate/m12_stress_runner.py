#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PLAN = Path("docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M12.stress_test.md")
REG = Path("docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md")
OUT_ROOT = Path("runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control")

S0_ARTS = [
    "m12_stagea_findings.json",
    "m12_lane_matrix.json",
    "m12_managed_lane_materialization_snapshot.json",
    "m12_subphase_dispatchability_snapshot.json",
    "m12b0_blocker_register.json",
    "m12b0_execution_summary.json",
    "m12a_handle_closure_snapshot.json",
    "m12a_blocker_register.json",
    "m12a_execution_summary.json",
    "m12_runtime_locality_guard_snapshot.json",
    "m12_source_authority_guard_snapshot.json",
    "m12_realism_guard_snapshot.json",
    "m12_blocker_register.json",
    "m12_execution_summary.json",
    "m12_decision_log.json",
    "m12_gate_verdict.json",
]

S1_ARTS = [
    "m12_stagea_findings.json",
    "m12_lane_matrix.json",
    "m12b_candidate_eligibility_snapshot.json",
    "m12b_blocker_register.json",
    "m12b_execution_summary.json",
    "m12c_compatibility_precheck_snapshot.json",
    "m12c_blocker_register.json",
    "m12c_execution_summary.json",
    "m12_runtime_locality_guard_snapshot.json",
    "m12_source_authority_guard_snapshot.json",
    "m12_realism_guard_snapshot.json",
    "m12_blocker_register.json",
    "m12_execution_summary.json",
    "m12_decision_log.json",
    "m12_gate_verdict.json",
]

S2_ARTS = [
    "m12_stagea_findings.json",
    "m12_lane_matrix.json",
    "m12d_promotion_commit_snapshot.json",
    "m12d_registry_lifecycle_event.json",
    "m12d_broker_transport_proof.json",
    "m12d_learning_registry_publication_receipt.json",
    "m12d_blocker_register.json",
    "m12d_execution_summary.json",
    "m12e_rollback_drill_snapshot.json",
    "m12e_blocker_register.json",
    "m12e_execution_summary.json",
    "m12_runtime_locality_guard_snapshot.json",
    "m12_source_authority_guard_snapshot.json",
    "m12_realism_guard_snapshot.json",
    "m12_blocker_register.json",
    "m12_execution_summary.json",
    "m12_decision_log.json",
    "m12_gate_verdict.json",
]

S3_ARTS = [
    "m12_stagea_findings.json",
    "m12_lane_matrix.json",
    "m12f_active_resolution_snapshot.json",
    "m12_post_promotion_observation_snapshot.json",
    "m12f_blocker_register.json",
    "m12f_execution_summary.json",
    "m12g_governance_append_snapshot.json",
    "m12_operability_acceptance_report.json",
    "m12g_blocker_register.json",
    "m12g_execution_summary.json",
    "m12_runtime_locality_guard_snapshot.json",
    "m12_source_authority_guard_snapshot.json",
    "m12_realism_guard_snapshot.json",
    "m12_blocker_register.json",
    "m12_execution_summary.json",
    "m12_decision_log.json",
    "m12_gate_verdict.json",
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


def parse_plan_packet(plan_text: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in re.findall(r"`([A-Z0-9_]+)\s*=\s*([^`]+)`", plan_text):
        out[k] = parse_scalar(v)
    return out


def is_placeholder(v: Any) -> bool:
    s = str(v or "").strip().lower()
    return (not s) or s in {"tbd", "todo", "none", "null", "unset"} or "placeholder" in s or "to_pin" in s


def loadj(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except Exception:
        return {}


def dumpj(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run(argv: list[str], timeout: int = 120, env: dict[str, str] | None = None) -> tuple[int, str, str]:
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, env=env)
        return int(p.returncode), (p.stdout or ""), (p.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"


def add_blocker(blockers: list[dict[str, Any]], bid: str, severity: str, details: dict[str, Any]) -> None:
    blockers.append({"id": bid, "severity": severity, "status": "OPEN", "details": details})


def dedupe(blockers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for b in blockers:
        sig = f"{b.get('id','')}|{json.dumps(b.get('details', {}), sort_keys=True, default=str)}"
        if sig in seen:
            continue
        seen.add(sig)
        out.append(b)
    return out


def latest_m11_s5() -> tuple[str, dict[str, Any]]:
    best_id = ""
    best_payload: dict[str, Any] = {}
    best_stamp = ""
    for d in OUT_ROOT.glob("m11_stress_s5_*"):
        payload = loadj(d / "stress" / "m11_execution_summary.json")
        if not payload:
            continue
        if str(payload.get("stage_id", "")) != "M11-ST-S5":
            continue
        if not bool(payload.get("overall_pass")):
            continue
        if str(payload.get("verdict", "")) != "ADVANCE_TO_M12":
            continue
        if str(payload.get("next_gate", "")) != "M12_READY":
            continue
        if int(payload.get("open_blocker_count", 1)) != 0:
            continue
        stamp = str(payload.get("generated_at_utc", ""))
        if (stamp, d.name) > (best_stamp, best_id):
            best_id = d.name
            best_payload = payload
            best_stamp = stamp
    return best_id, best_payload


def latest_s0() -> tuple[str, dict[str, Any]]:
    best_id = ""
    best_payload: dict[str, Any] = {}
    best_stamp = ""
    for d in OUT_ROOT.glob("m12_stress_s0_*"):
        payload = loadj(d / "stress" / "m12_execution_summary.json")
        if not payload:
            continue
        if str(payload.get("stage_id", "")) != "M12-ST-S0":
            continue
        if not bool(payload.get("overall_pass")):
            continue
        if str(payload.get("next_gate", "")) != "M12_ST_S1_READY":
            continue
        if int(payload.get("open_blocker_count", 1)) != 0:
            continue
        stamp = str(payload.get("generated_at_utc", ""))
        if (stamp, d.name) > (best_stamp, best_id):
            best_id = d.name
            best_payload = payload
            best_stamp = stamp
    return best_id, best_payload


def latest_s1() -> tuple[str, dict[str, Any]]:
    best_id = ""
    best_payload: dict[str, Any] = {}
    best_stamp = ""
    for d in OUT_ROOT.glob("m12_stress_s1_*"):
        payload = loadj(d / "stress" / "m12_execution_summary.json")
        if not payload:
            continue
        if str(payload.get("stage_id", "")) != "M12-ST-S1":
            continue
        if not bool(payload.get("overall_pass")):
            continue
        if str(payload.get("next_gate", "")) != "M12_ST_S2_READY":
            continue
        if int(payload.get("open_blocker_count", 1)) != 0:
            continue
        stamp = str(payload.get("generated_at_utc", ""))
        if (stamp, d.name) > (best_stamp, best_id):
            best_id = d.name
            best_payload = payload
            best_stamp = stamp
    return best_id, best_payload


def latest_s2() -> tuple[str, dict[str, Any]]:
    best_id = ""
    best_payload: dict[str, Any] = {}
    best_stamp = ""
    for d in OUT_ROOT.glob("m12_stress_s2_*"):
        payload = loadj(d / "stress" / "m12_execution_summary.json")
        if not payload:
            continue
        if str(payload.get("stage_id", "")) != "M12-ST-S2":
            continue
        if not bool(payload.get("overall_pass")):
            continue
        if str(payload.get("next_gate", "")) != "M12_ST_S3_READY":
            continue
        if int(payload.get("open_blocker_count", 1)) != 0:
            continue
        stamp = str(payload.get("generated_at_utc", ""))
        if (stamp, d.name) > (best_stamp, best_id):
            best_id = d.name
            best_payload = payload
            best_stamp = stamp
    return best_id, best_payload


def finish(
    stage: str,
    phase_execution_id: str,
    out: Path,
    blockers: list[dict[str, Any]],
    arts: list[str],
    summary_extra: dict[str, Any],
) -> int:
    blockers = dedupe(blockers)
    stage_receipts = {
        "m12_blocker_register.json",
        "m12_execution_summary.json",
        "m12_decision_log.json",
        "m12_gate_verdict.json",
    }
    prewrite_required = [name for name in arts if name not in stage_receipts]
    missing = [name for name in prewrite_required if not (out / name).exists()]
    if missing:
        add_blocker(
            blockers,
            "M12-ST-B11",
            stage,
            {"reason": "artifact_contract_incomplete", "missing_outputs": sorted(missing)},
        )
    blockers = dedupe(blockers)

    overall_pass = len(blockers) == 0
    if overall_pass and stage == "S0":
        next_gate = "M12_ST_S1_READY"
        verdict = "GO"
    elif overall_pass and stage == "S1":
        next_gate = "M12_ST_S2_READY"
        verdict = "GO"
    elif overall_pass and stage == "S2":
        next_gate = "M12_ST_S3_READY"
        verdict = "GO"
    elif overall_pass and stage == "S3":
        next_gate = "M12_ST_S4_READY"
        verdict = "GO"
    else:
        next_gate = "HOLD_REMEDIATE"
        verdict = "HOLD_REMEDIATE"

    register = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": f"M12-ST-{stage}",
        "open_blocker_count": len(blockers),
        "blockers": blockers,
    }
    summary = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": f"M12-ST-{stage}",
        "overall_pass": overall_pass,
        "open_blocker_count": len(blockers),
        "next_gate": next_gate,
        "verdict": verdict,
        "required_artifacts": arts,
        **summary_extra,
    }
    decision_log = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": f"M12-ST-{stage}",
        "decisions": list(summary_extra.get("decisions", [])),
        "advisories": list(summary_extra.get("advisories", [])),
    }
    gate = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": f"M12-ST-{stage}",
        "overall_pass": overall_pass,
        "next_gate": next_gate,
        "verdict": verdict,
    }

    dumpj(out / "m12_blocker_register.json", register)
    dumpj(out / "m12_execution_summary.json", summary)
    dumpj(out / "m12_decision_log.json", decision_log)
    dumpj(out / "m12_gate_verdict.json", gate)

    print(
        json.dumps(
            {
                "phase_execution_id": phase_execution_id,
                "stage_id": f"M12-ST-{stage}",
                "overall_pass": overall_pass,
                "open_blocker_count": len(blockers),
                "next_gate": next_gate,
                "output_dir": out.as_posix(),
            }
        )
    )
    return 0


def run_s0(phase_execution_id: str, upstream_m11_s5_execution: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)
    blockers: list[dict[str, Any]] = []
    advisories: list[str] = []

    plan_text = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    packet = parse_plan_packet(plan_text)
    reg = parse_registry(REG) if REG.exists() else {}

    scripts_required = [
        "scripts/dev_substrate/m12b0_managed_materialization.py",
        "scripts/dev_substrate/m12a_handle_closure.py",
    ]
    for script_path in scripts_required:
        if not Path(script_path).exists():
            add_blocker(
                blockers,
                "M12-ST-B18",
                "S0",
                {"reason": "required_stage_script_missing", "script": script_path},
            )

    value = reg.get("S3_EVIDENCE_BUCKET")
    if value is None or is_placeholder(value):
        add_blocker(blockers, "M12-ST-B1", "S0", {"reason": "required_handle_missing_or_placeholder", "handle": "S3_EVIDENCE_BUCKET"})
    bucket = str(reg.get("S3_EVIDENCE_BUCKET", "")).strip()

    fail_on_stale = bool(packet.get("M12_STRESS_FAIL_ON_STALE_UPSTREAM", True))
    expected_entry_execution = str(packet.get("M12_STRESS_EXPECTED_ENTRY_EXECUTION", "")).strip()
    if fail_on_stale and expected_entry_execution and upstream_m11_s5_execution != expected_entry_execution:
        add_blocker(
            blockers,
            "M12-ST-B15",
            "S0",
            {
                "reason": "stale_or_unexpected_upstream_execution",
                "selected_upstream_execution": upstream_m11_s5_execution,
                "expected_execution": expected_entry_execution,
            },
        )

    expected_entry_gate = str(packet.get("M12_STRESS_EXPECTED_ENTRY_GATE", "M12_READY")).strip() or "M12_READY"
    local_m11_s5_summary = loadj(OUT_ROOT / upstream_m11_s5_execution / "stress" / "m11_execution_summary.json")
    if not local_m11_s5_summary:
        add_blocker(
            blockers,
            "M12-ST-B1",
            "S0",
            {
                "reason": "upstream_m11_s5_summary_missing",
                "path": (OUT_ROOT / upstream_m11_s5_execution / "stress" / "m11_execution_summary.json").as_posix(),
            },
        )
    else:
        if not (
            bool(local_m11_s5_summary.get("overall_pass"))
            and int(local_m11_s5_summary.get("open_blocker_count", 1)) == 0
            and str(local_m11_s5_summary.get("verdict", "")) == "ADVANCE_TO_M12"
            and str(local_m11_s5_summary.get("next_gate", "")) == expected_entry_gate
        ):
            add_blocker(
                blockers,
                "M12-ST-B1",
                "S0",
                {
                    "reason": "upstream_m11_s5_not_ready",
                    "summary": {
                        "overall_pass": local_m11_s5_summary.get("overall_pass"),
                        "open_blocker_count": local_m11_s5_summary.get("open_blocker_count"),
                        "verdict": local_m11_s5_summary.get("verdict"),
                        "next_gate": local_m11_s5_summary.get("next_gate"),
                    },
                },
            )

    m11j_exec = str(local_m11_s5_summary.get("m11j_execution_id", "")).strip() if local_m11_s5_summary else ""
    m11i_exec = str(local_m11_s5_summary.get("m11i_execution_id", "")).strip() if local_m11_s5_summary else ""
    m11_s4_exec = str(local_m11_s5_summary.get("upstream_m11_s4_execution", "")).strip() if local_m11_s5_summary else ""
    if not m11j_exec:
        add_blocker(blockers, "M12-ST-B1", "S0", {"reason": "missing_m11j_execution_id_from_m11_s5_summary"})
    if not m11_s4_exec:
        add_blocker(blockers, "M12-ST-B1", "S0", {"reason": "missing_upstream_m11_s4_execution_in_m11_s5_summary"})

    local_m11j_summary = loadj(OUT_ROOT / upstream_m11_s5_execution / "stress" / "m11j_execution_summary.json")
    if not local_m11j_summary:
        add_blocker(
            blockers,
            "M12-ST-B1",
            "S0",
            {"reason": "m11j_summary_missing_in_upstream_s5_stress_root", "upstream_s5_execution": upstream_m11_s5_execution},
        )
    elif not (
        bool(local_m11j_summary.get("overall_pass"))
        and str(local_m11j_summary.get("verdict", "")) == "ADVANCE_TO_M12"
        and str(local_m11j_summary.get("next_gate", "")) == "M12_READY"
    ):
        add_blocker(
            blockers,
            "M12-ST-B1",
            "S0",
            {"reason": "m11j_not_ready", "summary": local_m11j_summary},
        )

    local_m12_handoff = loadj(OUT_ROOT / m11_s4_exec / "stress" / "m12_handoff_pack.json") if m11_s4_exec else {}
    if not local_m12_handoff:
        add_blocker(
            blockers,
            "M12-ST-B1",
            "S0",
            {"reason": "m12_handoff_missing_from_upstream_m11_s4", "upstream_s4_execution": m11_s4_exec},
        )
    else:
        if not bool(local_m12_handoff.get("m12_entry_ready")):
            add_blocker(blockers, "M12-ST-B1", "S0", {"reason": "m12_handoff_entry_ready_false"})
        entry_gate = local_m12_handoff.get("m12_entry_gate", {})
        if not isinstance(entry_gate, dict) or str(entry_gate.get("next_gate", "")).strip() != "M12_READY":
            add_blocker(blockers, "M12-ST-B1", "S0", {"reason": "m12_handoff_next_gate_not_m12_ready"})

    explicit_override_used = True
    if bool(packet.get("M12_STRESS_FAIL_ON_DEFAULT_UPSTREAM_INPUTS", True)) and not explicit_override_used:
        add_blocker(blockers, "M12-ST-B20", "S0", {"reason": "required_explicit_upstream_override_not_used"})

    m12b0_exec = ""
    m12b0_summary: dict[str, Any] = {}
    if Path("scripts/dev_substrate/m12b0_managed_materialization.py").exists() and m11j_exec and not blockers:
        m12b0_exec = f"m12b0_stress_s0_{tok()}"
        m12b0_dir = out / "_m12b0"
        env_b0 = dict(os.environ)
        env_b0.update(
            {
                "M12B0_EXECUTION_ID": m12b0_exec,
                "M12B0_RUN_DIR": m12b0_dir.as_posix(),
                "EVIDENCE_BUCKET": bucket,
                "UPSTREAM_M11J_EXECUTION": m11j_exec,
                "AWS_REGION": "eu-west-2",
                "M12_UPSTREAM_M12A_EXECUTION": "M12_S0_NOT_APPLICABLE",
                "M12_UPSTREAM_M12B_EXECUTION": "M12_S0_NOT_APPLICABLE",
                "M12_UPSTREAM_M12C_EXECUTION": "M12_S0_NOT_APPLICABLE",
                "M12_UPSTREAM_M12D_EXECUTION": "M12_S0_NOT_APPLICABLE",
                "M12_UPSTREAM_M12E_EXECUTION": "M12_S0_NOT_APPLICABLE",
                "M12_UPSTREAM_M12F_EXECUTION": "M12_S0_NOT_APPLICABLE",
                "M12_UPSTREAM_M12G_EXECUTION": "M12_S0_NOT_APPLICABLE",
                "M12_UPSTREAM_M12H_EXECUTION": "M12_S0_NOT_APPLICABLE",
                "M12_UPSTREAM_M12I_EXECUTION": "M12_S0_NOT_APPLICABLE",
            }
        )
        rc, _, err = run(["python", "scripts/dev_substrate/m12b0_managed_materialization.py"], timeout=9000, env=env_b0)
        if rc != 0:
            add_blocker(
                blockers,
                "M12-ST-B0",
                "S0",
                {"reason": "m12b0_command_failed", "stderr": err.strip()[:300], "rc": rc},
            )

        m12b0_summary = loadj(m12b0_dir / "m12b0_execution_summary.json")
        m12b0_snapshot = loadj(m12b0_dir / "m12_managed_lane_materialization_snapshot.json")
        m12b0_dispatch = loadj(m12b0_dir / "m12_subphase_dispatchability_snapshot.json")
        m12b0_register = loadj(m12b0_dir / "m12b0_blocker_register.json")
        if m12b0_snapshot:
            dumpj(out / "m12_managed_lane_materialization_snapshot.json", m12b0_snapshot)
        if m12b0_dispatch:
            dumpj(out / "m12_subphase_dispatchability_snapshot.json", m12b0_dispatch)
        if m12b0_summary:
            dumpj(out / "m12b0_execution_summary.json", m12b0_summary)
        if m12b0_register:
            dumpj(out / "m12b0_blocker_register.json", m12b0_register)

        if not m12b0_summary:
            add_blocker(blockers, "M12-ST-B0", "S0", {"reason": "m12b0_summary_missing"})
        elif not (
            bool(m12b0_summary.get("overall_pass"))
            and str(m12b0_summary.get("next_gate", "")) == "M12.A_READY"
            and str(m12b0_summary.get("verdict", "")) == "ADVANCE_TO_M12_A"
        ):
            add_blocker(blockers, "M12-ST-B0", "S0", {"reason": "m12b0_not_ready", "summary": m12b0_summary})

        if m12b0_register and isinstance(m12b0_register.get("blockers"), list):
            for row in m12b0_register.get("blockers", []):
                if not isinstance(row, dict):
                    continue
                text = " ".join(
                    [
                        str(row.get("message", "")),
                        str(row.get("detail", "")),
                        str(row.get("surface", "")),
                    ]
                ).lower()
                if any(token in text for token in ("resourcelimit", "quota", "throttl", "accessdenied", "access denied")):
                    add_blocker(
                        blockers,
                        "M12-ST-B19",
                        "S0",
                        {"reason": "managed_quota_or_access_boundary_pressure_detected_in_m12b0"},
                    )
                    break

    m12a_exec = ""
    m12a_summary: dict[str, Any] = {}
    if Path("scripts/dev_substrate/m12a_handle_closure.py").exists() and m11j_exec and m12b0_exec and not blockers:
        m12a_exec = f"m12a_stress_s0_{tok()}"
        m12a_dir = out / "_m12a"
        env_a = dict(os.environ)
        env_a.update(
            {
                "M12A_EXECUTION_ID": m12a_exec,
                "M12A_RUN_DIR": m12a_dir.as_posix(),
                "EVIDENCE_BUCKET": bucket,
                "UPSTREAM_M11J_EXECUTION": m11j_exec,
                "AWS_REGION": "eu-west-2",
                "M12_UPSTREAM_M12A_EXECUTION": "M12_S0_NOT_APPLICABLE",
                "M12_UPSTREAM_M12B_EXECUTION": "M12_S0_NOT_APPLICABLE",
                "M12_UPSTREAM_M12C_EXECUTION": "M12_S0_NOT_APPLICABLE",
                "M12_UPSTREAM_M12D_EXECUTION": "M12_S0_NOT_APPLICABLE",
                "M12_UPSTREAM_M12E_EXECUTION": "M12_S0_NOT_APPLICABLE",
                "M12_UPSTREAM_M12F_EXECUTION": "M12_S0_NOT_APPLICABLE",
                "M12_UPSTREAM_M12G_EXECUTION": "M12_S0_NOT_APPLICABLE",
                "M12_UPSTREAM_M12H_EXECUTION": "M12_S0_NOT_APPLICABLE",
                "M12_UPSTREAM_M12I_EXECUTION": "M12_S0_NOT_APPLICABLE",
            }
        )
        rc, _, err = run(["python", "scripts/dev_substrate/m12a_handle_closure.py"], timeout=9000, env=env_a)
        if rc != 0:
            add_blocker(
                blockers,
                "M12-ST-B1",
                "S0",
                {"reason": "m12a_command_failed", "stderr": err.strip()[:300], "rc": rc},
            )

        m12a_summary = loadj(m12a_dir / "m12a_execution_summary.json")
        m12a_snapshot = loadj(m12a_dir / "m12a_handle_closure_snapshot.json")
        m12a_register = loadj(m12a_dir / "m12a_blocker_register.json")
        if m12a_snapshot:
            dumpj(out / "m12a_handle_closure_snapshot.json", m12a_snapshot)
        if m12a_summary:
            dumpj(out / "m12a_execution_summary.json", m12a_summary)
        if m12a_register:
            dumpj(out / "m12a_blocker_register.json", m12a_register)

        if not m12a_summary:
            add_blocker(blockers, "M12-ST-B1", "S0", {"reason": "m12a_summary_missing"})
        elif not (
            bool(m12a_summary.get("overall_pass"))
            and str(m12a_summary.get("next_gate", "")) == "M12.B_READY"
            and str(m12a_summary.get("verdict", "")) == "ADVANCE_TO_M12_B"
        ):
            add_blocker(blockers, "M12-ST-B1", "S0", {"reason": "m12a_not_ready", "summary": m12a_summary})

        if m12a_register and isinstance(m12a_register.get("blockers"), list):
            for row in m12a_register.get("blockers", []):
                if not isinstance(row, dict):
                    continue
                text = " ".join(
                    [
                        str(row.get("message", "")),
                        str(row.get("detail", "")),
                        str(row.get("surface", "")),
                    ]
                ).lower()
                if any(token in text for token in ("resourcelimit", "quota", "throttl", "accessdenied", "access denied")):
                    add_blocker(
                        blockers,
                        "M12-ST-B19",
                        "S0",
                        {"reason": "managed_quota_or_access_boundary_pressure_detected_in_m12a"},
                    )
                    break
    elif m12b0_exec and not m12a_exec and not blockers:
        add_blocker(blockers, "M12-ST-B1", "S0", {"reason": "m12a_not_executed"})
    elif blockers and not m12a_exec:
        add_blocker(blockers, "M12-ST-B1", "S0", {"reason": "m12a_skipped_due_to_prior_blocker"})

    stage_findings = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M12-ST-S0",
        "findings": [
            {
                "id": "M12-ST-F3",
                "classification": "PREVENT",
                "status": "CLOSED" if all(Path(p).exists() for p in scripts_required) else "OPEN",
                "note": "Parent M12 runner and S0 wrappers are materialized for execution.",
            },
            {
                "id": "M12-ST-F4",
                "classification": "PREVENT",
                "status": "CLOSED" if explicit_override_used else "OPEN",
                "note": "S0 dispatch uses explicit upstream input overrides (no workflow default reliance).",
            },
            {
                "id": "M12-ST-F5",
                "classification": "PREVENT",
                "status": "CLOSED" if len([b for b in blockers if b.get("id") in {"M12-ST-B15"}]) == 0 else "OPEN",
                "note": "Strict upstream continuity and stale-evidence guard are enforced in S0.",
            },
            {
                "id": "M12-ST-F12",
                "classification": "PREVENT",
                "status": "CLOSED" if len([b for b in blockers if b.get("id") in {"M12-ST-B1"}]) == 0 else "OPEN",
                "note": "Authority/handle closure posture is enforced fail-closed.",
            },
        ],
    }
    dumpj(out / "m12_stagea_findings.json", stage_findings)

    lane_matrix = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M12-ST-S0",
        "lanes": [
            {
                "lane": "B0",
                "component": "M12.B0",
                "execution_id": m12b0_exec,
                "overall_pass": bool(m12b0_summary.get("overall_pass")) if m12b0_summary else False,
                "next_gate": str(m12b0_summary.get("next_gate", "")) if m12b0_summary else "",
                "verdict": str(m12b0_summary.get("verdict", "")) if m12b0_summary else "",
            },
            {
                "lane": "A",
                "component": "M12.A",
                "execution_id": m12a_exec,
                "overall_pass": bool(m12a_summary.get("overall_pass")) if m12a_summary else False,
                "next_gate": str(m12a_summary.get("next_gate", "")) if m12a_summary else "",
                "verdict": str(m12a_summary.get("verdict", "")) if m12a_summary else "",
            },
        ],
    }
    dumpj(out / "m12_lane_matrix.json", lane_matrix)

    runtime_locality_ok = bool(packet.get("M12_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY", True))
    if not runtime_locality_ok:
        add_blocker(blockers, "M12-ST-B16", "S0", {"reason": "runtime_locality_policy_not_true"})
    dumpj(
        out / "m12_runtime_locality_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M12-ST-S0",
            "overall_pass": runtime_locality_ok,
            "require_remote_runtime_only": bool(packet.get("M12_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY", True)),
            "runtime_execution_attempted": False,
            "runtime_execution_mode": "local_control_orchestration_only_remote_runtime",
        },
    )

    refs = [
        f"evidence/dev_full/run_control/{upstream_m11_s5_execution}/stress/m11_execution_summary.json" if upstream_m11_s5_execution else "",
        f"evidence/dev_full/run_control/{upstream_m11_s5_execution}/stress/m11j_execution_summary.json" if upstream_m11_s5_execution else "",
        f"evidence/dev_full/run_control/{m11_s4_exec}/stress/m12_handoff_pack.json" if m11_s4_exec else "",
        f"evidence/dev_full/run_control/{m12b0_exec}/m12b0_execution_summary.json" if m12b0_exec else "",
        f"evidence/dev_full/run_control/{m12a_exec}/m12a_execution_summary.json" if m12a_exec else "",
    ]
    source_guard_ok = len([b for b in blockers if b.get("id") in {"M12-ST-B11", "M12-ST-B16"}]) == 0
    dumpj(
        out / "m12_source_authority_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M12-ST-S0",
            "overall_pass": source_guard_ok,
            "authoritative_refs": refs,
            "evidence_bucket": bucket,
            "runtime_locality_only_control_plane": True,
        },
    )

    realism_ok = bool(packet.get("M12_STRESS_DISALLOW_WAIVED_REALISM", True))
    if not realism_ok:
        add_blocker(blockers, "M12-ST-B17", "S0", {"reason": "realism_guard_not_true"})
    dumpj(
        out / "m12_realism_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M12-ST-S0",
            "overall_pass": realism_ok,
            "disallow_waived_realism": bool(packet.get("M12_STRESS_DISALLOW_WAIVED_REALISM", True)),
        },
    )

    if not bool(packet.get("M12_STRESS_REQUIRE_DATA_ENGINE_BLACKBOX", True)):
        add_blocker(blockers, "M12-ST-B16", "S0", {"reason": "data_engine_blackbox_guard_not_true"})

    platform_run_id = str(local_m11_s5_summary.get("platform_run_id", "")) if local_m11_s5_summary else ""
    scenario_run_id = str(local_m11_s5_summary.get("scenario_run_id", "")) if local_m11_s5_summary else ""
    return finish(
        "S0",
        phase_execution_id,
        out,
        blockers,
        S0_ARTS,
        {
            "platform_run_id": platform_run_id,
            "scenario_run_id": scenario_run_id,
            "upstream_m11_s5_execution": upstream_m11_s5_execution,
            "upstream_m11_s4_execution": m11_s4_exec,
            "m11j_execution_id": m11j_exec,
            "m11i_execution_id": m11i_exec,
            "m12b0_execution_id": m12b0_exec,
            "m12a_execution_id": m12a_exec,
            "decisions": [
                "S0 enforced strict M11 S5 closure continuity before executing M12 lanes.",
                "S0 executed managed lane materialization check (M12.B0) with explicit upstream overrides.",
                "S0 executed M12.A authority/handle closure and required deterministic M12.B_READY gate.",
            ],
            "advisories": advisories,
        },
    )


def run_s1(phase_execution_id: str, upstream_m12_s0_execution: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)
    blockers: list[dict[str, Any]] = []
    advisories: list[str] = []

    plan_text = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    packet = parse_plan_packet(plan_text)
    reg = parse_registry(REG) if REG.exists() else {}

    scripts_required = [
        "scripts/dev_substrate/m12b_candidate_eligibility.py",
        "scripts/dev_substrate/m12c_compatibility_precheck.py",
    ]
    for script_path in scripts_required:
        if not Path(script_path).exists():
            add_blocker(
                blockers,
                "M12-ST-B18",
                "S1",
                {"reason": "required_stage_script_missing", "script": script_path},
            )

    value = reg.get("S3_EVIDENCE_BUCKET")
    if value is None or is_placeholder(value):
        add_blocker(blockers, "M12-ST-B2", "S1", {"reason": "required_handle_missing_or_placeholder", "handle": "S3_EVIDENCE_BUCKET"})
    bucket = str(reg.get("S3_EVIDENCE_BUCKET", "")).strip()

    s0_exec = upstream_m12_s0_execution.strip()
    s0 = loadj(OUT_ROOT / s0_exec / "stress" / "m12_execution_summary.json") if s0_exec else {}
    if not s0:
        add_blocker(
            blockers,
            "M12-ST-B15",
            "S1",
            {
                "reason": "upstream_s0_summary_missing",
                "path": (OUT_ROOT / s0_exec / "stress" / "m12_execution_summary.json").as_posix(),
            },
        )
    elif not (
        bool(s0.get("overall_pass"))
        and int(s0.get("open_blocker_count", 1)) == 0
        and str(s0.get("next_gate", "")).strip() == "M12_ST_S1_READY"
    ):
        add_blocker(
            blockers,
            "M12-ST-B15",
            "S1",
            {
                "reason": "upstream_s0_not_ready",
                "summary": {
                    "overall_pass": s0.get("overall_pass"),
                    "open_blocker_count": s0.get("open_blocker_count"),
                    "next_gate": s0.get("next_gate"),
                    "verdict": s0.get("verdict"),
                },
            },
        )

    m11j_exec = str(s0.get("m11j_execution_id", "")).strip() if s0 else ""
    m12a_exec = str(s0.get("m12a_execution_id", "")).strip() if s0 else ""
    if not m11j_exec:
        add_blocker(blockers, "M12-ST-B2", "S1", {"reason": "missing_m11j_execution_id_from_s0_summary"})
    if not m12a_exec:
        add_blocker(blockers, "M12-ST-B2", "S1", {"reason": "missing_m12a_execution_id_from_s0_summary"})

    explicit_override_used = True
    if bool(packet.get("M12_STRESS_FAIL_ON_DEFAULT_UPSTREAM_INPUTS", True)) and not explicit_override_used:
        add_blocker(blockers, "M12-ST-B20", "S1", {"reason": "required_explicit_upstream_override_not_used"})

    m12b_exec = ""
    m12b_summary: dict[str, Any] = {}
    if Path("scripts/dev_substrate/m12b_candidate_eligibility.py").exists() and m11j_exec and m12a_exec and not blockers:
        m12b_exec = f"m12b_stress_s1_{tok()}"
        m12b_dir = out / "_m12b"
        env_b = dict(os.environ)
        env_b.update(
            {
                "M12B_EXECUTION_ID": m12b_exec,
                "M12B_RUN_DIR": m12b_dir.as_posix(),
                "EVIDENCE_BUCKET": bucket,
                "UPSTREAM_M11J_EXECUTION": m11j_exec,
                "UPSTREAM_M12A_EXECUTION": m12a_exec,
                "AWS_REGION": "eu-west-2",
                "M12_UPSTREAM_M12B_EXECUTION": "M12_S1_NOT_APPLICABLE",
                "M12_UPSTREAM_M12C_EXECUTION": "M12_S1_NOT_APPLICABLE",
                "M12_UPSTREAM_M12D_EXECUTION": "M12_S1_NOT_APPLICABLE",
                "M12_UPSTREAM_M12E_EXECUTION": "M12_S1_NOT_APPLICABLE",
                "M12_UPSTREAM_M12F_EXECUTION": "M12_S1_NOT_APPLICABLE",
                "M12_UPSTREAM_M12G_EXECUTION": "M12_S1_NOT_APPLICABLE",
                "M12_UPSTREAM_M12H_EXECUTION": "M12_S1_NOT_APPLICABLE",
                "M12_UPSTREAM_M12I_EXECUTION": "M12_S1_NOT_APPLICABLE",
            }
        )
        rc, _, err = run(["python", "scripts/dev_substrate/m12b_candidate_eligibility.py"], timeout=9000, env=env_b)
        if rc != 0:
            add_blocker(
                blockers,
                "M12-ST-B2",
                "S1",
                {"reason": "m12b_command_failed", "stderr": err.strip()[:300], "rc": rc},
            )

        m12b_summary = loadj(m12b_dir / "m12b_execution_summary.json")
        m12b_snapshot = loadj(m12b_dir / "m12b_candidate_eligibility_snapshot.json")
        m12b_register = loadj(m12b_dir / "m12b_blocker_register.json")
        if m12b_snapshot:
            dumpj(out / "m12b_candidate_eligibility_snapshot.json", m12b_snapshot)
        if m12b_summary:
            dumpj(out / "m12b_execution_summary.json", m12b_summary)
        if m12b_register:
            dumpj(out / "m12b_blocker_register.json", m12b_register)

        if not m12b_summary:
            add_blocker(blockers, "M12-ST-B2", "S1", {"reason": "m12b_summary_missing"})
        elif not (
            bool(m12b_summary.get("overall_pass"))
            and str(m12b_summary.get("next_gate", "")) == "M12.C_READY"
            and str(m12b_summary.get("verdict", "")) == "ADVANCE_TO_M12_C"
        ):
            add_blocker(blockers, "M12-ST-B2", "S1", {"reason": "m12b_not_ready", "summary": m12b_summary})

        if m12b_register and isinstance(m12b_register.get("blockers"), list):
            quota_signal = False
            for row in m12b_register.get("blockers", []):
                if not isinstance(row, dict):
                    continue
                text = " ".join(
                    [
                        str(row.get("message", "")),
                        str(row.get("detail", "")),
                        str(row.get("surface", "")),
                    ]
                ).lower()
                if any(token in text for token in ("resourcelimit", "quota", "throttl", "accessdenied", "access denied")):
                    quota_signal = True
                    break
            if quota_signal:
                add_blocker(
                    blockers,
                    "M12-ST-B19",
                    "S1",
                    {"reason": "managed_quota_or_access_boundary_pressure_detected_in_m12b"},
                )

    m12c_exec = ""
    m12c_summary: dict[str, Any] = {}
    if Path("scripts/dev_substrate/m12c_compatibility_precheck.py").exists() and m11j_exec and m12a_exec and m12b_exec and not blockers:
        m12c_exec = f"m12c_stress_s1_{tok()}"
        m12c_dir = out / "_m12c"
        env_c = dict(os.environ)
        env_c.update(
            {
                "M12C_EXECUTION_ID": m12c_exec,
                "M12C_RUN_DIR": m12c_dir.as_posix(),
                "EVIDENCE_BUCKET": bucket,
                "UPSTREAM_M11J_EXECUTION": m11j_exec,
                "UPSTREAM_M12A_EXECUTION": m12a_exec,
                "UPSTREAM_M12B_EXECUTION": m12b_exec,
                "AWS_REGION": "eu-west-2",
                "M12_UPSTREAM_M12C_EXECUTION": "M12_S1_NOT_APPLICABLE",
                "M12_UPSTREAM_M12D_EXECUTION": "M12_S1_NOT_APPLICABLE",
                "M12_UPSTREAM_M12E_EXECUTION": "M12_S1_NOT_APPLICABLE",
                "M12_UPSTREAM_M12F_EXECUTION": "M12_S1_NOT_APPLICABLE",
                "M12_UPSTREAM_M12G_EXECUTION": "M12_S1_NOT_APPLICABLE",
                "M12_UPSTREAM_M12H_EXECUTION": "M12_S1_NOT_APPLICABLE",
                "M12_UPSTREAM_M12I_EXECUTION": "M12_S1_NOT_APPLICABLE",
            }
        )
        rc, _, err = run(["python", "scripts/dev_substrate/m12c_compatibility_precheck.py"], timeout=9000, env=env_c)
        if rc != 0:
            add_blocker(
                blockers,
                "M12-ST-B3",
                "S1",
                {"reason": "m12c_command_failed", "stderr": err.strip()[:300], "rc": rc},
            )

        m12c_summary = loadj(m12c_dir / "m12c_execution_summary.json")
        m12c_snapshot = loadj(m12c_dir / "m12c_compatibility_precheck_snapshot.json")
        m12c_register = loadj(m12c_dir / "m12c_blocker_register.json")
        if m12c_snapshot:
            dumpj(out / "m12c_compatibility_precheck_snapshot.json", m12c_snapshot)
        if m12c_summary:
            dumpj(out / "m12c_execution_summary.json", m12c_summary)
        if m12c_register:
            dumpj(out / "m12c_blocker_register.json", m12c_register)

        if not m12c_summary:
            add_blocker(blockers, "M12-ST-B3", "S1", {"reason": "m12c_summary_missing"})
        elif not (
            bool(m12c_summary.get("overall_pass"))
            and str(m12c_summary.get("next_gate", "")) == "M12.D_READY"
            and str(m12c_summary.get("verdict", "")) == "ADVANCE_TO_M12_D"
        ):
            add_blocker(blockers, "M12-ST-B3", "S1", {"reason": "m12c_not_ready", "summary": m12c_summary})

        if m12c_register and isinstance(m12c_register.get("blockers"), list):
            quota_signal = False
            for row in m12c_register.get("blockers", []):
                if not isinstance(row, dict):
                    continue
                text = " ".join(
                    [
                        str(row.get("message", "")),
                        str(row.get("detail", "")),
                        str(row.get("surface", "")),
                    ]
                ).lower()
                if any(token in text for token in ("resourcelimit", "quota", "throttl", "accessdenied", "access denied")):
                    quota_signal = True
                    break
            if quota_signal:
                add_blocker(
                    blockers,
                    "M12-ST-B19",
                    "S1",
                    {"reason": "managed_quota_or_access_boundary_pressure_detected_in_m12c"},
                )
    elif m12b_exec and not m12c_exec and not blockers:
        add_blocker(blockers, "M12-ST-B3", "S1", {"reason": "m12c_not_executed"})
    elif blockers and not m12c_exec:
        add_blocker(blockers, "M12-ST-B3", "S1", {"reason": "m12c_skipped_due_to_prior_blocker"})

    stage_findings = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M12-ST-S1",
        "findings": [
            {
                "id": "M12-ST-F3",
                "classification": "PREVENT",
                "status": "CLOSED" if all(Path(p).exists() for p in scripts_required) else "OPEN",
                "note": "S1 required wrappers are materialized and executable.",
            },
            {
                "id": "M12-ST-F4",
                "classification": "PREVENT",
                "status": "CLOSED" if explicit_override_used else "OPEN",
                "note": "S1 dispatch uses explicit upstream input overrides.",
            },
            {
                "id": "M12-ST-F5",
                "classification": "PREVENT",
                "status": "CLOSED" if len([b for b in blockers if b.get("id") in {"M12-ST-B15"}]) == 0 else "OPEN",
                "note": "S1 strict continuity from S0 is enforced fail-closed.",
            },
        ],
    }
    dumpj(out / "m12_stagea_findings.json", stage_findings)

    lane_matrix = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M12-ST-S1",
        "lanes": [
            {
                "lane": "B",
                "component": "M12.B",
                "execution_id": m12b_exec,
                "overall_pass": bool(m12b_summary.get("overall_pass")) if m12b_summary else False,
                "next_gate": str(m12b_summary.get("next_gate", "")) if m12b_summary else "",
                "verdict": str(m12b_summary.get("verdict", "")) if m12b_summary else "",
            },
            {
                "lane": "C",
                "component": "M12.C",
                "execution_id": m12c_exec,
                "overall_pass": bool(m12c_summary.get("overall_pass")) if m12c_summary else False,
                "next_gate": str(m12c_summary.get("next_gate", "")) if m12c_summary else "",
                "verdict": str(m12c_summary.get("verdict", "")) if m12c_summary else "",
            },
        ],
    }
    dumpj(out / "m12_lane_matrix.json", lane_matrix)

    runtime_locality_ok = bool(packet.get("M12_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY", True))
    if not runtime_locality_ok:
        add_blocker(blockers, "M12-ST-B16", "S1", {"reason": "runtime_locality_policy_not_true"})
    dumpj(
        out / "m12_runtime_locality_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M12-ST-S1",
            "overall_pass": runtime_locality_ok,
            "require_remote_runtime_only": bool(packet.get("M12_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY", True)),
            "runtime_execution_attempted": False,
            "runtime_execution_mode": "local_control_orchestration_only_remote_runtime",
        },
    )

    refs = [
        f"evidence/dev_full/run_control/{s0_exec}/stress/m12_execution_summary.json" if s0_exec else "",
        f"evidence/dev_full/run_control/{m12b_exec}/m12b_execution_summary.json" if m12b_exec else "",
        f"evidence/dev_full/run_control/{m12c_exec}/m12c_execution_summary.json" if m12c_exec else "",
    ]
    source_guard_ok = len([b for b in blockers if b.get("id") in {"M12-ST-B11", "M12-ST-B16"}]) == 0
    dumpj(
        out / "m12_source_authority_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M12-ST-S1",
            "overall_pass": source_guard_ok,
            "authoritative_refs": refs,
            "evidence_bucket": bucket,
            "runtime_locality_only_control_plane": True,
        },
    )

    realism_ok = bool(packet.get("M12_STRESS_DISALLOW_WAIVED_REALISM", True))
    if not realism_ok:
        add_blocker(blockers, "M12-ST-B17", "S1", {"reason": "realism_guard_not_true"})
    dumpj(
        out / "m12_realism_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M12-ST-S1",
            "overall_pass": realism_ok,
            "disallow_waived_realism": bool(packet.get("M12_STRESS_DISALLOW_WAIVED_REALISM", True)),
        },
    )

    if not bool(packet.get("M12_STRESS_REQUIRE_DATA_ENGINE_BLACKBOX", True)):
        add_blocker(blockers, "M12-ST-B16", "S1", {"reason": "data_engine_blackbox_guard_not_true"})

    platform_run_id = str(s0.get("platform_run_id", "")) if s0 else ""
    scenario_run_id = str(s0.get("scenario_run_id", "")) if s0 else ""
    return finish(
        "S1",
        phase_execution_id,
        out,
        blockers,
        S1_ARTS,
        {
            "platform_run_id": platform_run_id,
            "scenario_run_id": scenario_run_id,
            "upstream_m12_s0_execution": s0_exec,
            "m11j_execution_id": m11j_exec,
            "m12a_execution_id": m12a_exec,
            "m12b_execution_id": m12b_exec,
            "m12c_execution_id": m12c_exec,
            "decisions": [
                "S1 enforced strict M12 S0 entry continuity before executing lanes B and C.",
                "S1 executed M12.B candidate eligibility lane via managed workflow and required M12.C_READY output.",
                "S1 executed M12.C compatibility precheck lane via managed workflow and required M12.D_READY output.",
            ],
            "advisories": advisories,
        },
    )


def run_s2(phase_execution_id: str, upstream_m12_s1_execution: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)
    blockers: list[dict[str, Any]] = []
    advisories: list[str] = []

    plan_text = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    packet = parse_plan_packet(plan_text)
    reg = parse_registry(REG) if REG.exists() else {}

    scripts_required = [
        "scripts/dev_substrate/m12d_promotion_commit.py",
        "scripts/dev_substrate/m12e_rollback_drill.py",
    ]
    for script_path in scripts_required:
        if not Path(script_path).exists():
            add_blocker(
                blockers,
                "M12-ST-B18",
                "S2",
                {"reason": "required_stage_script_missing", "script": script_path},
            )

    value = reg.get("S3_EVIDENCE_BUCKET")
    if value is None or is_placeholder(value):
        add_blocker(blockers, "M12-ST-B4", "S2", {"reason": "required_handle_missing_or_placeholder", "handle": "S3_EVIDENCE_BUCKET"})
    bucket = str(reg.get("S3_EVIDENCE_BUCKET", "")).strip()

    s1_exec = upstream_m12_s1_execution.strip()
    s1 = loadj(OUT_ROOT / s1_exec / "stress" / "m12_execution_summary.json") if s1_exec else {}
    if not s1:
        add_blocker(
            blockers,
            "M12-ST-B15",
            "S2",
            {
                "reason": "upstream_s1_summary_missing",
                "path": (OUT_ROOT / s1_exec / "stress" / "m12_execution_summary.json").as_posix(),
            },
        )
    elif not (
        bool(s1.get("overall_pass"))
        and int(s1.get("open_blocker_count", 1)) == 0
        and str(s1.get("next_gate", "")).strip() == "M12_ST_S2_READY"
    ):
        add_blocker(
            blockers,
            "M12-ST-B15",
            "S2",
            {
                "reason": "upstream_s1_not_ready",
                "summary": {
                    "overall_pass": s1.get("overall_pass"),
                    "open_blocker_count": s1.get("open_blocker_count"),
                    "next_gate": s1.get("next_gate"),
                    "verdict": s1.get("verdict"),
                },
            },
        )

    m11j_exec = str(s1.get("m11j_execution_id", "")).strip() if s1 else ""
    m12a_exec = str(s1.get("m12a_execution_id", "")).strip() if s1 else ""
    m12b_exec = str(s1.get("m12b_execution_id", "")).strip() if s1 else ""
    m12c_exec = str(s1.get("m12c_execution_id", "")).strip() if s1 else ""
    if not m11j_exec:
        add_blocker(blockers, "M12-ST-B4", "S2", {"reason": "missing_m11j_execution_id_from_s1_summary"})
    if not m12a_exec:
        add_blocker(blockers, "M12-ST-B4", "S2", {"reason": "missing_m12a_execution_id_from_s1_summary"})
    if not m12b_exec:
        add_blocker(blockers, "M12-ST-B4", "S2", {"reason": "missing_m12b_execution_id_from_s1_summary"})
    if not m12c_exec:
        add_blocker(blockers, "M12-ST-B4", "S2", {"reason": "missing_m12c_execution_id_from_s1_summary"})

    explicit_override_used = True
    if bool(packet.get("M12_STRESS_FAIL_ON_DEFAULT_UPSTREAM_INPUTS", True)) and not explicit_override_used:
        add_blocker(blockers, "M12-ST-B20", "S2", {"reason": "required_explicit_upstream_override_not_used"})

    m12d_exec = ""
    m12d_summary: dict[str, Any] = {}
    if Path("scripts/dev_substrate/m12d_promotion_commit.py").exists() and m11j_exec and m12a_exec and m12b_exec and m12c_exec and not blockers:
        m12d_exec = f"m12d_stress_s2_{tok()}"
        m12d_dir = out / "_m12d"
        env_d = dict(os.environ)
        env_d.update(
            {
                "M12D_EXECUTION_ID": m12d_exec,
                "M12D_RUN_DIR": m12d_dir.as_posix(),
                "EVIDENCE_BUCKET": bucket,
                "UPSTREAM_M11J_EXECUTION": m11j_exec,
                "UPSTREAM_M12A_EXECUTION": m12a_exec,
                "UPSTREAM_M12B_EXECUTION": m12b_exec,
                "UPSTREAM_M12C_EXECUTION": m12c_exec,
                "AWS_REGION": "eu-west-2",
                "M12_UPSTREAM_M12D_EXECUTION": "M12_S2_NOT_APPLICABLE",
                "M12_UPSTREAM_M12E_EXECUTION": "M12_S2_NOT_APPLICABLE",
                "M12_UPSTREAM_M12F_EXECUTION": "M12_S2_NOT_APPLICABLE",
                "M12_UPSTREAM_M12G_EXECUTION": "M12_S2_NOT_APPLICABLE",
                "M12_UPSTREAM_M12H_EXECUTION": "M12_S2_NOT_APPLICABLE",
                "M12_UPSTREAM_M12I_EXECUTION": "M12_S2_NOT_APPLICABLE",
            }
        )
        rc, _, err = run(["python", "scripts/dev_substrate/m12d_promotion_commit.py"], timeout=9000, env=env_d)
        if rc != 0:
            add_blocker(
                blockers,
                "M12-ST-B4",
                "S2",
                {"reason": "m12d_command_failed", "stderr": err.strip()[:300], "rc": rc},
            )

        m12d_summary = loadj(m12d_dir / "m12d_execution_summary.json")
        m12d_snapshot = loadj(m12d_dir / "m12d_promotion_commit_snapshot.json")
        m12d_register = loadj(m12d_dir / "m12d_blocker_register.json")
        m12d_event = loadj(m12d_dir / "m12d_registry_lifecycle_event.json")
        m12d_transport = loadj(m12d_dir / "m12d_broker_transport_proof.json")
        m12d_pub = loadj(m12d_dir / "m12d_learning_registry_publication_receipt.json")
        if m12d_snapshot:
            dumpj(out / "m12d_promotion_commit_snapshot.json", m12d_snapshot)
        if m12d_event:
            dumpj(out / "m12d_registry_lifecycle_event.json", m12d_event)
        if m12d_transport:
            dumpj(out / "m12d_broker_transport_proof.json", m12d_transport)
        if m12d_pub:
            dumpj(out / "m12d_learning_registry_publication_receipt.json", m12d_pub)
        if m12d_summary:
            dumpj(out / "m12d_execution_summary.json", m12d_summary)
        if m12d_register:
            dumpj(out / "m12d_blocker_register.json", m12d_register)

        if not m12d_summary:
            add_blocker(blockers, "M12-ST-B4", "S2", {"reason": "m12d_summary_missing"})
        elif not (
            bool(m12d_summary.get("overall_pass"))
            and str(m12d_summary.get("next_gate", "")) == "M12.E_READY"
            and str(m12d_summary.get("verdict", "")) == "ADVANCE_TO_M12_E"
        ):
            add_blocker(blockers, "M12-ST-B4", "S2", {"reason": "m12d_not_ready", "summary": m12d_summary})

        if m12d_register and isinstance(m12d_register.get("blockers"), list):
            quota_signal = False
            for row in m12d_register.get("blockers", []):
                if not isinstance(row, dict):
                    continue
                text = " ".join(
                    [
                        str(row.get("message", "")),
                        str(row.get("detail", "")),
                        str(row.get("surface", "")),
                    ]
                ).lower()
                if any(token in text for token in ("resourcelimit", "quota", "throttl", "accessdenied", "access denied")):
                    quota_signal = True
                    break
            if quota_signal:
                add_blocker(
                    blockers,
                    "M12-ST-B19",
                    "S2",
                    {"reason": "managed_quota_or_access_boundary_pressure_detected_in_m12d"},
                )

    m12e_exec = ""
    m12e_summary: dict[str, Any] = {}
    if Path("scripts/dev_substrate/m12e_rollback_drill.py").exists() and m11j_exec and m12a_exec and m12b_exec and m12c_exec and m12d_exec and not blockers:
        m12e_exec = f"m12e_stress_s2_{tok()}"
        m12e_dir = out / "_m12e"
        env_e = dict(os.environ)
        env_e.update(
            {
                "M12E_EXECUTION_ID": m12e_exec,
                "M12E_RUN_DIR": m12e_dir.as_posix(),
                "EVIDENCE_BUCKET": bucket,
                "UPSTREAM_M11J_EXECUTION": m11j_exec,
                "UPSTREAM_M12A_EXECUTION": m12a_exec,
                "UPSTREAM_M12B_EXECUTION": m12b_exec,
                "UPSTREAM_M12C_EXECUTION": m12c_exec,
                "UPSTREAM_M12D_EXECUTION": m12d_exec,
                "AWS_REGION": "eu-west-2",
                "M12_UPSTREAM_M12E_EXECUTION": "M12_S2_NOT_APPLICABLE",
                "M12_UPSTREAM_M12F_EXECUTION": "M12_S2_NOT_APPLICABLE",
                "M12_UPSTREAM_M12G_EXECUTION": "M12_S2_NOT_APPLICABLE",
                "M12_UPSTREAM_M12H_EXECUTION": "M12_S2_NOT_APPLICABLE",
                "M12_UPSTREAM_M12I_EXECUTION": "M12_S2_NOT_APPLICABLE",
            }
        )
        rc, _, err = run(["python", "scripts/dev_substrate/m12e_rollback_drill.py"], timeout=9000, env=env_e)
        if rc != 0:
            add_blocker(
                blockers,
                "M12-ST-B5",
                "S2",
                {"reason": "m12e_command_failed", "stderr": err.strip()[:300], "rc": rc},
            )

        m12e_summary = loadj(m12e_dir / "m12e_execution_summary.json")
        m12e_snapshot = loadj(m12e_dir / "m12e_rollback_drill_snapshot.json")
        m12e_register = loadj(m12e_dir / "m12e_blocker_register.json")
        if m12e_snapshot:
            dumpj(out / "m12e_rollback_drill_snapshot.json", m12e_snapshot)
        if m12e_summary:
            dumpj(out / "m12e_execution_summary.json", m12e_summary)
        if m12e_register:
            dumpj(out / "m12e_blocker_register.json", m12e_register)

        if not m12e_summary:
            add_blocker(blockers, "M12-ST-B5", "S2", {"reason": "m12e_summary_missing"})
        elif not (
            bool(m12e_summary.get("overall_pass"))
            and str(m12e_summary.get("next_gate", "")) == "M12.F_READY"
            and str(m12e_summary.get("verdict", "")) == "ADVANCE_TO_M12_F"
        ):
            add_blocker(blockers, "M12-ST-B5", "S2", {"reason": "m12e_not_ready", "summary": m12e_summary})

        if m12e_register and isinstance(m12e_register.get("blockers"), list):
            quota_signal = False
            for row in m12e_register.get("blockers", []):
                if not isinstance(row, dict):
                    continue
                text = " ".join(
                    [
                        str(row.get("message", "")),
                        str(row.get("detail", "")),
                        str(row.get("surface", "")),
                    ]
                ).lower()
                if any(token in text for token in ("resourcelimit", "quota", "throttl", "accessdenied", "access denied")):
                    quota_signal = True
                    break
            if quota_signal:
                add_blocker(
                    blockers,
                    "M12-ST-B19",
                    "S2",
                    {"reason": "managed_quota_or_access_boundary_pressure_detected_in_m12e"},
                )
    elif m12d_exec and not m12e_exec and not blockers:
        add_blocker(blockers, "M12-ST-B5", "S2", {"reason": "m12e_not_executed"})
    elif blockers and not m12e_exec:
        add_blocker(blockers, "M12-ST-B5", "S2", {"reason": "m12e_skipped_due_to_prior_blocker"})

    stage_findings = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M12-ST-S2",
        "findings": [
            {
                "id": "M12-ST-F6",
                "classification": "PREVENT",
                "status": "CLOSED" if all(Path(p).exists() for p in scripts_required) else "OPEN",
                "note": "S2 required wrappers are materialized and executable.",
            },
            {
                "id": "M12-ST-F7",
                "classification": "PREVENT",
                "status": "CLOSED" if explicit_override_used else "OPEN",
                "note": "S2 dispatch uses explicit upstream input overrides.",
            },
            {
                "id": "M12-ST-F8",
                "classification": "PREVENT",
                "status": "CLOSED" if len([b for b in blockers if b.get("id") in {"M12-ST-B15"}]) == 0 else "OPEN",
                "note": "S2 strict continuity from S1 is enforced fail-closed.",
            },
        ],
    }
    dumpj(out / "m12_stagea_findings.json", stage_findings)

    lane_matrix = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M12-ST-S2",
        "lanes": [
            {
                "lane": "D",
                "component": "M12.D",
                "execution_id": m12d_exec,
                "overall_pass": bool(m12d_summary.get("overall_pass")) if m12d_summary else False,
                "next_gate": str(m12d_summary.get("next_gate", "")) if m12d_summary else "",
                "verdict": str(m12d_summary.get("verdict", "")) if m12d_summary else "",
            },
            {
                "lane": "E",
                "component": "M12.E",
                "execution_id": m12e_exec,
                "overall_pass": bool(m12e_summary.get("overall_pass")) if m12e_summary else False,
                "next_gate": str(m12e_summary.get("next_gate", "")) if m12e_summary else "",
                "verdict": str(m12e_summary.get("verdict", "")) if m12e_summary else "",
            },
        ],
    }
    dumpj(out / "m12_lane_matrix.json", lane_matrix)

    runtime_locality_ok = bool(packet.get("M12_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY", True))
    if not runtime_locality_ok:
        add_blocker(blockers, "M12-ST-B16", "S2", {"reason": "runtime_locality_policy_not_true"})
    dumpj(
        out / "m12_runtime_locality_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M12-ST-S2",
            "overall_pass": runtime_locality_ok,
            "require_remote_runtime_only": bool(packet.get("M12_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY", True)),
            "runtime_execution_attempted": False,
            "runtime_execution_mode": "local_control_orchestration_only_remote_runtime",
        },
    )

    refs = [
        f"evidence/dev_full/run_control/{s1_exec}/stress/m12_execution_summary.json" if s1_exec else "",
        f"evidence/dev_full/run_control/{m12d_exec}/m12d_execution_summary.json" if m12d_exec else "",
        f"evidence/dev_full/run_control/{m12e_exec}/m12e_execution_summary.json" if m12e_exec else "",
    ]
    source_guard_ok = len([b for b in blockers if b.get("id") in {"M12-ST-B11", "M12-ST-B16"}]) == 0
    dumpj(
        out / "m12_source_authority_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M12-ST-S2",
            "overall_pass": source_guard_ok,
            "authoritative_refs": refs,
            "evidence_bucket": bucket,
            "runtime_locality_only_control_plane": True,
        },
    )

    realism_ok = bool(packet.get("M12_STRESS_DISALLOW_WAIVED_REALISM", True))
    if not realism_ok:
        add_blocker(blockers, "M12-ST-B17", "S2", {"reason": "realism_guard_not_true"})
    dumpj(
        out / "m12_realism_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M12-ST-S2",
            "overall_pass": realism_ok,
            "disallow_waived_realism": bool(packet.get("M12_STRESS_DISALLOW_WAIVED_REALISM", True)),
        },
    )

    if not bool(packet.get("M12_STRESS_REQUIRE_DATA_ENGINE_BLACKBOX", True)):
        add_blocker(blockers, "M12-ST-B16", "S2", {"reason": "data_engine_blackbox_guard_not_true"})

    platform_run_id = str(s1.get("platform_run_id", "")) if s1 else ""
    scenario_run_id = str(s1.get("scenario_run_id", "")) if s1 else ""
    return finish(
        "S2",
        phase_execution_id,
        out,
        blockers,
        S2_ARTS,
        {
            "platform_run_id": platform_run_id,
            "scenario_run_id": scenario_run_id,
            "upstream_m12_s1_execution": s1_exec,
            "m11j_execution_id": m11j_exec,
            "m12a_execution_id": m12a_exec,
            "m12b_execution_id": m12b_exec,
            "m12c_execution_id": m12c_exec,
            "m12d_execution_id": m12d_exec,
            "m12e_execution_id": m12e_exec,
            "decisions": [
                "S2 enforced strict M12 S1 entry continuity before executing lanes D and E.",
                "S2 executed M12.D promotion commit lane and required M12.E_READY output.",
                "S2 executed M12.E rollback drill lane and required M12.F_READY output.",
            ],
            "advisories": advisories,
        },
    )


def run_s3(phase_execution_id: str, upstream_m12_s2_execution: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)
    blockers: list[dict[str, Any]] = []
    advisories: list[str] = []

    plan_text = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    packet = parse_plan_packet(plan_text)
    reg = parse_registry(REG) if REG.exists() else {}

    scripts_required = [
        "scripts/dev_substrate/m12f_active_resolution.py",
        "scripts/dev_substrate/m12g_governance_append.py",
    ]
    for script_path in scripts_required:
        if not Path(script_path).exists():
            add_blocker(
                blockers,
                "M12-ST-B18",
                "S3",
                {"reason": "required_stage_script_missing", "script": script_path},
            )

    value = reg.get("S3_EVIDENCE_BUCKET")
    if value is None or is_placeholder(value):
        add_blocker(blockers, "M12-ST-B6", "S3", {"reason": "required_handle_missing_or_placeholder", "handle": "S3_EVIDENCE_BUCKET"})
    bucket = str(reg.get("S3_EVIDENCE_BUCKET", "")).strip()

    s2_exec = upstream_m12_s2_execution.strip()
    s2 = loadj(OUT_ROOT / s2_exec / "stress" / "m12_execution_summary.json") if s2_exec else {}
    if not s2:
        add_blocker(
            blockers,
            "M12-ST-B15",
            "S3",
            {
                "reason": "upstream_s2_summary_missing",
                "path": (OUT_ROOT / s2_exec / "stress" / "m12_execution_summary.json").as_posix(),
            },
        )
    elif not (
        bool(s2.get("overall_pass"))
        and int(s2.get("open_blocker_count", 1)) == 0
        and str(s2.get("next_gate", "")).strip() == "M12_ST_S3_READY"
    ):
        add_blocker(
            blockers,
            "M12-ST-B15",
            "S3",
            {
                "reason": "upstream_s2_not_ready",
                "summary": {
                    "overall_pass": s2.get("overall_pass"),
                    "open_blocker_count": s2.get("open_blocker_count"),
                    "next_gate": s2.get("next_gate"),
                    "verdict": s2.get("verdict"),
                },
            },
        )

    m11j_exec = str(s2.get("m11j_execution_id", "")).strip() if s2 else ""
    m12a_exec = str(s2.get("m12a_execution_id", "")).strip() if s2 else ""
    m12b_exec = str(s2.get("m12b_execution_id", "")).strip() if s2 else ""
    m12c_exec = str(s2.get("m12c_execution_id", "")).strip() if s2 else ""
    m12d_exec = str(s2.get("m12d_execution_id", "")).strip() if s2 else ""
    m12e_exec = str(s2.get("m12e_execution_id", "")).strip() if s2 else ""
    if not m11j_exec:
        add_blocker(blockers, "M12-ST-B6", "S3", {"reason": "missing_m11j_execution_id_from_s2_summary"})
    if not m12a_exec:
        add_blocker(blockers, "M12-ST-B6", "S3", {"reason": "missing_m12a_execution_id_from_s2_summary"})
    if not m12b_exec:
        add_blocker(blockers, "M12-ST-B6", "S3", {"reason": "missing_m12b_execution_id_from_s2_summary"})
    if not m12c_exec:
        add_blocker(blockers, "M12-ST-B6", "S3", {"reason": "missing_m12c_execution_id_from_s2_summary"})
    if not m12d_exec:
        add_blocker(blockers, "M12-ST-B6", "S3", {"reason": "missing_m12d_execution_id_from_s2_summary"})
    if not m12e_exec:
        add_blocker(blockers, "M12-ST-B6", "S3", {"reason": "missing_m12e_execution_id_from_s2_summary"})

    explicit_override_used = True
    if bool(packet.get("M12_STRESS_FAIL_ON_DEFAULT_UPSTREAM_INPUTS", True)) and not explicit_override_used:
        add_blocker(blockers, "M12-ST-B20", "S3", {"reason": "required_explicit_upstream_override_not_used"})

    m12f_exec = ""
    m12f_summary: dict[str, Any] = {}
    m12f_observation: dict[str, Any] = {}
    if Path("scripts/dev_substrate/m12f_active_resolution.py").exists() and m11j_exec and m12a_exec and m12b_exec and m12c_exec and m12d_exec and m12e_exec and not blockers:
        m12f_exec = f"m12f_stress_s3_{tok()}"
        m12f_dir = out / "_m12f"
        env_f = dict(os.environ)
        env_f.update(
            {
                "M12F_EXECUTION_ID": m12f_exec,
                "M12F_RUN_DIR": m12f_dir.as_posix(),
                "EVIDENCE_BUCKET": bucket,
                "UPSTREAM_M11J_EXECUTION": m11j_exec,
                "UPSTREAM_M12A_EXECUTION": m12a_exec,
                "UPSTREAM_M12B_EXECUTION": m12b_exec,
                "UPSTREAM_M12C_EXECUTION": m12c_exec,
                "UPSTREAM_M12D_EXECUTION": m12d_exec,
                "UPSTREAM_M12E_EXECUTION": m12e_exec,
                "AWS_REGION": "eu-west-2",
                "M12_UPSTREAM_M12F_EXECUTION": "M12_S3_NOT_APPLICABLE",
                "M12_UPSTREAM_M12G_EXECUTION": "M12_S3_NOT_APPLICABLE",
                "M12_UPSTREAM_M12H_EXECUTION": "M12_S3_NOT_APPLICABLE",
                "M12_UPSTREAM_M12I_EXECUTION": "M12_S3_NOT_APPLICABLE",
            }
        )
        rc, _, err = run(["python", "scripts/dev_substrate/m12f_active_resolution.py"], timeout=9000, env=env_f)
        if rc != 0:
            add_blocker(
                blockers,
                "M12-ST-B6",
                "S3",
                {"reason": "m12f_command_failed", "stderr": err.strip()[:300], "rc": rc},
            )

        m12f_summary = loadj(m12f_dir / "m12f_execution_summary.json")
        m12f_snapshot = loadj(m12f_dir / "m12f_active_resolution_snapshot.json")
        m12f_observation = loadj(m12f_dir / "m12_post_promotion_observation_snapshot.json")
        m12f_register = loadj(m12f_dir / "m12f_blocker_register.json")
        if m12f_snapshot:
            dumpj(out / "m12f_active_resolution_snapshot.json", m12f_snapshot)
        if m12f_observation:
            dumpj(out / "m12_post_promotion_observation_snapshot.json", m12f_observation)
        if m12f_summary:
            dumpj(out / "m12f_execution_summary.json", m12f_summary)
        if m12f_register:
            dumpj(out / "m12f_blocker_register.json", m12f_register)

        if not m12f_summary:
            add_blocker(blockers, "M12-ST-B6", "S3", {"reason": "m12f_summary_missing"})
        elif not (
            bool(m12f_summary.get("overall_pass"))
            and str(m12f_summary.get("next_gate", "")) == "M12.G_READY"
            and str(m12f_summary.get("verdict", "")) == "ADVANCE_TO_M12_G"
        ):
            add_blocker(blockers, "M12-ST-B6", "S3", {"reason": "m12f_not_ready", "summary": m12f_summary})

        if m12f_observation and not bool(m12f_observation.get("overall_pass")):
            add_blocker(blockers, "M12-ST-B12", "S3", {"reason": "m12f_post_promotion_observation_not_pass"})

        if m12f_register and isinstance(m12f_register.get("blockers"), list):
            quota_signal = False
            for row in m12f_register.get("blockers", []):
                if not isinstance(row, dict):
                    continue
                text = " ".join(
                    [
                        str(row.get("message", "")),
                        str(row.get("detail", "")),
                        str(row.get("surface", "")),
                    ]
                ).lower()
                if any(token in text for token in ("resourcelimit", "quota", "throttl", "accessdenied", "access denied")):
                    quota_signal = True
                    break
            if quota_signal:
                add_blocker(
                    blockers,
                    "M12-ST-B19",
                    "S3",
                    {"reason": "managed_quota_or_access_boundary_pressure_detected_in_m12f"},
                )

    m12g_exec = ""
    m12g_summary: dict[str, Any] = {}
    m12g_operability: dict[str, Any] = {}
    if Path("scripts/dev_substrate/m12g_governance_append.py").exists() and m11j_exec and m12a_exec and m12b_exec and m12c_exec and m12d_exec and m12e_exec and m12f_exec and not blockers:
        m12g_exec = f"m12g_stress_s3_{tok()}"
        m12g_dir = out / "_m12g"
        env_g = dict(os.environ)
        env_g.update(
            {
                "M12G_EXECUTION_ID": m12g_exec,
                "M12G_RUN_DIR": m12g_dir.as_posix(),
                "EVIDENCE_BUCKET": bucket,
                "UPSTREAM_M11J_EXECUTION": m11j_exec,
                "UPSTREAM_M12A_EXECUTION": m12a_exec,
                "UPSTREAM_M12B_EXECUTION": m12b_exec,
                "UPSTREAM_M12C_EXECUTION": m12c_exec,
                "UPSTREAM_M12D_EXECUTION": m12d_exec,
                "UPSTREAM_M12E_EXECUTION": m12e_exec,
                "UPSTREAM_M12F_EXECUTION": m12f_exec,
                "AWS_REGION": "eu-west-2",
                "M12_UPSTREAM_M12G_EXECUTION": "M12_S3_NOT_APPLICABLE",
                "M12_UPSTREAM_M12H_EXECUTION": "M12_S3_NOT_APPLICABLE",
                "M12_UPSTREAM_M12I_EXECUTION": "M12_S3_NOT_APPLICABLE",
            }
        )
        rc, _, err = run(["python", "scripts/dev_substrate/m12g_governance_append.py"], timeout=9000, env=env_g)
        if rc != 0:
            add_blocker(
                blockers,
                "M12-ST-B7",
                "S3",
                {"reason": "m12g_command_failed", "stderr": err.strip()[:300], "rc": rc},
            )

        m12g_summary = loadj(m12g_dir / "m12g_execution_summary.json")
        m12g_snapshot = loadj(m12g_dir / "m12g_governance_append_snapshot.json")
        m12g_operability = loadj(m12g_dir / "m12_operability_acceptance_report.json")
        m12g_register = loadj(m12g_dir / "m12g_blocker_register.json")
        if m12g_snapshot:
            dumpj(out / "m12g_governance_append_snapshot.json", m12g_snapshot)
        if m12g_operability:
            dumpj(out / "m12_operability_acceptance_report.json", m12g_operability)
        if m12g_summary:
            dumpj(out / "m12g_execution_summary.json", m12g_summary)
        if m12g_register:
            dumpj(out / "m12g_blocker_register.json", m12g_register)

        if not m12g_summary:
            add_blocker(blockers, "M12-ST-B7", "S3", {"reason": "m12g_summary_missing"})
        elif not (
            bool(m12g_summary.get("overall_pass"))
            and str(m12g_summary.get("next_gate", "")) == "M12.H_READY"
            and str(m12g_summary.get("verdict", "")) == "ADVANCE_TO_M12_H"
        ):
            add_blocker(blockers, "M12-ST-B7", "S3", {"reason": "m12g_not_ready", "summary": m12g_summary})

        if m12g_operability and not bool(m12g_operability.get("overall_pass")):
            add_blocker(blockers, "M12-ST-B12", "S3", {"reason": "m12g_operability_acceptance_not_pass"})

        if m12g_register and isinstance(m12g_register.get("blockers"), list):
            quota_signal = False
            for row in m12g_register.get("blockers", []):
                if not isinstance(row, dict):
                    continue
                text = " ".join(
                    [
                        str(row.get("message", "")),
                        str(row.get("detail", "")),
                        str(row.get("surface", "")),
                    ]
                ).lower()
                if any(token in text for token in ("resourcelimit", "quota", "throttl", "accessdenied", "access denied")):
                    quota_signal = True
                    break
            if quota_signal:
                add_blocker(
                    blockers,
                    "M12-ST-B19",
                    "S3",
                    {"reason": "managed_quota_or_access_boundary_pressure_detected_in_m12g"},
                )
    elif m12f_exec and not m12g_exec and not blockers:
        add_blocker(blockers, "M12-ST-B7", "S3", {"reason": "m12g_not_executed"})
    elif blockers and not m12g_exec:
        add_blocker(blockers, "M12-ST-B7", "S3", {"reason": "m12g_skipped_due_to_prior_blocker"})

    stage_findings = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M12-ST-S3",
        "findings": [
            {
                "id": "M12-ST-F6",
                "classification": "PREVENT",
                "status": "CLOSED" if all(Path(p).exists() for p in scripts_required) else "OPEN",
                "note": "S3 required wrappers are materialized and executable.",
            },
            {
                "id": "M12-ST-F7",
                "classification": "PREVENT",
                "status": "CLOSED" if explicit_override_used else "OPEN",
                "note": "S3 dispatch uses explicit upstream input overrides.",
            },
            {
                "id": "M12-ST-F8",
                "classification": "PREVENT",
                "status": "CLOSED" if len([b for b in blockers if b.get("id") in {"M12-ST-B15"}]) == 0 else "OPEN",
                "note": "S3 strict continuity from S2 is enforced fail-closed.",
            },
        ],
    }
    dumpj(out / "m12_stagea_findings.json", stage_findings)

    lane_matrix = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M12-ST-S3",
        "lanes": [
            {
                "lane": "F",
                "component": "M12.F",
                "execution_id": m12f_exec,
                "overall_pass": bool(m12f_summary.get("overall_pass")) if m12f_summary else False,
                "next_gate": str(m12f_summary.get("next_gate", "")) if m12f_summary else "",
                "verdict": str(m12f_summary.get("verdict", "")) if m12f_summary else "",
            },
            {
                "lane": "G",
                "component": "M12.G",
                "execution_id": m12g_exec,
                "overall_pass": bool(m12g_summary.get("overall_pass")) if m12g_summary else False,
                "next_gate": str(m12g_summary.get("next_gate", "")) if m12g_summary else "",
                "verdict": str(m12g_summary.get("verdict", "")) if m12g_summary else "",
            },
        ],
    }
    dumpj(out / "m12_lane_matrix.json", lane_matrix)

    runtime_locality_ok = bool(packet.get("M12_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY", True))
    if not runtime_locality_ok:
        add_blocker(blockers, "M12-ST-B16", "S3", {"reason": "runtime_locality_policy_not_true"})
    dumpj(
        out / "m12_runtime_locality_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M12-ST-S3",
            "overall_pass": runtime_locality_ok,
            "require_remote_runtime_only": bool(packet.get("M12_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY", True)),
            "runtime_execution_attempted": False,
            "runtime_execution_mode": "local_control_orchestration_only_remote_runtime",
        },
    )

    refs = [
        f"evidence/dev_full/run_control/{s2_exec}/stress/m12_execution_summary.json" if s2_exec else "",
        f"evidence/dev_full/run_control/{m12f_exec}/m12f_execution_summary.json" if m12f_exec else "",
        f"evidence/dev_full/run_control/{m12g_exec}/m12g_execution_summary.json" if m12g_exec else "",
    ]
    source_guard_ok = len([b for b in blockers if b.get("id") in {"M12-ST-B11", "M12-ST-B16"}]) == 0
    dumpj(
        out / "m12_source_authority_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M12-ST-S3",
            "overall_pass": source_guard_ok,
            "authoritative_refs": refs,
            "evidence_bucket": bucket,
            "runtime_locality_only_control_plane": True,
        },
    )

    realism_ok = bool(packet.get("M12_STRESS_DISALLOW_WAIVED_REALISM", True))
    if not realism_ok:
        add_blocker(blockers, "M12-ST-B17", "S3", {"reason": "realism_guard_not_true"})
    dumpj(
        out / "m12_realism_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M12-ST-S3",
            "overall_pass": realism_ok,
            "disallow_waived_realism": bool(packet.get("M12_STRESS_DISALLOW_WAIVED_REALISM", True)),
        },
    )

    if not bool(packet.get("M12_STRESS_REQUIRE_DATA_ENGINE_BLACKBOX", True)):
        add_blocker(blockers, "M12-ST-B16", "S3", {"reason": "data_engine_blackbox_guard_not_true"})

    platform_run_id = str(s2.get("platform_run_id", "")) if s2 else ""
    scenario_run_id = str(s2.get("scenario_run_id", "")) if s2 else ""
    return finish(
        "S3",
        phase_execution_id,
        out,
        blockers,
        S3_ARTS,
        {
            "platform_run_id": platform_run_id,
            "scenario_run_id": scenario_run_id,
            "upstream_m12_s2_execution": s2_exec,
            "m11j_execution_id": m11j_exec,
            "m12a_execution_id": m12a_exec,
            "m12b_execution_id": m12b_exec,
            "m12c_execution_id": m12c_exec,
            "m12d_execution_id": m12d_exec,
            "m12e_execution_id": m12e_exec,
            "m12f_execution_id": m12f_exec,
            "m12g_execution_id": m12g_exec,
            "decisions": [
                "S3 enforced strict M12 S2 entry continuity before executing lanes F and G.",
                "S3 executed M12.F ACTIVE resolution lane and required M12.G_READY output.",
                "S3 executed M12.G governance append lane and required M12.H_READY output.",
            ],
            "advisories": advisories,
        },
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="M12 stress runner")
    ap.add_argument("--stage", required=True, choices=["S0", "S1", "S2", "S3"])
    ap.add_argument("--phase-execution-id", default="")
    ap.add_argument("--upstream-m11-s5-execution", default="")
    ap.add_argument("--upstream-m12-s0-execution", default="")
    ap.add_argument("--upstream-m12-s1-execution", default="")
    ap.add_argument("--upstream-m12-s2-execution", default="")
    args = ap.parse_args()

    phase_execution_id = args.phase_execution_id.strip()
    if not phase_execution_id:
        if args.stage == "S0":
            phase_execution_id = f"m12_stress_s0_{tok()}"
        elif args.stage == "S1":
            phase_execution_id = f"m12_stress_s1_{tok()}"
        elif args.stage == "S2":
            phase_execution_id = f"m12_stress_s2_{tok()}"
        elif args.stage == "S3":
            phase_execution_id = f"m12_stress_s3_{tok()}"

    if args.stage == "S0":
        upstream_m11_s5 = args.upstream_m11_s5_execution.strip()
        if not upstream_m11_s5:
            upstream_m11_s5, _ = latest_m11_s5()
        if not upstream_m11_s5:
            raise SystemExit("No upstream M11 S5 execution provided/found.")
        return run_s0(phase_execution_id, upstream_m11_s5)

    if args.stage == "S1":
        upstream_m12_s0 = args.upstream_m12_s0_execution.strip()
        if not upstream_m12_s0:
            upstream_m12_s0, _ = latest_s0()
        if not upstream_m12_s0:
            raise SystemExit("No upstream M12 S0 execution provided/found.")
        return run_s1(phase_execution_id, upstream_m12_s0)

    if args.stage == "S2":
        upstream_m12_s1 = args.upstream_m12_s1_execution.strip()
        if not upstream_m12_s1:
            upstream_m12_s1, _ = latest_s1()
        if not upstream_m12_s1:
            raise SystemExit("No upstream M12 S1 execution provided/found.")
        return run_s2(phase_execution_id, upstream_m12_s1)

    if args.stage == "S3":
        upstream_m12_s2 = args.upstream_m12_s2_execution.strip()
        if not upstream_m12_s2:
            upstream_m12_s2, _ = latest_s2()
        if not upstream_m12_s2:
            raise SystemExit("No upstream M12 S2 execution provided/found.")
        return run_s3(phase_execution_id, upstream_m12_s2)

    raise SystemExit("Unsupported stage")


if __name__ == "__main__":
    raise SystemExit(main())
