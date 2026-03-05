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
    else:
        next_gate = "HOLD_REMEDIATE"
    verdict = "GO" if overall_pass else "HOLD_REMEDIATE"

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


def main() -> int:
    ap = argparse.ArgumentParser(description="M9 stress runner")
    ap.add_argument("--stage", required=True, choices=["S0", "S1"])
    ap.add_argument("--phase-execution-id", default="")
    ap.add_argument("--upstream-m8-execution", default="")
    ap.add_argument("--upstream-m9-s0-execution", default="")
    args = ap.parse_args()

    phase_execution_id = args.phase_execution_id.strip()
    if not phase_execution_id:
        if args.stage == "S0":
            phase_execution_id = f"m9_stress_s0_{tok()}"
        elif args.stage == "S1":
            phase_execution_id = f"m9_stress_s1_{tok()}"

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
    raise SystemExit("Unsupported stage")


if __name__ == "__main__":
    raise SystemExit(main())
