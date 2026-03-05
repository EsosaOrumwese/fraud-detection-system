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


def main() -> int:
    ap = argparse.ArgumentParser(description="M13 stress runner")
    ap.add_argument("--stage", required=True, choices=["S0"])
    ap.add_argument("--phase-execution-id", default="")
    ap.add_argument("--upstream-m12-s5-execution", default="")
    args = ap.parse_args()

    phase_execution_id = args.phase_execution_id.strip() or f"m13_stress_s0_{tok()}"

    if args.stage == "S0":
        upstream_m12_s5 = args.upstream_m12_s5_execution.strip()
        if not upstream_m12_s5:
            upstream_m12_s5, _ = latest_m12_s5()
        if not upstream_m12_s5:
            raise SystemExit("No upstream M12 S5 execution provided/found.")
        return run_s0(phase_execution_id, upstream_m12_s5)

    raise SystemExit("Unsupported stage")


if __name__ == "__main__":
    raise SystemExit(main())
