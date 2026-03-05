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

PLAN = Path("docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M9.stress_test.md")
REG = Path("docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md")
OUT_ROOT = Path("runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control")

S0_ARTS = [
    "m9_stagea_findings.json",
    "m9_lane_matrix.json",
    "m9a_handle_closure_snapshot.json",
    "m9b_handoff_scope_snapshot.json",
    "m9_runtime_locality_guard_snapshot.json",
    "m9_source_authority_guard_snapshot.json",
    "m9_realism_guard_snapshot.json",
    "m9_blocker_register.json",
    "m9_execution_summary.json",
    "m9_decision_log.json",
    "m9_gate_verdict.json",
]

S1_ARTS = [
    "m9c_replay_basis_receipt.json",
    "m9d_asof_maturity_policy_snapshot.json",
    "m9_runtime_locality_guard_snapshot.json",
    "m9_source_authority_guard_snapshot.json",
    "m9_realism_guard_snapshot.json",
    "m9_blocker_register.json",
    "m9_execution_summary.json",
    "m9_decision_log.json",
    "m9_gate_verdict.json",
]

S2_ARTS = [
    "m9e_leakage_guardrail_report.json",
    "m9f_surface_separation_snapshot.json",
    "m9_runtime_locality_guard_snapshot.json",
    "m9_source_authority_guard_snapshot.json",
    "m9_realism_guard_snapshot.json",
    "m9_blocker_register.json",
    "m9_execution_summary.json",
    "m9_decision_log.json",
    "m9_gate_verdict.json",
]

S3_ARTS = [
    "m9g_learning_input_readiness_snapshot.json",
    "m9h_p12_rollup_matrix.json",
    "m9h_p12_gate_verdict.json",
    "m10_handoff_pack.json",
    "m9_runtime_locality_guard_snapshot.json",
    "m9_source_authority_guard_snapshot.json",
    "m9_realism_guard_snapshot.json",
    "m9_blocker_register.json",
    "m9_execution_summary.json",
    "m9_decision_log.json",
    "m9_gate_verdict.json",
]

S4_ARTS = [
    "m9_phase_budget_envelope.json",
    "m9_phase_cost_outcome_receipt.json",
    "m9i_execution_summary.json",
    "m9_runtime_locality_guard_snapshot.json",
    "m9_source_authority_guard_snapshot.json",
    "m9_realism_guard_snapshot.json",
    "m9_blocker_register.json",
    "m9_execution_summary.json",
    "m9_decision_log.json",
    "m9_gate_verdict.json",
]

S5_ARTS = [
    "m9j_execution_summary.json",
    "m9j_blocker_register.json",
    "m9_runtime_locality_guard_snapshot.json",
    "m9_source_authority_guard_snapshot.json",
    "m9_realism_guard_snapshot.json",
    "m9_blocker_register.json",
    "m9_execution_summary.json",
    "m9_decision_log.json",
    "m9_gate_verdict.json",
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


def run(argv: list[str], timeout: int = 90, env: dict[str, str] | None = None) -> tuple[int, str, str]:
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


def latest_m8_s5() -> tuple[str, dict[str, Any]]:
    best_id = ""
    best_payload: dict[str, Any] = {}
    best_stamp = ""
    for d in OUT_ROOT.glob("m8_stress_s5_*"):
        payload = loadj(d / "stress" / "m8_execution_summary.json")
        if not payload:
            continue
        if str(payload.get("stage_id", "")) != "M8-ST-S5":
            continue
        if not bool(payload.get("overall_pass")):
            continue
        if str(payload.get("verdict", "")) != "ADVANCE_TO_M9":
            continue
        if str(payload.get("next_gate", "")) != "M9_READY":
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
    for d in OUT_ROOT.glob("m9_stress_s0_*"):
        payload = loadj(d / "stress" / "m9_execution_summary.json")
        if not payload:
            continue
        if str(payload.get("stage_id", "")) != "M9-ST-S0":
            continue
        if not bool(payload.get("overall_pass")):
            continue
        if str(payload.get("next_gate", "")) != "M9_ST_S1_READY":
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
    for d in OUT_ROOT.glob("m9_stress_s1_*"):
        payload = loadj(d / "stress" / "m9_execution_summary.json")
        if not payload:
            continue
        if str(payload.get("stage_id", "")) != "M9-ST-S1":
            continue
        if not bool(payload.get("overall_pass")):
            continue
        if str(payload.get("next_gate", "")) != "M9_ST_S2_READY":
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
    for d in OUT_ROOT.glob("m9_stress_s2_*"):
        payload = loadj(d / "stress" / "m9_execution_summary.json")
        if not payload:
            continue
        if str(payload.get("stage_id", "")) != "M9-ST-S2":
            continue
        if not bool(payload.get("overall_pass")):
            continue
        if str(payload.get("next_gate", "")) != "M9_ST_S3_READY":
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
    for d in OUT_ROOT.glob("m9_stress_s3_*"):
        payload = loadj(d / "stress" / "m9_execution_summary.json")
        if not payload:
            continue
        if str(payload.get("stage_id", "")) != "M9-ST-S3":
            continue
        if not bool(payload.get("overall_pass")):
            continue
        if str(payload.get("next_gate", "")) != "M9_ST_S4_READY":
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
    for d in OUT_ROOT.glob("m9_stress_s4_*"):
        payload = loadj(d / "stress" / "m9_execution_summary.json")
        if not payload:
            continue
        if str(payload.get("stage_id", "")) != "M9-ST-S4":
            continue
        if not bool(payload.get("overall_pass")):
            continue
        if str(payload.get("next_gate", "")) != "M9_ST_S5_READY":
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
        "m9_blocker_register.json",
        "m9_execution_summary.json",
        "m9_decision_log.json",
        "m9_gate_verdict.json",
    }
    prewrite_required = [name for name in arts if name not in stage_receipts]
    missing = [name for name in prewrite_required if not (out / name).exists()]
    if missing:
        blockers.append(
            {
                "id": "M9-ST-B11",
                "severity": stage,
                "status": "OPEN",
                "details": {"reason": "artifact_contract_incomplete", "missing_outputs": missing},
            }
        )
    blockers = dedupe(blockers)

    overall_pass = len(blockers) == 0
    if overall_pass and stage == "S0":
        next_gate = "M9_ST_S1_READY"
    elif overall_pass and stage == "S1":
        next_gate = "M9_ST_S2_READY"
    elif overall_pass and stage == "S2":
        next_gate = "M9_ST_S3_READY"
    elif overall_pass and stage == "S3":
        next_gate = "M9_ST_S4_READY"
    elif overall_pass and stage == "S4":
        next_gate = "M9_ST_S5_READY"
    elif overall_pass and stage == "S5":
        next_gate = "M10_READY"
    else:
        next_gate = "HOLD_REMEDIATE"
    if overall_pass and stage == "S5":
        verdict = "ADVANCE_TO_M10"
    elif overall_pass:
        verdict = "GO"
    else:
        verdict = "HOLD_REMEDIATE"

    register = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": f"M9-ST-{stage}",
        "open_blocker_count": len(blockers),
        "blockers": blockers,
    }
    summary = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": f"M9-ST-{stage}",
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
        "stage_id": f"M9-ST-{stage}",
        "decisions": list(summary_extra.get("decisions", [])),
        "advisories": list(summary_extra.get("advisories", [])),
    }
    gate = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": f"M9-ST-{stage}",
        "overall_pass": overall_pass,
        "next_gate": next_gate,
        "verdict": verdict,
    }

    dumpj(out / "m9_blocker_register.json", register)
    dumpj(out / "m9_execution_summary.json", summary)
    dumpj(out / "m9_decision_log.json", decision_log)
    dumpj(out / "m9_gate_verdict.json", gate)

    print(
        json.dumps(
            {
                "phase_execution_id": phase_execution_id,
                "stage_id": f"M9-ST-{stage}",
                "overall_pass": overall_pass,
                "open_blocker_count": len(blockers),
                "next_gate": next_gate,
                "output_dir": out.as_posix(),
            }
        )
    )
    return 0


def run_s0(phase_execution_id: str, upstream_m8_execution: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)
    blockers: list[dict[str, Any]] = []
    advisories: list[str] = []

    plan_text = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    packet = parse_plan_packet(plan_text)
    reg = parse_registry(REG) if REG.exists() else {}

    for handle in ["S3_EVIDENCE_BUCKET", "S3_RUN_CONTROL_ROOT_PATTERN"]:
        value = reg.get(handle)
        if value is None or is_placeholder(value):
            add_blocker(blockers, "M9-ST-B1", "S0", {"reason": "required_handle_missing_or_placeholder", "handle": handle})

    bucket = str(reg.get("S3_EVIDENCE_BUCKET", "")).strip()
    local_m8_summary = loadj(OUT_ROOT / upstream_m8_execution / "stress" / "m8_execution_summary.json")
    if not local_m8_summary:
        add_blocker(
            blockers,
            "M9-ST-B2",
            "S0",
            {
                "reason": "upstream_m8_summary_missing",
                "path": (OUT_ROOT / upstream_m8_execution / "stress" / "m8_execution_summary.json").as_posix(),
            },
        )
    else:
        if not (
            bool(local_m8_summary.get("overall_pass"))
            and int(local_m8_summary.get("open_blocker_count", 1)) == 0
            and str(local_m8_summary.get("verdict", "")) == "ADVANCE_TO_M9"
            and str(local_m8_summary.get("next_gate", "")) == "M9_READY"
        ):
            add_blocker(
                blockers,
                "M9-ST-B2",
                "S0",
                {
                    "reason": "upstream_m8_not_ready",
                    "summary": {
                        "overall_pass": local_m8_summary.get("overall_pass"),
                        "open_blocker_count": local_m8_summary.get("open_blocker_count"),
                        "verdict": local_m8_summary.get("verdict"),
                        "next_gate": local_m8_summary.get("next_gate"),
                    },
                },
            )

    m8_bridge_snapshot: dict[str, Any] = {}
    if not blockers:
        bridge_payload = dict(local_m8_summary)
        bridge_refs = dict(bridge_payload.get("upstream_refs", {}))
        if not str(bridge_refs.get("m8i_execution_id", "")).strip():
            bridge_refs["m8i_execution_id"] = str(bridge_payload.get("m8i_execution_id", "")).strip()
        bridge_payload["upstream_refs"] = bridge_refs
        bridge_local = out / "_m8_entry_bridge" / "m8_execution_summary.json"
        dumpj(bridge_local, bridge_payload)
        bridge_key = f"evidence/dev_full/run_control/{upstream_m8_execution}/m8_execution_summary.json"
        rc, _, err = run(["aws", "s3", "cp", bridge_local.as_posix(), f"s3://{bucket}/{bridge_key}", "--region", "eu-west-2"], timeout=120)
        if rc != 0:
            add_blocker(
                blockers,
                "M9-ST-B11",
                "S0",
                {"reason": "m8_entry_bridge_upload_failed", "key": bridge_key, "stderr": err.strip()[:300], "rc": rc},
            )
        m8_bridge_snapshot = {
            "generated_at_utc": now(),
            "source_summary_path": (OUT_ROOT / upstream_m8_execution / "stress" / "m8_execution_summary.json").as_posix(),
            "bridge_payload_path": bridge_local.as_posix(),
            "target_s3_key": bridge_key,
            "upload_rc": rc,
        }

    m9a_exec = ""
    m9b_exec = ""
    m9a_summary: dict[str, Any] = {}
    m9b_summary: dict[str, Any] = {}
    m9a_snapshot: dict[str, Any] = {}
    m9b_snapshot: dict[str, Any] = {}

    if not blockers:
        m9a_exec = f"m9a_stress_s0_{tok()}"
        m9a_dir = out / "_m9a"
        env_m9a = dict(os.environ)
        env_m9a.update(
            {
                "M9A_EXECUTION_ID": m9a_exec,
                "M9A_RUN_DIR": m9a_dir.as_posix(),
                "EVIDENCE_BUCKET": bucket,
                "UPSTREAM_M8_EXECUTION": upstream_m8_execution,
                "AWS_REGION": "eu-west-2",
            }
        )
        rc, _, err = run(["python", "scripts/dev_substrate/m9a_handle_closure.py"], timeout=1800, env=env_m9a)
        if rc != 0:
            add_blocker(blockers, "M9-ST-B1", "S0", {"reason": "m9a_command_failed", "stderr": err.strip()[:300], "rc": rc})
        m9a_summary = loadj(m9a_dir / "m9a_execution_summary.json")
        m9a_snapshot = loadj(m9a_dir / "m9a_handle_closure_snapshot.json")
        if not m9a_summary:
            add_blocker(blockers, "M9-ST-B1", "S0", {"reason": "m9a_summary_missing"})
        elif not (bool(m9a_summary.get("overall_pass")) and str(m9a_summary.get("next_gate", "")) == "M9.B_READY"):
            add_blocker(blockers, "M9-ST-B1", "S0", {"reason": "m9a_not_ready", "summary": m9a_summary})

    if not blockers:
        m9b_exec = f"m9b_stress_s0_{tok()}"
        m9b_dir = out / "_m9b"
        env_m9b = dict(os.environ)
        env_m9b.update(
            {
                "M9B_EXECUTION_ID": m9b_exec,
                "M9B_RUN_DIR": m9b_dir.as_posix(),
                "EVIDENCE_BUCKET": bucket,
                "UPSTREAM_M8_EXECUTION": upstream_m8_execution,
                "UPSTREAM_M9A_EXECUTION": m9a_exec,
                "AWS_REGION": "eu-west-2",
            }
        )
        rc, _, err = run(["python", "scripts/dev_substrate/m9b_handoff_scope_lock.py"], timeout=1800, env=env_m9b)
        if rc != 0:
            add_blocker(blockers, "M9-ST-B2", "S0", {"reason": "m9b_command_failed", "stderr": err.strip()[:300], "rc": rc})
        m9b_summary = loadj(m9b_dir / "m9b_execution_summary.json")
        m9b_snapshot = loadj(m9b_dir / "m9b_handoff_scope_snapshot.json")
        if not m9b_summary:
            add_blocker(blockers, "M9-ST-B2", "S0", {"reason": "m9b_summary_missing"})
        elif not (bool(m9b_summary.get("overall_pass")) and str(m9b_summary.get("next_gate", "")) == "M9.C_READY"):
            add_blocker(blockers, "M9-ST-B2", "S0", {"reason": "m9b_not_ready", "summary": m9b_summary})

    stage_findings = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M9-ST-S0",
        "findings": [
            {"id": "M9-ST-F1", "classification": "PREVENT", "status": "CLOSED", "note": "Dedicated M9 stress authority is present."},
            {"id": "M9-ST-F4", "classification": "PREVENT", "status": "CLOSED" if not blockers else "OPEN", "note": "M8->M9 continuity enforced fail-closed in S0."},
        ],
    }
    dumpj(out / "m9_stagea_findings.json", stage_findings)

    lane_matrix = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M9-ST-S0",
        "lanes": [
            {
                "lane": "A",
                "component": "M9.A",
                "execution_id": m9a_exec,
                "overall_pass": bool(m9a_summary.get("overall_pass")) if m9a_summary else False,
                "next_gate": str(m9a_summary.get("next_gate", "")) if m9a_summary else "",
            },
            {
                "lane": "B",
                "component": "M9.B",
                "execution_id": m9b_exec,
                "overall_pass": bool(m9b_summary.get("overall_pass")) if m9b_summary else False,
                "next_gate": str(m9b_summary.get("next_gate", "")) if m9b_summary else "",
            },
        ],
    }
    dumpj(out / "m9_lane_matrix.json", lane_matrix)

    if m9a_snapshot:
        dumpj(out / "m9a_handle_closure_snapshot.json", m9a_snapshot)
    if m9b_snapshot:
        dumpj(out / "m9b_handoff_scope_snapshot.json", m9b_snapshot)
    if m8_bridge_snapshot:
        dumpj(out / "m9_m8_entry_bridge_snapshot.json", m8_bridge_snapshot)

    runtime_locality_ok = bool(packet.get("M9_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY", True))
    dumpj(
        out / "m9_runtime_locality_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M9-ST-S0",
            "overall_pass": runtime_locality_ok,
            "require_remote_runtime_only": bool(packet.get("M9_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY", True)),
            "runtime_execution_attempted": False,
            "runtime_execution_mode": "none_in_s0_validations",
        },
    )
    if not runtime_locality_ok:
        add_blocker(blockers, "M9-ST-B15", "S0", {"reason": "runtime_locality_policy_not_true"})

    refs = [
        f"evidence/dev_full/run_control/{upstream_m8_execution}/m8_execution_summary.json",
        f"evidence/dev_full/run_control/{m9a_exec}/m9a_execution_summary.json" if m9a_exec else "",
        f"evidence/dev_full/run_control/{m9b_exec}/m9b_execution_summary.json" if m9b_exec else "",
    ]
    source_guard_ok = len([b for b in blockers if b.get("id") in {"M9-ST-B11", "M9-ST-B15"}]) == 0
    dumpj(
        out / "m9_source_authority_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M9-ST-S0",
            "overall_pass": source_guard_ok,
            "authoritative_refs": refs,
            "evidence_bucket": bucket,
        },
    )

    realism_ok = bool(packet.get("M9_STRESS_DISALLOW_WAIVED_REALISM", True))
    if not realism_ok:
        add_blocker(blockers, "M9-ST-B16", "S0", {"reason": "non_toy_realism_guard_not_satisfied"})
    dumpj(
        out / "m9_realism_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M9-ST-S0",
            "overall_pass": realism_ok,
            "disallow_waived_realism": bool(packet.get("M9_STRESS_DISALLOW_WAIVED_REALISM", True)),
        },
    )

    if not bool(packet.get("M9_STRESS_REQUIRE_DATA_ENGINE_BLACKBOX", True)):
        add_blocker(blockers, "M9-ST-B15", "S0", {"reason": "data_engine_blackbox_guard_not_true"})

    return finish(
        "S0",
        phase_execution_id,
        out,
        blockers,
        S0_ARTS,
        {
            "platform_run_id": str(local_m8_summary.get("platform_run_id", "")) if local_m8_summary else "",
            "scenario_run_id": str(local_m8_summary.get("scenario_run_id", "")) if local_m8_summary else "",
            "upstream_m8_execution": upstream_m8_execution,
            "m9a_execution_id": m9a_exec,
            "m9b_execution_id": m9b_exec,
            "decisions": [
                "S0 executed M9.A handle closure then M9.B handoff scope lock under strict M8 entry authority.",
                "S0 published deterministic root bridge for upstream M8 summary to satisfy M9.A contract without semantic override.",
            ],
            "advisories": advisories,
        },
    )


def run_s1(phase_execution_id: str, upstream_m9_s0_execution: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)
    blockers: list[dict[str, Any]] = []
    advisories: list[str] = []

    plan_text = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    packet = parse_plan_packet(plan_text)
    reg = parse_registry(REG) if REG.exists() else {}

    for handle in ["S3_EVIDENCE_BUCKET"]:
        value = reg.get(handle)
        if value is None or is_placeholder(value):
            add_blocker(blockers, "M9-ST-B3", "S1", {"reason": "required_handle_missing_or_placeholder", "handle": handle})

    bucket = str(reg.get("S3_EVIDENCE_BUCKET", "")).strip()
    s0_exec = upstream_m9_s0_execution.strip()
    s0 = loadj(OUT_ROOT / s0_exec / "stress" / "m9_execution_summary.json") if s0_exec else {}
    if not s0:
        s0_exec, s0 = latest_s0()
    if not s0 or not bool(s0.get("overall_pass")) or str(s0.get("next_gate", "")) != "M9_ST_S1_READY":
        add_blocker(blockers, "M9-ST-B3", "S1", {"reason": "upstream_s0_not_ready", "execution_id": s0_exec})

    m9b_exec = str(s0.get("m9b_execution_id", "")).strip() if s0 else ""
    if not m9b_exec:
        add_blocker(blockers, "M9-ST-B3", "S1", {"reason": "missing_m9b_execution_id", "upstream_s0_execution": s0_exec})

    m9c_exec = ""
    m9d_exec = ""
    m9c_summary: dict[str, Any] = {}
    m9d_summary: dict[str, Any] = {}
    m9c_receipt: dict[str, Any] = {}
    m9d_snapshot: dict[str, Any] = {}

    if not blockers:
        m9c_exec = f"m9c_stress_s1_{tok()}"
        m9c_dir = out / "_m9c"
        env_m9c = dict(os.environ)
        env_m9c.update(
            {
                "M9C_EXECUTION_ID": m9c_exec,
                "M9C_RUN_DIR": m9c_dir.as_posix(),
                "EVIDENCE_BUCKET": bucket,
                "UPSTREAM_M9B_EXECUTION": m9b_exec,
                "AWS_REGION": "eu-west-2",
            }
        )
        rc, _, err = run(["python", "scripts/dev_substrate/m9c_replay_basis_receipt.py"], timeout=2400, env=env_m9c)
        if rc != 0:
            add_blocker(blockers, "M9-ST-B3", "S1", {"reason": "m9c_command_failed", "stderr": err.strip()[:300], "rc": rc})
        m9c_summary = loadj(m9c_dir / "m9c_execution_summary.json")
        m9c_receipt = loadj(m9c_dir / "m9c_replay_basis_receipt.json")
        if not m9c_summary:
            add_blocker(blockers, "M9-ST-B3", "S1", {"reason": "m9c_summary_missing"})
        elif not (bool(m9c_summary.get("overall_pass")) and str(m9c_summary.get("next_gate", "")) == "M9.D_READY"):
            add_blocker(blockers, "M9-ST-B3", "S1", {"reason": "m9c_not_ready", "summary": m9c_summary})

    if not blockers:
        m9d_exec = f"m9d_stress_s1_{tok()}"
        m9d_dir = out / "_m9d"
        env_m9d = dict(os.environ)
        env_m9d.update(
            {
                "M9D_EXECUTION_ID": m9d_exec,
                "M9D_RUN_DIR": m9d_dir.as_posix(),
                "EVIDENCE_BUCKET": bucket,
                "UPSTREAM_M9C_EXECUTION": m9c_exec,
                "AWS_REGION": "eu-west-2",
            }
        )
        rc, _, err = run(["python", "scripts/dev_substrate/m9d_asof_maturity_policy.py"], timeout=2400, env=env_m9d)
        if rc != 0:
            add_blocker(blockers, "M9-ST-B4", "S1", {"reason": "m9d_command_failed", "stderr": err.strip()[:300], "rc": rc})
        m9d_summary = loadj(m9d_dir / "m9d_execution_summary.json")
        m9d_snapshot = loadj(m9d_dir / "m9d_asof_maturity_policy_snapshot.json")
        if not m9d_summary:
            add_blocker(blockers, "M9-ST-B4", "S1", {"reason": "m9d_summary_missing"})
        elif not (bool(m9d_summary.get("overall_pass")) and str(m9d_summary.get("next_gate", "")) == "M9.E_READY"):
            add_blocker(blockers, "M9-ST-B4", "S1", {"reason": "m9d_not_ready", "summary": m9d_summary})

    if m9c_receipt:
        dumpj(out / "m9c_replay_basis_receipt.json", m9c_receipt)
    if m9d_snapshot:
        dumpj(out / "m9d_asof_maturity_policy_snapshot.json", m9d_snapshot)

    runtime_locality_ok = bool(packet.get("M9_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY", True))
    dumpj(
        out / "m9_runtime_locality_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M9-ST-S1",
            "overall_pass": runtime_locality_ok,
            "require_remote_runtime_only": bool(packet.get("M9_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY", True)),
            "runtime_execution_attempted": False,
            "runtime_execution_mode": "none_in_s1_validations",
        },
    )
    if not runtime_locality_ok:
        add_blocker(blockers, "M9-ST-B15", "S1", {"reason": "runtime_locality_policy_not_true"})

    refs = [
        f"evidence/dev_full/run_control/{m9b_exec}/m9b_execution_summary.json" if m9b_exec else "",
        f"evidence/dev_full/run_control/{m9c_exec}/m9c_execution_summary.json" if m9c_exec else "",
        f"evidence/dev_full/run_control/{m9d_exec}/m9d_execution_summary.json" if m9d_exec else "",
    ]
    source_guard_ok = len([b for b in blockers if b.get("id") in {"M9-ST-B11", "M9-ST-B15"}]) == 0
    dumpj(
        out / "m9_source_authority_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M9-ST-S1",
            "overall_pass": source_guard_ok,
            "authoritative_refs": refs,
            "evidence_bucket": bucket,
        },
    )

    realism_ok = bool(packet.get("M9_STRESS_DISALLOW_WAIVED_REALISM", True))
    if not realism_ok:
        add_blocker(blockers, "M9-ST-B16", "S1", {"reason": "non_toy_realism_guard_not_satisfied"})
    dumpj(
        out / "m9_realism_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M9-ST-S1",
            "overall_pass": realism_ok,
            "disallow_waived_realism": bool(packet.get("M9_STRESS_DISALLOW_WAIVED_REALISM", True)),
        },
    )

    if not bool(packet.get("M9_STRESS_REQUIRE_DATA_ENGINE_BLACKBOX", True)):
        add_blocker(blockers, "M9-ST-B15", "S1", {"reason": "data_engine_blackbox_guard_not_true"})

    return finish(
        "S1",
        phase_execution_id,
        out,
        blockers,
        S1_ARTS,
        {
            "platform_run_id": str(s0.get("platform_run_id", "")) if s0 else "",
            "scenario_run_id": str(s0.get("scenario_run_id", "")) if s0 else "",
            "upstream_m9_s0_execution": s0_exec,
            "m9c_execution_id": m9c_exec,
            "m9d_execution_id": m9d_exec,
            "decisions": [
                "S1 executed M9.C replay-basis receipt closure then M9.D as-of/maturity policy closure.",
                "S1 enforced strict S0 entry gate and retained source/locality/realism/black-box guards.",
            ],
            "advisories": advisories,
        },
    )


def run_s2(phase_execution_id: str, upstream_m9_s1_execution: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)
    blockers: list[dict[str, Any]] = []
    advisories: list[str] = []

    plan_text = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    packet = parse_plan_packet(plan_text)
    reg = parse_registry(REG) if REG.exists() else {}

    for handle in ["S3_EVIDENCE_BUCKET"]:
        value = reg.get(handle)
        if value is None or is_placeholder(value):
            add_blocker(blockers, "M9-ST-B5", "S2", {"reason": "required_handle_missing_or_placeholder", "handle": handle})

    bucket = str(reg.get("S3_EVIDENCE_BUCKET", "")).strip()
    s1_exec = upstream_m9_s1_execution.strip()
    s1 = loadj(OUT_ROOT / s1_exec / "stress" / "m9_execution_summary.json") if s1_exec else {}
    if not s1:
        s1_exec, s1 = latest_s1()
    if not s1 or not bool(s1.get("overall_pass")) or str(s1.get("next_gate", "")) != "M9_ST_S2_READY":
        add_blocker(blockers, "M9-ST-B5", "S2", {"reason": "upstream_s1_not_ready", "execution_id": s1_exec})

    m9d_exec = str(s1.get("m9d_execution_id", "")).strip() if s1 else ""
    if not m9d_exec:
        add_blocker(blockers, "M9-ST-B5", "S2", {"reason": "missing_m9d_execution_id", "upstream_s1_execution": s1_exec})

    s0_exec = str(s1.get("upstream_m9_s0_execution", "")).strip() if s1 else ""
    s0 = loadj(OUT_ROOT / s0_exec / "stress" / "m9_execution_summary.json") if s0_exec else {}
    if not s0_exec:
        add_blocker(blockers, "M9-ST-B6", "S2", {"reason": "missing_upstream_m9_s0_execution_in_s1_summary", "upstream_s1_execution": s1_exec})
    elif not s0:
        add_blocker(blockers, "M9-ST-B6", "S2", {"reason": "upstream_s0_summary_missing", "upstream_s0_execution": s0_exec})
    elif not bool(s0.get("overall_pass")) or str(s0.get("next_gate", "")) != "M9_ST_S1_READY":
        add_blocker(
            blockers,
            "M9-ST-B6",
            "S2",
            {
                "reason": "upstream_s0_not_ready_for_m9f",
                "upstream_s0_execution": s0_exec,
                "summary": {
                    "overall_pass": s0.get("overall_pass"),
                    "next_gate": s0.get("next_gate"),
                    "open_blocker_count": s0.get("open_blocker_count"),
                },
            },
        )
    m9b_exec = str(s0.get("m9b_execution_id", "")).strip() if s0 else ""
    if not m9b_exec:
        add_blocker(blockers, "M9-ST-B6", "S2", {"reason": "missing_m9b_execution_id", "upstream_s0_execution": s0_exec})

    m9e_exec = ""
    m9f_exec = ""
    m9e_summary: dict[str, Any] = {}
    m9f_summary: dict[str, Any] = {}
    m9e_report: dict[str, Any] = {}
    m9f_snapshot: dict[str, Any] = {}

    if not blockers:
        m9e_exec = f"m9e_stress_s2_{tok()}"
        m9e_dir = out / "_m9e"
        env_m9e = dict(os.environ)
        env_m9e.update(
            {
                "M9E_EXECUTION_ID": m9e_exec,
                "M9E_RUN_DIR": m9e_dir.as_posix(),
                "EVIDENCE_BUCKET": bucket,
                "UPSTREAM_M9D_EXECUTION": m9d_exec,
                "AWS_REGION": "eu-west-2",
            }
        )
        rc, _, err = run(["python", "scripts/dev_substrate/m9e_leakage_guardrail.py"], timeout=3000, env=env_m9e)
        if rc != 0:
            add_blocker(blockers, "M9-ST-B5", "S2", {"reason": "m9e_command_failed", "stderr": err.strip()[:300], "rc": rc})
        m9e_summary = loadj(m9e_dir / "m9e_execution_summary.json")
        m9e_report = loadj(m9e_dir / "m9e_leakage_guardrail_report.json")
        if not m9e_summary:
            add_blocker(blockers, "M9-ST-B5", "S2", {"reason": "m9e_summary_missing"})
        elif not (bool(m9e_summary.get("overall_pass")) and str(m9e_summary.get("next_gate", "")) == "M9.F_READY"):
            add_blocker(blockers, "M9-ST-B5", "S2", {"reason": "m9e_not_ready", "summary": m9e_summary})

    if not blockers:
        m9f_exec = f"m9f_stress_s2_{tok()}"
        m9f_dir = out / "_m9f"
        env_m9f = dict(os.environ)
        env_m9f.update(
            {
                "M9F_EXECUTION_ID": m9f_exec,
                "M9F_RUN_DIR": m9f_dir.as_posix(),
                "EVIDENCE_BUCKET": bucket,
                "UPSTREAM_M9E_EXECUTION": m9e_exec,
                "UPSTREAM_M9B_EXECUTION": m9b_exec,
                "AWS_REGION": "eu-west-2",
            }
        )
        rc, _, err = run(["python", "scripts/dev_substrate/m9f_runtime_learning_surface_separation.py"], timeout=3000, env=env_m9f)
        if rc != 0:
            add_blocker(blockers, "M9-ST-B6", "S2", {"reason": "m9f_command_failed", "stderr": err.strip()[:300], "rc": rc})
        m9f_summary = loadj(m9f_dir / "m9f_execution_summary.json")
        m9f_snapshot = loadj(m9f_dir / "m9f_surface_separation_snapshot.json")
        if not m9f_summary:
            add_blocker(blockers, "M9-ST-B6", "S2", {"reason": "m9f_summary_missing"})
        elif not (bool(m9f_summary.get("overall_pass")) and str(m9f_summary.get("next_gate", "")) == "M9.G_READY"):
            add_blocker(blockers, "M9-ST-B6", "S2", {"reason": "m9f_not_ready", "summary": m9f_summary})

    if m9e_report:
        dumpj(out / "m9e_leakage_guardrail_report.json", m9e_report)
    if m9f_snapshot:
        dumpj(out / "m9f_surface_separation_snapshot.json", m9f_snapshot)

    runtime_locality_ok = bool(packet.get("M9_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY", True))
    dumpj(
        out / "m9_runtime_locality_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M9-ST-S2",
            "overall_pass": runtime_locality_ok,
            "require_remote_runtime_only": bool(packet.get("M9_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY", True)),
            "runtime_execution_attempted": False,
            "runtime_execution_mode": "none_in_s2_validations",
        },
    )
    if not runtime_locality_ok:
        add_blocker(blockers, "M9-ST-B15", "S2", {"reason": "runtime_locality_policy_not_true"})

    refs = [
        f"evidence/dev_full/run_control/{m9d_exec}/m9d_execution_summary.json" if m9d_exec else "",
        f"evidence/dev_full/run_control/{m9e_exec}/m9e_execution_summary.json" if m9e_exec else "",
        f"evidence/dev_full/run_control/{m9f_exec}/m9f_execution_summary.json" if m9f_exec else "",
    ]
    source_guard_ok = len([b for b in blockers if b.get("id") in {"M9-ST-B11", "M9-ST-B15"}]) == 0
    dumpj(
        out / "m9_source_authority_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M9-ST-S2",
            "overall_pass": source_guard_ok,
            "authoritative_refs": refs,
            "evidence_bucket": bucket,
        },
    )

    realism_ok = bool(packet.get("M9_STRESS_DISALLOW_WAIVED_REALISM", True))
    if not realism_ok:
        add_blocker(blockers, "M9-ST-B16", "S2", {"reason": "non_toy_realism_guard_not_satisfied"})
    dumpj(
        out / "m9_realism_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M9-ST-S2",
            "overall_pass": realism_ok,
            "disallow_waived_realism": bool(packet.get("M9_STRESS_DISALLOW_WAIVED_REALISM", True)),
        },
    )

    if not bool(packet.get("M9_STRESS_REQUIRE_DATA_ENGINE_BLACKBOX", True)):
        add_blocker(blockers, "M9-ST-B15", "S2", {"reason": "data_engine_blackbox_guard_not_true"})

    return finish(
        "S2",
        phase_execution_id,
        out,
        blockers,
        S2_ARTS,
        {
            "platform_run_id": str(s1.get("platform_run_id", "")) if s1 else "",
            "scenario_run_id": str(s1.get("scenario_run_id", "")) if s1 else "",
            "upstream_m9_s1_execution": s1_exec,
            "m9e_execution_id": m9e_exec,
            "m9f_execution_id": m9f_exec,
            "decisions": [
                "S2 executed M9.E leakage guardrail closure then M9.F runtime-learning surface separation closure.",
                "S2 enforced strict S1->S0 continuity to resolve required upstream references for M9.F without bypassing source authority.",
            ],
            "advisories": advisories,
        },
    )


def run_s3(phase_execution_id: str, upstream_m9_s2_execution: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)
    blockers: list[dict[str, Any]] = []
    advisories: list[str] = []

    plan_text = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    packet = parse_plan_packet(plan_text)
    reg = parse_registry(REG) if REG.exists() else {}

    for handle in ["S3_EVIDENCE_BUCKET"]:
        value = reg.get(handle)
        if value is None or is_placeholder(value):
            add_blocker(blockers, "M9-ST-B7", "S3", {"reason": "required_handle_missing_or_placeholder", "handle": handle})

    bucket = str(reg.get("S3_EVIDENCE_BUCKET", "")).strip()
    s2_exec = upstream_m9_s2_execution.strip()
    s2 = loadj(OUT_ROOT / s2_exec / "stress" / "m9_execution_summary.json") if s2_exec else {}
    if not s2:
        s2_exec, s2 = latest_s2()
    if not s2 or not bool(s2.get("overall_pass")) or str(s2.get("next_gate", "")) != "M9_ST_S3_READY":
        add_blocker(blockers, "M9-ST-B7", "S3", {"reason": "upstream_s2_not_ready", "execution_id": s2_exec})

    m9e_exec = str(s2.get("m9e_execution_id", "")).strip() if s2 else ""
    m9f_exec = str(s2.get("m9f_execution_id", "")).strip() if s2 else ""
    if not m9e_exec:
        add_blocker(blockers, "M9-ST-B7", "S3", {"reason": "missing_m9e_execution_id", "upstream_s2_execution": s2_exec})
    if not m9f_exec:
        add_blocker(blockers, "M9-ST-B7", "S3", {"reason": "missing_m9f_execution_id", "upstream_s2_execution": s2_exec})

    s1_exec = str(s2.get("upstream_m9_s1_execution", "")).strip() if s2 else ""
    s1 = loadj(OUT_ROOT / s1_exec / "stress" / "m9_execution_summary.json") if s1_exec else {}
    if not s1_exec:
        add_blocker(blockers, "M9-ST-B7", "S3", {"reason": "missing_upstream_m9_s1_execution_in_s2_summary", "upstream_s2_execution": s2_exec})
    elif not s1:
        add_blocker(blockers, "M9-ST-B7", "S3", {"reason": "upstream_s1_summary_missing", "upstream_s1_execution": s1_exec})
    elif not bool(s1.get("overall_pass")) or str(s1.get("next_gate", "")) != "M9_ST_S2_READY":
        add_blocker(
            blockers,
            "M9-ST-B7",
            "S3",
            {
                "reason": "upstream_s1_not_ready_for_m9g",
                "upstream_s1_execution": s1_exec,
                "summary": {
                    "overall_pass": s1.get("overall_pass"),
                    "next_gate": s1.get("next_gate"),
                    "open_blocker_count": s1.get("open_blocker_count"),
                },
            },
        )

    m9c_exec = str(s1.get("m9c_execution_id", "")).strip() if s1 else ""
    m9d_exec = str(s1.get("m9d_execution_id", "")).strip() if s1 else ""
    if not m9c_exec:
        add_blocker(blockers, "M9-ST-B7", "S3", {"reason": "missing_m9c_execution_id", "upstream_s1_execution": s1_exec})
    if not m9d_exec:
        add_blocker(blockers, "M9-ST-B7", "S3", {"reason": "missing_m9d_execution_id", "upstream_s1_execution": s1_exec})

    s0_exec = str(s1.get("upstream_m9_s0_execution", "")).strip() if s1 else ""
    s0 = loadj(OUT_ROOT / s0_exec / "stress" / "m9_execution_summary.json") if s0_exec else {}
    if not s0_exec:
        add_blocker(blockers, "M9-ST-B8", "S3", {"reason": "missing_upstream_m9_s0_execution_in_s1_summary", "upstream_s1_execution": s1_exec})
    elif not s0:
        add_blocker(blockers, "M9-ST-B8", "S3", {"reason": "upstream_s0_summary_missing", "upstream_s0_execution": s0_exec})
    elif not bool(s0.get("overall_pass")) or str(s0.get("next_gate", "")) != "M9_ST_S1_READY":
        add_blocker(
            blockers,
            "M9-ST-B8",
            "S3",
            {
                "reason": "upstream_s0_not_ready_for_m9h",
                "upstream_s0_execution": s0_exec,
                "summary": {
                    "overall_pass": s0.get("overall_pass"),
                    "next_gate": s0.get("next_gate"),
                    "open_blocker_count": s0.get("open_blocker_count"),
                },
            },
        )

    m9a_exec = str(s0.get("m9a_execution_id", "")).strip() if s0 else ""
    m9b_exec = str(s0.get("m9b_execution_id", "")).strip() if s0 else ""
    if not m9a_exec:
        add_blocker(blockers, "M9-ST-B8", "S3", {"reason": "missing_m9a_execution_id", "upstream_s0_execution": s0_exec})
    if not m9b_exec:
        add_blocker(blockers, "M9-ST-B8", "S3", {"reason": "missing_m9b_execution_id", "upstream_s0_execution": s0_exec})

    m9g_exec = ""
    m9h_exec = ""
    m9g_summary: dict[str, Any] = {}
    m9h_summary: dict[str, Any] = {}
    m9g_snapshot: dict[str, Any] = {}
    m9h_rollup: dict[str, Any] = {}
    m9h_verdict_payload: dict[str, Any] = {}
    m10_handoff: dict[str, Any] = {}

    if not blockers:
        m9g_exec = f"m9g_stress_s3_{tok()}"
        m9g_dir = out / "_m9g"
        env_m9g = dict(os.environ)
        env_m9g.update(
            {
                "M9G_EXECUTION_ID": m9g_exec,
                "M9G_RUN_DIR": m9g_dir.as_posix(),
                "EVIDENCE_BUCKET": bucket,
                "UPSTREAM_M9C_EXECUTION": m9c_exec,
                "UPSTREAM_M9D_EXECUTION": m9d_exec,
                "UPSTREAM_M9E_EXECUTION": m9e_exec,
                "UPSTREAM_M9F_EXECUTION": m9f_exec,
                "AWS_REGION": "eu-west-2",
            }
        )
        rc, _, err = run(["python", "scripts/dev_substrate/m9g_learning_input_readiness.py"], timeout=3000, env=env_m9g)
        if rc != 0:
            add_blocker(blockers, "M9-ST-B7", "S3", {"reason": "m9g_command_failed", "stderr": err.strip()[:300], "rc": rc})
        m9g_summary = loadj(m9g_dir / "m9g_execution_summary.json")
        m9g_snapshot = loadj(m9g_dir / "m9g_learning_input_readiness_snapshot.json")
        if not m9g_summary:
            add_blocker(blockers, "M9-ST-B7", "S3", {"reason": "m9g_summary_missing"})
        elif not (bool(m9g_summary.get("overall_pass")) and str(m9g_summary.get("next_gate", "")) == "M9.H_READY"):
            add_blocker(blockers, "M9-ST-B7", "S3", {"reason": "m9g_not_ready", "summary": m9g_summary})

    if not blockers:
        m9h_exec = f"m9h_stress_s3_{tok()}"
        m9h_dir = out / "_m9h"
        env_m9h = dict(os.environ)
        env_m9h.update(
            {
                "M9H_EXECUTION_ID": m9h_exec,
                "M9H_RUN_DIR": m9h_dir.as_posix(),
                "EVIDENCE_BUCKET": bucket,
                "UPSTREAM_M9A_EXECUTION": m9a_exec,
                "UPSTREAM_M9B_EXECUTION": m9b_exec,
                "UPSTREAM_M9C_EXECUTION": m9c_exec,
                "UPSTREAM_M9D_EXECUTION": m9d_exec,
                "UPSTREAM_M9E_EXECUTION": m9e_exec,
                "UPSTREAM_M9F_EXECUTION": m9f_exec,
                "UPSTREAM_M9G_EXECUTION": m9g_exec,
                "AWS_REGION": "eu-west-2",
            }
        )
        rc, _, err = run(["python", "scripts/dev_substrate/m9h_p12_rollup_handoff.py"], timeout=3000, env=env_m9h)
        if rc != 0:
            add_blocker(blockers, "M9-ST-B8", "S3", {"reason": "m9h_command_failed", "stderr": err.strip()[:300], "rc": rc})
        m9h_summary = loadj(m9h_dir / "m9h_execution_summary.json")
        m9h_rollup = loadj(m9h_dir / "m9h_p12_rollup_matrix.json")
        m9h_verdict_payload = loadj(m9h_dir / "m9h_p12_gate_verdict.json")
        m10_handoff = loadj(m9h_dir / "m10_handoff_pack.json")
        if not m9h_summary:
            add_blocker(blockers, "M9-ST-B8", "S3", {"reason": "m9h_summary_missing"})
        else:
            verdict = str(m9h_summary.get("verdict", ""))
            next_gate = str(m9h_summary.get("next_gate", ""))
            pass_posture = bool(m9h_summary.get("overall_pass")) and verdict == "ADVANCE_TO_P13" and next_gate == "M10_READY"
            if not pass_posture:
                rollup_blockers = m9h_rollup.get("blockers", []) if isinstance(m9h_rollup.get("blockers", []), list) else []
                blocker_codes = sorted(
                    {
                        str(b.get("code", "")).strip()
                        for b in rollup_blockers
                        if isinstance(b, dict) and str(b.get("code", "")).strip()
                    }
                )
                if "M9-B9" in blocker_codes:
                    add_blocker(
                        blockers,
                        "M9-ST-B9",
                        "S3",
                        {"reason": "m9h_handoff_contract_failure", "summary": m9h_summary, "blocker_codes": blocker_codes},
                    )
                if "M9-B11" in blocker_codes:
                    add_blocker(
                        blockers,
                        "M9-ST-B11",
                        "S3",
                        {"reason": "m9h_artifact_publication_failure", "summary": m9h_summary, "blocker_codes": blocker_codes},
                    )
                if ("M9-B8" in blocker_codes) or (not blocker_codes):
                    add_blocker(
                        blockers,
                        "M9-ST-B8",
                        "S3",
                        {"reason": "m9h_rollup_verdict_not_ready", "summary": m9h_summary, "blocker_codes": blocker_codes},
                    )

    if m9g_snapshot:
        dumpj(out / "m9g_learning_input_readiness_snapshot.json", m9g_snapshot)
    if m9h_rollup:
        dumpj(out / "m9h_p12_rollup_matrix.json", m9h_rollup)
    if m9h_verdict_payload:
        dumpj(out / "m9h_p12_gate_verdict.json", m9h_verdict_payload)
    if m10_handoff:
        dumpj(out / "m10_handoff_pack.json", m10_handoff)

    runtime_locality_ok = bool(packet.get("M9_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY", True))
    dumpj(
        out / "m9_runtime_locality_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M9-ST-S3",
            "overall_pass": runtime_locality_ok,
            "require_remote_runtime_only": bool(packet.get("M9_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY", True)),
            "runtime_execution_attempted": False,
            "runtime_execution_mode": "none_in_s3_validations",
        },
    )
    if not runtime_locality_ok:
        add_blocker(blockers, "M9-ST-B15", "S3", {"reason": "runtime_locality_policy_not_true"})

    refs = [
        f"evidence/dev_full/run_control/{m9a_exec}/m9a_execution_summary.json" if m9a_exec else "",
        f"evidence/dev_full/run_control/{m9b_exec}/m9b_execution_summary.json" if m9b_exec else "",
        f"evidence/dev_full/run_control/{m9c_exec}/m9c_execution_summary.json" if m9c_exec else "",
        f"evidence/dev_full/run_control/{m9d_exec}/m9d_execution_summary.json" if m9d_exec else "",
        f"evidence/dev_full/run_control/{m9e_exec}/m9e_execution_summary.json" if m9e_exec else "",
        f"evidence/dev_full/run_control/{m9f_exec}/m9f_execution_summary.json" if m9f_exec else "",
        f"evidence/dev_full/run_control/{m9g_exec}/m9g_execution_summary.json" if m9g_exec else "",
        f"evidence/dev_full/run_control/{m9h_exec}/m9h_execution_summary.json" if m9h_exec else "",
    ]
    source_guard_ok = len([b for b in blockers if b.get("id") in {"M9-ST-B11", "M9-ST-B15"}]) == 0
    dumpj(
        out / "m9_source_authority_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M9-ST-S3",
            "overall_pass": source_guard_ok,
            "authoritative_refs": refs,
            "evidence_bucket": bucket,
        },
    )

    realism_ok = bool(packet.get("M9_STRESS_DISALLOW_WAIVED_REALISM", True))
    if not realism_ok:
        add_blocker(blockers, "M9-ST-B16", "S3", {"reason": "non_toy_realism_guard_not_satisfied"})
    dumpj(
        out / "m9_realism_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M9-ST-S3",
            "overall_pass": realism_ok,
            "disallow_waived_realism": bool(packet.get("M9_STRESS_DISALLOW_WAIVED_REALISM", True)),
        },
    )

    if not bool(packet.get("M9_STRESS_REQUIRE_DATA_ENGINE_BLACKBOX", True)):
        add_blocker(blockers, "M9-ST-B15", "S3", {"reason": "data_engine_blackbox_guard_not_true"})

    return finish(
        "S3",
        phase_execution_id,
        out,
        blockers,
        S3_ARTS,
        {
            "platform_run_id": str(s2.get("platform_run_id", "")) if s2 else "",
            "scenario_run_id": str(s2.get("scenario_run_id", "")) if s2 else "",
            "upstream_m9_s2_execution": s2_exec,
            "m9g_execution_id": m9g_exec,
            "m9h_execution_id": m9h_exec,
            "decisions": [
                "S3 executed M9.G readiness closure then M9.H deterministic P12 rollup and M10 handoff closure.",
                "S3 enforced strict S2->S1->S0 continuity to recover authoritative upstream chain A..F for rollup/handoff proof.",
            ],
            "advisories": advisories,
        },
    )


def run_s4(phase_execution_id: str, upstream_m9_s3_execution: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)
    blockers: list[dict[str, Any]] = []
    advisories: list[str] = []

    plan_text = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    packet = parse_plan_packet(plan_text)
    reg = parse_registry(REG) if REG.exists() else {}

    for handle in ["S3_EVIDENCE_BUCKET"]:
        value = reg.get(handle)
        if value is None or is_placeholder(value):
            add_blocker(blockers, "M9-ST-B10", "S4", {"reason": "required_handle_missing_or_placeholder", "handle": handle})

    bucket = str(reg.get("S3_EVIDENCE_BUCKET", "")).strip()
    s3_exec = upstream_m9_s3_execution.strip()
    s3 = loadj(OUT_ROOT / s3_exec / "stress" / "m9_execution_summary.json") if s3_exec else {}
    if not s3:
        s3_exec, s3 = latest_s3()
    if not s3 or not bool(s3.get("overall_pass")) or str(s3.get("next_gate", "")) != "M9_ST_S4_READY":
        add_blocker(blockers, "M9-ST-B10", "S4", {"reason": "upstream_s3_not_ready", "execution_id": s3_exec})

    m9g_exec = str(s3.get("m9g_execution_id", "")).strip() if s3 else ""
    m9h_exec = str(s3.get("m9h_execution_id", "")).strip() if s3 else ""
    if not m9g_exec:
        add_blocker(blockers, "M9-ST-B10", "S4", {"reason": "missing_m9g_execution_id", "upstream_s3_execution": s3_exec})
    if not m9h_exec:
        add_blocker(blockers, "M9-ST-B10", "S4", {"reason": "missing_m9h_execution_id", "upstream_s3_execution": s3_exec})

    s2_exec = str(s3.get("upstream_m9_s2_execution", "")).strip() if s3 else ""
    s2 = loadj(OUT_ROOT / s2_exec / "stress" / "m9_execution_summary.json") if s2_exec else {}
    if not s2_exec:
        add_blocker(blockers, "M9-ST-B10", "S4", {"reason": "missing_upstream_m9_s2_execution_in_s3_summary", "upstream_s3_execution": s3_exec})
    elif not s2:
        add_blocker(blockers, "M9-ST-B10", "S4", {"reason": "upstream_s2_summary_missing", "upstream_s2_execution": s2_exec})
    elif not bool(s2.get("overall_pass")) or str(s2.get("next_gate", "")) != "M9_ST_S3_READY":
        add_blocker(
            blockers,
            "M9-ST-B10",
            "S4",
            {
                "reason": "upstream_s2_not_ready_for_m9i",
                "upstream_s2_execution": s2_exec,
                "summary": {
                    "overall_pass": s2.get("overall_pass"),
                    "next_gate": s2.get("next_gate"),
                    "open_blocker_count": s2.get("open_blocker_count"),
                },
            },
        )

    m9e_exec = str(s2.get("m9e_execution_id", "")).strip() if s2 else ""
    m9f_exec = str(s2.get("m9f_execution_id", "")).strip() if s2 else ""
    if not m9e_exec:
        add_blocker(blockers, "M9-ST-B10", "S4", {"reason": "missing_m9e_execution_id", "upstream_s2_execution": s2_exec})
    if not m9f_exec:
        add_blocker(blockers, "M9-ST-B10", "S4", {"reason": "missing_m9f_execution_id", "upstream_s2_execution": s2_exec})

    s1_exec = str(s2.get("upstream_m9_s1_execution", "")).strip() if s2 else ""
    s1 = loadj(OUT_ROOT / s1_exec / "stress" / "m9_execution_summary.json") if s1_exec else {}
    if not s1_exec:
        add_blocker(blockers, "M9-ST-B10", "S4", {"reason": "missing_upstream_m9_s1_execution_in_s2_summary", "upstream_s2_execution": s2_exec})
    elif not s1:
        add_blocker(blockers, "M9-ST-B10", "S4", {"reason": "upstream_s1_summary_missing", "upstream_s1_execution": s1_exec})
    elif not bool(s1.get("overall_pass")) or str(s1.get("next_gate", "")) != "M9_ST_S2_READY":
        add_blocker(
            blockers,
            "M9-ST-B10",
            "S4",
            {
                "reason": "upstream_s1_not_ready_for_m9i",
                "upstream_s1_execution": s1_exec,
                "summary": {
                    "overall_pass": s1.get("overall_pass"),
                    "next_gate": s1.get("next_gate"),
                    "open_blocker_count": s1.get("open_blocker_count"),
                },
            },
        )

    m9c_exec = str(s1.get("m9c_execution_id", "")).strip() if s1 else ""
    m9d_exec = str(s1.get("m9d_execution_id", "")).strip() if s1 else ""
    if not m9c_exec:
        add_blocker(blockers, "M9-ST-B10", "S4", {"reason": "missing_m9c_execution_id", "upstream_s1_execution": s1_exec})
    if not m9d_exec:
        add_blocker(blockers, "M9-ST-B10", "S4", {"reason": "missing_m9d_execution_id", "upstream_s1_execution": s1_exec})

    s0_exec = str(s1.get("upstream_m9_s0_execution", "")).strip() if s1 else ""
    s0 = loadj(OUT_ROOT / s0_exec / "stress" / "m9_execution_summary.json") if s0_exec else {}
    if not s0_exec:
        add_blocker(blockers, "M9-ST-B10", "S4", {"reason": "missing_upstream_m9_s0_execution_in_s1_summary", "upstream_s1_execution": s1_exec})
    elif not s0:
        add_blocker(blockers, "M9-ST-B10", "S4", {"reason": "upstream_s0_summary_missing", "upstream_s0_execution": s0_exec})
    elif not bool(s0.get("overall_pass")) or str(s0.get("next_gate", "")) != "M9_ST_S1_READY":
        add_blocker(
            blockers,
            "M9-ST-B10",
            "S4",
            {
                "reason": "upstream_s0_not_ready_for_m9i",
                "upstream_s0_execution": s0_exec,
                "summary": {
                    "overall_pass": s0.get("overall_pass"),
                    "next_gate": s0.get("next_gate"),
                    "open_blocker_count": s0.get("open_blocker_count"),
                },
            },
        )

    m9a_exec = str(s0.get("m9a_execution_id", "")).strip() if s0 else ""
    m9b_exec = str(s0.get("m9b_execution_id", "")).strip() if s0 else ""
    if not m9a_exec:
        add_blocker(blockers, "M9-ST-B10", "S4", {"reason": "missing_m9a_execution_id", "upstream_s0_execution": s0_exec})
    if not m9b_exec:
        add_blocker(blockers, "M9-ST-B10", "S4", {"reason": "missing_m9b_execution_id", "upstream_s0_execution": s0_exec})

    m9i_exec = ""
    m9i_summary: dict[str, Any] = {}
    m9i_blockers: dict[str, Any] = {}
    m9i_budget: dict[str, Any] = {}
    m9i_cost_receipt: dict[str, Any] = {}

    if not blockers:
        m9i_exec = f"m9i_stress_s4_{tok()}"
        m9i_dir = out / "_m9i"
        env_m9i = dict(os.environ)
        env_m9i.update(
            {
                "M9I_EXECUTION_ID": m9i_exec,
                "M9I_RUN_DIR": m9i_dir.as_posix(),
                "EVIDENCE_BUCKET": bucket,
                "UPSTREAM_M9A_EXECUTION": m9a_exec,
                "UPSTREAM_M9B_EXECUTION": m9b_exec,
                "UPSTREAM_M9C_EXECUTION": m9c_exec,
                "UPSTREAM_M9D_EXECUTION": m9d_exec,
                "UPSTREAM_M9E_EXECUTION": m9e_exec,
                "UPSTREAM_M9F_EXECUTION": m9f_exec,
                "UPSTREAM_M9G_EXECUTION": m9g_exec,
                "UPSTREAM_M9H_EXECUTION": m9h_exec,
                "AWS_REGION": "eu-west-2",
                "BILLING_REGION": "us-east-1",
            }
        )
        rc, _, err = run(["python", "scripts/dev_substrate/m9i_phase_cost_closure.py"], timeout=3600, env=env_m9i)
        if rc != 0:
            add_blocker(blockers, "M9-ST-B10", "S4", {"reason": "m9i_command_failed", "stderr": err.strip()[:300], "rc": rc})
        m9i_summary = loadj(m9i_dir / "m9i_execution_summary.json")
        m9i_blockers = loadj(m9i_dir / "m9i_blocker_register.json")
        m9i_budget = loadj(m9i_dir / "m9_phase_budget_envelope.json")
        m9i_cost_receipt = loadj(m9i_dir / "m9_phase_cost_outcome_receipt.json")
        if not m9i_summary:
            add_blocker(blockers, "M9-ST-B10", "S4", {"reason": "m9i_summary_missing"})
        else:
            verdict = str(m9i_summary.get("verdict", ""))
            next_gate = str(m9i_summary.get("next_gate", ""))
            pass_posture = bool(m9i_summary.get("overall_pass")) and verdict == "ADVANCE_TO_M9J" and next_gate == "M9.J_READY"
            if not pass_posture:
                row_blockers = m9i_blockers.get("blockers", []) if isinstance(m9i_blockers.get("blockers", []), list) else []
                blocker_codes = sorted(
                    {
                        str(b.get("code", "")).strip()
                        for b in row_blockers
                        if isinstance(b, dict) and str(b.get("code", "")).strip()
                    }
                )
                if "M9-B11" in blocker_codes:
                    add_blocker(
                        blockers,
                        "M9-ST-B11",
                        "S4",
                        {"reason": "m9i_artifact_publication_failure", "summary": m9i_summary, "blocker_codes": blocker_codes},
                    )
                if ("M9-B10" in blocker_codes) or (not blocker_codes):
                    add_blocker(
                        blockers,
                        "M9-ST-B10",
                        "S4",
                        {"reason": "m9i_cost_outcome_not_ready", "summary": m9i_summary, "blocker_codes": blocker_codes},
                    )

    if m9i_budget:
        dumpj(out / "m9_phase_budget_envelope.json", m9i_budget)
    if m9i_cost_receipt:
        dumpj(out / "m9_phase_cost_outcome_receipt.json", m9i_cost_receipt)
    if m9i_summary:
        dumpj(out / "m9i_execution_summary.json", m9i_summary)

    runtime_locality_ok = bool(packet.get("M9_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY", True))
    dumpj(
        out / "m9_runtime_locality_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M9-ST-S4",
            "overall_pass": runtime_locality_ok,
            "require_remote_runtime_only": bool(packet.get("M9_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY", True)),
            "runtime_execution_attempted": False,
            "runtime_execution_mode": "none_in_s4_validations",
        },
    )
    if not runtime_locality_ok:
        add_blocker(blockers, "M9-ST-B15", "S4", {"reason": "runtime_locality_policy_not_true"})

    refs = [
        f"evidence/dev_full/run_control/{m9a_exec}/m9a_execution_summary.json" if m9a_exec else "",
        f"evidence/dev_full/run_control/{m9b_exec}/m9b_execution_summary.json" if m9b_exec else "",
        f"evidence/dev_full/run_control/{m9c_exec}/m9c_execution_summary.json" if m9c_exec else "",
        f"evidence/dev_full/run_control/{m9d_exec}/m9d_execution_summary.json" if m9d_exec else "",
        f"evidence/dev_full/run_control/{m9e_exec}/m9e_execution_summary.json" if m9e_exec else "",
        f"evidence/dev_full/run_control/{m9f_exec}/m9f_execution_summary.json" if m9f_exec else "",
        f"evidence/dev_full/run_control/{m9g_exec}/m9g_execution_summary.json" if m9g_exec else "",
        f"evidence/dev_full/run_control/{m9h_exec}/m9h_execution_summary.json" if m9h_exec else "",
        f"evidence/dev_full/run_control/{m9i_exec}/m9i_execution_summary.json" if m9i_exec else "",
    ]
    source_guard_ok = len([b for b in blockers if b.get("id") in {"M9-ST-B11", "M9-ST-B15"}]) == 0
    dumpj(
        out / "m9_source_authority_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M9-ST-S4",
            "overall_pass": source_guard_ok,
            "authoritative_refs": refs,
            "evidence_bucket": bucket,
        },
    )

    realism_ok = bool(packet.get("M9_STRESS_DISALLOW_WAIVED_REALISM", True))
    if not realism_ok:
        add_blocker(blockers, "M9-ST-B16", "S4", {"reason": "non_toy_realism_guard_not_satisfied"})
    dumpj(
        out / "m9_realism_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M9-ST-S4",
            "overall_pass": realism_ok,
            "disallow_waived_realism": bool(packet.get("M9_STRESS_DISALLOW_WAIVED_REALISM", True)),
        },
    )

    if not bool(packet.get("M9_STRESS_REQUIRE_DATA_ENGINE_BLACKBOX", True)):
        add_blocker(blockers, "M9-ST-B15", "S4", {"reason": "data_engine_blackbox_guard_not_true"})

    return finish(
        "S4",
        phase_execution_id,
        out,
        blockers,
        S4_ARTS,
        {
            "platform_run_id": str(s3.get("platform_run_id", "")) if s3 else "",
            "scenario_run_id": str(s3.get("scenario_run_id", "")) if s3 else "",
            "upstream_m9_s3_execution": s3_exec,
            "m9i_execution_id": m9i_exec,
            "decisions": [
                "S4 executed M9.I phase budget and cost-outcome closure after strict continuity recovery of upstream chain A..H.",
                "S4 retained locality/source/realism guards while enforcing fail-closed cost posture and artifact parity.",
            ],
            "advisories": advisories,
        },
    )


def run_s5(phase_execution_id: str, upstream_m9_s4_execution: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)
    blockers: list[dict[str, Any]] = []
    advisories: list[str] = []

    plan_text = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    packet = parse_plan_packet(plan_text)
    reg = parse_registry(REG) if REG.exists() else {}

    for handle in ["S3_EVIDENCE_BUCKET"]:
        value = reg.get(handle)
        if value is None or is_placeholder(value):
            add_blocker(blockers, "M9-ST-B10", "S5", {"reason": "required_handle_missing_or_placeholder", "handle": handle})

    bucket = str(reg.get("S3_EVIDENCE_BUCKET", "")).strip()
    s4_exec = upstream_m9_s4_execution.strip()
    s4 = loadj(OUT_ROOT / s4_exec / "stress" / "m9_execution_summary.json") if s4_exec else {}
    if not s4:
        s4_exec, s4 = latest_s4()
    if not s4 or not bool(s4.get("overall_pass")) or str(s4.get("next_gate", "")) != "M9_ST_S5_READY":
        add_blocker(blockers, "M9-ST-B10", "S5", {"reason": "upstream_s4_not_ready", "execution_id": s4_exec})

    m9i_exec = str(s4.get("m9i_execution_id", "")).strip() if s4 else ""
    if not m9i_exec:
        add_blocker(blockers, "M9-ST-B10", "S5", {"reason": "missing_m9i_execution_id", "upstream_s4_execution": s4_exec})

    s3_exec = str(s4.get("upstream_m9_s3_execution", "")).strip() if s4 else ""
    s3 = loadj(OUT_ROOT / s3_exec / "stress" / "m9_execution_summary.json") if s3_exec else {}
    if not s3_exec:
        add_blocker(blockers, "M9-ST-B10", "S5", {"reason": "missing_upstream_m9_s3_execution_in_s4_summary", "upstream_s4_execution": s4_exec})
    elif not s3:
        add_blocker(blockers, "M9-ST-B10", "S5", {"reason": "upstream_s3_summary_missing", "upstream_s3_execution": s3_exec})
    elif not bool(s3.get("overall_pass")) or str(s3.get("next_gate", "")) != "M9_ST_S4_READY":
        add_blocker(
            blockers,
            "M9-ST-B10",
            "S5",
            {
                "reason": "upstream_s3_not_ready_for_m9j",
                "upstream_s3_execution": s3_exec,
                "summary": {
                    "overall_pass": s3.get("overall_pass"),
                    "next_gate": s3.get("next_gate"),
                    "open_blocker_count": s3.get("open_blocker_count"),
                },
            },
        )

    m9g_exec = str(s3.get("m9g_execution_id", "")).strip() if s3 else ""
    m9h_exec = str(s3.get("m9h_execution_id", "")).strip() if s3 else ""
    if not m9g_exec:
        add_blocker(blockers, "M9-ST-B10", "S5", {"reason": "missing_m9g_execution_id", "upstream_s3_execution": s3_exec})
    if not m9h_exec:
        add_blocker(blockers, "M9-ST-B10", "S5", {"reason": "missing_m9h_execution_id", "upstream_s3_execution": s3_exec})

    s2_exec = str(s3.get("upstream_m9_s2_execution", "")).strip() if s3 else ""
    s2 = loadj(OUT_ROOT / s2_exec / "stress" / "m9_execution_summary.json") if s2_exec else {}
    if not s2_exec:
        add_blocker(blockers, "M9-ST-B10", "S5", {"reason": "missing_upstream_m9_s2_execution_in_s3_summary", "upstream_s3_execution": s3_exec})
    elif not s2:
        add_blocker(blockers, "M9-ST-B10", "S5", {"reason": "upstream_s2_summary_missing", "upstream_s2_execution": s2_exec})
    elif not bool(s2.get("overall_pass")) or str(s2.get("next_gate", "")) != "M9_ST_S3_READY":
        add_blocker(
            blockers,
            "M9-ST-B10",
            "S5",
            {
                "reason": "upstream_s2_not_ready_for_m9j",
                "upstream_s2_execution": s2_exec,
                "summary": {
                    "overall_pass": s2.get("overall_pass"),
                    "next_gate": s2.get("next_gate"),
                    "open_blocker_count": s2.get("open_blocker_count"),
                },
            },
        )

    m9e_exec = str(s2.get("m9e_execution_id", "")).strip() if s2 else ""
    m9f_exec = str(s2.get("m9f_execution_id", "")).strip() if s2 else ""
    if not m9e_exec:
        add_blocker(blockers, "M9-ST-B10", "S5", {"reason": "missing_m9e_execution_id", "upstream_s2_execution": s2_exec})
    if not m9f_exec:
        add_blocker(blockers, "M9-ST-B10", "S5", {"reason": "missing_m9f_execution_id", "upstream_s2_execution": s2_exec})

    s1_exec = str(s2.get("upstream_m9_s1_execution", "")).strip() if s2 else ""
    s1 = loadj(OUT_ROOT / s1_exec / "stress" / "m9_execution_summary.json") if s1_exec else {}
    if not s1_exec:
        add_blocker(blockers, "M9-ST-B10", "S5", {"reason": "missing_upstream_m9_s1_execution_in_s2_summary", "upstream_s2_execution": s2_exec})
    elif not s1:
        add_blocker(blockers, "M9-ST-B10", "S5", {"reason": "upstream_s1_summary_missing", "upstream_s1_execution": s1_exec})
    elif not bool(s1.get("overall_pass")) or str(s1.get("next_gate", "")) != "M9_ST_S2_READY":
        add_blocker(
            blockers,
            "M9-ST-B10",
            "S5",
            {
                "reason": "upstream_s1_not_ready_for_m9j",
                "upstream_s1_execution": s1_exec,
                "summary": {
                    "overall_pass": s1.get("overall_pass"),
                    "next_gate": s1.get("next_gate"),
                    "open_blocker_count": s1.get("open_blocker_count"),
                },
            },
        )

    m9c_exec = str(s1.get("m9c_execution_id", "")).strip() if s1 else ""
    m9d_exec = str(s1.get("m9d_execution_id", "")).strip() if s1 else ""
    if not m9c_exec:
        add_blocker(blockers, "M9-ST-B10", "S5", {"reason": "missing_m9c_execution_id", "upstream_s1_execution": s1_exec})
    if not m9d_exec:
        add_blocker(blockers, "M9-ST-B10", "S5", {"reason": "missing_m9d_execution_id", "upstream_s1_execution": s1_exec})

    s0_exec = str(s1.get("upstream_m9_s0_execution", "")).strip() if s1 else ""
    s0 = loadj(OUT_ROOT / s0_exec / "stress" / "m9_execution_summary.json") if s0_exec else {}
    if not s0_exec:
        add_blocker(blockers, "M9-ST-B10", "S5", {"reason": "missing_upstream_m9_s0_execution_in_s1_summary", "upstream_s1_execution": s1_exec})
    elif not s0:
        add_blocker(blockers, "M9-ST-B10", "S5", {"reason": "upstream_s0_summary_missing", "upstream_s0_execution": s0_exec})
    elif not bool(s0.get("overall_pass")) or str(s0.get("next_gate", "")) != "M9_ST_S1_READY":
        add_blocker(
            blockers,
            "M9-ST-B10",
            "S5",
            {
                "reason": "upstream_s0_not_ready_for_m9j",
                "upstream_s0_execution": s0_exec,
                "summary": {
                    "overall_pass": s0.get("overall_pass"),
                    "next_gate": s0.get("next_gate"),
                    "open_blocker_count": s0.get("open_blocker_count"),
                },
            },
        )

    m9a_exec = str(s0.get("m9a_execution_id", "")).strip() if s0 else ""
    m9b_exec = str(s0.get("m9b_execution_id", "")).strip() if s0 else ""
    if not m9a_exec:
        add_blocker(blockers, "M9-ST-B10", "S5", {"reason": "missing_m9a_execution_id", "upstream_s0_execution": s0_exec})
    if not m9b_exec:
        add_blocker(blockers, "M9-ST-B10", "S5", {"reason": "missing_m9b_execution_id", "upstream_s0_execution": s0_exec})

    m9j_exec = ""
    m9j_summary: dict[str, Any] = {}
    m9j_blockers: dict[str, Any] = {}

    if not blockers:
        m9j_exec = f"m9j_stress_s5_{tok()}"
        m9j_dir = out / "_m9j"
        env_m9j = dict(os.environ)
        env_m9j.update(
            {
                "M9J_EXECUTION_ID": m9j_exec,
                "M9J_RUN_DIR": m9j_dir.as_posix(),
                "EVIDENCE_BUCKET": bucket,
                "UPSTREAM_M9A_EXECUTION": m9a_exec,
                "UPSTREAM_M9B_EXECUTION": m9b_exec,
                "UPSTREAM_M9C_EXECUTION": m9c_exec,
                "UPSTREAM_M9D_EXECUTION": m9d_exec,
                "UPSTREAM_M9E_EXECUTION": m9e_exec,
                "UPSTREAM_M9F_EXECUTION": m9f_exec,
                "UPSTREAM_M9G_EXECUTION": m9g_exec,
                "UPSTREAM_M9H_EXECUTION": m9h_exec,
                "UPSTREAM_M9I_EXECUTION": m9i_exec,
                "AWS_REGION": "eu-west-2",
            }
        )
        rc, _, err = run(["python", "scripts/dev_substrate/m9j_closure_sync.py"], timeout=3600, env=env_m9j)
        if rc != 0:
            add_blocker(blockers, "M9-ST-B10", "S5", {"reason": "m9j_command_failed", "stderr": err.strip()[:300], "rc": rc})
        m9j_summary = loadj(m9j_dir / "m9j_execution_summary.json")
        m9j_blockers = loadj(m9j_dir / "m9j_blocker_register.json")
        if not m9j_summary:
            add_blocker(blockers, "M9-ST-B10", "S5", {"reason": "m9j_summary_missing"})
        else:
            verdict = str(m9j_summary.get("verdict", ""))
            next_gate = str(m9j_summary.get("next_gate", ""))
            pass_posture = bool(m9j_summary.get("overall_pass")) and verdict == "ADVANCE_TO_M10" and next_gate == "M10_READY"
            if not pass_posture:
                row_blockers = m9j_blockers.get("blockers", []) if isinstance(m9j_blockers.get("blockers", []), list) else []
                blocker_codes = sorted(
                    {
                        str(b.get("code", "")).strip()
                        for b in row_blockers
                        if isinstance(b, dict) and str(b.get("code", "")).strip()
                    }
                )
                if "M9-B11" in blocker_codes:
                    add_blocker(
                        blockers,
                        "M9-ST-B11",
                        "S5",
                        {"reason": "m9j_artifact_publication_failure", "summary": m9j_summary, "blocker_codes": blocker_codes},
                    )
                if ("M9-B10" in blocker_codes) or (not blocker_codes):
                    add_blocker(
                        blockers,
                        "M9-ST-B10",
                        "S5",
                        {"reason": "m9j_closure_sync_not_ready", "summary": m9j_summary, "blocker_codes": blocker_codes},
                    )

    if m9j_summary:
        dumpj(out / "m9j_execution_summary.json", m9j_summary)
    if m9j_blockers:
        dumpj(out / "m9j_blocker_register.json", m9j_blockers)

    runtime_locality_ok = bool(packet.get("M9_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY", True))
    dumpj(
        out / "m9_runtime_locality_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M9-ST-S5",
            "overall_pass": runtime_locality_ok,
            "require_remote_runtime_only": bool(packet.get("M9_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY", True)),
            "runtime_execution_attempted": False,
            "runtime_execution_mode": "none_in_s5_validations",
        },
    )
    if not runtime_locality_ok:
        add_blocker(blockers, "M9-ST-B15", "S5", {"reason": "runtime_locality_policy_not_true"})

    refs = [
        f"evidence/dev_full/run_control/{m9a_exec}/m9a_execution_summary.json" if m9a_exec else "",
        f"evidence/dev_full/run_control/{m9b_exec}/m9b_execution_summary.json" if m9b_exec else "",
        f"evidence/dev_full/run_control/{m9c_exec}/m9c_execution_summary.json" if m9c_exec else "",
        f"evidence/dev_full/run_control/{m9d_exec}/m9d_execution_summary.json" if m9d_exec else "",
        f"evidence/dev_full/run_control/{m9e_exec}/m9e_execution_summary.json" if m9e_exec else "",
        f"evidence/dev_full/run_control/{m9f_exec}/m9f_execution_summary.json" if m9f_exec else "",
        f"evidence/dev_full/run_control/{m9g_exec}/m9g_execution_summary.json" if m9g_exec else "",
        f"evidence/dev_full/run_control/{m9h_exec}/m9h_execution_summary.json" if m9h_exec else "",
        f"evidence/dev_full/run_control/{m9i_exec}/m9i_execution_summary.json" if m9i_exec else "",
        f"evidence/dev_full/run_control/{m9j_exec}/m9j_execution_summary.json" if m9j_exec else "",
    ]
    source_guard_ok = len([b for b in blockers if b.get("id") in {"M9-ST-B11", "M9-ST-B15"}]) == 0
    dumpj(
        out / "m9_source_authority_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M9-ST-S5",
            "overall_pass": source_guard_ok,
            "authoritative_refs": refs,
            "evidence_bucket": bucket,
        },
    )

    realism_ok = bool(packet.get("M9_STRESS_DISALLOW_WAIVED_REALISM", True))
    if not realism_ok:
        add_blocker(blockers, "M9-ST-B16", "S5", {"reason": "non_toy_realism_guard_not_satisfied"})
    dumpj(
        out / "m9_realism_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M9-ST-S5",
            "overall_pass": realism_ok,
            "disallow_waived_realism": bool(packet.get("M9_STRESS_DISALLOW_WAIVED_REALISM", True)),
        },
    )

    if not bool(packet.get("M9_STRESS_REQUIRE_DATA_ENGINE_BLACKBOX", True)):
        add_blocker(blockers, "M9-ST-B15", "S5", {"reason": "data_engine_blackbox_guard_not_true"})

    return finish(
        "S5",
        phase_execution_id,
        out,
        blockers,
        S5_ARTS,
        {
            "platform_run_id": str(s4.get("platform_run_id", "")) if s4 else "",
            "scenario_run_id": str(s4.get("scenario_run_id", "")) if s4 else "",
            "upstream_m9_s4_execution": s4_exec,
            "m9j_execution_id": m9j_exec,
            "decisions": [
                "S5 executed M9.J closure sync against strict upstream chain A..I and enforced deterministic final closure gates.",
                "S5 emitted final M9 stage decision with fail-closed posture on closure parity, locality, and realism.",
            ],
            "advisories": advisories,
        },
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="M9 stress runner")
    ap.add_argument("--stage", required=True, choices=["S0", "S1", "S2", "S3", "S4", "S5"])
    ap.add_argument("--phase-execution-id", default="")
    ap.add_argument("--upstream-m8-execution", default="")
    ap.add_argument("--upstream-m9-s0-execution", default="")
    ap.add_argument("--upstream-m9-s1-execution", default="")
    ap.add_argument("--upstream-m9-s2-execution", default="")
    ap.add_argument("--upstream-m9-s3-execution", default="")
    ap.add_argument("--upstream-m9-s4-execution", default="")
    args = ap.parse_args()

    phase_execution_id = args.phase_execution_id.strip()
    if not phase_execution_id:
        if args.stage == "S0":
            phase_execution_id = f"m9_stress_s0_{tok()}"
        elif args.stage == "S1":
            phase_execution_id = f"m9_stress_s1_{tok()}"
        elif args.stage == "S2":
            phase_execution_id = f"m9_stress_s2_{tok()}"
        elif args.stage == "S3":
            phase_execution_id = f"m9_stress_s3_{tok()}"
        elif args.stage == "S4":
            phase_execution_id = f"m9_stress_s4_{tok()}"
        elif args.stage == "S5":
            phase_execution_id = f"m9_stress_s5_{tok()}"

    if args.stage == "S0":
        upstream_m8 = args.upstream_m8_execution.strip()
        if not upstream_m8:
            upstream_m8, _ = latest_m8_s5()
        if not upstream_m8:
            raise SystemExit("No upstream M8 S5 execution provided/found.")
        return run_s0(phase_execution_id, upstream_m8)
    if args.stage == "S1":
        upstream_s0 = args.upstream_m9_s0_execution.strip()
        if not upstream_s0:
            upstream_s0, _ = latest_s0()
        if not upstream_s0:
            raise SystemExit("No upstream M9 S0 execution provided/found.")
        return run_s1(phase_execution_id, upstream_s0)
    if args.stage == "S2":
        upstream_s1 = args.upstream_m9_s1_execution.strip()
        if not upstream_s1:
            upstream_s1, _ = latest_s1()
        if not upstream_s1:
            raise SystemExit("No upstream M9 S1 execution provided/found.")
        return run_s2(phase_execution_id, upstream_s1)
    if args.stage == "S3":
        upstream_s2 = args.upstream_m9_s2_execution.strip()
        if not upstream_s2:
            upstream_s2, _ = latest_s2()
        if not upstream_s2:
            raise SystemExit("No upstream M9 S2 execution provided/found.")
        return run_s3(phase_execution_id, upstream_s2)
    if args.stage == "S4":
        upstream_s3 = args.upstream_m9_s3_execution.strip()
        if not upstream_s3:
            upstream_s3, _ = latest_s3()
        if not upstream_s3:
            raise SystemExit("No upstream M9 S3 execution provided/found.")
        return run_s4(phase_execution_id, upstream_s3)
    if args.stage == "S5":
        upstream_s4 = args.upstream_m9_s4_execution.strip()
        if not upstream_s4:
            upstream_s4, _ = latest_s4()
        if not upstream_s4:
            raise SystemExit("No upstream M9 S4 execution provided/found.")
        return run_s5(phase_execution_id, upstream_s4)
    raise SystemExit("Unsupported stage")


if __name__ == "__main__":
    raise SystemExit(main())
