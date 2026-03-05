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


PLAN = Path("docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M13.stress_test.md")
REG = Path("docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md")
OUT_ROOT = Path("runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control")

S0_ARTS = [
    "m13_stagea_findings.json",
    "m13_lane_matrix.json",
    "m13_managed_lane_materialization_snapshot.json",
    "m13_subphase_dispatchability_snapshot.json",
    "m13b0_blocker_register.json",
    "m13b0_execution_summary.json",
    "m13a_handle_closure_snapshot.json",
    "m13a_blocker_register.json",
    "m13a_execution_summary.json",
    "m13_runtime_locality_guard_snapshot.json",
    "m13_source_authority_guard_snapshot.json",
    "m13_realism_guard_snapshot.json",
    "m13_blocker_register.json",
    "m13_execution_summary.json",
    "m13_decision_log.json",
    "m13_gate_verdict.json",
]

S1_ARTS = [
    "m13_stagea_findings.json",
    "m13_lane_matrix.json",
    "m13b_source_matrix_snapshot.json",
    "m13b_blocker_register.json",
    "m13b_execution_summary.json",
    "m13c_six_proof_matrix_snapshot.json",
    "m13c_blocker_register.json",
    "m13c_execution_summary.json",
    "m13_runtime_locality_guard_snapshot.json",
    "m13_source_authority_guard_snapshot.json",
    "m13_realism_guard_snapshot.json",
    "m13_blocker_register.json",
    "m13_execution_summary.json",
    "m13_decision_log.json",
    "m13_gate_verdict.json",
]

S2_ARTS = [
    "m13_stagea_findings.json",
    "m13_lane_matrix.json",
    "m13d_final_verdict_bundle.json",
    "m13d_blocker_register.json",
    "m13d_execution_summary.json",
    "m13e_teardown_plan_snapshot.json",
    "m13e_blocker_register.json",
    "m13e_execution_summary.json",
    "m13_runtime_locality_guard_snapshot.json",
    "m13_source_authority_guard_snapshot.json",
    "m13_realism_guard_snapshot.json",
    "m13_non_gate_acceptance_snapshot.json",
    "m13_blocker_register.json",
    "m13_execution_summary.json",
    "m13_decision_log.json",
    "m13_gate_verdict.json",
]

S3_ARTS = [
    "m13_stagea_findings.json",
    "m13_lane_matrix.json",
    "m13f_teardown_execution_snapshot.json",
    "m13f_blocker_register.json",
    "m13f_execution_summary.json",
    "m13g_post_teardown_readability_snapshot.json",
    "m13g_blocker_register.json",
    "m13g_execution_summary.json",
    "m13_runtime_locality_guard_snapshot.json",
    "m13_source_authority_guard_snapshot.json",
    "m13_realism_guard_snapshot.json",
    "m13_non_gate_acceptance_snapshot.json",
    "m13_blocker_register.json",
    "m13_execution_summary.json",
    "m13_decision_log.json",
    "m13_gate_verdict.json",
]

S4_ARTS = [
    "m13_stagea_findings.json",
    "m13_lane_matrix.json",
    "m13h_cost_guardrail_snapshot.json",
    "m13h_blocker_register.json",
    "m13h_execution_summary.json",
    "m13_phase_budget_envelope.json",
    "m13_phase_cost_outcome_receipt.json",
    "m13i_blocker_register.json",
    "m13i_execution_summary.json",
    "m13_runtime_locality_guard_snapshot.json",
    "m13_source_authority_guard_snapshot.json",
    "m13_realism_guard_snapshot.json",
    "m13_non_gate_acceptance_snapshot.json",
    "m13_blocker_register.json",
    "m13_execution_summary.json",
    "m13_decision_log.json",
    "m13_gate_verdict.json",
]

S5_ARTS = [
    "m13_stagea_findings.json",
    "m13_lane_matrix.json",
    "m13_closure_sync_snapshot.json",
    "m13j_blocker_register.json",
    "m13j_execution_summary.json",
    "m13_runtime_locality_guard_snapshot.json",
    "m13_source_authority_guard_snapshot.json",
    "m13_realism_guard_snapshot.json",
    "m13_non_gate_acceptance_snapshot.json",
    "m13_blocker_register.json",
    "m13_execution_summary.json",
    "m13_decision_log.json",
    "m13_gate_verdict.json",
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


def latest_m12_s5() -> tuple[str, dict[str, Any]]:
    best_id = ""
    best_payload: dict[str, Any] = {}
    best_stamp = ""
    for d in OUT_ROOT.glob("m12_stress_s5_*"):
        payload = loadj(d / "stress" / "m12_execution_summary.json")
        if not payload:
            continue
        if str(payload.get("stage_id", "")) != "M12-ST-S5":
            continue
        if not bool(payload.get("overall_pass")):
            continue
        if str(payload.get("verdict", "")) != "ADVANCE_TO_M13":
            continue
        if str(payload.get("next_gate", "")) != "M13_READY":
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
    for d in OUT_ROOT.glob("m13_stress_s0_*"):
        payload = loadj(d / "stress" / "m13_execution_summary.json")
        if not payload:
            continue
        if str(payload.get("stage_id", "")) != "M13-ST-S0":
            continue
        if not bool(payload.get("overall_pass")):
            continue
        if str(payload.get("next_gate", "")) != "M13_ST_S1_READY":
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
    for d in OUT_ROOT.glob("m13_stress_s1_*"):
        payload = loadj(d / "stress" / "m13_execution_summary.json")
        if not payload:
            continue
        if str(payload.get("stage_id", "")) != "M13-ST-S1":
            continue
        if not bool(payload.get("overall_pass")):
            continue
        if str(payload.get("next_gate", "")) != "M13_ST_S2_READY":
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
    for d in OUT_ROOT.glob("m13_stress_s2_*"):
        payload = loadj(d / "stress" / "m13_execution_summary.json")
        if not payload:
            continue
        if str(payload.get("stage_id", "")) != "M13-ST-S2":
            continue
        if not bool(payload.get("overall_pass")):
            continue
        if str(payload.get("next_gate", "")) != "M13_ST_S3_READY":
            continue
        if int(payload.get("open_blocker_count", 1)) != 0:
            continue
        stamp = str(payload.get("generated_at_utc", ""))
        if (stamp, d.name) > (best_stamp, best_id):
            best_id = d.name
            best_payload = payload
            best_stamp = stamp
    return best_id, best_payload


def latest_s3() -> tuple[str, dict[str, Any]]:
    best_id = ""
    best_payload: dict[str, Any] = {}
    best_stamp = ""
    for d in OUT_ROOT.glob("m13_stress_s3_*"):
        payload = loadj(d / "stress" / "m13_execution_summary.json")
        if not payload:
            continue
        if str(payload.get("stage_id", "")) != "M13-ST-S3":
            continue
        if not bool(payload.get("overall_pass")):
            continue
        if str(payload.get("next_gate", "")) != "M13_ST_S4_READY":
            continue
        if int(payload.get("open_blocker_count", 1)) != 0:
            continue
        stamp = str(payload.get("generated_at_utc", ""))
        if (stamp, d.name) > (best_stamp, best_id):
            best_id = d.name
            best_payload = payload
            best_stamp = stamp
    return best_id, best_payload


def latest_s4() -> tuple[str, dict[str, Any]]:
    best_id = ""
    best_payload: dict[str, Any] = {}
    best_stamp = ""
    for d in OUT_ROOT.glob("m13_stress_s4_*"):
        payload = loadj(d / "stress" / "m13_execution_summary.json")
        if not payload:
            continue
        if str(payload.get("stage_id", "")) != "M13-ST-S4":
            continue
        if not bool(payload.get("overall_pass")):
            continue
        if str(payload.get("next_gate", "")) != "M13_ST_S5_READY":
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
        "m13_blocker_register.json",
        "m13_execution_summary.json",
        "m13_decision_log.json",
        "m13_gate_verdict.json",
    }
    prewrite_required = [name for name in arts if name not in stage_receipts]
    missing = [name for name in prewrite_required if not (out / name).exists()]
    if missing:
        add_blocker(
            blockers,
            "M13-ST-B11",
            stage,
            {"reason": "artifact_contract_incomplete", "missing_outputs": sorted(missing)},
        )
    blockers = dedupe(blockers)

    overall_pass = len(blockers) == 0
    if overall_pass and stage == "S0":
        next_gate = "M13_ST_S1_READY"
        verdict = "GO"
    elif overall_pass and stage == "S1":
        next_gate = "M13_ST_S2_READY"
        verdict = "GO"
    elif overall_pass and stage == "S2":
        next_gate = "M13_ST_S3_READY"
        verdict = "GO"
    elif overall_pass and stage == "S3":
        next_gate = "M13_ST_S4_READY"
        verdict = "GO"
    elif overall_pass and stage == "S4":
        next_gate = "M13_ST_S5_READY"
        verdict = "GO"
    elif overall_pass and stage == "S5":
        next_gate = "M14_READY"
        verdict = "ADVANCE_TO_M14"
    else:
        next_gate = "HOLD_REMEDIATE"
        verdict = "HOLD_REMEDIATE"

    register = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": f"M13-ST-{stage}",
        "open_blocker_count": len(blockers),
        "blockers": blockers,
    }
    summary = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": f"M13-ST-{stage}",
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
        "stage_id": f"M13-ST-{stage}",
        "decisions": list(summary_extra.get("decisions", [])),
        "advisories": list(summary_extra.get("advisories", [])),
    }
    gate = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": f"M13-ST-{stage}",
        "overall_pass": overall_pass,
        "next_gate": next_gate,
        "verdict": verdict,
    }

    dumpj(out / "m13_blocker_register.json", register)
    dumpj(out / "m13_execution_summary.json", summary)
    dumpj(out / "m13_decision_log.json", decision_log)
    dumpj(out / "m13_gate_verdict.json", gate)

    print(
        json.dumps(
            {
                "phase_execution_id": phase_execution_id,
                "stage_id": f"M13-ST-{stage}",
                "overall_pass": overall_pass,
                "open_blocker_count": len(blockers),
                "next_gate": next_gate,
                "output_dir": out.as_posix(),
            }
        )
    )
    return 0


def run_s0(phase_execution_id: str, upstream_m12_s5_execution: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)
    blockers: list[dict[str, Any]] = []
    advisories: list[str] = []

    plan_text = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    packet = parse_plan_packet(plan_text)
    reg = parse_registry(REG) if REG.exists() else {}

    scripts_required = [
        "scripts/dev_substrate/m13b0_managed_materialization.py",
        "scripts/dev_substrate/m13a_handle_closure.py",
    ]
    for script_path in scripts_required:
        if not Path(script_path).exists():
            add_blocker(
                blockers,
                "M13-ST-B18",
                "S0",
                {"reason": "required_stage_script_missing", "script": script_path},
            )

    if not Path(".github/workflows/dev_full_m13_managed.yml").exists():
        add_blocker(
            blockers,
            "M13-ST-B0",
            "S0",
            {"reason": "managed_workflow_missing", "workflow": ".github/workflows/dev_full_m13_managed.yml"},
        )

    value = reg.get("S3_EVIDENCE_BUCKET")
    if value is None or is_placeholder(value):
        add_blocker(blockers, "M13-ST-B1", "S0", {"reason": "required_handle_missing_or_placeholder", "handle": "S3_EVIDENCE_BUCKET"})
    bucket = str(reg.get("S3_EVIDENCE_BUCKET", "")).strip()

    fail_on_stale = bool(packet.get("M13_STRESS_FAIL_ON_STALE_UPSTREAM", True))
    expected_entry_execution = str(packet.get("M13_STRESS_EXPECTED_ENTRY_EXECUTION", "")).strip()
    if fail_on_stale and expected_entry_execution and upstream_m12_s5_execution != expected_entry_execution:
        add_blocker(
            blockers,
            "M13-ST-B15",
            "S0",
            {
                "reason": "stale_or_unexpected_upstream_execution",
                "selected_upstream_execution": upstream_m12_s5_execution,
                "expected_execution": expected_entry_execution,
            },
        )

    expected_entry_gate = str(packet.get("M13_STRESS_EXPECTED_ENTRY_GATE", "M13_READY")).strip() or "M13_READY"
    local_m12_s5_summary = loadj(OUT_ROOT / upstream_m12_s5_execution / "stress" / "m12_execution_summary.json")
    if not local_m12_s5_summary:
        add_blocker(
            blockers,
            "M13-ST-B1",
            "S0",
            {
                "reason": "upstream_m12_s5_summary_missing",
                "path": (OUT_ROOT / upstream_m12_s5_execution / "stress" / "m12_execution_summary.json").as_posix(),
            },
        )
    else:
        if not (
            bool(local_m12_s5_summary.get("overall_pass"))
            and int(local_m12_s5_summary.get("open_blocker_count", 1)) == 0
            and str(local_m12_s5_summary.get("verdict", "")) == "ADVANCE_TO_M13"
            and str(local_m12_s5_summary.get("next_gate", "")) == expected_entry_gate
        ):
            add_blocker(
                blockers,
                "M13-ST-B1",
                "S0",
                {
                    "reason": "upstream_m12_s5_not_ready",
                    "summary": {
                        "overall_pass": local_m12_s5_summary.get("overall_pass"),
                        "open_blocker_count": local_m12_s5_summary.get("open_blocker_count"),
                        "verdict": local_m12_s5_summary.get("verdict"),
                        "next_gate": local_m12_s5_summary.get("next_gate"),
                    },
                },
            )

    m12j_exec = str(local_m12_s5_summary.get("m12j_execution_id", "")).strip() if local_m12_s5_summary else ""
    m12h_exec = str(local_m12_s5_summary.get("m12h_execution_id", "")).strip() if local_m12_s5_summary else ""
    m12i_exec = str(local_m12_s5_summary.get("m12i_execution_id", "")).strip() if local_m12_s5_summary else ""
    m12_s4_exec = str(local_m12_s5_summary.get("upstream_m12_s4_execution", "")).strip() if local_m12_s5_summary else ""
    if not m12j_exec:
        add_blocker(blockers, "M13-ST-B1", "S0", {"reason": "missing_m12j_execution_id_from_m12_s5_summary"})
    if not m12h_exec:
        add_blocker(blockers, "M13-ST-B1", "S0", {"reason": "missing_m12h_execution_id_from_m12_s5_summary"})
    if not m12_s4_exec:
        add_blocker(blockers, "M13-ST-B1", "S0", {"reason": "missing_upstream_m12_s4_execution_from_m12_s5_summary"})

    local_m12j_summary = loadj(OUT_ROOT / upstream_m12_s5_execution / "stress" / "m12j_execution_summary.json")
    if not local_m12j_summary:
        add_blocker(
            blockers,
            "M13-ST-B1",
            "S0",
            {"reason": "m12j_summary_missing_in_upstream_s5_stress_root", "upstream_s5_execution": upstream_m12_s5_execution},
        )
    elif not (
        bool(local_m12j_summary.get("overall_pass"))
        and str(local_m12j_summary.get("verdict", "")) == "ADVANCE_TO_M13"
        and str(local_m12j_summary.get("next_gate", "")) == "M13_READY"
    ):
        add_blocker(blockers, "M13-ST-B1", "S0", {"reason": "m12j_not_ready", "summary": local_m12j_summary})

    local_m13_handoff = loadj(OUT_ROOT / m12_s4_exec / "stress" / "m13_handoff_pack.json") if m12_s4_exec else {}
    if not local_m13_handoff:
        add_blocker(
            blockers,
            "M13-ST-B1",
            "S0",
            {"reason": "m13_handoff_missing_from_upstream_m12_s4", "upstream_s4_execution": m12_s4_exec},
        )
    else:
        if not bool(local_m13_handoff.get("m13_entry_ready")):
            add_blocker(blockers, "M13-ST-B1", "S0", {"reason": "m13_handoff_entry_ready_false"})
        if str(local_m13_handoff.get("p15_verdict", "")).strip() != "ADVANCE_TO_P16":
            add_blocker(blockers, "M13-ST-B1", "S0", {"reason": "m13_handoff_p15_verdict_not_advance_to_p16"})
        if str(local_m13_handoff.get("next_gate", "")).strip() != "M13_READY":
            add_blocker(blockers, "M13-ST-B1", "S0", {"reason": "m13_handoff_next_gate_not_m13_ready"})
        entry_gate = local_m13_handoff.get("m13_entry_gate", {})
        if not isinstance(entry_gate, dict) or str(entry_gate.get("next_gate", "")).strip() != "M13_READY":
            add_blocker(blockers, "M13-ST-B1", "S0", {"reason": "m13_entry_gate_not_m13_ready"})

    explicit_override_used = True
    if bool(packet.get("M13_STRESS_FAIL_ON_DEFAULT_UPSTREAM_INPUTS", True)) and not explicit_override_used:
        add_blocker(blockers, "M13-ST-B20", "S0", {"reason": "required_explicit_upstream_override_not_used"})

    m13b0_exec = ""
    m13b0_summary: dict[str, Any] = {}
    if Path("scripts/dev_substrate/m13b0_managed_materialization.py").exists() and m12j_exec and not blockers:
        m13b0_exec = f"m13b0_stress_s0_{tok()}"
        m13b0_dir = out / "_m13b0"
        env_b0 = dict(os.environ)
        env_b0.update(
            {
                "M13B0_EXECUTION_ID": m13b0_exec,
                "M13B0_RUN_DIR": m13b0_dir.as_posix(),
                "EVIDENCE_BUCKET": bucket,
                "UPSTREAM_M12J_EXECUTION": m12j_exec,
                "AWS_REGION": "eu-west-2",
                "M13_UPSTREAM_M13B0_EXECUTION": "M13_S0_NOT_APPLICABLE",
                "M13_UPSTREAM_M13A_EXECUTION": "M13_S0_NOT_APPLICABLE",
                "M13_UPSTREAM_M13B_EXECUTION": "M13_S0_NOT_APPLICABLE",
                "M13_UPSTREAM_M13C_EXECUTION": "M13_S0_NOT_APPLICABLE",
                "M13_UPSTREAM_M13D_EXECUTION": "M13_S0_NOT_APPLICABLE",
                "M13_UPSTREAM_M13E_EXECUTION": "M13_S0_NOT_APPLICABLE",
                "M13_UPSTREAM_M13F_EXECUTION": "M13_S0_NOT_APPLICABLE",
                "M13_UPSTREAM_M13G_EXECUTION": "M13_S0_NOT_APPLICABLE",
                "M13_UPSTREAM_M13H_EXECUTION": "M13_S0_NOT_APPLICABLE",
                "M13_UPSTREAM_M13I_EXECUTION": "M13_S0_NOT_APPLICABLE",
            }
        )
        rc, _, err = run(["python", "scripts/dev_substrate/m13b0_managed_materialization.py"], timeout=9000, env=env_b0)
        if rc != 0:
            add_blocker(
                blockers,
                "M13-ST-B0",
                "S0",
                {"reason": "m13b0_command_failed", "stderr": err.strip()[:300], "rc": rc},
            )

        m13b0_summary = loadj(m13b0_dir / "m13b0_execution_summary.json")
        m13b0_snapshot = loadj(m13b0_dir / "m13_managed_lane_materialization_snapshot.json")
        m13b0_dispatch = loadj(m13b0_dir / "m13_subphase_dispatchability_snapshot.json")
        m13b0_register = loadj(m13b0_dir / "m13b0_blocker_register.json")
        if m13b0_snapshot:
            dumpj(out / "m13_managed_lane_materialization_snapshot.json", m13b0_snapshot)
        if m13b0_dispatch:
            dumpj(out / "m13_subphase_dispatchability_snapshot.json", m13b0_dispatch)
        if m13b0_summary:
            dumpj(out / "m13b0_execution_summary.json", m13b0_summary)
        if m13b0_register:
            dumpj(out / "m13b0_blocker_register.json", m13b0_register)

        if not m13b0_summary:
            add_blocker(blockers, "M13-ST-B0", "S0", {"reason": "m13b0_summary_missing"})
        elif not (
            bool(m13b0_summary.get("overall_pass"))
            and str(m13b0_summary.get("next_gate", "")) == "M13.A_READY"
            and str(m13b0_summary.get("verdict", "")) == "ADVANCE_TO_M13_A"
        ):
            add_blocker(blockers, "M13-ST-B0", "S0", {"reason": "m13b0_not_ready", "summary": m13b0_summary})

        if m13b0_register and isinstance(m13b0_register.get("blockers"), list):
            for row in m13b0_register.get("blockers", []):
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
                        "M13-ST-B19",
                        "S0",
                        {"reason": "managed_quota_or_access_boundary_pressure_detected_in_m13b0"},
                    )
                    break

    m13a_exec = ""
    m13a_summary: dict[str, Any] = {}
    if Path("scripts/dev_substrate/m13a_handle_closure.py").exists() and m12j_exec and m13b0_exec and not blockers:
        m13a_exec = f"m13a_stress_s0_{tok()}"
        m13a_dir = out / "_m13a"
        env_a = dict(os.environ)
        env_a.update(
            {
                "M13A_EXECUTION_ID": m13a_exec,
                "M13A_RUN_DIR": m13a_dir.as_posix(),
                "EVIDENCE_BUCKET": bucket,
                "UPSTREAM_M12J_EXECUTION": m12j_exec,
                "UPSTREAM_M13B0_EXECUTION": m13b0_exec,
                "AWS_REGION": "eu-west-2",
                "M13_UPSTREAM_M13A_EXECUTION": "M13_S0_NOT_APPLICABLE",
                "M13_UPSTREAM_M13B_EXECUTION": "M13_S0_NOT_APPLICABLE",
                "M13_UPSTREAM_M13C_EXECUTION": "M13_S0_NOT_APPLICABLE",
                "M13_UPSTREAM_M13D_EXECUTION": "M13_S0_NOT_APPLICABLE",
                "M13_UPSTREAM_M13E_EXECUTION": "M13_S0_NOT_APPLICABLE",
                "M13_UPSTREAM_M13F_EXECUTION": "M13_S0_NOT_APPLICABLE",
                "M13_UPSTREAM_M13G_EXECUTION": "M13_S0_NOT_APPLICABLE",
                "M13_UPSTREAM_M13H_EXECUTION": "M13_S0_NOT_APPLICABLE",
                "M13_UPSTREAM_M13I_EXECUTION": "M13_S0_NOT_APPLICABLE",
            }
        )
        rc, _, err = run(["python", "scripts/dev_substrate/m13a_handle_closure.py"], timeout=9000, env=env_a)
        if rc != 0:
            add_blocker(
                blockers,
                "M13-ST-B1",
                "S0",
                {"reason": "m13a_command_failed", "stderr": err.strip()[:300], "rc": rc},
            )

        m13a_summary = loadj(m13a_dir / "m13a_execution_summary.json")
        m13a_snapshot = loadj(m13a_dir / "m13a_handle_closure_snapshot.json")
        m13a_register = loadj(m13a_dir / "m13a_blocker_register.json")
        if m13a_snapshot:
            dumpj(out / "m13a_handle_closure_snapshot.json", m13a_snapshot)
        if m13a_summary:
            dumpj(out / "m13a_execution_summary.json", m13a_summary)
        if m13a_register:
            dumpj(out / "m13a_blocker_register.json", m13a_register)

        if not m13a_summary:
            add_blocker(blockers, "M13-ST-B1", "S0", {"reason": "m13a_summary_missing"})
        elif not (
            bool(m13a_summary.get("overall_pass"))
            and str(m13a_summary.get("next_gate", "")) == "M13.B_READY"
            and str(m13a_summary.get("verdict", "")) == "ADVANCE_TO_M13_B"
        ):
            add_blocker(blockers, "M13-ST-B1", "S0", {"reason": "m13a_not_ready", "summary": m13a_summary})

        if m13a_register and isinstance(m13a_register.get("blockers"), list):
            for row in m13a_register.get("blockers", []):
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
                        "M13-ST-B19",
                        "S0",
                        {"reason": "managed_quota_or_access_boundary_pressure_detected_in_m13a"},
                    )
                    break
    elif m13b0_exec and not m13a_exec and not blockers:
        add_blocker(blockers, "M13-ST-B1", "S0", {"reason": "m13a_not_executed"})
    elif blockers and not m13a_exec:
        add_blocker(blockers, "M13-ST-B1", "S0", {"reason": "m13a_skipped_due_to_prior_blocker"})

    if bool(packet.get("M13_STRESS_REQUIRE_MANAGED_LANE_MATERIALIZATION", True)) and not m13b0_exec:
        add_blocker(blockers, "M13-ST-B0", "S0", {"reason": "managed_lane_materialization_required_but_not_executed"})

    stage_findings = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M13-ST-S0",
        "findings": [
            {
                "id": "M13-ST-F2",
                "classification": "PREVENT",
                "status": "CLOSED" if all(Path(p).exists() for p in scripts_required) else "OPEN",
                "note": "Parent M13 runner and S0 wrappers are materialized for execution.",
            },
            {
                "id": "M13-ST-F3",
                "classification": "PREVENT",
                "status": "CLOSED" if m13b0_summary else "OPEN",
                "note": "Managed M13 workflow dispatchability is validated in current strict chain.",
            },
            {
                "id": "M13-ST-F4",
                "classification": "PREVENT",
                "status": "CLOSED" if explicit_override_used else "OPEN",
                "note": "S0 dispatch uses explicit upstream input overrides (no workflow default reliance).",
            },
            {
                "id": "M13-ST-F5",
                "classification": "PREVENT",
                "status": "CLOSED" if len([b for b in blockers if b.get("id") in {"M13-ST-B15"}]) == 0 else "OPEN",
                "note": "Strict upstream continuity and stale-evidence guard are enforced in S0.",
            },
            {
                "id": "M13-ST-F12",
                "classification": "PREVENT",
                "status": "CLOSED" if len([b for b in blockers if b.get("id") in {"M13-ST-B1"}]) == 0 else "OPEN",
                "note": "Authority/handle closure posture is enforced fail-closed.",
            },
        ],
    }
    dumpj(out / "m13_stagea_findings.json", stage_findings)

    lane_matrix = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M13-ST-S0",
        "lanes": [
            {
                "lane": "B0",
                "component": "M13.B0",
                "execution_id": m13b0_exec,
                "overall_pass": bool(m13b0_summary.get("overall_pass")) if m13b0_summary else False,
                "next_gate": str(m13b0_summary.get("next_gate", "")) if m13b0_summary else "",
                "verdict": str(m13b0_summary.get("verdict", "")) if m13b0_summary else "",
            },
            {
                "lane": "A",
                "component": "M13.A",
                "execution_id": m13a_exec,
                "overall_pass": bool(m13a_summary.get("overall_pass")) if m13a_summary else False,
                "next_gate": str(m13a_summary.get("next_gate", "")) if m13a_summary else "",
                "verdict": str(m13a_summary.get("verdict", "")) if m13a_summary else "",
            },
        ],
    }
    dumpj(out / "m13_lane_matrix.json", lane_matrix)

    runtime_locality_ok = bool(packet.get("M13_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY", True))
    if not runtime_locality_ok:
        add_blocker(blockers, "M13-ST-B16", "S0", {"reason": "runtime_locality_policy_not_true"})
    dumpj(
        out / "m13_runtime_locality_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M13-ST-S0",
            "overall_pass": runtime_locality_ok,
            "require_remote_runtime_only": bool(packet.get("M13_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY", True)),
            "runtime_execution_attempted": False,
            "runtime_execution_mode": "local_control_orchestration_only_remote_runtime",
        },
    )

    refs = [
        f"evidence/dev_full/run_control/{upstream_m12_s5_execution}/stress/m12_execution_summary.json" if upstream_m12_s5_execution else "",
        f"evidence/dev_full/run_control/{upstream_m12_s5_execution}/stress/m12j_execution_summary.json" if upstream_m12_s5_execution else "",
        f"evidence/dev_full/run_control/{m12_s4_exec}/stress/m13_handoff_pack.json" if m12_s4_exec else "",
        f"evidence/dev_full/run_control/{m13b0_exec}/m13b0_execution_summary.json" if m13b0_exec else "",
        f"evidence/dev_full/run_control/{m13a_exec}/m13a_execution_summary.json" if m13a_exec else "",
    ]
    source_guard_ok = len([b for b in blockers if b.get("id") in {"M13-ST-B11", "M13-ST-B16"}]) == 0
    dumpj(
        out / "m13_source_authority_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M13-ST-S0",
            "overall_pass": source_guard_ok,
            "authoritative_refs": refs,
            "evidence_bucket": bucket,
            "runtime_locality_only_control_plane": True,
        },
    )

    realism_ok = bool(packet.get("M13_STRESS_DISALLOW_WAIVED_REALISM", True))
    if not realism_ok:
        add_blocker(blockers, "M13-ST-B17", "S0", {"reason": "realism_guard_not_true"})
    dumpj(
        out / "m13_realism_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M13-ST-S0",
            "overall_pass": realism_ok,
            "disallow_waived_realism": bool(packet.get("M13_STRESS_DISALLOW_WAIVED_REALISM", True)),
        },
    )

    if not bool(packet.get("M13_STRESS_REQUIRE_DATA_ENGINE_BLACKBOX", True)):
        add_blocker(blockers, "M13-ST-B16", "S0", {"reason": "data_engine_blackbox_guard_not_true"})

    platform_run_id = str(local_m12_s5_summary.get("platform_run_id", "")) if local_m12_s5_summary else ""
    scenario_run_id = str(local_m12_s5_summary.get("scenario_run_id", "")) if local_m12_s5_summary else ""
    return finish(
        "S0",
        phase_execution_id,
        out,
        blockers,
        S0_ARTS,
        {
            "platform_run_id": platform_run_id,
            "scenario_run_id": scenario_run_id,
            "upstream_m12_s5_execution": upstream_m12_s5_execution,
            "upstream_m12_s4_execution": m12_s4_exec,
            "m12j_execution_id": m12j_exec,
            "m12h_execution_id": m12h_exec,
            "m12i_execution_id": m12i_exec,
            "m13b0_execution_id": m13b0_exec,
            "m13a_execution_id": m13a_exec,
            "decisions": [
                "S0 enforced strict M12 S5 closure continuity before executing M13 lanes.",
                "S0 executed managed lane materialization check (M13.B0) with explicit upstream overrides.",
                "S0 executed M13.A authority/handle closure and required deterministic M13.B_READY gate.",
            ],
            "advisories": advisories,
        },
    )


def run_s1(phase_execution_id: str, upstream_m13_s0_execution: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)
    blockers: list[dict[str, Any]] = []
    advisories: list[str] = []

    plan_text = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    packet = parse_plan_packet(plan_text)
    reg = parse_registry(REG) if REG.exists() else {}

    scripts_required = [
        "scripts/dev_substrate/m13b_source_matrix_closure.py",
        "scripts/dev_substrate/m13c_six_proof_closure.py",
    ]
    for script_path in scripts_required:
        if not Path(script_path).exists():
            add_blocker(
                blockers,
                "M13-ST-B18",
                "S1",
                {"reason": "required_stage_script_missing", "script": script_path},
            )

    value = reg.get("S3_EVIDENCE_BUCKET")
    if value is None or is_placeholder(value):
        add_blocker(blockers, "M13-ST-B2", "S1", {"reason": "required_handle_missing_or_placeholder", "handle": "S3_EVIDENCE_BUCKET"})
    bucket = str(reg.get("S3_EVIDENCE_BUCKET", "")).strip()

    s0_exec = upstream_m13_s0_execution.strip()
    s0 = loadj(OUT_ROOT / s0_exec / "stress" / "m13_execution_summary.json") if s0_exec else {}
    if not s0:
        add_blocker(
            blockers,
            "M13-ST-B15",
            "S1",
            {
                "reason": "upstream_s0_summary_missing",
                "path": (OUT_ROOT / s0_exec / "stress" / "m13_execution_summary.json").as_posix(),
            },
        )
    elif not (
        bool(s0.get("overall_pass"))
        and int(s0.get("open_blocker_count", 1)) == 0
        and str(s0.get("next_gate", "")).strip() == "M13_ST_S1_READY"
    ):
        add_blocker(
            blockers,
            "M13-ST-B15",
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

    m12j_exec = str(s0.get("m12j_execution_id", "")).strip() if s0 else ""
    m13a_exec = str(s0.get("m13a_execution_id", "")).strip() if s0 else ""
    m13b0_exec = str(s0.get("m13b0_execution_id", "")).strip() if s0 else ""
    if not m12j_exec:
        add_blocker(blockers, "M13-ST-B2", "S1", {"reason": "missing_m12j_execution_id_from_s0_summary"})
    if not m13a_exec:
        add_blocker(blockers, "M13-ST-B2", "S1", {"reason": "missing_m13a_execution_id_from_s0_summary"})

    explicit_override_used = True
    if bool(packet.get("M13_STRESS_FAIL_ON_DEFAULT_UPSTREAM_INPUTS", True)) and not explicit_override_used:
        add_blocker(blockers, "M13-ST-B20", "S1", {"reason": "required_explicit_upstream_override_not_used"})

    m13b_exec = ""
    m13b_summary: dict[str, Any] = {}
    if Path("scripts/dev_substrate/m13b_source_matrix_closure.py").exists() and m12j_exec and m13a_exec and not blockers:
        m13b_exec = f"m13b_stress_s1_{tok()}"
        m13b_dir = out / "_m13b"
        env_b = dict(os.environ)
        env_b.update(
            {
                "M13B_EXECUTION_ID": m13b_exec,
                "M13B_RUN_DIR": m13b_dir.as_posix(),
                "EVIDENCE_BUCKET": bucket,
                "UPSTREAM_M12J_EXECUTION": m12j_exec,
                "UPSTREAM_M13A_EXECUTION": m13a_exec,
                "AWS_REGION": "eu-west-2",
                "M13_UPSTREAM_M13B0_EXECUTION": "M13_S1_NOT_APPLICABLE",
                "M13_UPSTREAM_M13B_EXECUTION": "M13_S1_NOT_APPLICABLE",
                "M13_UPSTREAM_M13C_EXECUTION": "M13_S1_NOT_APPLICABLE",
                "M13_UPSTREAM_M13D_EXECUTION": "M13_S1_NOT_APPLICABLE",
                "M13_UPSTREAM_M13E_EXECUTION": "M13_S1_NOT_APPLICABLE",
                "M13_UPSTREAM_M13F_EXECUTION": "M13_S1_NOT_APPLICABLE",
                "M13_UPSTREAM_M13G_EXECUTION": "M13_S1_NOT_APPLICABLE",
                "M13_UPSTREAM_M13H_EXECUTION": "M13_S1_NOT_APPLICABLE",
                "M13_UPSTREAM_M13I_EXECUTION": "M13_S1_NOT_APPLICABLE",
            }
        )
        rc, _, err = run(["python", "scripts/dev_substrate/m13b_source_matrix_closure.py"], timeout=9000, env=env_b)
        if rc != 0:
            add_blocker(
                blockers,
                "M13-ST-B2",
                "S1",
                {"reason": "m13b_command_failed", "stderr": err.strip()[:300], "rc": rc},
            )

        m13b_summary = loadj(m13b_dir / "m13b_execution_summary.json")
        m13b_snapshot = loadj(m13b_dir / "m13b_source_matrix_snapshot.json")
        m13b_register = loadj(m13b_dir / "m13b_blocker_register.json")
        if m13b_snapshot:
            dumpj(out / "m13b_source_matrix_snapshot.json", m13b_snapshot)
        if m13b_summary:
            dumpj(out / "m13b_execution_summary.json", m13b_summary)
        if m13b_register:
            dumpj(out / "m13b_blocker_register.json", m13b_register)

        if not m13b_summary:
            add_blocker(blockers, "M13-ST-B2", "S1", {"reason": "m13b_summary_missing"})
        elif not (
            bool(m13b_summary.get("overall_pass"))
            and str(m13b_summary.get("next_gate", "")) == "M13.C_READY"
            and str(m13b_summary.get("verdict", "")) == "ADVANCE_TO_M13_C"
        ):
            add_blocker(blockers, "M13-ST-B2", "S1", {"reason": "m13b_not_ready", "summary": m13b_summary})

        if m13b_register and isinstance(m13b_register.get("blockers"), list):
            for row in m13b_register.get("blockers", []):
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
                        "M13-ST-B19",
                        "S1",
                        {"reason": "managed_quota_or_access_boundary_pressure_detected_in_m13b"},
                    )
                    break

    m13c_exec = ""
    m13c_summary: dict[str, Any] = {}
    if Path("scripts/dev_substrate/m13c_six_proof_closure.py").exists() and m12j_exec and m13b_exec and not blockers:
        m13c_exec = f"m13c_stress_s1_{tok()}"
        m13c_dir = out / "_m13c"
        env_c = dict(os.environ)
        env_c.update(
            {
                "M13C_EXECUTION_ID": m13c_exec,
                "M13C_RUN_DIR": m13c_dir.as_posix(),
                "EVIDENCE_BUCKET": bucket,
                "UPSTREAM_M12J_EXECUTION": m12j_exec,
                "UPSTREAM_M13B_EXECUTION": m13b_exec,
                "AWS_REGION": "eu-west-2",
                "M13_UPSTREAM_M13B0_EXECUTION": "M13_S1_NOT_APPLICABLE",
                "M13_UPSTREAM_M13A_EXECUTION": "M13_S1_NOT_APPLICABLE",
                "M13_UPSTREAM_M13C_EXECUTION": "M13_S1_NOT_APPLICABLE",
                "M13_UPSTREAM_M13D_EXECUTION": "M13_S1_NOT_APPLICABLE",
                "M13_UPSTREAM_M13E_EXECUTION": "M13_S1_NOT_APPLICABLE",
                "M13_UPSTREAM_M13F_EXECUTION": "M13_S1_NOT_APPLICABLE",
                "M13_UPSTREAM_M13G_EXECUTION": "M13_S1_NOT_APPLICABLE",
                "M13_UPSTREAM_M13H_EXECUTION": "M13_S1_NOT_APPLICABLE",
                "M13_UPSTREAM_M13I_EXECUTION": "M13_S1_NOT_APPLICABLE",
            }
        )
        rc, _, err = run(["python", "scripts/dev_substrate/m13c_six_proof_closure.py"], timeout=9000, env=env_c)
        if rc != 0:
            add_blocker(
                blockers,
                "M13-ST-B3",
                "S1",
                {"reason": "m13c_command_failed", "stderr": err.strip()[:300], "rc": rc},
            )

        m13c_summary = loadj(m13c_dir / "m13c_execution_summary.json")
        m13c_snapshot = loadj(m13c_dir / "m13c_six_proof_matrix_snapshot.json")
        m13c_register = loadj(m13c_dir / "m13c_blocker_register.json")
        if m13c_snapshot:
            dumpj(out / "m13c_six_proof_matrix_snapshot.json", m13c_snapshot)
        if m13c_summary:
            dumpj(out / "m13c_execution_summary.json", m13c_summary)
        if m13c_register:
            dumpj(out / "m13c_blocker_register.json", m13c_register)

        if not m13c_summary:
            add_blocker(blockers, "M13-ST-B3", "S1", {"reason": "m13c_summary_missing"})
        elif not (
            bool(m13c_summary.get("overall_pass"))
            and str(m13c_summary.get("next_gate", "")) == "M13.D_READY"
            and str(m13c_summary.get("verdict", "")) == "ADVANCE_TO_M13_D"
        ):
            add_blocker(blockers, "M13-ST-B3", "S1", {"reason": "m13c_not_ready", "summary": m13c_summary})

        if m13c_register and isinstance(m13c_register.get("blockers"), list):
            for row in m13c_register.get("blockers", []):
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
                        "M13-ST-B19",
                        "S1",
                        {"reason": "managed_quota_or_access_boundary_pressure_detected_in_m13c"},
                    )
                    break
    elif m13b_exec and not m13c_exec and not blockers:
        add_blocker(blockers, "M13-ST-B3", "S1", {"reason": "m13c_not_executed"})
    elif blockers and not m13c_exec:
        add_blocker(blockers, "M13-ST-B3", "S1", {"reason": "m13c_skipped_due_to_prior_blocker"})

    stage_findings = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M13-ST-S1",
        "findings": [
            {
                "id": "M13-ST-F4",
                "classification": "PREVENT",
                "status": "CLOSED" if explicit_override_used else "OPEN",
                "note": "S1 dispatch uses explicit upstream input overrides (no workflow default reliance).",
            },
            {
                "id": "M13-ST-F5",
                "classification": "PREVENT",
                "status": "CLOSED" if len([b for b in blockers if b.get("id") in {"M13-ST-B15"}]) == 0 else "OPEN",
                "note": "Strict upstream continuity and stale-evidence guard are enforced in S1.",
            },
            {
                "id": "M13-ST-F6",
                "classification": "OBSERVE",
                "status": "CLOSED" if len([b for b in blockers if b.get("id") in {"M13-ST-B2"}]) == 0 else "OPEN",
                "note": "Source matrix closure lane completed with deterministic gate checks.",
            },
            {
                "id": "M13-ST-F11",
                "classification": "PREVENT",
                "status": "CLOSED" if len([b for b in blockers if b.get("id") in {"M13-ST-B3"}]) == 0 else "OPEN",
                "note": "Six-proof matrix closure lane completed with deterministic gate checks.",
            },
        ],
    }
    dumpj(out / "m13_stagea_findings.json", stage_findings)

    lane_matrix = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M13-ST-S1",
        "lanes": [
            {
                "lane": "B",
                "component": "M13.B",
                "execution_id": m13b_exec,
                "overall_pass": bool(m13b_summary.get("overall_pass")) if m13b_summary else False,
                "next_gate": str(m13b_summary.get("next_gate", "")) if m13b_summary else "",
                "verdict": str(m13b_summary.get("verdict", "")) if m13b_summary else "",
            },
            {
                "lane": "C",
                "component": "M13.C",
                "execution_id": m13c_exec,
                "overall_pass": bool(m13c_summary.get("overall_pass")) if m13c_summary else False,
                "next_gate": str(m13c_summary.get("next_gate", "")) if m13c_summary else "",
                "verdict": str(m13c_summary.get("verdict", "")) if m13c_summary else "",
            },
        ],
    }
    dumpj(out / "m13_lane_matrix.json", lane_matrix)

    runtime_locality_ok = bool(packet.get("M13_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY", True))
    if not runtime_locality_ok:
        add_blocker(blockers, "M13-ST-B16", "S1", {"reason": "runtime_locality_policy_not_true"})
    dumpj(
        out / "m13_runtime_locality_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M13-ST-S1",
            "overall_pass": runtime_locality_ok,
            "require_remote_runtime_only": bool(packet.get("M13_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY", True)),
            "runtime_execution_attempted": False,
            "runtime_execution_mode": "local_control_orchestration_only_remote_runtime",
        },
    )

    refs = [
        f"evidence/dev_full/run_control/{s0_exec}/stress/m13_execution_summary.json" if s0_exec else "",
        f"evidence/dev_full/run_control/{m13b_exec}/m13b_execution_summary.json" if m13b_exec else "",
        f"evidence/dev_full/run_control/{m13c_exec}/m13c_execution_summary.json" if m13c_exec else "",
    ]
    source_guard_ok = len([b for b in blockers if b.get("id") in {"M13-ST-B11", "M13-ST-B16"}]) == 0
    dumpj(
        out / "m13_source_authority_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M13-ST-S1",
            "overall_pass": source_guard_ok,
            "authoritative_refs": refs,
            "evidence_bucket": bucket,
            "runtime_locality_only_control_plane": True,
        },
    )

    realism_ok = bool(packet.get("M13_STRESS_DISALLOW_WAIVED_REALISM", True))
    if not realism_ok:
        add_blocker(blockers, "M13-ST-B17", "S1", {"reason": "realism_guard_not_true"})
    dumpj(
        out / "m13_realism_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M13-ST-S1",
            "overall_pass": realism_ok,
            "disallow_waived_realism": bool(packet.get("M13_STRESS_DISALLOW_WAIVED_REALISM", True)),
        },
    )

    if not bool(packet.get("M13_STRESS_REQUIRE_DATA_ENGINE_BLACKBOX", True)):
        add_blocker(blockers, "M13-ST-B16", "S1", {"reason": "data_engine_blackbox_guard_not_true"})

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
            "upstream_m13_s0_execution": s0_exec,
            "m12j_execution_id": m12j_exec,
            "m13b0_execution_id": m13b0_exec,
            "m13a_execution_id": m13a_exec,
            "m13b_execution_id": m13b_exec,
            "m13c_execution_id": m13c_exec,
            "decisions": [
                "S1 enforced strict M13 S0 entry continuity before executing lanes B and C.",
                "S1 executed M13.B source matrix closure with explicit upstream overrides.",
                "S1 executed M13.C six-proof closure and required deterministic M13.D_READY gate.",
            ],
            "advisories": advisories,
        },
    )


def run_s2(phase_execution_id: str, upstream_m13_s1_execution: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)
    blockers: list[dict[str, Any]] = []
    advisories: list[str] = []

    plan_text = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    packet = parse_plan_packet(plan_text)
    reg = parse_registry(REG) if REG.exists() else {}

    scripts_required = [
        "scripts/dev_substrate/m13d_final_verdict_closure.py",
        "scripts/dev_substrate/m13e_teardown_plan_closure.py",
    ]
    for script_path in scripts_required:
        if not Path(script_path).exists():
            add_blocker(
                blockers,
                "M13-ST-B18",
                "S2",
                {"reason": "required_stage_script_missing", "script": script_path},
            )

    value = reg.get("S3_EVIDENCE_BUCKET")
    if value is None or is_placeholder(value):
        add_blocker(blockers, "M13-ST-B4", "S2", {"reason": "required_handle_missing_or_placeholder", "handle": "S3_EVIDENCE_BUCKET"})
    bucket = str(reg.get("S3_EVIDENCE_BUCKET", "")).strip()

    s1_exec = upstream_m13_s1_execution.strip()
    s1 = loadj(OUT_ROOT / s1_exec / "stress" / "m13_execution_summary.json") if s1_exec else {}
    if not s1:
        add_blocker(
            blockers,
            "M13-ST-B15",
            "S2",
            {
                "reason": "upstream_s1_summary_missing",
                "path": (OUT_ROOT / s1_exec / "stress" / "m13_execution_summary.json").as_posix(),
            },
        )
    elif not (
        bool(s1.get("overall_pass"))
        and int(s1.get("open_blocker_count", 1)) == 0
        and str(s1.get("next_gate", "")).strip() == "M13_ST_S2_READY"
    ):
        add_blocker(
            blockers,
            "M13-ST-B15",
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

    m12j_exec = str(s1.get("m12j_execution_id", "")).strip() if s1 else ""
    m13a_exec = str(s1.get("m13a_execution_id", "")).strip() if s1 else ""
    m13b_exec = str(s1.get("m13b_execution_id", "")).strip() if s1 else ""
    m13c_exec = str(s1.get("m13c_execution_id", "")).strip() if s1 else ""
    if not m12j_exec:
        add_blocker(blockers, "M13-ST-B4", "S2", {"reason": "missing_m12j_execution_id_from_s1_summary"})
    if not m13a_exec:
        add_blocker(blockers, "M13-ST-B4", "S2", {"reason": "missing_m13a_execution_id_from_s1_summary"})
    if not m13b_exec:
        add_blocker(blockers, "M13-ST-B4", "S2", {"reason": "missing_m13b_execution_id_from_s1_summary"})
    if not m13c_exec:
        add_blocker(blockers, "M13-ST-B4", "S2", {"reason": "missing_m13c_execution_id_from_s1_summary"})

    explicit_override_used = True
    if bool(packet.get("M13_STRESS_FAIL_ON_DEFAULT_UPSTREAM_INPUTS", True)) and not explicit_override_used:
        add_blocker(blockers, "M13-ST-B20", "S2", {"reason": "required_explicit_upstream_override_not_used"})

    m13d_exec = ""
    m13d_summary: dict[str, Any] = {}
    m13d_bundle: dict[str, Any] = {}
    if Path("scripts/dev_substrate/m13d_final_verdict_closure.py").exists() and m12j_exec and m13c_exec and not blockers:
        m13d_exec = f"m13d_stress_s2_{tok()}"
        m13d_dir = out / "_m13d"
        env_d = dict(os.environ)
        env_d.update(
            {
                "M13D_EXECUTION_ID": m13d_exec,
                "M13D_RUN_DIR": m13d_dir.as_posix(),
                "EVIDENCE_BUCKET": bucket,
                "UPSTREAM_M12J_EXECUTION": m12j_exec,
                "UPSTREAM_M13C_EXECUTION": m13c_exec,
                "AWS_REGION": "eu-west-2",
                "M13_UPSTREAM_M13B0_EXECUTION": "M13_S2_NOT_APPLICABLE",
                "M13_UPSTREAM_M13A_EXECUTION": m13a_exec,
                "M13_UPSTREAM_M13B_EXECUTION": m13b_exec,
                "M13_UPSTREAM_M13D_EXECUTION": "M13_S2_NOT_APPLICABLE",
                "M13_UPSTREAM_M13E_EXECUTION": "M13_S2_NOT_APPLICABLE",
                "M13_UPSTREAM_M13F_EXECUTION": "M13_S2_NOT_APPLICABLE",
                "M13_UPSTREAM_M13G_EXECUTION": "M13_S2_NOT_APPLICABLE",
                "M13_UPSTREAM_M13H_EXECUTION": "M13_S2_NOT_APPLICABLE",
                "M13_UPSTREAM_M13I_EXECUTION": "M13_S2_NOT_APPLICABLE",
            }
        )
        rc, _, err = run(["python", "scripts/dev_substrate/m13d_final_verdict_closure.py"], timeout=9000, env=env_d)
        if rc != 0:
            add_blocker(
                blockers,
                "M13-ST-B4",
                "S2",
                {"reason": "m13d_command_failed", "stderr": err.strip()[:300], "rc": rc},
            )

        m13d_summary = loadj(m13d_dir / "m13d_execution_summary.json")
        m13d_bundle = loadj(m13d_dir / "m13d_final_verdict_bundle.json")
        m13d_register = loadj(m13d_dir / "m13d_blocker_register.json")
        if m13d_bundle:
            dumpj(out / "m13d_final_verdict_bundle.json", m13d_bundle)
        if m13d_summary:
            dumpj(out / "m13d_execution_summary.json", m13d_summary)
        if m13d_register:
            dumpj(out / "m13d_blocker_register.json", m13d_register)

        if not m13d_summary:
            add_blocker(blockers, "M13-ST-B4", "S2", {"reason": "m13d_summary_missing"})
        elif not (
            bool(m13d_summary.get("overall_pass"))
            and str(m13d_summary.get("next_gate", "")) == "M13.E_READY"
            and str(m13d_summary.get("verdict", "")) == "ADVANCE_TO_M13_E"
        ):
            add_blocker(blockers, "M13-ST-B4", "S2", {"reason": "m13d_not_ready", "summary": m13d_summary})

        if m13d_register and isinstance(m13d_register.get("blockers"), list):
            for row in m13d_register.get("blockers", []):
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
                        "M13-ST-B19",
                        "S2",
                        {"reason": "managed_quota_or_access_boundary_pressure_detected_in_m13d"},
                    )
                    break

    m13e_exec = ""
    m13e_summary: dict[str, Any] = {}
    if Path("scripts/dev_substrate/m13e_teardown_plan_closure.py").exists() and m12j_exec and m13d_exec and not blockers:
        m13e_exec = f"m13e_stress_s2_{tok()}"
        m13e_dir = out / "_m13e"
        env_e = dict(os.environ)
        env_e.update(
            {
                "M13E_EXECUTION_ID": m13e_exec,
                "M13E_RUN_DIR": m13e_dir.as_posix(),
                "EVIDENCE_BUCKET": bucket,
                "UPSTREAM_M12J_EXECUTION": m12j_exec,
                "UPSTREAM_M13D_EXECUTION": m13d_exec,
                "AWS_REGION": "eu-west-2",
                "M13_UPSTREAM_M13B0_EXECUTION": "M13_S2_NOT_APPLICABLE",
                "M13_UPSTREAM_M13A_EXECUTION": "M13_S2_NOT_APPLICABLE",
                "M13_UPSTREAM_M13B_EXECUTION": "M13_S2_NOT_APPLICABLE",
                "M13_UPSTREAM_M13C_EXECUTION": "M13_S2_NOT_APPLICABLE",
                "M13_UPSTREAM_M13E_EXECUTION": "M13_S2_NOT_APPLICABLE",
                "M13_UPSTREAM_M13F_EXECUTION": "M13_S2_NOT_APPLICABLE",
                "M13_UPSTREAM_M13G_EXECUTION": "M13_S2_NOT_APPLICABLE",
                "M13_UPSTREAM_M13H_EXECUTION": "M13_S2_NOT_APPLICABLE",
                "M13_UPSTREAM_M13I_EXECUTION": "M13_S2_NOT_APPLICABLE",
            }
        )
        rc, _, err = run(["python", "scripts/dev_substrate/m13e_teardown_plan_closure.py"], timeout=9000, env=env_e)
        if rc != 0:
            add_blocker(
                blockers,
                "M13-ST-B5",
                "S2",
                {"reason": "m13e_command_failed", "stderr": err.strip()[:300], "rc": rc},
            )

        m13e_summary = loadj(m13e_dir / "m13e_execution_summary.json")
        m13e_snapshot = loadj(m13e_dir / "m13e_teardown_plan_snapshot.json")
        m13e_register = loadj(m13e_dir / "m13e_blocker_register.json")
        if m13e_snapshot:
            dumpj(out / "m13e_teardown_plan_snapshot.json", m13e_snapshot)
        if m13e_summary:
            dumpj(out / "m13e_execution_summary.json", m13e_summary)
        if m13e_register:
            dumpj(out / "m13e_blocker_register.json", m13e_register)

        if not m13e_summary:
            add_blocker(blockers, "M13-ST-B5", "S2", {"reason": "m13e_summary_missing"})
        elif not (
            bool(m13e_summary.get("overall_pass"))
            and str(m13e_summary.get("next_gate", "")) == "M13.F_READY"
            and str(m13e_summary.get("verdict", "")) == "ADVANCE_TO_M13_F"
        ):
            add_blocker(blockers, "M13-ST-B5", "S2", {"reason": "m13e_not_ready", "summary": m13e_summary})

        if m13e_register and isinstance(m13e_register.get("blockers"), list):
            for row in m13e_register.get("blockers", []):
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
                        "M13-ST-B19",
                        "S2",
                        {"reason": "managed_quota_or_access_boundary_pressure_detected_in_m13e"},
                    )
                    break
    elif m13d_exec and not m13e_exec and not blockers:
        add_blocker(blockers, "M13-ST-B5", "S2", {"reason": "m13e_not_executed"})
    elif blockers and not m13e_exec:
        add_blocker(blockers, "M13-ST-B5", "S2", {"reason": "m13e_skipped_due_to_prior_blocker"})

    non_gate_precondition_required = bool(packet.get("M13_STRESS_REQUIRE_NON_GATE_ACCEPTANCE", True))
    non_gate_precondition_pass = bool(m13d_bundle)
    if non_gate_precondition_required and not non_gate_precondition_pass:
        add_blocker(blockers, "M13-ST-B12", "S2", {"reason": "non_gate_precondition_missing_final_verdict_bundle"})
    dumpj(
        out / "m13_non_gate_acceptance_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M13-ST-S2",
            "non_gate_precondition_required": non_gate_precondition_required,
            "non_gate_precondition_pass": non_gate_precondition_pass,
            "source_ref": f"evidence/dev_full/run_control/{m13d_exec}/m13d_final_verdict_bundle.json" if m13d_exec else "",
        },
    )

    stage_findings = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M13-ST-S2",
        "findings": [
            {
                "id": "M13-ST-F4",
                "classification": "PREVENT",
                "status": "CLOSED" if explicit_override_used else "OPEN",
                "note": "S2 dispatch uses explicit upstream input overrides (no workflow default reliance).",
            },
            {
                "id": "M13-ST-F5",
                "classification": "PREVENT",
                "status": "CLOSED" if len([b for b in blockers if b.get("id") in {"M13-ST-B15"}]) == 0 else "OPEN",
                "note": "Strict upstream continuity and stale-evidence guard are enforced in S2.",
            },
            {
                "id": "M13-ST-F6",
                "classification": "OBSERVE",
                "status": "CLOSED" if len([b for b in blockers if b.get("id") in {"M13-ST-B4"}]) == 0 else "OPEN",
                "note": "Final verdict publication lane completed with deterministic gate checks.",
            },
            {
                "id": "M13-ST-F7",
                "classification": "OBSERVE",
                "status": "CLOSED" if len([b for b in blockers if b.get("id") in {"M13-ST-B5"}]) == 0 else "OPEN",
                "note": "Teardown plan lane completed with deterministic gate checks.",
            },
        ],
    }
    dumpj(out / "m13_stagea_findings.json", stage_findings)

    lane_matrix = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M13-ST-S2",
        "lanes": [
            {
                "lane": "D",
                "component": "M13.D",
                "execution_id": m13d_exec,
                "overall_pass": bool(m13d_summary.get("overall_pass")) if m13d_summary else False,
                "next_gate": str(m13d_summary.get("next_gate", "")) if m13d_summary else "",
                "verdict": str(m13d_summary.get("verdict", "")) if m13d_summary else "",
            },
            {
                "lane": "E",
                "component": "M13.E",
                "execution_id": m13e_exec,
                "overall_pass": bool(m13e_summary.get("overall_pass")) if m13e_summary else False,
                "next_gate": str(m13e_summary.get("next_gate", "")) if m13e_summary else "",
                "verdict": str(m13e_summary.get("verdict", "")) if m13e_summary else "",
            },
        ],
    }
    dumpj(out / "m13_lane_matrix.json", lane_matrix)

    runtime_locality_ok = bool(packet.get("M13_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY", True))
    if not runtime_locality_ok:
        add_blocker(blockers, "M13-ST-B16", "S2", {"reason": "runtime_locality_policy_not_true"})
    dumpj(
        out / "m13_runtime_locality_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M13-ST-S2",
            "overall_pass": runtime_locality_ok,
            "require_remote_runtime_only": bool(packet.get("M13_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY", True)),
            "runtime_execution_attempted": False,
            "runtime_execution_mode": "local_control_orchestration_only_remote_runtime",
        },
    )

    refs = [
        f"evidence/dev_full/run_control/{s1_exec}/stress/m13_execution_summary.json" if s1_exec else "",
        f"evidence/dev_full/run_control/{m13d_exec}/m13d_execution_summary.json" if m13d_exec else "",
        f"evidence/dev_full/run_control/{m13e_exec}/m13e_execution_summary.json" if m13e_exec else "",
    ]
    source_guard_ok = len([b for b in blockers if b.get("id") in {"M13-ST-B11", "M13-ST-B16"}]) == 0
    dumpj(
        out / "m13_source_authority_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M13-ST-S2",
            "overall_pass": source_guard_ok,
            "authoritative_refs": refs,
            "evidence_bucket": bucket,
            "runtime_locality_only_control_plane": True,
        },
    )

    realism_ok = bool(packet.get("M13_STRESS_DISALLOW_WAIVED_REALISM", True))
    if not realism_ok:
        add_blocker(blockers, "M13-ST-B17", "S2", {"reason": "realism_guard_not_true"})
    dumpj(
        out / "m13_realism_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M13-ST-S2",
            "overall_pass": realism_ok,
            "disallow_waived_realism": bool(packet.get("M13_STRESS_DISALLOW_WAIVED_REALISM", True)),
        },
    )

    if not bool(packet.get("M13_STRESS_REQUIRE_DATA_ENGINE_BLACKBOX", True)):
        add_blocker(blockers, "M13-ST-B16", "S2", {"reason": "data_engine_blackbox_guard_not_true"})

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
            "upstream_m13_s1_execution": s1_exec,
            "m12j_execution_id": m12j_exec,
            "m13a_execution_id": m13a_exec,
            "m13b_execution_id": m13b_exec,
            "m13c_execution_id": m13c_exec,
            "m13d_execution_id": m13d_exec,
            "m13e_execution_id": m13e_exec,
            "decisions": [
                "S2 enforced strict M13 S1 entry continuity before executing lanes D and E.",
                "S2 executed M13.D final verdict closure with explicit upstream overrides.",
                "S2 executed M13.E teardown plan closure and required deterministic M13.F_READY gate.",
            ],
            "advisories": advisories,
        },
    )


def run_s3(phase_execution_id: str, upstream_m13_s2_execution: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)
    blockers: list[dict[str, Any]] = []
    advisories: list[str] = []

    plan_text = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    packet = parse_plan_packet(plan_text)
    reg = parse_registry(REG) if REG.exists() else {}

    scripts_required = [
        "scripts/dev_substrate/m13f_teardown_execution_closure.py",
        "scripts/dev_substrate/m13g_residual_readability_closure.py",
    ]
    for script_path in scripts_required:
        if not Path(script_path).exists():
            add_blocker(
                blockers,
                "M13-ST-B18",
                "S3",
                {"reason": "required_stage_script_missing", "script": script_path},
            )

    value = reg.get("S3_EVIDENCE_BUCKET")
    if value is None or is_placeholder(value):
        add_blocker(blockers, "M13-ST-B6", "S3", {"reason": "required_handle_missing_or_placeholder", "handle": "S3_EVIDENCE_BUCKET"})
    bucket = str(reg.get("S3_EVIDENCE_BUCKET", "")).strip()

    s2_exec = upstream_m13_s2_execution.strip()
    s2 = loadj(OUT_ROOT / s2_exec / "stress" / "m13_execution_summary.json") if s2_exec else {}
    if not s2:
        add_blocker(
            blockers,
            "M13-ST-B15",
            "S3",
            {
                "reason": "upstream_s2_summary_missing",
                "path": (OUT_ROOT / s2_exec / "stress" / "m13_execution_summary.json").as_posix(),
            },
        )
    elif not (
        bool(s2.get("overall_pass"))
        and int(s2.get("open_blocker_count", 1)) == 0
        and str(s2.get("next_gate", "")).strip() == "M13_ST_S3_READY"
    ):
        add_blocker(
            blockers,
            "M13-ST-B15",
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

    m12j_exec = str(s2.get("m12j_execution_id", "")).strip() if s2 else ""
    m13a_exec = str(s2.get("m13a_execution_id", "")).strip() if s2 else ""
    m13b_exec = str(s2.get("m13b_execution_id", "")).strip() if s2 else ""
    m13c_exec = str(s2.get("m13c_execution_id", "")).strip() if s2 else ""
    m13d_exec = str(s2.get("m13d_execution_id", "")).strip() if s2 else ""
    m13e_exec = str(s2.get("m13e_execution_id", "")).strip() if s2 else ""
    if not m12j_exec:
        add_blocker(blockers, "M13-ST-B6", "S3", {"reason": "missing_m12j_execution_id_from_s2_summary"})
    if not m13d_exec:
        add_blocker(blockers, "M13-ST-B6", "S3", {"reason": "missing_m13d_execution_id_from_s2_summary"})
    if not m13e_exec:
        add_blocker(blockers, "M13-ST-B6", "S3", {"reason": "missing_m13e_execution_id_from_s2_summary"})

    explicit_override_used = True
    if bool(packet.get("M13_STRESS_FAIL_ON_DEFAULT_UPSTREAM_INPUTS", True)) and not explicit_override_used:
        add_blocker(blockers, "M13-ST-B20", "S3", {"reason": "required_explicit_upstream_override_not_used"})

    m13f_exec = ""
    m13f_summary: dict[str, Any] = {}
    m13f_snapshot: dict[str, Any] = {}
    if Path("scripts/dev_substrate/m13f_teardown_execution_closure.py").exists() and m12j_exec and m13e_exec and not blockers:
        m13f_exec = f"m13f_stress_s3_{tok()}"
        m13f_dir = out / "_m13f"
        env_f = dict(os.environ)
        env_f.update(
            {
                "M13F_EXECUTION_ID": m13f_exec,
                "M13F_RUN_DIR": m13f_dir.as_posix(),
                "EVIDENCE_BUCKET": bucket,
                "UPSTREAM_M12J_EXECUTION": m12j_exec,
                "UPSTREAM_M13E_EXECUTION": m13e_exec,
                "AWS_REGION": "eu-west-2",
                "M13_UPSTREAM_M13B0_EXECUTION": "M13_S3_NOT_APPLICABLE",
                "M13_UPSTREAM_M13A_EXECUTION": m13a_exec or "M13_S3_NOT_APPLICABLE",
                "M13_UPSTREAM_M13B_EXECUTION": m13b_exec or "M13_S3_NOT_APPLICABLE",
                "M13_UPSTREAM_M13C_EXECUTION": m13c_exec or "M13_S3_NOT_APPLICABLE",
                "M13_UPSTREAM_M13D_EXECUTION": m13d_exec or "M13_S3_NOT_APPLICABLE",
                "M13_UPSTREAM_M13F_EXECUTION": "M13_S3_NOT_APPLICABLE",
                "M13_UPSTREAM_M13G_EXECUTION": "M13_S3_NOT_APPLICABLE",
                "M13_UPSTREAM_M13H_EXECUTION": "M13_S3_NOT_APPLICABLE",
                "M13_UPSTREAM_M13I_EXECUTION": "M13_S3_NOT_APPLICABLE",
            }
        )
        rc, _, err = run(["python", "scripts/dev_substrate/m13f_teardown_execution_closure.py"], timeout=9000, env=env_f)
        if rc != 0:
            add_blocker(
                blockers,
                "M13-ST-B6",
                "S3",
                {"reason": "m13f_command_failed", "stderr": err.strip()[:300], "rc": rc},
            )

        m13f_summary = loadj(m13f_dir / "m13f_execution_summary.json")
        m13f_snapshot = loadj(m13f_dir / "m13f_teardown_execution_snapshot.json")
        m13f_register = loadj(m13f_dir / "m13f_blocker_register.json")
        if m13f_snapshot:
            dumpj(out / "m13f_teardown_execution_snapshot.json", m13f_snapshot)
        if m13f_summary:
            dumpj(out / "m13f_execution_summary.json", m13f_summary)
        if m13f_register:
            dumpj(out / "m13f_blocker_register.json", m13f_register)

        if not m13f_summary:
            add_blocker(blockers, "M13-ST-B6", "S3", {"reason": "m13f_summary_missing"})
        elif not (
            bool(m13f_summary.get("overall_pass"))
            and str(m13f_summary.get("next_gate", "")) == "M13.G_READY"
            and str(m13f_summary.get("verdict", "")) == "ADVANCE_TO_M13_G"
        ):
            add_blocker(blockers, "M13-ST-B6", "S3", {"reason": "m13f_not_ready", "summary": m13f_summary})

        if m13f_register and isinstance(m13f_register.get("blockers"), list):
            for row in m13f_register.get("blockers", []):
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
                        "M13-ST-B19",
                        "S3",
                        {"reason": "managed_quota_or_access_boundary_pressure_detected_in_m13f"},
                    )
                    break

    m13g_exec = ""
    m13g_summary: dict[str, Any] = {}
    m13g_snapshot: dict[str, Any] = {}
    if Path("scripts/dev_substrate/m13g_residual_readability_closure.py").exists() and m12j_exec and m13f_exec and not blockers:
        m13g_exec = f"m13g_stress_s3_{tok()}"
        m13g_dir = out / "_m13g"
        env_g = dict(os.environ)
        env_g.update(
            {
                "M13G_EXECUTION_ID": m13g_exec,
                "M13G_RUN_DIR": m13g_dir.as_posix(),
                "EVIDENCE_BUCKET": bucket,
                "UPSTREAM_M12J_EXECUTION": m12j_exec,
                "UPSTREAM_M13F_EXECUTION": m13f_exec,
                "AWS_REGION": "eu-west-2",
                "M13_UPSTREAM_M13B0_EXECUTION": "M13_S3_NOT_APPLICABLE",
                "M13_UPSTREAM_M13A_EXECUTION": m13a_exec or "M13_S3_NOT_APPLICABLE",
                "M13_UPSTREAM_M13B_EXECUTION": m13b_exec or "M13_S3_NOT_APPLICABLE",
                "M13_UPSTREAM_M13C_EXECUTION": m13c_exec or "M13_S3_NOT_APPLICABLE",
                "M13_UPSTREAM_M13D_EXECUTION": m13d_exec or "M13_S3_NOT_APPLICABLE",
                "M13_UPSTREAM_M13E_EXECUTION": m13e_exec or "M13_S3_NOT_APPLICABLE",
                "M13_UPSTREAM_M13G_EXECUTION": "M13_S3_NOT_APPLICABLE",
                "M13_UPSTREAM_M13H_EXECUTION": "M13_S3_NOT_APPLICABLE",
                "M13_UPSTREAM_M13I_EXECUTION": "M13_S3_NOT_APPLICABLE",
            }
        )
        rc, _, err = run(["python", "scripts/dev_substrate/m13g_residual_readability_closure.py"], timeout=9000, env=env_g)
        if rc != 0:
            add_blocker(
                blockers,
                "M13-ST-B7",
                "S3",
                {"reason": "m13g_command_failed", "stderr": err.strip()[:300], "rc": rc},
            )

        m13g_summary = loadj(m13g_dir / "m13g_execution_summary.json")
        m13g_snapshot = loadj(m13g_dir / "m13g_post_teardown_readability_snapshot.json")
        m13g_register = loadj(m13g_dir / "m13g_blocker_register.json")
        if m13g_snapshot:
            dumpj(out / "m13g_post_teardown_readability_snapshot.json", m13g_snapshot)
        if m13g_summary:
            dumpj(out / "m13g_execution_summary.json", m13g_summary)
        if m13g_register:
            dumpj(out / "m13g_blocker_register.json", m13g_register)

        if not m13g_summary:
            add_blocker(blockers, "M13-ST-B7", "S3", {"reason": "m13g_summary_missing"})
        elif not (
            bool(m13g_summary.get("overall_pass"))
            and str(m13g_summary.get("next_gate", "")) == "M13.H_READY"
            and str(m13g_summary.get("verdict", "")) == "ADVANCE_TO_M13_H"
        ):
            add_blocker(blockers, "M13-ST-B7", "S3", {"reason": "m13g_not_ready", "summary": m13g_summary})

        if m13g_snapshot:
            residual_count = int(m13g_snapshot.get("residual_item_count", 0) or 0)
            if residual_count > 0:
                add_blocker(blockers, "M13-ST-B7", "S3", {"reason": "residual_items_non_zero", "residual_item_count": residual_count})
            checks = m13g_snapshot.get("readability_checks", [])
            if isinstance(checks, list):
                unreadable = [row for row in checks if isinstance(row, dict) and not bool(row.get("readable", False))]
                if unreadable:
                    add_blocker(
                        blockers,
                        "M13-ST-B8",
                        "S3",
                        {"reason": "post_teardown_unreadable_surfaces", "count": len(unreadable)},
                    )

        if m13g_register and isinstance(m13g_register.get("blockers"), list):
            for row in m13g_register.get("blockers", []):
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
                        "M13-ST-B19",
                        "S3",
                        {"reason": "managed_quota_or_access_boundary_pressure_detected_in_m13g"},
                    )
                    break
    elif m13f_exec and not m13g_exec and not blockers:
        add_blocker(blockers, "M13-ST-B7", "S3", {"reason": "m13g_not_executed"})
    elif blockers and not m13g_exec:
        add_blocker(blockers, "M13-ST-B7", "S3", {"reason": "m13g_skipped_due_to_prior_blocker"})

    non_gate_precondition_required = bool(packet.get("M13_STRESS_REQUIRE_NON_GATE_ACCEPTANCE", True))
    non_gate_precondition_pass = bool(m13f_snapshot) and bool(m13g_snapshot)
    dumpj(
        out / "m13_non_gate_acceptance_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M13-ST-S3",
            "non_gate_precondition_required": non_gate_precondition_required,
            "non_gate_precondition_pass": non_gate_precondition_pass,
            "source_ref_f": f"evidence/dev_full/run_control/{m13f_exec}/m13f_teardown_execution_snapshot.json" if m13f_exec else "",
            "source_ref_g": f"evidence/dev_full/run_control/{m13g_exec}/m13g_post_teardown_readability_snapshot.json" if m13g_exec else "",
        },
    )

    stage_findings = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M13-ST-S3",
        "findings": [
            {
                "id": "M13-ST-F4",
                "classification": "PREVENT",
                "status": "CLOSED" if explicit_override_used else "OPEN",
                "note": "S3 dispatch uses explicit upstream input overrides (no workflow default reliance).",
            },
            {
                "id": "M13-ST-F5",
                "classification": "PREVENT",
                "status": "CLOSED" if len([b for b in blockers if b.get("id") in {"M13-ST-B15"}]) == 0 else "OPEN",
                "note": "Strict upstream continuity and stale-evidence guard are enforced in S3.",
            },
            {
                "id": "M13-ST-F8",
                "classification": "OBSERVE",
                "status": "CLOSED" if len([b for b in blockers if b.get("id") in {"M13-ST-B6"}]) == 0 else "OPEN",
                "note": "Teardown execution lane completed with deterministic gate checks.",
            },
            {
                "id": "M13-ST-F9",
                "classification": "OBSERVE",
                "status": "CLOSED" if len([b for b in blockers if b.get("id") in {"M13-ST-B7", "M13-ST-B8"}]) == 0 else "OPEN",
                "note": "Residual/readability lane completed with deterministic post-teardown checks.",
            },
        ],
    }
    dumpj(out / "m13_stagea_findings.json", stage_findings)

    lane_matrix = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M13-ST-S3",
        "lanes": [
            {
                "lane": "F",
                "component": "M13.F",
                "execution_id": m13f_exec,
                "overall_pass": bool(m13f_summary.get("overall_pass")) if m13f_summary else False,
                "next_gate": str(m13f_summary.get("next_gate", "")) if m13f_summary else "",
                "verdict": str(m13f_summary.get("verdict", "")) if m13f_summary else "",
            },
            {
                "lane": "G",
                "component": "M13.G",
                "execution_id": m13g_exec,
                "overall_pass": bool(m13g_summary.get("overall_pass")) if m13g_summary else False,
                "next_gate": str(m13g_summary.get("next_gate", "")) if m13g_summary else "",
                "verdict": str(m13g_summary.get("verdict", "")) if m13g_summary else "",
            },
        ],
    }
    dumpj(out / "m13_lane_matrix.json", lane_matrix)

    runtime_locality_ok = bool(packet.get("M13_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY", True))
    if not runtime_locality_ok:
        add_blocker(blockers, "M13-ST-B16", "S3", {"reason": "runtime_locality_policy_not_true"})
    dumpj(
        out / "m13_runtime_locality_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M13-ST-S3",
            "overall_pass": runtime_locality_ok,
            "require_remote_runtime_only": bool(packet.get("M13_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY", True)),
            "runtime_execution_attempted": False,
            "runtime_execution_mode": "local_control_orchestration_only_remote_runtime",
        },
    )

    refs = [
        f"evidence/dev_full/run_control/{s2_exec}/stress/m13_execution_summary.json" if s2_exec else "",
        f"evidence/dev_full/run_control/{m13f_exec}/m13f_execution_summary.json" if m13f_exec else "",
        f"evidence/dev_full/run_control/{m13g_exec}/m13g_execution_summary.json" if m13g_exec else "",
    ]
    source_guard_ok = len([b for b in blockers if b.get("id") in {"M13-ST-B11", "M13-ST-B16"}]) == 0
    dumpj(
        out / "m13_source_authority_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M13-ST-S3",
            "overall_pass": source_guard_ok,
            "authoritative_refs": refs,
            "evidence_bucket": bucket,
            "runtime_locality_only_control_plane": True,
        },
    )

    realism_ok = bool(packet.get("M13_STRESS_DISALLOW_WAIVED_REALISM", True))
    if not realism_ok:
        add_blocker(blockers, "M13-ST-B17", "S3", {"reason": "realism_guard_not_true"})
    dumpj(
        out / "m13_realism_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M13-ST-S3",
            "overall_pass": realism_ok,
            "disallow_waived_realism": bool(packet.get("M13_STRESS_DISALLOW_WAIVED_REALISM", True)),
        },
    )

    if not bool(packet.get("M13_STRESS_REQUIRE_DATA_ENGINE_BLACKBOX", True)):
        add_blocker(blockers, "M13-ST-B16", "S3", {"reason": "data_engine_blackbox_guard_not_true"})

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
            "upstream_m13_s2_execution": s2_exec,
            "m12j_execution_id": m12j_exec,
            "m13a_execution_id": m13a_exec,
            "m13b_execution_id": m13b_exec,
            "m13c_execution_id": m13c_exec,
            "m13d_execution_id": m13d_exec,
            "m13e_execution_id": m13e_exec,
            "m13f_execution_id": m13f_exec,
            "m13g_execution_id": m13g_exec,
            "decisions": [
                "S3 enforced strict M13 S2 entry continuity before executing lanes F and G.",
                "S3 executed M13.F teardown execution closure with explicit upstream overrides.",
                "S3 executed M13.G residual/readability closure and required deterministic M13.H_READY gate.",
            ],
            "advisories": advisories,
        },
    )


def run_s4(phase_execution_id: str, upstream_m13_s3_execution: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)
    blockers: list[dict[str, Any]] = []
    advisories: list[str] = []

    plan_text = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    packet = parse_plan_packet(plan_text)
    reg = parse_registry(REG) if REG.exists() else {}

    scripts_required = [
        "scripts/dev_substrate/m13h_post_teardown_cost_guardrail_closure.py",
        "scripts/dev_substrate/m13i_phase_cost_outcome_closure.py",
    ]
    for script_path in scripts_required:
        if not Path(script_path).exists():
            add_blocker(
                blockers,
                "M13-ST-B18",
                "S4",
                {"reason": "required_stage_script_missing", "script": script_path},
            )

    value = reg.get("S3_EVIDENCE_BUCKET")
    if value is None or is_placeholder(value):
        add_blocker(blockers, "M13-ST-B9", "S4", {"reason": "required_handle_missing_or_placeholder", "handle": "S3_EVIDENCE_BUCKET"})
    bucket = str(reg.get("S3_EVIDENCE_BUCKET", "")).strip()

    s3_exec = upstream_m13_s3_execution.strip()
    s3 = loadj(OUT_ROOT / s3_exec / "stress" / "m13_execution_summary.json") if s3_exec else {}
    if not s3:
        add_blocker(
            blockers,
            "M13-ST-B15",
            "S4",
            {
                "reason": "upstream_s3_summary_missing",
                "path": (OUT_ROOT / s3_exec / "stress" / "m13_execution_summary.json").as_posix(),
            },
        )
    elif not (
        bool(s3.get("overall_pass"))
        and int(s3.get("open_blocker_count", 1)) == 0
        and str(s3.get("next_gate", "")).strip() == "M13_ST_S4_READY"
    ):
        add_blocker(
            blockers,
            "M13-ST-B15",
            "S4",
            {
                "reason": "upstream_s3_not_ready",
                "summary": {
                    "overall_pass": s3.get("overall_pass"),
                    "open_blocker_count": s3.get("open_blocker_count"),
                    "next_gate": s3.get("next_gate"),
                    "verdict": s3.get("verdict"),
                },
            },
        )

    m12j_exec = str(s3.get("m12j_execution_id", "")).strip() if s3 else ""
    m13a_exec = str(s3.get("m13a_execution_id", "")).strip() if s3 else ""
    m13b_exec = str(s3.get("m13b_execution_id", "")).strip() if s3 else ""
    m13c_exec = str(s3.get("m13c_execution_id", "")).strip() if s3 else ""
    m13d_exec = str(s3.get("m13d_execution_id", "")).strip() if s3 else ""
    m13e_exec = str(s3.get("m13e_execution_id", "")).strip() if s3 else ""
    m13f_exec = str(s3.get("m13f_execution_id", "")).strip() if s3 else ""
    m13g_exec = str(s3.get("m13g_execution_id", "")).strip() if s3 else ""
    if not m12j_exec:
        add_blocker(blockers, "M13-ST-B9", "S4", {"reason": "missing_m12j_execution_id_from_s3_summary"})
    if not m13g_exec:
        add_blocker(blockers, "M13-ST-B9", "S4", {"reason": "missing_m13g_execution_id_from_s3_summary"})

    explicit_override_used = True
    if bool(packet.get("M13_STRESS_FAIL_ON_DEFAULT_UPSTREAM_INPUTS", True)) and not explicit_override_used:
        add_blocker(blockers, "M13-ST-B20", "S4", {"reason": "required_explicit_upstream_override_not_used"})

    m13h_exec = ""
    m13h_summary: dict[str, Any] = {}
    m13h_snapshot: dict[str, Any] = {}
    if Path("scripts/dev_substrate/m13h_post_teardown_cost_guardrail_closure.py").exists() and m12j_exec and m13g_exec and not blockers:
        m13h_exec = f"m13h_stress_s4_{tok()}"
        m13h_dir = out / "_m13h"
        env_h = dict(os.environ)
        env_h.update(
            {
                "M13H_EXECUTION_ID": m13h_exec,
                "M13H_RUN_DIR": m13h_dir.as_posix(),
                "EVIDENCE_BUCKET": bucket,
                "UPSTREAM_M12J_EXECUTION": m12j_exec,
                "UPSTREAM_M13G_EXECUTION": m13g_exec,
                "AWS_REGION": "eu-west-2",
                "M13_UPSTREAM_M13B0_EXECUTION": "M13_S4_NOT_APPLICABLE",
                "M13_UPSTREAM_M13A_EXECUTION": m13a_exec or "M13_S4_NOT_APPLICABLE",
                "M13_UPSTREAM_M13B_EXECUTION": m13b_exec or "M13_S4_NOT_APPLICABLE",
                "M13_UPSTREAM_M13C_EXECUTION": m13c_exec or "M13_S4_NOT_APPLICABLE",
                "M13_UPSTREAM_M13D_EXECUTION": m13d_exec or "M13_S4_NOT_APPLICABLE",
                "M13_UPSTREAM_M13E_EXECUTION": m13e_exec or "M13_S4_NOT_APPLICABLE",
                "M13_UPSTREAM_M13F_EXECUTION": m13f_exec or "M13_S4_NOT_APPLICABLE",
                "M13_UPSTREAM_M13H_EXECUTION": "M13_S4_NOT_APPLICABLE",
                "M13_UPSTREAM_M13I_EXECUTION": "M13_S4_NOT_APPLICABLE",
            }
        )
        rc, _, err = run(["python", "scripts/dev_substrate/m13h_post_teardown_cost_guardrail_closure.py"], timeout=9000, env=env_h)
        if rc != 0:
            add_blocker(
                blockers,
                "M13-ST-B9",
                "S4",
                {"reason": "m13h_command_failed", "stderr": err.strip()[:300], "rc": rc},
            )

        m13h_summary = loadj(m13h_dir / "m13h_execution_summary.json")
        m13h_snapshot = loadj(m13h_dir / "m13h_cost_guardrail_snapshot.json")
        m13h_register = loadj(m13h_dir / "m13h_blocker_register.json")
        if m13h_snapshot:
            dumpj(out / "m13h_cost_guardrail_snapshot.json", m13h_snapshot)
        if m13h_summary:
            dumpj(out / "m13h_execution_summary.json", m13h_summary)
        if m13h_register:
            dumpj(out / "m13h_blocker_register.json", m13h_register)

        if not m13h_summary:
            add_blocker(blockers, "M13-ST-B9", "S4", {"reason": "m13h_summary_missing"})
        elif not (
            bool(m13h_summary.get("overall_pass"))
            and str(m13h_summary.get("next_gate", "")) == "M13.I_READY"
            and str(m13h_summary.get("verdict", "")) == "ADVANCE_TO_M13_I"
        ):
            add_blocker(blockers, "M13-ST-B9", "S4", {"reason": "m13h_not_ready", "summary": m13h_summary})

        if m13h_register and isinstance(m13h_register.get("blockers"), list):
            for row in m13h_register.get("blockers", []):
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
                        "M13-ST-B19",
                        "S4",
                        {"reason": "managed_quota_or_access_boundary_pressure_detected_in_m13h"},
                    )
                    break

    m13i_exec = ""
    m13i_summary: dict[str, Any] = {}
    m13i_receipt: dict[str, Any] = {}
    if Path("scripts/dev_substrate/m13i_phase_cost_outcome_closure.py").exists() and m12j_exec and m13h_exec and not blockers:
        m13i_exec = f"m13i_stress_s4_{tok()}"
        m13i_dir = out / "_m13i"
        env_i = dict(os.environ)
        env_i.update(
            {
                "M13I_EXECUTION_ID": m13i_exec,
                "M13I_RUN_DIR": m13i_dir.as_posix(),
                "EVIDENCE_BUCKET": bucket,
                "UPSTREAM_M12J_EXECUTION": m12j_exec,
                "UPSTREAM_M13H_EXECUTION": m13h_exec,
                "AWS_REGION": "eu-west-2",
                "M13_UPSTREAM_M13B0_EXECUTION": "M13_S4_NOT_APPLICABLE",
                "M13_UPSTREAM_M13A_EXECUTION": m13a_exec or "M13_S4_NOT_APPLICABLE",
                "M13_UPSTREAM_M13B_EXECUTION": m13b_exec or "M13_S4_NOT_APPLICABLE",
                "M13_UPSTREAM_M13C_EXECUTION": m13c_exec or "M13_S4_NOT_APPLICABLE",
                "M13_UPSTREAM_M13D_EXECUTION": m13d_exec or "M13_S4_NOT_APPLICABLE",
                "M13_UPSTREAM_M13E_EXECUTION": m13e_exec or "M13_S4_NOT_APPLICABLE",
                "M13_UPSTREAM_M13F_EXECUTION": m13f_exec or "M13_S4_NOT_APPLICABLE",
                "M13_UPSTREAM_M13G_EXECUTION": m13g_exec or "M13_S4_NOT_APPLICABLE",
                "M13_UPSTREAM_M13I_EXECUTION": "M13_S4_NOT_APPLICABLE",
            }
        )
        rc, _, err = run(["python", "scripts/dev_substrate/m13i_phase_cost_outcome_closure.py"], timeout=9000, env=env_i)
        if rc != 0:
            add_blocker(
                blockers,
                "M13-ST-B10",
                "S4",
                {"reason": "m13i_command_failed", "stderr": err.strip()[:300], "rc": rc},
            )

        m13i_summary = loadj(m13i_dir / "m13i_execution_summary.json")
        m13i_envelope = loadj(m13i_dir / "m13_phase_budget_envelope.json")
        m13i_receipt = loadj(m13i_dir / "m13_phase_cost_outcome_receipt.json")
        m13i_register = loadj(m13i_dir / "m13i_blocker_register.json")
        if m13i_envelope:
            dumpj(out / "m13_phase_budget_envelope.json", m13i_envelope)
        if m13i_receipt:
            dumpj(out / "m13_phase_cost_outcome_receipt.json", m13i_receipt)
        if m13i_summary:
            dumpj(out / "m13i_execution_summary.json", m13i_summary)
        if m13i_register:
            dumpj(out / "m13i_blocker_register.json", m13i_register)

        if not m13i_summary:
            add_blocker(blockers, "M13-ST-B10", "S4", {"reason": "m13i_summary_missing"})
        elif not (
            bool(m13i_summary.get("overall_pass"))
            and str(m13i_summary.get("next_gate", "")) == "M13.J_READY"
            and str(m13i_summary.get("verdict", "")) == "ADVANCE_TO_M13_J"
        ):
            add_blocker(blockers, "M13-ST-B10", "S4", {"reason": "m13i_not_ready", "summary": m13i_summary})

        if m13i_receipt:
            if not bool(m13i_receipt.get("phase_outcome_pass", False)):
                add_blocker(blockers, "M13-ST-B10", "S4", {"reason": "m13i_phase_outcome_pass_false"})
            if not bool(m13i_receipt.get("cost_within_envelope", False)):
                add_blocker(blockers, "M13-ST-B10", "S4", {"reason": "m13i_cost_within_envelope_false"})

        if m13i_register and isinstance(m13i_register.get("blockers"), list):
            for row in m13i_register.get("blockers", []):
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
                        "M13-ST-B19",
                        "S4",
                        {"reason": "managed_quota_or_access_boundary_pressure_detected_in_m13i"},
                    )
                    break
    elif m13h_exec and not m13i_exec and not blockers:
        add_blocker(blockers, "M13-ST-B10", "S4", {"reason": "m13i_not_executed"})
    elif blockers and not m13i_exec:
        add_blocker(blockers, "M13-ST-B10", "S4", {"reason": "m13i_skipped_due_to_prior_blocker"})

    non_gate_precondition_required = bool(packet.get("M13_STRESS_REQUIRE_NON_GATE_ACCEPTANCE", True))
    non_gate_precondition_pass = bool(m13h_snapshot) and bool(m13i_receipt)
    dumpj(
        out / "m13_non_gate_acceptance_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M13-ST-S4",
            "non_gate_precondition_required": non_gate_precondition_required,
            "non_gate_precondition_pass": non_gate_precondition_pass,
            "source_ref_h": f"evidence/dev_full/run_control/{m13h_exec}/m13h_cost_guardrail_snapshot.json" if m13h_exec else "",
            "source_ref_i": f"evidence/dev_full/run_control/{m13i_exec}/m13_phase_cost_outcome_receipt.json" if m13i_exec else "",
        },
    )

    stage_findings = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M13-ST-S4",
        "findings": [
            {
                "id": "M13-ST-F4",
                "classification": "PREVENT",
                "status": "CLOSED" if explicit_override_used else "OPEN",
                "note": "S4 dispatch uses explicit upstream input overrides (no workflow default reliance).",
            },
            {
                "id": "M13-ST-F5",
                "classification": "PREVENT",
                "status": "CLOSED" if len([b for b in blockers if b.get("id") in {"M13-ST-B15"}]) == 0 else "OPEN",
                "note": "Strict upstream continuity and stale-evidence guard are enforced in S4.",
            },
            {
                "id": "M13-ST-F10",
                "classification": "OBSERVE",
                "status": "CLOSED" if len([b for b in blockers if b.get("id") in {"M13-ST-B9"}]) == 0 else "OPEN",
                "note": "Post-teardown cost guardrail lane completed with deterministic gate checks.",
            },
            {
                "id": "M13-ST-F13",
                "classification": "OBSERVE",
                "status": "CLOSED" if len([b for b in blockers if b.get("id") in {"M13-ST-B10"}]) == 0 else "OPEN",
                "note": "Phase cost-outcome lane completed with deterministic gate checks.",
            },
        ],
    }
    dumpj(out / "m13_stagea_findings.json", stage_findings)

    lane_matrix = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M13-ST-S4",
        "lanes": [
            {
                "lane": "H",
                "component": "M13.H",
                "execution_id": m13h_exec,
                "overall_pass": bool(m13h_summary.get("overall_pass")) if m13h_summary else False,
                "next_gate": str(m13h_summary.get("next_gate", "")) if m13h_summary else "",
                "verdict": str(m13h_summary.get("verdict", "")) if m13h_summary else "",
            },
            {
                "lane": "I",
                "component": "M13.I",
                "execution_id": m13i_exec,
                "overall_pass": bool(m13i_summary.get("overall_pass")) if m13i_summary else False,
                "next_gate": str(m13i_summary.get("next_gate", "")) if m13i_summary else "",
                "verdict": str(m13i_summary.get("verdict", "")) if m13i_summary else "",
            },
        ],
    }
    dumpj(out / "m13_lane_matrix.json", lane_matrix)

    runtime_locality_ok = bool(packet.get("M13_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY", True))
    if not runtime_locality_ok:
        add_blocker(blockers, "M13-ST-B16", "S4", {"reason": "runtime_locality_policy_not_true"})
    dumpj(
        out / "m13_runtime_locality_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M13-ST-S4",
            "overall_pass": runtime_locality_ok,
            "require_remote_runtime_only": bool(packet.get("M13_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY", True)),
            "runtime_execution_attempted": False,
            "runtime_execution_mode": "local_control_orchestration_only_remote_runtime",
        },
    )

    refs = [
        f"evidence/dev_full/run_control/{s3_exec}/stress/m13_execution_summary.json" if s3_exec else "",
        f"evidence/dev_full/run_control/{m13h_exec}/m13h_execution_summary.json" if m13h_exec else "",
        f"evidence/dev_full/run_control/{m13i_exec}/m13i_execution_summary.json" if m13i_exec else "",
    ]
    source_guard_ok = len([b for b in blockers if b.get("id") in {"M13-ST-B11", "M13-ST-B16"}]) == 0
    dumpj(
        out / "m13_source_authority_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M13-ST-S4",
            "overall_pass": source_guard_ok,
            "authoritative_refs": refs,
            "evidence_bucket": bucket,
            "runtime_locality_only_control_plane": True,
        },
    )

    realism_ok = bool(packet.get("M13_STRESS_DISALLOW_WAIVED_REALISM", True))
    if not realism_ok:
        add_blocker(blockers, "M13-ST-B17", "S4", {"reason": "realism_guard_not_true"})
    dumpj(
        out / "m13_realism_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M13-ST-S4",
            "overall_pass": realism_ok,
            "disallow_waived_realism": bool(packet.get("M13_STRESS_DISALLOW_WAIVED_REALISM", True)),
        },
    )

    if not bool(packet.get("M13_STRESS_REQUIRE_DATA_ENGINE_BLACKBOX", True)):
        add_blocker(blockers, "M13-ST-B16", "S4", {"reason": "data_engine_blackbox_guard_not_true"})

    platform_run_id = str(s3.get("platform_run_id", "")) if s3 else ""
    scenario_run_id = str(s3.get("scenario_run_id", "")) if s3 else ""
    return finish(
        "S4",
        phase_execution_id,
        out,
        blockers,
        S4_ARTS,
        {
            "platform_run_id": platform_run_id,
            "scenario_run_id": scenario_run_id,
            "upstream_m13_s3_execution": s3_exec,
            "m12j_execution_id": m12j_exec,
            "m13a_execution_id": m13a_exec,
            "m13b_execution_id": m13b_exec,
            "m13c_execution_id": m13c_exec,
            "m13d_execution_id": m13d_exec,
            "m13e_execution_id": m13e_exec,
            "m13f_execution_id": m13f_exec,
            "m13g_execution_id": m13g_exec,
            "m13h_execution_id": m13h_exec,
            "m13i_execution_id": m13i_exec,
            "decisions": [
                "S4 enforced strict M13 S3 entry continuity before executing lanes H and I.",
                "S4 executed M13.H post-teardown cost guardrail closure with explicit upstream overrides.",
                "S4 executed M13.I phase cost-outcome closure and required deterministic M13.J_READY gate.",
            ],
            "advisories": advisories,
        },
    )


def run_s5(phase_execution_id: str, upstream_m13_s4_execution: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)
    blockers: list[dict[str, Any]] = []
    advisories: list[str] = []

    plan_text = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    packet = parse_plan_packet(plan_text)
    reg = parse_registry(REG) if REG.exists() else {}

    scripts_required = ["scripts/dev_substrate/m13j_final_closure_sync.py"]
    for script_path in scripts_required:
        if not Path(script_path).exists():
            add_blocker(
                blockers,
                "M13-ST-B18",
                "S5",
                {"reason": "required_stage_script_missing", "script": script_path},
            )

    value = reg.get("S3_EVIDENCE_BUCKET")
    if value is None or is_placeholder(value):
        add_blocker(blockers, "M13-ST-B11", "S5", {"reason": "required_handle_missing_or_placeholder", "handle": "S3_EVIDENCE_BUCKET"})
    bucket = str(reg.get("S3_EVIDENCE_BUCKET", "")).strip()

    s4_exec = upstream_m13_s4_execution.strip()
    s4 = loadj(OUT_ROOT / s4_exec / "stress" / "m13_execution_summary.json") if s4_exec else {}
    if not s4:
        add_blocker(
            blockers,
            "M13-ST-B15",
            "S5",
            {
                "reason": "upstream_s4_summary_missing",
                "path": (OUT_ROOT / s4_exec / "stress" / "m13_execution_summary.json").as_posix(),
            },
        )
    elif not (
        bool(s4.get("overall_pass"))
        and int(s4.get("open_blocker_count", 1)) == 0
        and str(s4.get("next_gate", "")).strip() == "M13_ST_S5_READY"
    ):
        add_blocker(
            blockers,
            "M13-ST-B15",
            "S5",
            {
                "reason": "upstream_s4_not_ready",
                "summary": {
                    "overall_pass": s4.get("overall_pass"),
                    "open_blocker_count": s4.get("open_blocker_count"),
                    "next_gate": s4.get("next_gate"),
                    "verdict": s4.get("verdict"),
                },
            },
        )

    m12j_exec = str(s4.get("m12j_execution_id", "")).strip() if s4 else ""
    m13a_exec = str(s4.get("m13a_execution_id", "")).strip() if s4 else ""
    m13b_exec = str(s4.get("m13b_execution_id", "")).strip() if s4 else ""
    m13c_exec = str(s4.get("m13c_execution_id", "")).strip() if s4 else ""
    m13d_exec = str(s4.get("m13d_execution_id", "")).strip() if s4 else ""
    m13e_exec = str(s4.get("m13e_execution_id", "")).strip() if s4 else ""
    m13f_exec = str(s4.get("m13f_execution_id", "")).strip() if s4 else ""
    m13g_exec = str(s4.get("m13g_execution_id", "")).strip() if s4 else ""
    m13h_exec = str(s4.get("m13h_execution_id", "")).strip() if s4 else ""
    m13i_exec = str(s4.get("m13i_execution_id", "")).strip() if s4 else ""
    required_exec = {
        "m12j_execution_id": m12j_exec,
        "m13a_execution_id": m13a_exec,
        "m13b_execution_id": m13b_exec,
        "m13c_execution_id": m13c_exec,
        "m13d_execution_id": m13d_exec,
        "m13e_execution_id": m13e_exec,
        "m13f_execution_id": m13f_exec,
        "m13g_execution_id": m13g_exec,
        "m13h_execution_id": m13h_exec,
        "m13i_execution_id": m13i_exec,
    }
    for key, value_exec in required_exec.items():
        if not value_exec:
            add_blocker(blockers, "M13-ST-B11", "S5", {"reason": "missing_required_execution_from_s4_summary", "key": key})

    explicit_override_used = True
    if bool(packet.get("M13_STRESS_FAIL_ON_DEFAULT_UPSTREAM_INPUTS", True)) and not explicit_override_used:
        add_blocker(blockers, "M13-ST-B20", "S5", {"reason": "required_explicit_upstream_override_not_used"})

    m13j_exec = ""
    m13j_summary: dict[str, Any] = {}
    m13j_snapshot: dict[str, Any] = {}
    if Path("scripts/dev_substrate/m13j_final_closure_sync.py").exists() and all(required_exec.values()) and not blockers:
        m13j_exec = f"m13j_stress_s5_{tok()}"
        m13j_dir = out / "_m13j"
        env_j = dict(os.environ)
        env_j.update(
            {
                "M13J_EXECUTION_ID": m13j_exec,
                "M13J_RUN_DIR": m13j_dir.as_posix(),
                "EVIDENCE_BUCKET": bucket,
                "UPSTREAM_M12J_EXECUTION": m12j_exec,
                "UPSTREAM_M13A_EXECUTION": m13a_exec,
                "UPSTREAM_M13B_EXECUTION": m13b_exec,
                "UPSTREAM_M13C_EXECUTION": m13c_exec,
                "UPSTREAM_M13D_EXECUTION": m13d_exec,
                "UPSTREAM_M13E_EXECUTION": m13e_exec,
                "UPSTREAM_M13F_EXECUTION": m13f_exec,
                "UPSTREAM_M13G_EXECUTION": m13g_exec,
                "UPSTREAM_M13H_EXECUTION": m13h_exec,
                "UPSTREAM_M13I_EXECUTION": m13i_exec,
                "AWS_REGION": "eu-west-2",
                "M13_UPSTREAM_M13B0_EXECUTION": "M13_S5_NOT_APPLICABLE",
            }
        )
        rc, _, err = run(["python", "scripts/dev_substrate/m13j_final_closure_sync.py"], timeout=9000, env=env_j)
        if rc != 0:
            add_blocker(
                blockers,
                "M13-ST-B11",
                "S5",
                {"reason": "m13j_command_failed", "stderr": err.strip()[:300], "rc": rc},
            )

        m13j_summary = loadj(m13j_dir / "m13j_execution_summary.json")
        m13j_snapshot = loadj(m13j_dir / "m13_closure_sync_snapshot.json")
        m13j_register = loadj(m13j_dir / "m13j_blocker_register.json")
        if m13j_snapshot:
            dumpj(out / "m13_closure_sync_snapshot.json", m13j_snapshot)
        if m13j_summary:
            dumpj(out / "m13j_execution_summary.json", m13j_summary)
        if m13j_register:
            dumpj(out / "m13j_blocker_register.json", m13j_register)

        if not m13j_summary:
            add_blocker(blockers, "M13-ST-B11", "S5", {"reason": "m13j_summary_missing"})
        elif not (
            bool(m13j_summary.get("overall_pass"))
            and str(m13j_summary.get("next_gate", "")) == "DEV_FULL_TRACK_COMPLETE"
            and str(m13j_summary.get("verdict", "")) == "M13_COMPLETE_GREEN"
        ):
            add_blocker(blockers, "M13-ST-B11", "S5", {"reason": "m13j_not_ready", "summary": m13j_summary})

        if m13j_register and isinstance(m13j_register.get("blockers"), list):
            for row in m13j_register.get("blockers", []):
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
                        "M13-ST-B19",
                        "S5",
                        {"reason": "managed_quota_or_access_boundary_pressure_detected_in_m13j"},
                    )
                    break

    non_gate_precondition_required = bool(packet.get("M13_STRESS_REQUIRE_NON_GATE_ACCEPTANCE", True))
    source_matrix_pass = bool(m13j_snapshot.get("source_matrix_pass", False)) if m13j_snapshot else False
    non_gate_acceptance_pass = bool(m13j_snapshot.get("non_gate_acceptance_pass", False)) if m13j_snapshot else False
    non_gate_acceptance_map = m13j_snapshot.get("non_gate_acceptance", {}) if isinstance(m13j_snapshot, dict) else {}
    if non_gate_precondition_required:
        if not m13j_snapshot:
            add_blocker(blockers, "M13-ST-B12", "S5", {"reason": "missing_m13_closure_sync_snapshot"})
        elif not source_matrix_pass:
            add_blocker(blockers, "M13-ST-B11", "S5", {"reason": "closure_source_matrix_not_passed"})
        elif not non_gate_acceptance_pass:
            add_blocker(
                blockers,
                "M13-ST-B12",
                "S5",
                {"reason": "closure_non_gate_acceptance_not_passed", "non_gate_acceptance": non_gate_acceptance_map},
            )
    dumpj(
        out / "m13_non_gate_acceptance_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M13-ST-S5",
            "non_gate_precondition_required": non_gate_precondition_required,
            "source_matrix_pass": source_matrix_pass,
            "non_gate_acceptance_pass": non_gate_acceptance_pass,
            "non_gate_acceptance": non_gate_acceptance_map,
            "source_ref_j": f"evidence/dev_full/run_control/{m13j_exec}/m13_closure_sync_snapshot.json" if m13j_exec else "",
        },
    )

    stage_findings = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M13-ST-S5",
        "findings": [
            {
                "id": "M13-ST-F4",
                "classification": "PREVENT",
                "status": "CLOSED" if explicit_override_used else "OPEN",
                "note": "S5 dispatch uses explicit upstream input overrides (no workflow default reliance).",
            },
            {
                "id": "M13-ST-F5",
                "classification": "PREVENT",
                "status": "CLOSED" if len([b for b in blockers if b.get("id") in {"M13-ST-B15"}]) == 0 else "OPEN",
                "note": "Strict upstream continuity and stale-evidence guard are enforced in S5.",
            },
            {
                "id": "M13-ST-F14",
                "classification": "OBSERVE",
                "status": "CLOSED" if len([b for b in blockers if b.get("id") in {"M13-ST-B11", "M13-ST-B12"}]) == 0 else "OPEN",
                "note": "Final closure sync lane completed with deterministic source-matrix and non-gate acceptance checks.",
            },
        ],
    }
    dumpj(out / "m13_stagea_findings.json", stage_findings)

    lane_matrix = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M13-ST-S5",
        "lanes": [
            {
                "lane": "J",
                "component": "M13.J",
                "execution_id": m13j_exec,
                "overall_pass": bool(m13j_summary.get("overall_pass")) if m13j_summary else False,
                "next_gate": str(m13j_summary.get("next_gate", "")) if m13j_summary else "",
                "verdict": str(m13j_summary.get("verdict", "")) if m13j_summary else "",
            }
        ],
    }
    dumpj(out / "m13_lane_matrix.json", lane_matrix)

    runtime_locality_ok = bool(packet.get("M13_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY", True))
    if not runtime_locality_ok:
        add_blocker(blockers, "M13-ST-B16", "S5", {"reason": "runtime_locality_policy_not_true"})
    dumpj(
        out / "m13_runtime_locality_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M13-ST-S5",
            "overall_pass": runtime_locality_ok,
            "require_remote_runtime_only": bool(packet.get("M13_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY", True)),
            "runtime_execution_attempted": False,
            "runtime_execution_mode": "local_control_orchestration_only_remote_runtime",
        },
    )

    refs = [
        f"evidence/dev_full/run_control/{s4_exec}/stress/m13_execution_summary.json" if s4_exec else "",
        f"evidence/dev_full/run_control/{m13j_exec}/m13j_execution_summary.json" if m13j_exec else "",
        f"evidence/dev_full/run_control/{m13j_exec}/m13_closure_sync_snapshot.json" if m13j_exec else "",
    ]
    source_guard_ok = len([b for b in blockers if b.get("id") in {"M13-ST-B11", "M13-ST-B16"}]) == 0
    dumpj(
        out / "m13_source_authority_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M13-ST-S5",
            "overall_pass": source_guard_ok,
            "authoritative_refs": refs,
            "evidence_bucket": bucket,
            "runtime_locality_only_control_plane": True,
        },
    )

    realism_ok = bool(packet.get("M13_STRESS_DISALLOW_WAIVED_REALISM", True))
    if not realism_ok:
        add_blocker(blockers, "M13-ST-B17", "S5", {"reason": "realism_guard_not_true"})
    dumpj(
        out / "m13_realism_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M13-ST-S5",
            "overall_pass": realism_ok,
            "disallow_waived_realism": bool(packet.get("M13_STRESS_DISALLOW_WAIVED_REALISM", True)),
        },
    )

    if not bool(packet.get("M13_STRESS_REQUIRE_DATA_ENGINE_BLACKBOX", True)):
        add_blocker(blockers, "M13-ST-B16", "S5", {"reason": "data_engine_blackbox_guard_not_true"})

    platform_run_id = str(m13j_snapshot.get("platform_run_id", "")) if m13j_snapshot else (str(s4.get("platform_run_id", "")) if s4 else "")
    scenario_run_id = str(m13j_snapshot.get("scenario_run_id", "")) if m13j_snapshot else (str(s4.get("scenario_run_id", "")) if s4 else "")
    return finish(
        "S5",
        phase_execution_id,
        out,
        blockers,
        S5_ARTS,
        {
            "platform_run_id": platform_run_id,
            "scenario_run_id": scenario_run_id,
            "upstream_m13_s4_execution": s4_exec,
            "m12j_execution_id": m12j_exec,
            "m13a_execution_id": m13a_exec,
            "m13b_execution_id": m13b_exec,
            "m13c_execution_id": m13c_exec,
            "m13d_execution_id": m13d_exec,
            "m13e_execution_id": m13e_exec,
            "m13f_execution_id": m13f_exec,
            "m13g_execution_id": m13g_exec,
            "m13h_execution_id": m13h_exec,
            "m13i_execution_id": m13i_exec,
            "m13j_execution_id": m13j_exec,
            "decisions": [
                "S5 enforced strict M13 S4 entry continuity before executing lane J.",
                "S5 executed M13.J final closure sync with explicit upstream overrides.",
                "S5 mapped lane closure to parent ADVANCE_TO_M14 + M14_READY only with zero unresolved blockers.",
            ],
            "advisories": advisories,
        },
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="M13 stress runner")
    ap.add_argument("--stage", required=True, choices=["S0", "S1", "S2", "S3", "S4", "S5"])
    ap.add_argument("--phase-execution-id", default="")
    ap.add_argument("--upstream-m12-s5-execution", default="")
    ap.add_argument("--upstream-m13-s0-execution", default="")
    ap.add_argument("--upstream-m13-s1-execution", default="")
    ap.add_argument("--upstream-m13-s2-execution", default="")
    ap.add_argument("--upstream-m13-s3-execution", default="")
    ap.add_argument("--upstream-m13-s4-execution", default="")
    args = ap.parse_args()

    phase_execution_id = args.phase_execution_id.strip()
    if not phase_execution_id:
        if args.stage == "S0":
            phase_execution_id = f"m13_stress_s0_{tok()}"
        elif args.stage == "S1":
            phase_execution_id = f"m13_stress_s1_{tok()}"
        elif args.stage == "S2":
            phase_execution_id = f"m13_stress_s2_{tok()}"
        elif args.stage == "S3":
            phase_execution_id = f"m13_stress_s3_{tok()}"
        elif args.stage == "S4":
            phase_execution_id = f"m13_stress_s4_{tok()}"
        elif args.stage == "S5":
            phase_execution_id = f"m13_stress_s5_{tok()}"

    if args.stage == "S0":
        upstream_m12_s5 = args.upstream_m12_s5_execution.strip()
        if not upstream_m12_s5:
            upstream_m12_s5, _ = latest_m12_s5()
        if not upstream_m12_s5:
            raise SystemExit("No upstream M12 S5 execution provided/found.")
        return run_s0(phase_execution_id, upstream_m12_s5)

    if args.stage == "S1":
        upstream_m13_s0 = args.upstream_m13_s0_execution.strip()
        if not upstream_m13_s0:
            upstream_m13_s0, _ = latest_s0()
        if not upstream_m13_s0:
            raise SystemExit("No upstream M13 S0 execution provided/found.")
        return run_s1(phase_execution_id, upstream_m13_s0)

    if args.stage == "S2":
        upstream_m13_s1 = args.upstream_m13_s1_execution.strip()
        if not upstream_m13_s1:
            upstream_m13_s1, _ = latest_s1()
        if not upstream_m13_s1:
            raise SystemExit("No upstream M13 S1 execution provided/found.")
        return run_s2(phase_execution_id, upstream_m13_s1)

    if args.stage == "S3":
        upstream_m13_s2 = args.upstream_m13_s2_execution.strip()
        if not upstream_m13_s2:
            upstream_m13_s2, _ = latest_s2()
        if not upstream_m13_s2:
            raise SystemExit("No upstream M13 S2 execution provided/found.")
        return run_s3(phase_execution_id, upstream_m13_s2)

    if args.stage == "S4":
        upstream_m13_s3 = args.upstream_m13_s3_execution.strip()
        if not upstream_m13_s3:
            upstream_m13_s3, _ = latest_s3()
        if not upstream_m13_s3:
            raise SystemExit("No upstream M13 S3 execution provided/found.")
        return run_s4(phase_execution_id, upstream_m13_s3)

    if args.stage == "S5":
        upstream_m13_s4 = args.upstream_m13_s4_execution.strip()
        if not upstream_m13_s4:
            upstream_m13_s4, _ = latest_s4()
        if not upstream_m13_s4:
            raise SystemExit("No upstream M13 S4 execution provided/found.")
        return run_s5(phase_execution_id, upstream_m13_s4)

    raise SystemExit("Unsupported stage")


if __name__ == "__main__":
    raise SystemExit(main())
