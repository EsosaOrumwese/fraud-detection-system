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

PLAN = Path("docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M10.stress_test.md")
REG = Path("docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md")
OUT_ROOT = Path("runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control")

S0_ARTS = [
    "m10_stagea_findings.json",
    "m10_lane_matrix.json",
    "m10a_handle_closure_snapshot.json",
    "m10a_execution_summary.json",
    "m10b_databricks_job_upsert_receipt.json",
    "m10b_databricks_readiness_snapshot.json",
    "m10b_execution_summary.json",
    "m10_runtime_locality_guard_snapshot.json",
    "m10_source_authority_guard_snapshot.json",
    "m10_realism_guard_snapshot.json",
    "m10_blocker_register.json",
    "m10_execution_summary.json",
    "m10_decision_log.json",
    "m10_gate_verdict.json",
]

S1_ARTS = [
    "m10_lane_matrix.json",
    "m10c_input_binding_snapshot.json",
    "m10c_blocker_register.json",
    "m10c_execution_summary.json",
    "m10d_ofs_build_execution_snapshot.json",
    "m10d_blocker_register.json",
    "m10d_execution_summary.json",
    "m10_runtime_locality_guard_snapshot.json",
    "m10_source_authority_guard_snapshot.json",
    "m10_realism_guard_snapshot.json",
    "m10_blocker_register.json",
    "m10_execution_summary.json",
    "m10_decision_log.json",
    "m10_gate_verdict.json",
]

S2_ARTS = [
    "m10_lane_matrix.json",
    "m10e_quality_gate_snapshot.json",
    "m10e_blocker_register.json",
    "m10e_execution_summary.json",
    "m10f_iceberg_commit_snapshot.json",
    "m10f_blocker_register.json",
    "m10f_execution_summary.json",
    "m10_runtime_locality_guard_snapshot.json",
    "m10_source_authority_guard_snapshot.json",
    "m10_realism_guard_snapshot.json",
    "m10_blocker_register.json",
    "m10_execution_summary.json",
    "m10_decision_log.json",
    "m10_gate_verdict.json",
]

S3_ARTS = [
    "m10_lane_matrix.json",
    "m10g_manifest_fingerprint_snapshot.json",
    "m10g_blocker_register.json",
    "m10g_execution_summary.json",
    "m10h_rollback_recipe_snapshot.json",
    "m10h_blocker_register.json",
    "m10h_execution_summary.json",
    "m10_runtime_locality_guard_snapshot.json",
    "m10_source_authority_guard_snapshot.json",
    "m10_realism_guard_snapshot.json",
    "m10_blocker_register.json",
    "m10_execution_summary.json",
    "m10_decision_log.json",
    "m10_gate_verdict.json",
]

S4_ARTS = [
    "m10_lane_matrix.json",
    "m10i_p13_rollup_matrix.json",
    "m10i_p13_gate_verdict.json",
    "m11_handoff_pack.json",
    "m10i_blocker_register.json",
    "m10i_execution_summary.json",
    "m10_runtime_locality_guard_snapshot.json",
    "m10_source_authority_guard_snapshot.json",
    "m10_realism_guard_snapshot.json",
    "m10_blocker_register.json",
    "m10_execution_summary.json",
    "m10_decision_log.json",
    "m10_gate_verdict.json",
]

S5_ARTS = [
    "m10_phase_budget_envelope.json",
    "m10_phase_cost_outcome_receipt.json",
    "m10j_execution_summary.json",
    "m10j_blocker_register.json",
    "m10_runtime_locality_guard_snapshot.json",
    "m10_source_authority_guard_snapshot.json",
    "m10_realism_guard_snapshot.json",
    "m10_blocker_register.json",
    "m10_execution_summary.json",
    "m10_decision_log.json",
    "m10_gate_verdict.json",
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


def latest_m9_s5() -> tuple[str, dict[str, Any]]:
    best_id = ""
    best_payload: dict[str, Any] = {}
    best_stamp = ""
    for d in OUT_ROOT.glob("m9_stress_s5_*"):
        payload = loadj(d / "stress" / "m9_execution_summary.json")
        if not payload:
            continue
        if str(payload.get("stage_id", "")) != "M9-ST-S5":
            continue
        if not bool(payload.get("overall_pass")):
            continue
        if str(payload.get("verdict", "")) != "ADVANCE_TO_M10":
            continue
        if str(payload.get("next_gate", "")) != "M10_READY":
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
    for d in OUT_ROOT.glob("m10_stress_s0_*"):
        payload = loadj(d / "stress" / "m10_execution_summary.json")
        if not payload:
            continue
        if str(payload.get("stage_id", "")) != "M10-ST-S0":
            continue
        if not bool(payload.get("overall_pass")):
            continue
        if str(payload.get("next_gate", "")) != "M10_ST_S1_READY":
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
    for d in OUT_ROOT.glob("m10_stress_s1_*"):
        payload = loadj(d / "stress" / "m10_execution_summary.json")
        if not payload:
            continue
        if str(payload.get("stage_id", "")) != "M10-ST-S1":
            continue
        if not bool(payload.get("overall_pass")):
            continue
        if str(payload.get("next_gate", "")) != "M10_ST_S2_READY":
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
    for d in OUT_ROOT.glob("m10_stress_s2_*"):
        payload = loadj(d / "stress" / "m10_execution_summary.json")
        if not payload:
            continue
        if str(payload.get("stage_id", "")) != "M10-ST-S2":
            continue
        if not bool(payload.get("overall_pass")):
            continue
        if str(payload.get("next_gate", "")) != "M10_ST_S3_READY":
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
    for d in OUT_ROOT.glob("m10_stress_s3_*"):
        payload = loadj(d / "stress" / "m10_execution_summary.json")
        if not payload:
            continue
        if str(payload.get("stage_id", "")) != "M10-ST-S3":
            continue
        if not bool(payload.get("overall_pass")):
            continue
        if str(payload.get("next_gate", "")) != "M10_ST_S4_READY":
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
    for d in OUT_ROOT.glob("m10_stress_s4_*"):
        payload = loadj(d / "stress" / "m10_execution_summary.json")
        if not payload:
            continue
        if str(payload.get("stage_id", "")) != "M10-ST-S4":
            continue
        if not bool(payload.get("overall_pass")):
            continue
        if str(payload.get("next_gate", "")) != "M10_ST_S5_READY":
            continue
        stamp = str(payload.get("generated_at_utc", ""))
        if (stamp, d.name) > (best_stamp, best_id):
            best_id = d.name
            best_payload = payload
            best_stamp = stamp
    return best_id, best_payload


def resolve_dbx_token(reg: dict[str, Any]) -> tuple[str, str]:
    token = str(os.environ.get("DBX_TOKEN", "")).strip()
    if token:
        return token, "env"
    ssm_path = str(reg.get("SSM_DATABRICKS_TOKEN_PATH", "")).strip()
    if is_placeholder(ssm_path):
        return "", "missing_ssm_token_path"
    rc, out, err = run(
        [
            "aws",
            "ssm",
            "get-parameter",
            "--name",
            ssm_path,
            "--with-decryption",
            "--query",
            "Parameter.Value",
            "--output",
            "text",
            "--region",
            "eu-west-2",
        ],
        timeout=120,
    )
    if rc != 0:
        return "", f"ssm_read_failed:{err.strip()[:160]}"
    token = out.strip()
    if not token:
        return "", "ssm_empty_value"
    return token, "ssm"


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
        "m10_blocker_register.json",
        "m10_execution_summary.json",
        "m10_decision_log.json",
        "m10_gate_verdict.json",
    }
    prewrite_required = [name for name in arts if name not in stage_receipts]
    missing = [name for name in prewrite_required if not (out / name).exists()]
    if missing:
        add_blocker(
            blockers,
            "M10-ST-B12",
            stage,
            {"reason": "artifact_contract_incomplete", "missing_outputs": sorted(missing)},
        )
    blockers = dedupe(blockers)

    overall_pass = len(blockers) == 0
    if overall_pass and stage == "S0":
        next_gate = "M10_ST_S1_READY"
        verdict = "GO"
    elif overall_pass and stage == "S1":
        next_gate = "M10_ST_S2_READY"
        verdict = "GO"
    elif overall_pass and stage == "S2":
        next_gate = "M10_ST_S3_READY"
        verdict = "GO"
    elif overall_pass and stage == "S3":
        next_gate = "M10_ST_S4_READY"
        verdict = "GO"
    elif overall_pass and stage == "S4":
        next_gate = "M10_ST_S5_READY"
        verdict = "GO"
    elif overall_pass and stage == "S5":
        next_gate = "M11_READY"
        verdict = "ADVANCE_TO_M11"
    else:
        next_gate = "HOLD_REMEDIATE"
        verdict = "HOLD_REMEDIATE"

    register = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": f"M10-ST-{stage}",
        "open_blocker_count": len(blockers),
        "blockers": blockers,
    }
    summary = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": f"M10-ST-{stage}",
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
        "stage_id": f"M10-ST-{stage}",
        "decisions": list(summary_extra.get("decisions", [])),
        "advisories": list(summary_extra.get("advisories", [])),
    }
    gate = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": f"M10-ST-{stage}",
        "overall_pass": overall_pass,
        "next_gate": next_gate,
        "verdict": verdict,
    }

    dumpj(out / "m10_blocker_register.json", register)
    dumpj(out / "m10_execution_summary.json", summary)
    dumpj(out / "m10_decision_log.json", decision_log)
    dumpj(out / "m10_gate_verdict.json", gate)

    print(
        json.dumps(
            {
                "phase_execution_id": phase_execution_id,
                "stage_id": f"M10-ST-{stage}",
                "overall_pass": overall_pass,
                "open_blocker_count": len(blockers),
                "next_gate": next_gate,
                "output_dir": out.as_posix(),
            }
        )
    )
    return 0


def run_s0(phase_execution_id: str, upstream_m9_s5_execution: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)
    blockers: list[dict[str, Any]] = []
    advisories: list[str] = []

    plan_text = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    packet = parse_plan_packet(plan_text)
    reg = parse_registry(REG) if REG.exists() else {}

    scripts_required = [
        "scripts/dev_substrate/m10a_handle_closure.py",
        "scripts/dev_substrate/m10b_upsert_databricks_jobs.py",
        "scripts/dev_substrate/m10b_databricks_readiness.py",
    ]
    for script_path in scripts_required:
        if not Path(script_path).exists():
            add_blocker(
                blockers,
                "M10-ST-B18",
                "S0",
                {"reason": "required_stage_script_missing", "script": script_path},
            )

    value = reg.get("S3_EVIDENCE_BUCKET")
    if value is None or is_placeholder(value):
        add_blocker(blockers, "M10-ST-B1", "S0", {"reason": "required_handle_missing_or_placeholder", "handle": "S3_EVIDENCE_BUCKET"})
    bucket = str(reg.get("S3_EVIDENCE_BUCKET", "")).strip()

    fail_on_stale = bool(packet.get("M10_STRESS_FAIL_ON_STALE_UPSTREAM", True))
    expected_entry_execution = str(packet.get("M10_STRESS_EXPECTED_ENTRY_EXECUTION", "")).strip()
    if fail_on_stale and expected_entry_execution and upstream_m9_s5_execution != expected_entry_execution:
        add_blocker(
            blockers,
            "M10-ST-B1",
            "S0",
            {
                "reason": "stale_or_unexpected_upstream_execution",
                "selected_upstream_execution": upstream_m9_s5_execution,
                "expected_execution": expected_entry_execution,
            },
        )

    expected_entry_gate = str(packet.get("M10_STRESS_EXPECTED_ENTRY_GATE", "M10_READY")).strip() or "M10_READY"
    local_m9_s5_summary = loadj(OUT_ROOT / upstream_m9_s5_execution / "stress" / "m9_execution_summary.json")
    if not local_m9_s5_summary:
        add_blocker(
            blockers,
            "M10-ST-B1",
            "S0",
            {
                "reason": "upstream_m9_s5_summary_missing",
                "path": (OUT_ROOT / upstream_m9_s5_execution / "stress" / "m9_execution_summary.json").as_posix(),
            },
        )
    else:
        if not (
            bool(local_m9_s5_summary.get("overall_pass"))
            and int(local_m9_s5_summary.get("open_blocker_count", 1)) == 0
            and str(local_m9_s5_summary.get("verdict", "")) == "ADVANCE_TO_M10"
            and str(local_m9_s5_summary.get("next_gate", "")) == expected_entry_gate
        ):
            add_blocker(
                blockers,
                "M10-ST-B1",
                "S0",
                {
                    "reason": "upstream_m9_s5_not_ready",
                    "summary": {
                        "overall_pass": local_m9_s5_summary.get("overall_pass"),
                        "open_blocker_count": local_m9_s5_summary.get("open_blocker_count"),
                        "verdict": local_m9_s5_summary.get("verdict"),
                        "next_gate": local_m9_s5_summary.get("next_gate"),
                    },
                },
            )

    m9_bridge_snapshot: dict[str, Any] = {}
    if local_m9_s5_summary and bucket and not is_placeholder(bucket):
        bridge_payload = dict(local_m9_s5_summary)
        bridge_local = out / "_m9_entry_bridge" / "m9_execution_summary.json"
        dumpj(bridge_local, bridge_payload)
        bridge_key = f"evidence/dev_full/run_control/{upstream_m9_s5_execution}/m9_execution_summary.json"
        rc, _, err = run(
            [
                "aws",
                "s3",
                "cp",
                bridge_local.as_posix(),
                f"s3://{bucket}/{bridge_key}",
                "--region",
                "eu-west-2",
            ],
            timeout=180,
        )
        if rc != 0:
            add_blocker(
                blockers,
                "M10-ST-B12",
                "S0",
                {"reason": "m9_entry_bridge_upload_failed", "key": bridge_key, "stderr": err.strip()[:300], "rc": rc},
            )
        m9_bridge_snapshot = {
            "generated_at_utc": now(),
            "source_summary_path": (OUT_ROOT / upstream_m9_s5_execution / "stress" / "m9_execution_summary.json").as_posix(),
            "bridge_payload_path": bridge_local.as_posix(),
            "target_s3_key": bridge_key,
            "upload_rc": rc,
        }

    s4_exec = str(local_m9_s5_summary.get("upstream_m9_s4_execution", "")).strip() if local_m9_s5_summary else ""
    local_m9_s4_summary = loadj(OUT_ROOT / s4_exec / "stress" / "m9_execution_summary.json") if s4_exec else {}
    if not s4_exec:
        add_blocker(blockers, "M10-ST-B1", "S0", {"reason": "missing_upstream_m9_s4_execution_in_m9_s5_summary"})
    elif not local_m9_s4_summary:
        add_blocker(blockers, "M10-ST-B1", "S0", {"reason": "upstream_m9_s4_summary_missing", "upstream_s4_execution": s4_exec})
    elif not (bool(local_m9_s4_summary.get("overall_pass")) and str(local_m9_s4_summary.get("next_gate", "")) == "M9_ST_S5_READY"):
        add_blocker(
            blockers,
            "M10-ST-B1",
            "S0",
            {
                "reason": "upstream_m9_s4_not_ready",
                "upstream_s4_execution": s4_exec,
                "summary": {
                    "overall_pass": local_m9_s4_summary.get("overall_pass"),
                    "next_gate": local_m9_s4_summary.get("next_gate"),
                    "open_blocker_count": local_m9_s4_summary.get("open_blocker_count"),
                },
            },
        )

    s3_exec = str(local_m9_s4_summary.get("upstream_m9_s3_execution", "")).strip() if local_m9_s4_summary else ""
    local_m9_s3_summary = loadj(OUT_ROOT / s3_exec / "stress" / "m9_execution_summary.json") if s3_exec else {}
    if not s3_exec:
        add_blocker(blockers, "M10-ST-B1", "S0", {"reason": "missing_upstream_m9_s3_execution_in_m9_s4_summary"})
    elif not local_m9_s3_summary:
        add_blocker(blockers, "M10-ST-B1", "S0", {"reason": "upstream_m9_s3_summary_missing", "upstream_s3_execution": s3_exec})
    elif not (bool(local_m9_s3_summary.get("overall_pass")) and str(local_m9_s3_summary.get("next_gate", "")) == "M9_ST_S4_READY"):
        add_blocker(
            blockers,
            "M10-ST-B1",
            "S0",
            {
                "reason": "upstream_m9_s3_not_ready",
                "upstream_s3_execution": s3_exec,
                "summary": {
                    "overall_pass": local_m9_s3_summary.get("overall_pass"),
                    "next_gate": local_m9_s3_summary.get("next_gate"),
                    "open_blocker_count": local_m9_s3_summary.get("open_blocker_count"),
                },
            },
        )

    m9h_exec = str(local_m9_s3_summary.get("m9h_execution_id", "")).strip() if local_m9_s3_summary else ""
    if not m9h_exec:
        add_blocker(
            blockers,
            "M10-ST-B1",
            "S0",
            {"reason": "missing_m9h_execution_id_from_strict_chain", "upstream_s3_execution": s3_exec},
        )

    m10a_exec = ""
    m10a_summary: dict[str, Any] = {}
    m10a_snapshot: dict[str, Any] = {}
    if Path("scripts/dev_substrate/m10a_handle_closure.py").exists():
        m10a_exec = f"m10a_stress_s0_{tok()}"
        m10a_dir = out / "_m10a"
        env_m10a = dict(os.environ)
        env_m10a.update(
            {
                "M10A_EXECUTION_ID": m10a_exec,
                "M10A_RUN_DIR": m10a_dir.as_posix(),
                "EVIDENCE_BUCKET": bucket,
                "UPSTREAM_M9_EXECUTION": upstream_m9_s5_execution,
                "UPSTREAM_M9H_EXECUTION": m9h_exec,
                "AWS_REGION": "eu-west-2",
            }
        )
        rc, _, err = run(["python", "scripts/dev_substrate/m10a_handle_closure.py"], timeout=3000, env=env_m10a)
        if rc != 0:
            add_blocker(
                blockers,
                "M10-ST-B1",
                "S0",
                {"reason": "m10a_command_failed", "stderr": err.strip()[:300], "rc": rc},
            )
        m10a_summary = loadj(m10a_dir / "m10a_execution_summary.json")
        m10a_snapshot = loadj(m10a_dir / "m10a_handle_closure_snapshot.json")
        m10a_register = loadj(m10a_dir / "m10a_blocker_register.json")
        if m10a_snapshot:
            dumpj(out / "m10a_handle_closure_snapshot.json", m10a_snapshot)
        if m10a_summary:
            dumpj(out / "m10a_execution_summary.json", m10a_summary)
        if m10a_register:
            dumpj(out / "m10a_blocker_register.json", m10a_register)
        if not m10a_summary:
            add_blocker(blockers, "M10-ST-B1", "S0", {"reason": "m10a_summary_missing"})
        elif not (bool(m10a_summary.get("overall_pass")) and str(m10a_summary.get("next_gate", "")) == "M10.B_READY"):
            add_blocker(blockers, "M10-ST-B1", "S0", {"reason": "m10a_not_ready", "summary": m10a_summary})

    m10b_exec = ""
    m10b_summary: dict[str, Any] = {}
    m10b_snapshot: dict[str, Any] = {}
    upsert_receipt_path = out / "_m10b" / "m10b_databricks_job_upsert_receipt.json"
    upsert_receipt: dict[str, Any] = {}
    upsert_token_source = ""

    required_upsert_handles = [
        "DBX_WORKSPACE_URL",
        "DBX_JOB_OFS_BUILD_V0",
        "DBX_JOB_OFS_QUALITY_GATES_V0",
        "DBX_AUTOSCALE_WORKERS",
        "DBX_AUTO_TERMINATE_MINUTES",
        "SSM_DATABRICKS_TOKEN_PATH",
    ]
    unresolved_upsert: list[str] = []
    for key in required_upsert_handles:
        if key not in reg or is_placeholder(reg.get(key)):
            unresolved_upsert.append(key)
    if unresolved_upsert:
        add_blocker(
            blockers,
            "M10-ST-B2",
            "S0",
            {"reason": "upsert_required_handles_unresolved", "handles": sorted(unresolved_upsert)},
        )

    dbx_token, upsert_token_source = resolve_dbx_token(reg)
    if not dbx_token:
        add_blocker(
            blockers,
            "M10-ST-B2",
            "S0",
            {"reason": "dbx_token_unavailable_for_upsert", "source": upsert_token_source},
        )

    if Path("scripts/dev_substrate/m10b_upsert_databricks_jobs.py").exists():
        upsert_env = dict(os.environ)
        upsert_env.update(
            {
                "DBX_WORKSPACE_URL": str(reg.get("DBX_WORKSPACE_URL", "")).strip(),
                "DBX_TOKEN": dbx_token,
                "DBX_JOB_OFS_BUILD_V0": str(reg.get("DBX_JOB_OFS_BUILD_V0", "")).strip(),
                "DBX_JOB_OFS_QUALITY_GATES_V0": str(reg.get("DBX_JOB_OFS_QUALITY_GATES_V0", "")).strip(),
                "DBX_AUTOSCALE_WORKERS": str(reg.get("DBX_AUTOSCALE_WORKERS", "1-8")).strip(),
                "DBX_AUTO_TERMINATE_MINUTES": str(reg.get("DBX_AUTO_TERMINATE_MINUTES", "20")).strip(),
                "DBX_WORKSPACE_PROJECT_ROOT": str(reg.get("DBX_WORKSPACE_PROJECT_ROOT", "/Shared/fraud-platform/dev_full")).strip(),
                "M10B_DBX_JOB_UPSERT_RECEIPT_PATH": upsert_receipt_path.as_posix(),
                "OFS_BUILD_SOURCE_PATH": "platform/databricks/dev_full/ofs_build_v0.py",
                "OFS_QUALITY_SOURCE_PATH": "platform/databricks/dev_full/ofs_quality_v0.py",
            }
        )
        if not unresolved_upsert and dbx_token:
            rc, _, err = run(["python", "scripts/dev_substrate/m10b_upsert_databricks_jobs.py"], timeout=3600, env=upsert_env)
            if rc != 0:
                add_blocker(
                    blockers,
                    "M10-ST-B2",
                    "S0",
                    {"reason": "m10b_upsert_command_failed", "stderr": err.strip()[:300], "rc": rc},
                )
        if upsert_receipt_path.exists():
            upsert_receipt = loadj(upsert_receipt_path)
            if upsert_receipt:
                dumpj(out / "m10b_databricks_job_upsert_receipt.json", upsert_receipt)
                if not bool(upsert_receipt.get("overall_pass")):
                    add_blocker(
                        blockers,
                        "M10-ST-B2",
                        "S0",
                        {"reason": "m10b_upsert_receipt_not_pass", "receipt_overall_pass": upsert_receipt.get("overall_pass")},
                    )
        else:
            add_blocker(
                blockers,
                "M10-ST-B2",
                "S0",
                {"reason": "m10b_upsert_receipt_missing", "path": upsert_receipt_path.as_posix()},
            )

    if Path("scripts/dev_substrate/m10b_databricks_readiness.py").exists() and m10a_exec:
        m10b_exec = f"m10b_stress_s0_{tok()}"
        m10b_dir = out / "_m10b"
        env_m10b = dict(os.environ)
        env_m10b.update(
            {
                "M10B_EXECUTION_ID": m10b_exec,
                "M10B_RUN_DIR": m10b_dir.as_posix(),
                "EVIDENCE_BUCKET": bucket,
                "UPSTREAM_M10A_EXECUTION": m10a_exec,
                "M10B_DBX_JOB_UPSERT_RECEIPT_PATH": upsert_receipt_path.as_posix(),
                "AWS_REGION": "eu-west-2",
            }
        )
        rc, _, err = run(["python", "scripts/dev_substrate/m10b_databricks_readiness.py"], timeout=3600, env=env_m10b)
        if rc != 0:
            add_blocker(
                blockers,
                "M10-ST-B2",
                "S0",
                {"reason": "m10b_command_failed", "stderr": err.strip()[:300], "rc": rc},
            )
        m10b_summary = loadj(m10b_dir / "m10b_execution_summary.json")
        m10b_snapshot = loadj(m10b_dir / "m10b_databricks_readiness_snapshot.json")
        m10b_register = loadj(m10b_dir / "m10b_blocker_register.json")
        if m10b_snapshot:
            dumpj(out / "m10b_databricks_readiness_snapshot.json", m10b_snapshot)
        if m10b_summary:
            dumpj(out / "m10b_execution_summary.json", m10b_summary)
        if m10b_register:
            dumpj(out / "m10b_blocker_register.json", m10b_register)
        if not m10b_summary:
            add_blocker(blockers, "M10-ST-B2", "S0", {"reason": "m10b_summary_missing"})
        elif not (bool(m10b_summary.get("overall_pass")) and str(m10b_summary.get("next_gate", "")) == "M10.C_READY"):
            add_blocker(blockers, "M10-ST-B2", "S0", {"reason": "m10b_not_ready", "summary": m10b_summary})
    elif not m10a_exec:
        add_blocker(
            blockers,
            "M10-ST-B2",
            "S0",
            {"reason": "m10b_skipped_missing_upstream_m10a_execution"},
        )

    stage_findings = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M10-ST-S0",
        "findings": [
            {
                "id": "M10-ST-F3",
                "classification": "PREVENT",
                "status": "CLOSED",
                "note": "Parent M10 runner exists and executes S0 deterministically.",
            },
            {
                "id": "M10-ST-F4",
                "classification": "PREVENT",
                "status": "CLOSED"
                if all(Path(p).exists() for p in scripts_required)
                else "OPEN",
                "note": "S0 required execution scripts are present.",
            },
            {
                "id": "M10-ST-F5",
                "classification": "PREVENT",
                "status": "CLOSED" if len([b for b in blockers if b.get("id") == "M10-ST-B1"]) == 0 else "OPEN",
                "note": "Strict upstream continuity and stale-evidence guard are enforced in S0.",
            },
        ],
    }
    dumpj(out / "m10_stagea_findings.json", stage_findings)

    lane_matrix = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M10-ST-S0",
        "lanes": [
            {
                "lane": "A",
                "component": "M10.A",
                "execution_id": m10a_exec,
                "overall_pass": bool(m10a_summary.get("overall_pass")) if m10a_summary else False,
                "next_gate": str(m10a_summary.get("next_gate", "")) if m10a_summary else "",
            },
            {
                "lane": "B",
                "component": "M10.B",
                "execution_id": m10b_exec,
                "overall_pass": bool(m10b_summary.get("overall_pass")) if m10b_summary else False,
                "next_gate": str(m10b_summary.get("next_gate", "")) if m10b_summary else "",
                "upsert_receipt_path": upsert_receipt_path.as_posix(),
                "upsert_token_source": upsert_token_source,
            },
        ],
    }
    dumpj(out / "m10_lane_matrix.json", lane_matrix)
    if m9_bridge_snapshot:
        dumpj(out / "m10_m9_entry_bridge_snapshot.json", m9_bridge_snapshot)

    runtime_locality_ok = bool(packet.get("M10_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY", True))
    if not runtime_locality_ok:
        add_blocker(blockers, "M10-ST-B16", "S0", {"reason": "runtime_locality_policy_not_true"})
    dumpj(
        out / "m10_runtime_locality_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M10-ST-S0",
            "overall_pass": runtime_locality_ok,
            "require_remote_runtime_only": bool(packet.get("M10_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY", True)),
            "runtime_execution_attempted": False,
            "runtime_execution_mode": "local_control_orchestration_only_remote_runtime",
        },
    )

    refs = [
        f"evidence/dev_full/run_control/{upstream_m9_s5_execution}/m9_execution_summary.json" if upstream_m9_s5_execution else "",
        f"evidence/dev_full/run_control/{s3_exec}/m9_execution_summary.json" if s3_exec else "",
        f"evidence/dev_full/run_control/{m9h_exec}/m10_handoff_pack.json" if m9h_exec else "",
        f"evidence/dev_full/run_control/{m10a_exec}/m10a_execution_summary.json" if m10a_exec else "",
        f"evidence/dev_full/run_control/{m10b_exec}/m10b_execution_summary.json" if m10b_exec else "",
    ]
    source_guard_ok = len([b for b in blockers if b.get("id") in {"M10-ST-B12", "M10-ST-B16"}]) == 0
    dumpj(
        out / "m10_source_authority_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M10-ST-S0",
            "overall_pass": source_guard_ok,
            "authoritative_refs": refs,
            "evidence_bucket": bucket,
            "runtime_locality_only_control_plane": True,
        },
    )

    realism_ok = bool(packet.get("M10_STRESS_DISALLOW_WAIVED_REALISM", True))
    if not realism_ok:
        add_blocker(blockers, "M10-ST-B16", "S0", {"reason": "realism_guard_not_true"})
    dumpj(
        out / "m10_realism_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M10-ST-S0",
            "overall_pass": realism_ok,
            "disallow_waived_realism": bool(packet.get("M10_STRESS_DISALLOW_WAIVED_REALISM", True)),
        },
    )

    if not bool(packet.get("M10_STRESS_REQUIRE_DATA_ENGINE_BLACKBOX", True)):
        add_blocker(blockers, "M10-ST-B16", "S0", {"reason": "data_engine_blackbox_guard_not_true"})

    return finish(
        "S0",
        phase_execution_id,
        out,
        blockers,
        S0_ARTS,
        {
            "platform_run_id": str(local_m9_s5_summary.get("platform_run_id", "")) if local_m9_s5_summary else "",
            "scenario_run_id": str(local_m9_s5_summary.get("scenario_run_id", "")) if local_m9_s5_summary else "",
            "upstream_m9_s5_execution": upstream_m9_s5_execution,
            "upstream_m9_s4_execution": s4_exec,
            "upstream_m9_s3_execution": s3_exec,
            "upstream_m9h_execution": m9h_exec,
            "m10a_execution_id": m10a_exec,
            "m10b_execution_id": m10b_exec,
            "decisions": [
                "S0 enforced strict M9 closure continuity (S5->S4->S3) before any M10 lane execution.",
                "S0 published the strict upstream M9 summary bridge to the S3 authority key required by M10.A.",
                "S0 executed M10.A authority closure, Databricks upsert receipt generation, and M10.B readiness adjudication with fail-closed blocker mapping.",
            ],
            "advisories": advisories,
        },
    )


def run_s1(phase_execution_id: str, upstream_m10_s0_execution: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)
    blockers: list[dict[str, Any]] = []
    advisories: list[str] = []

    plan_text = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    packet = parse_plan_packet(plan_text)
    reg = parse_registry(REG) if REG.exists() else {}

    scripts_required = [
        "scripts/dev_substrate/m10c_input_binding.py",
        "scripts/dev_substrate/m10d_ofs_build_execution.py",
    ]
    for script_path in scripts_required:
        if not Path(script_path).exists():
            add_blocker(
                blockers,
                "M10-ST-B18",
                "S1",
                {"reason": "required_stage_script_missing", "script": script_path},
            )

    value = reg.get("S3_EVIDENCE_BUCKET")
    if value is None or is_placeholder(value):
        add_blocker(blockers, "M10-ST-B3", "S1", {"reason": "required_handle_missing_or_placeholder", "handle": "S3_EVIDENCE_BUCKET"})
    bucket = str(reg.get("S3_EVIDENCE_BUCKET", "")).strip()

    s0_exec = upstream_m10_s0_execution.strip()
    s0 = loadj(OUT_ROOT / s0_exec / "stress" / "m10_execution_summary.json") if s0_exec else {}
    if not s0:
        s0_exec, s0 = latest_s0()
    if not s0:
        add_blocker(blockers, "M10-ST-B3", "S1", {"reason": "upstream_s0_summary_missing"})
    elif not bool(s0.get("overall_pass")) or str(s0.get("next_gate", "")) != "M10_ST_S1_READY":
        add_blocker(
            blockers,
            "M10-ST-B3",
            "S1",
            {
                "reason": "upstream_s0_not_ready",
                "upstream_s0_execution": s0_exec,
                "summary": {
                    "overall_pass": s0.get("overall_pass"),
                    "next_gate": s0.get("next_gate"),
                    "open_blocker_count": s0.get("open_blocker_count"),
                },
            },
        )

    m10b_exec = str(s0.get("m10b_execution_id", "")).strip() if s0 else ""
    upstream_m9_exec = str(s0.get("upstream_m9_s5_execution", "")).strip() if s0 else ""
    upstream_m9h_exec = str(s0.get("upstream_m9h_execution", "")).strip() if s0 else ""
    if not m10b_exec:
        add_blocker(blockers, "M10-ST-B3", "S1", {"reason": "missing_m10b_execution_id", "upstream_s0_execution": s0_exec})
    if not upstream_m9_exec:
        add_blocker(blockers, "M10-ST-B3", "S1", {"reason": "missing_upstream_m9_s5_execution", "upstream_s0_execution": s0_exec})
    if not upstream_m9h_exec:
        add_blocker(blockers, "M10-ST-B3", "S1", {"reason": "missing_upstream_m9h_execution", "upstream_s0_execution": s0_exec})

    m10c_exec = ""
    m10c_summary: dict[str, Any] = {}
    m10c_snapshot: dict[str, Any] = {}
    if not blockers and Path("scripts/dev_substrate/m10c_input_binding.py").exists():
        m10c_exec = f"m10c_stress_s1_{tok()}"
        m10c_dir = out / "_m10c"
        env_m10c = dict(os.environ)
        env_m10c.update(
            {
                "M10C_EXECUTION_ID": m10c_exec,
                "M10C_RUN_DIR": m10c_dir.as_posix(),
                "EVIDENCE_BUCKET": bucket,
                "UPSTREAM_M10B_EXECUTION": m10b_exec,
                "UPSTREAM_M9_EXECUTION": upstream_m9_exec,
                "UPSTREAM_M9H_EXECUTION": upstream_m9h_exec,
                "AWS_REGION": "eu-west-2",
            }
        )
        rc, _, err = run(["python", "scripts/dev_substrate/m10c_input_binding.py"], timeout=3600, env=env_m10c)
        if rc != 0:
            add_blocker(
                blockers,
                "M10-ST-B3",
                "S1",
                {"reason": "m10c_command_failed", "stderr": err.strip()[:300], "rc": rc},
            )
        m10c_summary = loadj(m10c_dir / "m10c_execution_summary.json")
        m10c_snapshot = loadj(m10c_dir / "m10c_input_binding_snapshot.json")
        m10c_register = loadj(m10c_dir / "m10c_blocker_register.json")
        if m10c_snapshot:
            dumpj(out / "m10c_input_binding_snapshot.json", m10c_snapshot)
        if m10c_summary:
            dumpj(out / "m10c_execution_summary.json", m10c_summary)
        if m10c_register:
            dumpj(out / "m10c_blocker_register.json", m10c_register)
        if not m10c_summary:
            add_blocker(blockers, "M10-ST-B3", "S1", {"reason": "m10c_summary_missing"})
        elif not (bool(m10c_summary.get("overall_pass")) and str(m10c_summary.get("next_gate", "")) == "M10.D_READY"):
            add_blocker(blockers, "M10-ST-B3", "S1", {"reason": "m10c_not_ready", "summary": m10c_summary})

    m10d_exec = ""
    m10d_summary: dict[str, Any] = {}
    m10d_snapshot: dict[str, Any] = {}
    if not blockers and Path("scripts/dev_substrate/m10d_ofs_build_execution.py").exists():
        m10d_exec = f"m10d_stress_s1_{tok()}"
        m10d_dir = out / "_m10d"
        env_m10d = dict(os.environ)
        env_m10d.update(
            {
                "M10D_EXECUTION_ID": m10d_exec,
                "M10D_RUN_DIR": m10d_dir.as_posix(),
                "EVIDENCE_BUCKET": bucket,
                "UPSTREAM_M10C_EXECUTION": m10c_exec,
                "AWS_REGION": "eu-west-2",
            }
        )
        rc, _, err = run(["python", "scripts/dev_substrate/m10d_ofs_build_execution.py"], timeout=7200, env=env_m10d)
        if rc != 0:
            add_blocker(
                blockers,
                "M10-ST-B4",
                "S1",
                {"reason": "m10d_command_failed", "stderr": err.strip()[:300], "rc": rc},
            )
        m10d_summary = loadj(m10d_dir / "m10d_execution_summary.json")
        m10d_snapshot = loadj(m10d_dir / "m10d_ofs_build_execution_snapshot.json")
        m10d_register = loadj(m10d_dir / "m10d_blocker_register.json")
        if m10d_snapshot:
            dumpj(out / "m10d_ofs_build_execution_snapshot.json", m10d_snapshot)
        if m10d_summary:
            dumpj(out / "m10d_execution_summary.json", m10d_summary)
        if m10d_register:
            dumpj(out / "m10d_blocker_register.json", m10d_register)
        if not m10d_summary:
            add_blocker(blockers, "M10-ST-B4", "S1", {"reason": "m10d_summary_missing"})
        elif not (bool(m10d_summary.get("overall_pass")) and str(m10d_summary.get("next_gate", "")) == "M10.E_READY"):
            add_blocker(blockers, "M10-ST-B4", "S1", {"reason": "m10d_not_ready", "summary": m10d_summary})

    lane_matrix = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M10-ST-S1",
        "lanes": [
            {
                "lane": "C",
                "component": "M10.C",
                "execution_id": m10c_exec,
                "overall_pass": bool(m10c_summary.get("overall_pass")) if m10c_summary else False,
                "next_gate": str(m10c_summary.get("next_gate", "")) if m10c_summary else "",
            },
            {
                "lane": "D",
                "component": "M10.D",
                "execution_id": m10d_exec,
                "overall_pass": bool(m10d_summary.get("overall_pass")) if m10d_summary else False,
                "next_gate": str(m10d_summary.get("next_gate", "")) if m10d_summary else "",
            },
        ],
    }
    dumpj(out / "m10_lane_matrix.json", lane_matrix)

    runtime_locality_ok = bool(packet.get("M10_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY", True))
    if not runtime_locality_ok:
        add_blocker(blockers, "M10-ST-B12", "S1", {"reason": "runtime_locality_policy_not_true"})
    dumpj(
        out / "m10_runtime_locality_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M10-ST-S1",
            "overall_pass": runtime_locality_ok,
            "require_remote_runtime_only": bool(packet.get("M10_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY", True)),
            "runtime_execution_attempted": False,
            "runtime_execution_mode": "local_control_orchestration_only_remote_runtime",
        },
    )

    refs = [
        f"evidence/dev_full/run_control/{s0_exec}/stress/m10_execution_summary.json" if s0_exec else "",
        f"evidence/dev_full/run_control/{m10b_exec}/m10b_execution_summary.json" if m10b_exec else "",
        f"evidence/dev_full/run_control/{m10c_exec}/m10c_execution_summary.json" if m10c_exec else "",
        f"evidence/dev_full/run_control/{m10d_exec}/m10d_execution_summary.json" if m10d_exec else "",
    ]
    source_guard_ok = len([b for b in blockers if b.get("id") == "M10-ST-B12"]) == 0
    dumpj(
        out / "m10_source_authority_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M10-ST-S1",
            "overall_pass": source_guard_ok,
            "authoritative_refs": refs,
            "evidence_bucket": bucket,
            "runtime_locality_only_control_plane": True,
        },
    )

    realism_ok = bool(packet.get("M10_STRESS_DISALLOW_WAIVED_REALISM", True))
    if not realism_ok:
        add_blocker(blockers, "M10-ST-B12", "S1", {"reason": "realism_guard_not_true"})
    dumpj(
        out / "m10_realism_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M10-ST-S1",
            "overall_pass": realism_ok,
            "disallow_waived_realism": bool(packet.get("M10_STRESS_DISALLOW_WAIVED_REALISM", True)),
        },
    )

    if not bool(packet.get("M10_STRESS_REQUIRE_DATA_ENGINE_BLACKBOX", True)):
        add_blocker(blockers, "M10-ST-B12", "S1", {"reason": "data_engine_blackbox_guard_not_true"})

    return finish(
        "S1",
        phase_execution_id,
        out,
        blockers,
        S1_ARTS,
        {
            "platform_run_id": str(s0.get("platform_run_id", "")) if s0 else "",
            "scenario_run_id": str(s0.get("scenario_run_id", "")) if s0 else "",
            "upstream_m10_s0_execution": s0_exec,
            "upstream_m10b_execution": m10b_exec,
            "upstream_m9_s5_execution": upstream_m9_exec,
            "upstream_m9h_execution": upstream_m9h_exec,
            "m10c_execution_id": m10c_exec,
            "m10d_execution_id": m10d_exec,
            "decisions": [
                "S1 validated strict S0 continuity before executing lane C and lane D.",
                "S1 executed M10.C input-binding immutability checks followed by M10.D Databricks OFS build execution.",
            ],
            "advisories": advisories,
        },
    )


def run_s2(phase_execution_id: str, upstream_m10_s1_execution: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)
    blockers: list[dict[str, Any]] = []
    advisories: list[str] = []

    plan_text = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    packet = parse_plan_packet(plan_text)
    reg = parse_registry(REG) if REG.exists() else {}

    scripts_required = [
        "scripts/dev_substrate/m10e_quality_gate.py",
        "scripts/dev_substrate/m10f_iceberg_commit.py",
    ]
    for script_path in scripts_required:
        if not Path(script_path).exists():
            add_blocker(
                blockers,
                "M10-ST-B18",
                "S2",
                {"reason": "required_stage_script_missing", "script": script_path},
            )

    value = reg.get("S3_EVIDENCE_BUCKET")
    if value is None or is_placeholder(value):
        add_blocker(blockers, "M10-ST-B5", "S2", {"reason": "required_handle_missing_or_placeholder", "handle": "S3_EVIDENCE_BUCKET"})
    bucket = str(reg.get("S3_EVIDENCE_BUCKET", "")).strip()

    s1_exec = upstream_m10_s1_execution.strip()
    s1 = loadj(OUT_ROOT / s1_exec / "stress" / "m10_execution_summary.json") if s1_exec else {}
    if not s1:
        s1_exec, s1 = latest_s1()
    if not s1:
        add_blocker(blockers, "M10-ST-B5", "S2", {"reason": "upstream_s1_summary_missing"})
    elif not bool(s1.get("overall_pass")) or str(s1.get("next_gate", "")) != "M10_ST_S2_READY":
        add_blocker(
            blockers,
            "M10-ST-B5",
            "S2",
            {
                "reason": "upstream_s1_not_ready",
                "upstream_s1_execution": s1_exec,
                "summary": {
                    "overall_pass": s1.get("overall_pass"),
                    "next_gate": s1.get("next_gate"),
                    "open_blocker_count": s1.get("open_blocker_count"),
                },
            },
        )

    m10d_exec = str(s1.get("m10d_execution_id", "")).strip() if s1 else ""
    if not m10d_exec:
        add_blocker(blockers, "M10-ST-B5", "S2", {"reason": "missing_m10d_execution_id", "upstream_s1_execution": s1_exec})

    m10e_exec = ""
    m10e_summary: dict[str, Any] = {}
    m10e_snapshot: dict[str, Any] = {}
    if not blockers and Path("scripts/dev_substrate/m10e_quality_gate.py").exists():
        m10e_exec = f"m10e_stress_s2_{tok()}"
        m10e_dir = out / "_m10e"
        env_m10e = dict(os.environ)
        env_m10e.update(
            {
                "M10E_EXECUTION_ID": m10e_exec,
                "M10E_RUN_DIR": m10e_dir.as_posix(),
                "EVIDENCE_BUCKET": bucket,
                "UPSTREAM_M10D_EXECUTION": m10d_exec,
                "AWS_REGION": "eu-west-2",
            }
        )
        rc, _, err = run(["python", "scripts/dev_substrate/m10e_quality_gate.py"], timeout=3600, env=env_m10e)
        if rc != 0:
            add_blocker(
                blockers,
                "M10-ST-B5",
                "S2",
                {"reason": "m10e_command_failed", "stderr": err.strip()[:300], "rc": rc},
            )
        m10e_summary = loadj(m10e_dir / "m10e_execution_summary.json")
        m10e_snapshot = loadj(m10e_dir / "m10e_quality_gate_snapshot.json")
        m10e_register = loadj(m10e_dir / "m10e_blocker_register.json")
        if m10e_snapshot:
            dumpj(out / "m10e_quality_gate_snapshot.json", m10e_snapshot)
        if m10e_summary:
            dumpj(out / "m10e_execution_summary.json", m10e_summary)
        if m10e_register:
            dumpj(out / "m10e_blocker_register.json", m10e_register)
        if not m10e_summary:
            add_blocker(blockers, "M10-ST-B5", "S2", {"reason": "m10e_summary_missing"})
        elif not (bool(m10e_summary.get("overall_pass")) and str(m10e_summary.get("next_gate", "")) == "M10.F_READY"):
            add_blocker(blockers, "M10-ST-B5", "S2", {"reason": "m10e_not_ready", "summary": m10e_summary})

    m10f_exec = ""
    m10f_summary: dict[str, Any] = {}
    m10f_snapshot: dict[str, Any] = {}
    if not blockers and Path("scripts/dev_substrate/m10f_iceberg_commit.py").exists():
        m10f_exec = f"m10f_stress_s2_{tok()}"
        m10f_dir = out / "_m10f"
        env_m10f = dict(os.environ)
        env_m10f.update(
            {
                "M10F_EXECUTION_ID": m10f_exec,
                "M10F_RUN_DIR": m10f_dir.as_posix(),
                "EVIDENCE_BUCKET": bucket,
                "UPSTREAM_M10E_EXECUTION": m10e_exec,
                "AWS_REGION": "eu-west-2",
            }
        )
        rc, _, err = run(["python", "scripts/dev_substrate/m10f_iceberg_commit.py"], timeout=3600, env=env_m10f)
        if rc != 0:
            add_blocker(
                blockers,
                "M10-ST-B6",
                "S2",
                {"reason": "m10f_command_failed", "stderr": err.strip()[:300], "rc": rc},
            )
        m10f_summary = loadj(m10f_dir / "m10f_execution_summary.json")
        m10f_snapshot = loadj(m10f_dir / "m10f_iceberg_commit_snapshot.json")
        m10f_register = loadj(m10f_dir / "m10f_blocker_register.json")
        if m10f_snapshot:
            dumpj(out / "m10f_iceberg_commit_snapshot.json", m10f_snapshot)
        if m10f_summary:
            dumpj(out / "m10f_execution_summary.json", m10f_summary)
        if m10f_register:
            dumpj(out / "m10f_blocker_register.json", m10f_register)
        if not m10f_summary:
            add_blocker(blockers, "M10-ST-B6", "S2", {"reason": "m10f_summary_missing"})
        elif not (bool(m10f_summary.get("overall_pass")) and str(m10f_summary.get("next_gate", "")) == "M10.G_READY"):
            add_blocker(blockers, "M10-ST-B6", "S2", {"reason": "m10f_not_ready", "summary": m10f_summary})

    lane_matrix = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M10-ST-S2",
        "lanes": [
            {
                "lane": "E",
                "component": "M10.E",
                "execution_id": m10e_exec,
                "overall_pass": bool(m10e_summary.get("overall_pass")) if m10e_summary else False,
                "next_gate": str(m10e_summary.get("next_gate", "")) if m10e_summary else "",
            },
            {
                "lane": "F",
                "component": "M10.F",
                "execution_id": m10f_exec,
                "overall_pass": bool(m10f_summary.get("overall_pass")) if m10f_summary else False,
                "next_gate": str(m10f_summary.get("next_gate", "")) if m10f_summary else "",
            },
        ],
    }
    dumpj(out / "m10_lane_matrix.json", lane_matrix)

    runtime_locality_ok = bool(packet.get("M10_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY", True))
    if not runtime_locality_ok:
        add_blocker(blockers, "M10-ST-B12", "S2", {"reason": "runtime_locality_policy_not_true"})
    dumpj(
        out / "m10_runtime_locality_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M10-ST-S2",
            "overall_pass": runtime_locality_ok,
            "require_remote_runtime_only": bool(packet.get("M10_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY", True)),
            "runtime_execution_attempted": False,
            "runtime_execution_mode": "local_control_orchestration_only_remote_runtime",
        },
    )

    refs = [
        f"evidence/dev_full/run_control/{s1_exec}/stress/m10_execution_summary.json" if s1_exec else "",
        f"evidence/dev_full/run_control/{m10d_exec}/m10d_execution_summary.json" if m10d_exec else "",
        f"evidence/dev_full/run_control/{m10e_exec}/m10e_execution_summary.json" if m10e_exec else "",
        f"evidence/dev_full/run_control/{m10f_exec}/m10f_execution_summary.json" if m10f_exec else "",
    ]
    source_guard_ok = len([b for b in blockers if b.get("id") == "M10-ST-B12"]) == 0
    dumpj(
        out / "m10_source_authority_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M10-ST-S2",
            "overall_pass": source_guard_ok,
            "authoritative_refs": refs,
            "evidence_bucket": bucket,
            "runtime_locality_only_control_plane": True,
        },
    )

    realism_ok = bool(packet.get("M10_STRESS_DISALLOW_WAIVED_REALISM", True))
    if not realism_ok:
        add_blocker(blockers, "M10-ST-B12", "S2", {"reason": "realism_guard_not_true"})
    dumpj(
        out / "m10_realism_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M10-ST-S2",
            "overall_pass": realism_ok,
            "disallow_waived_realism": bool(packet.get("M10_STRESS_DISALLOW_WAIVED_REALISM", True)),
        },
    )

    if not bool(packet.get("M10_STRESS_REQUIRE_DATA_ENGINE_BLACKBOX", True)):
        add_blocker(blockers, "M10-ST-B12", "S2", {"reason": "data_engine_blackbox_guard_not_true"})

    return finish(
        "S2",
        phase_execution_id,
        out,
        blockers,
        S2_ARTS,
        {
            "platform_run_id": str(s1.get("platform_run_id", "")) if s1 else "",
            "scenario_run_id": str(s1.get("scenario_run_id", "")) if s1 else "",
            "upstream_m10_s1_execution": s1_exec,
            "upstream_m10d_execution": m10d_exec,
            "m10e_execution_id": m10e_exec,
            "m10f_execution_id": m10f_exec,
            "decisions": [
                "S2 validated strict S1 continuity before executing lane E and lane F.",
                "S2 executed M10.E quality-gate adjudication and M10.F Iceberg/Glue commit verification against deterministic committed surfaces.",
            ],
            "advisories": advisories,
        },
    )


def run_s3(phase_execution_id: str, upstream_m10_s2_execution: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)
    blockers: list[dict[str, Any]] = []
    advisories: list[str] = []

    plan_text = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    packet = parse_plan_packet(plan_text)
    reg = parse_registry(REG) if REG.exists() else {}

    scripts_required = [
        "scripts/dev_substrate/m10g_manifest_fingerprint.py",
        "scripts/dev_substrate/m10h_rollback_recipe.py",
    ]
    for script_path in scripts_required:
        if not Path(script_path).exists():
            add_blocker(
                blockers,
                "M10-ST-B18",
                "S3",
                {"reason": "required_stage_script_missing", "script": script_path},
            )

    value = reg.get("S3_EVIDENCE_BUCKET")
    if value is None or is_placeholder(value):
        add_blocker(blockers, "M10-ST-B7", "S3", {"reason": "required_handle_missing_or_placeholder", "handle": "S3_EVIDENCE_BUCKET"})
    bucket = str(reg.get("S3_EVIDENCE_BUCKET", "")).strip()

    s2_exec = upstream_m10_s2_execution.strip()
    s2 = loadj(OUT_ROOT / s2_exec / "stress" / "m10_execution_summary.json") if s2_exec else {}
    if not s2:
        s2_exec, s2 = latest_s2()
    if not s2:
        add_blocker(blockers, "M10-ST-B7", "S3", {"reason": "upstream_s2_summary_missing"})
    elif not bool(s2.get("overall_pass")) or str(s2.get("next_gate", "")) != "M10_ST_S3_READY":
        add_blocker(
            blockers,
            "M10-ST-B7",
            "S3",
            {
                "reason": "upstream_s2_not_ready",
                "upstream_s2_execution": s2_exec,
                "summary": {
                    "overall_pass": s2.get("overall_pass"),
                    "next_gate": s2.get("next_gate"),
                    "open_blocker_count": s2.get("open_blocker_count"),
                },
            },
        )

    m10f_exec = str(s2.get("m10f_execution_id", "")).strip() if s2 else ""
    if not m10f_exec:
        add_blocker(blockers, "M10-ST-B7", "S3", {"reason": "missing_m10f_execution_id", "upstream_s2_execution": s2_exec})

    m10g_exec = ""
    m10g_summary: dict[str, Any] = {}
    m10g_snapshot: dict[str, Any] = {}
    if not blockers and Path("scripts/dev_substrate/m10g_manifest_fingerprint.py").exists():
        m10g_exec = f"m10g_stress_s3_{tok()}"
        m10g_dir = out / "_m10g"
        env_m10g = dict(os.environ)
        env_m10g.update(
            {
                "M10G_EXECUTION_ID": m10g_exec,
                "M10G_RUN_DIR": m10g_dir.as_posix(),
                "EVIDENCE_BUCKET": bucket,
                "UPSTREAM_M10F_EXECUTION": m10f_exec,
                "AWS_REGION": "eu-west-2",
            }
        )
        rc, _, err = run(["python", "scripts/dev_substrate/m10g_manifest_fingerprint.py"], timeout=3600, env=env_m10g)
        if rc != 0:
            add_blocker(
                blockers,
                "M10-ST-B7",
                "S3",
                {"reason": "m10g_command_failed", "stderr": err.strip()[:300], "rc": rc},
            )
        m10g_summary = loadj(m10g_dir / "m10g_execution_summary.json")
        m10g_snapshot = loadj(m10g_dir / "m10g_manifest_fingerprint_snapshot.json")
        m10g_register = loadj(m10g_dir / "m10g_blocker_register.json")
        if m10g_snapshot:
            dumpj(out / "m10g_manifest_fingerprint_snapshot.json", m10g_snapshot)
        if m10g_summary:
            dumpj(out / "m10g_execution_summary.json", m10g_summary)
        if m10g_register:
            dumpj(out / "m10g_blocker_register.json", m10g_register)
        if not m10g_summary:
            add_blocker(blockers, "M10-ST-B7", "S3", {"reason": "m10g_summary_missing"})
        elif not (bool(m10g_summary.get("overall_pass")) and str(m10g_summary.get("next_gate", "")) == "M10.H_READY"):
            add_blocker(blockers, "M10-ST-B7", "S3", {"reason": "m10g_not_ready", "summary": m10g_summary})

    m10h_exec = ""
    m10h_summary: dict[str, Any] = {}
    m10h_snapshot: dict[str, Any] = {}
    if not blockers and Path("scripts/dev_substrate/m10h_rollback_recipe.py").exists():
        m10h_exec = f"m10h_stress_s3_{tok()}"
        m10h_dir = out / "_m10h"
        env_m10h = dict(os.environ)
        env_m10h.update(
            {
                "M10H_EXECUTION_ID": m10h_exec,
                "M10H_RUN_DIR": m10h_dir.as_posix(),
                "EVIDENCE_BUCKET": bucket,
                "UPSTREAM_M10G_EXECUTION": m10g_exec,
                "AWS_REGION": "eu-west-2",
            }
        )
        rc, _, err = run(["python", "scripts/dev_substrate/m10h_rollback_recipe.py"], timeout=3600, env=env_m10h)
        if rc != 0:
            add_blocker(
                blockers,
                "M10-ST-B8",
                "S3",
                {"reason": "m10h_command_failed", "stderr": err.strip()[:300], "rc": rc},
            )
        m10h_summary = loadj(m10h_dir / "m10h_execution_summary.json")
        m10h_snapshot = loadj(m10h_dir / "m10h_rollback_recipe_snapshot.json")
        m10h_register = loadj(m10h_dir / "m10h_blocker_register.json")
        if m10h_snapshot:
            dumpj(out / "m10h_rollback_recipe_snapshot.json", m10h_snapshot)
        if m10h_summary:
            dumpj(out / "m10h_execution_summary.json", m10h_summary)
        if m10h_register:
            dumpj(out / "m10h_blocker_register.json", m10h_register)
        if not m10h_summary:
            add_blocker(blockers, "M10-ST-B8", "S3", {"reason": "m10h_summary_missing"})
        elif not (bool(m10h_summary.get("overall_pass")) and str(m10h_summary.get("next_gate", "")) == "M10.I_READY"):
            add_blocker(blockers, "M10-ST-B8", "S3", {"reason": "m10h_not_ready", "summary": m10h_summary})

    lane_matrix = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M10-ST-S3",
        "lanes": [
            {
                "lane": "G",
                "component": "M10.G",
                "execution_id": m10g_exec,
                "overall_pass": bool(m10g_summary.get("overall_pass")) if m10g_summary else False,
                "next_gate": str(m10g_summary.get("next_gate", "")) if m10g_summary else "",
            },
            {
                "lane": "H",
                "component": "M10.H",
                "execution_id": m10h_exec,
                "overall_pass": bool(m10h_summary.get("overall_pass")) if m10h_summary else False,
                "next_gate": str(m10h_summary.get("next_gate", "")) if m10h_summary else "",
            },
        ],
    }
    dumpj(out / "m10_lane_matrix.json", lane_matrix)

    runtime_locality_ok = bool(packet.get("M10_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY", True))
    if not runtime_locality_ok:
        add_blocker(blockers, "M10-ST-B12", "S3", {"reason": "runtime_locality_policy_not_true"})
    dumpj(
        out / "m10_runtime_locality_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M10-ST-S3",
            "overall_pass": runtime_locality_ok,
            "require_remote_runtime_only": bool(packet.get("M10_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY", True)),
            "runtime_execution_attempted": False,
            "runtime_execution_mode": "local_control_orchestration_only_remote_runtime",
        },
    )

    refs = [
        f"evidence/dev_full/run_control/{s2_exec}/stress/m10_execution_summary.json" if s2_exec else "",
        f"evidence/dev_full/run_control/{m10f_exec}/m10f_execution_summary.json" if m10f_exec else "",
        f"evidence/dev_full/run_control/{m10g_exec}/m10g_execution_summary.json" if m10g_exec else "",
        f"evidence/dev_full/run_control/{m10h_exec}/m10h_execution_summary.json" if m10h_exec else "",
    ]
    source_guard_ok = len([b for b in blockers if b.get("id") == "M10-ST-B12"]) == 0
    dumpj(
        out / "m10_source_authority_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M10-ST-S3",
            "overall_pass": source_guard_ok,
            "authoritative_refs": refs,
            "evidence_bucket": bucket,
            "runtime_locality_only_control_plane": True,
        },
    )

    realism_ok = bool(packet.get("M10_STRESS_DISALLOW_WAIVED_REALISM", True))
    if not realism_ok:
        add_blocker(blockers, "M10-ST-B12", "S3", {"reason": "realism_guard_not_true"})
    dumpj(
        out / "m10_realism_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M10-ST-S3",
            "overall_pass": realism_ok,
            "disallow_waived_realism": bool(packet.get("M10_STRESS_DISALLOW_WAIVED_REALISM", True)),
        },
    )

    if not bool(packet.get("M10_STRESS_REQUIRE_DATA_ENGINE_BLACKBOX", True)):
        add_blocker(blockers, "M10-ST-B12", "S3", {"reason": "data_engine_blackbox_guard_not_true"})

    return finish(
        "S3",
        phase_execution_id,
        out,
        blockers,
        S3_ARTS,
        {
            "platform_run_id": str(s2.get("platform_run_id", "")) if s2 else "",
            "scenario_run_id": str(s2.get("scenario_run_id", "")) if s2 else "",
            "upstream_m10_s2_execution": s2_exec,
            "upstream_m10f_execution": m10f_exec,
            "m10g_execution_id": m10g_exec,
            "m10h_execution_id": m10h_exec,
            "decisions": [
                "S3 validated strict S2 continuity before executing lane G and lane H.",
                "S3 executed M10.G manifest/fingerprint/time-bound audit synthesis followed by M10.H rollback recipe and deterministic non-destructive drill closure.",
            ],
            "advisories": advisories,
        },
    )


def run_s4(phase_execution_id: str, upstream_m10_s3_execution: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)
    blockers: list[dict[str, Any]] = []
    advisories: list[str] = []

    plan_text = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    packet = parse_plan_packet(plan_text)
    reg = parse_registry(REG) if REG.exists() else {}

    scripts_required = [
        "scripts/dev_substrate/m10i_p13_rollup_handoff.py",
    ]
    for script_path in scripts_required:
        if not Path(script_path).exists():
            add_blocker(
                blockers,
                "M10-ST-B18",
                "S4",
                {"reason": "required_stage_script_missing", "script": script_path},
            )

    value = reg.get("S3_EVIDENCE_BUCKET")
    if value is None or is_placeholder(value):
        add_blocker(blockers, "M10-ST-B10", "S4", {"reason": "required_handle_missing_or_placeholder", "handle": "S3_EVIDENCE_BUCKET"})
    bucket = str(reg.get("S3_EVIDENCE_BUCKET", "")).strip()

    s3_exec = upstream_m10_s3_execution.strip()
    s3 = loadj(OUT_ROOT / s3_exec / "stress" / "m10_execution_summary.json") if s3_exec else {}
    if not s3:
        s3_exec, s3 = latest_s3()
    if not s3:
        add_blocker(blockers, "M10-ST-B9", "S4", {"reason": "upstream_s3_summary_missing"})
    elif not bool(s3.get("overall_pass")) or str(s3.get("next_gate", "")) != "M10_ST_S4_READY":
        add_blocker(
            blockers,
            "M10-ST-B9",
            "S4",
            {
                "reason": "upstream_s3_not_ready",
                "upstream_s3_execution": s3_exec,
                "summary": {
                    "overall_pass": s3.get("overall_pass"),
                    "next_gate": s3.get("next_gate"),
                    "open_blocker_count": s3.get("open_blocker_count"),
                },
            },
        )

    m10g_exec = str(s3.get("m10g_execution_id", "")).strip() if s3 else ""
    m10h_exec = str(s3.get("m10h_execution_id", "")).strip() if s3 else ""
    s2_exec = str(s3.get("upstream_m10_s2_execution", "")).strip() if s3 else ""
    if not m10g_exec:
        add_blocker(blockers, "M10-ST-B9", "S4", {"reason": "missing_m10g_execution_id", "upstream_s3_execution": s3_exec})
    if not m10h_exec:
        add_blocker(blockers, "M10-ST-B9", "S4", {"reason": "missing_m10h_execution_id", "upstream_s3_execution": s3_exec})
    if not s2_exec:
        add_blocker(blockers, "M10-ST-B9", "S4", {"reason": "missing_upstream_m10_s2_execution_in_s3_summary", "upstream_s3_execution": s3_exec})

    s2 = loadj(OUT_ROOT / s2_exec / "stress" / "m10_execution_summary.json") if s2_exec else {}
    if s2_exec and not s2:
        add_blocker(blockers, "M10-ST-B9", "S4", {"reason": "upstream_s2_summary_missing", "upstream_s2_execution": s2_exec})
    elif s2_exec and (not bool(s2.get("overall_pass")) or str(s2.get("next_gate", "")) != "M10_ST_S3_READY"):
        add_blocker(
            blockers,
            "M10-ST-B9",
            "S4",
            {
                "reason": "upstream_s2_not_ready_for_m10i",
                "upstream_s2_execution": s2_exec,
                "summary": {
                    "overall_pass": s2.get("overall_pass"),
                    "next_gate": s2.get("next_gate"),
                    "open_blocker_count": s2.get("open_blocker_count"),
                },
            },
        )

    m10e_exec = str(s2.get("m10e_execution_id", "")).strip() if s2 else ""
    m10f_exec = str(s2.get("m10f_execution_id", "")).strip() if s2 else ""
    s1_exec = str(s2.get("upstream_m10_s1_execution", "")).strip() if s2 else ""
    if not m10e_exec:
        add_blocker(blockers, "M10-ST-B9", "S4", {"reason": "missing_m10e_execution_id", "upstream_s2_execution": s2_exec})
    if not m10f_exec:
        add_blocker(blockers, "M10-ST-B9", "S4", {"reason": "missing_m10f_execution_id", "upstream_s2_execution": s2_exec})
    if not s1_exec:
        add_blocker(blockers, "M10-ST-B9", "S4", {"reason": "missing_upstream_m10_s1_execution_in_s2_summary", "upstream_s2_execution": s2_exec})

    s1 = loadj(OUT_ROOT / s1_exec / "stress" / "m10_execution_summary.json") if s1_exec else {}
    if s1_exec and not s1:
        add_blocker(blockers, "M10-ST-B9", "S4", {"reason": "upstream_s1_summary_missing", "upstream_s1_execution": s1_exec})
    elif s1_exec and (not bool(s1.get("overall_pass")) or str(s1.get("next_gate", "")) != "M10_ST_S2_READY"):
        add_blocker(
            blockers,
            "M10-ST-B9",
            "S4",
            {
                "reason": "upstream_s1_not_ready_for_m10i",
                "upstream_s1_execution": s1_exec,
                "summary": {
                    "overall_pass": s1.get("overall_pass"),
                    "next_gate": s1.get("next_gate"),
                    "open_blocker_count": s1.get("open_blocker_count"),
                },
            },
        )

    m10c_exec = str(s1.get("m10c_execution_id", "")).strip() if s1 else ""
    m10d_exec = str(s1.get("m10d_execution_id", "")).strip() if s1 else ""
    s0_exec = str(s1.get("upstream_m10_s0_execution", "")).strip() if s1 else ""
    if not m10c_exec:
        add_blocker(blockers, "M10-ST-B9", "S4", {"reason": "missing_m10c_execution_id", "upstream_s1_execution": s1_exec})
    if not m10d_exec:
        add_blocker(blockers, "M10-ST-B9", "S4", {"reason": "missing_m10d_execution_id", "upstream_s1_execution": s1_exec})
    if not s0_exec:
        add_blocker(blockers, "M10-ST-B9", "S4", {"reason": "missing_upstream_m10_s0_execution_in_s1_summary", "upstream_s1_execution": s1_exec})

    s0 = loadj(OUT_ROOT / s0_exec / "stress" / "m10_execution_summary.json") if s0_exec else {}
    if s0_exec and not s0:
        add_blocker(blockers, "M10-ST-B9", "S4", {"reason": "upstream_s0_summary_missing", "upstream_s0_execution": s0_exec})
    elif s0_exec and (not bool(s0.get("overall_pass")) or str(s0.get("next_gate", "")) != "M10_ST_S1_READY"):
        add_blocker(
            blockers,
            "M10-ST-B9",
            "S4",
            {
                "reason": "upstream_s0_not_ready_for_m10i",
                "upstream_s0_execution": s0_exec,
                "summary": {
                    "overall_pass": s0.get("overall_pass"),
                    "next_gate": s0.get("next_gate"),
                    "open_blocker_count": s0.get("open_blocker_count"),
                },
            },
        )

    m10a_exec = str(s0.get("m10a_execution_id", "")).strip() if s0 else ""
    m10b_exec = str(s0.get("m10b_execution_id", "")).strip() if s0 else ""
    if not m10a_exec:
        add_blocker(blockers, "M10-ST-B9", "S4", {"reason": "missing_m10a_execution_id", "upstream_s0_execution": s0_exec})
    if not m10b_exec:
        add_blocker(blockers, "M10-ST-B9", "S4", {"reason": "missing_m10b_execution_id", "upstream_s0_execution": s0_exec})

    m10i_exec = ""
    m10i_summary: dict[str, Any] = {}
    m10i_rollup: dict[str, Any] = {}
    m10i_verdict: dict[str, Any] = {}
    m11_handoff: dict[str, Any] = {}
    m10i_register: dict[str, Any] = {}
    if not blockers and Path("scripts/dev_substrate/m10i_p13_rollup_handoff.py").exists():
        m10i_exec = f"m10i_stress_s4_{tok()}"
        m10i_dir = out / "_m10i"
        env_m10i = dict(os.environ)
        env_m10i.update(
            {
                "M10I_EXECUTION_ID": m10i_exec,
                "M10I_RUN_DIR": m10i_dir.as_posix(),
                "EVIDENCE_BUCKET": bucket,
                "UPSTREAM_M10A_EXECUTION": m10a_exec,
                "UPSTREAM_M10B_EXECUTION": m10b_exec,
                "UPSTREAM_M10C_EXECUTION": m10c_exec,
                "UPSTREAM_M10D_EXECUTION": m10d_exec,
                "UPSTREAM_M10E_EXECUTION": m10e_exec,
                "UPSTREAM_M10F_EXECUTION": m10f_exec,
                "UPSTREAM_M10G_EXECUTION": m10g_exec,
                "UPSTREAM_M10H_EXECUTION": m10h_exec,
                "AWS_REGION": "eu-west-2",
            }
        )
        rc, _, err = run(["python", "scripts/dev_substrate/m10i_p13_rollup_handoff.py"], timeout=3600, env=env_m10i)
        if rc != 0:
            add_blocker(blockers, "M10-ST-B9", "S4", {"reason": "m10i_command_failed", "stderr": err.strip()[:300], "rc": rc})
        m10i_summary = loadj(m10i_dir / "m10i_execution_summary.json")
        m10i_rollup = loadj(m10i_dir / "m10i_p13_rollup_matrix.json")
        m10i_verdict = loadj(m10i_dir / "m10i_p13_gate_verdict.json")
        m11_handoff = loadj(m10i_dir / "m11_handoff_pack.json")
        m10i_register = loadj(m10i_dir / "m10i_blocker_register.json")
        if m10i_rollup:
            dumpj(out / "m10i_p13_rollup_matrix.json", m10i_rollup)
        if m10i_verdict:
            dumpj(out / "m10i_p13_gate_verdict.json", m10i_verdict)
        if m11_handoff:
            dumpj(out / "m11_handoff_pack.json", m11_handoff)
        if m10i_register:
            dumpj(out / "m10i_blocker_register.json", m10i_register)
        if m10i_summary:
            dumpj(out / "m10i_execution_summary.json", m10i_summary)
        if not m10i_summary:
            add_blocker(blockers, "M10-ST-B9", "S4", {"reason": "m10i_summary_missing"})
        else:
            pass_posture = (
                bool(m10i_summary.get("overall_pass"))
                and str(m10i_summary.get("verdict", "")) == "ADVANCE_TO_P14"
                and str(m10i_summary.get("next_gate", "")) == "M11_READY"
            )
            if not pass_posture:
                row_blockers = m10i_register.get("blockers", []) if isinstance(m10i_register.get("blockers", []), list) else []
                blocker_codes = sorted(
                    {
                        str(b.get("code", "")).strip()
                        for b in row_blockers
                        if isinstance(b, dict) and str(b.get("code", "")).strip()
                    }
                )
                if "M10-B12" in blocker_codes:
                    add_blocker(
                        blockers,
                        "M10-ST-B12",
                        "S4",
                        {"reason": "m10i_artifact_publication_failure", "summary": m10i_summary, "blocker_codes": blocker_codes},
                    )
                if "M10-B10" in blocker_codes:
                    add_blocker(
                        blockers,
                        "M10-ST-B10",
                        "S4",
                        {"reason": "m10i_handoff_not_ready", "summary": m10i_summary, "blocker_codes": blocker_codes},
                    )
                if ("M10-B9" in blocker_codes) or (not blocker_codes):
                    add_blocker(
                        blockers,
                        "M10-ST-B9",
                        "S4",
                        {"reason": "m10i_rollup_not_ready", "summary": m10i_summary, "blocker_codes": blocker_codes},
                    )

    lane_matrix = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M10-ST-S4",
        "lanes": [
            {
                "lane": "I",
                "component": "M10.I",
                "execution_id": m10i_exec,
                "overall_pass": bool(m10i_summary.get("overall_pass")) if m10i_summary else False,
                "next_gate": str(m10i_summary.get("next_gate", "")) if m10i_summary else "",
                "verdict": str(m10i_summary.get("verdict", "")) if m10i_summary else "",
            },
        ],
    }
    dumpj(out / "m10_lane_matrix.json", lane_matrix)

    runtime_locality_ok = bool(packet.get("M10_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY", True))
    if not runtime_locality_ok:
        add_blocker(blockers, "M10-ST-B12", "S4", {"reason": "runtime_locality_policy_not_true"})
    dumpj(
        out / "m10_runtime_locality_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M10-ST-S4",
            "overall_pass": runtime_locality_ok,
            "require_remote_runtime_only": bool(packet.get("M10_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY", True)),
            "runtime_execution_attempted": False,
            "runtime_execution_mode": "local_control_orchestration_only_remote_runtime",
        },
    )

    refs = [
        f"evidence/dev_full/run_control/{s3_exec}/stress/m10_execution_summary.json" if s3_exec else "",
        f"evidence/dev_full/run_control/{m10a_exec}/m10a_execution_summary.json" if m10a_exec else "",
        f"evidence/dev_full/run_control/{m10b_exec}/m10b_execution_summary.json" if m10b_exec else "",
        f"evidence/dev_full/run_control/{m10c_exec}/m10c_execution_summary.json" if m10c_exec else "",
        f"evidence/dev_full/run_control/{m10d_exec}/m10d_execution_summary.json" if m10d_exec else "",
        f"evidence/dev_full/run_control/{m10e_exec}/m10e_execution_summary.json" if m10e_exec else "",
        f"evidence/dev_full/run_control/{m10f_exec}/m10f_execution_summary.json" if m10f_exec else "",
        f"evidence/dev_full/run_control/{m10g_exec}/m10g_execution_summary.json" if m10g_exec else "",
        f"evidence/dev_full/run_control/{m10h_exec}/m10h_execution_summary.json" if m10h_exec else "",
        f"evidence/dev_full/run_control/{m10i_exec}/m10i_execution_summary.json" if m10i_exec else "",
    ]
    source_guard_ok = len([b for b in blockers if b.get("id") == "M10-ST-B12"]) == 0
    dumpj(
        out / "m10_source_authority_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M10-ST-S4",
            "overall_pass": source_guard_ok,
            "authoritative_refs": refs,
            "evidence_bucket": bucket,
            "runtime_locality_only_control_plane": True,
        },
    )

    realism_ok = bool(packet.get("M10_STRESS_DISALLOW_WAIVED_REALISM", True))
    if not realism_ok:
        add_blocker(blockers, "M10-ST-B12", "S4", {"reason": "realism_guard_not_true"})
    dumpj(
        out / "m10_realism_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M10-ST-S4",
            "overall_pass": realism_ok,
            "disallow_waived_realism": bool(packet.get("M10_STRESS_DISALLOW_WAIVED_REALISM", True)),
        },
    )

    if not bool(packet.get("M10_STRESS_REQUIRE_DATA_ENGINE_BLACKBOX", True)):
        add_blocker(blockers, "M10-ST-B12", "S4", {"reason": "data_engine_blackbox_guard_not_true"})

    return finish(
        "S4",
        phase_execution_id,
        out,
        blockers,
        S4_ARTS,
        {
            "platform_run_id": str(s3.get("platform_run_id", "")) if s3 else "",
            "scenario_run_id": str(s3.get("scenario_run_id", "")) if s3 else "",
            "upstream_m10_s3_execution": s3_exec,
            "upstream_m10_s2_execution": s2_exec,
            "upstream_m10_s1_execution": s1_exec,
            "upstream_m10_s0_execution": s0_exec,
            "m10i_execution_id": m10i_exec,
            "decisions": [
                "S4 recovered strict continuity for M10.A..M10.H from the green S3 chain before lane I execution.",
                "S4 executed M10.I deterministic P13 rollup and M11 handoff publication with fail-closed mapping across rollup/handoff/parity blocker classes.",
            ],
            "advisories": advisories,
        },
    )


def run_s5(phase_execution_id: str, upstream_m10_s4_execution: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)
    blockers: list[dict[str, Any]] = []
    advisories: list[str] = []

    plan_text = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    packet = parse_plan_packet(plan_text)
    reg = parse_registry(REG) if REG.exists() else {}

    scripts_required = [
        "scripts/dev_substrate/m10j_closure_sync.py",
    ]
    for script_path in scripts_required:
        if not Path(script_path).exists():
            add_blocker(
                blockers,
                "M10-ST-B18",
                "S5",
                {"reason": "required_stage_script_missing", "script": script_path},
            )

    value = reg.get("S3_EVIDENCE_BUCKET")
    if value is None or is_placeholder(value):
        add_blocker(blockers, "M10-ST-B11", "S5", {"reason": "required_handle_missing_or_placeholder", "handle": "S3_EVIDENCE_BUCKET"})
    bucket = str(reg.get("S3_EVIDENCE_BUCKET", "")).strip()

    s4_exec = upstream_m10_s4_execution.strip()
    s4 = loadj(OUT_ROOT / s4_exec / "stress" / "m10_execution_summary.json") if s4_exec else {}
    if not s4:
        s4_exec, s4 = latest_s4()
    if not s4:
        add_blocker(blockers, "M10-ST-B11", "S5", {"reason": "upstream_s4_summary_missing"})
    elif not bool(s4.get("overall_pass")) or str(s4.get("next_gate", "")) != "M10_ST_S5_READY":
        add_blocker(
            blockers,
            "M10-ST-B11",
            "S5",
            {
                "reason": "upstream_s4_not_ready",
                "upstream_s4_execution": s4_exec,
                "summary": {
                    "overall_pass": s4.get("overall_pass"),
                    "next_gate": s4.get("next_gate"),
                    "open_blocker_count": s4.get("open_blocker_count"),
                },
            },
        )

    m10i_exec = str(s4.get("m10i_execution_id", "")).strip() if s4 else ""
    s3_exec = str(s4.get("upstream_m10_s3_execution", "")).strip() if s4 else ""
    s2_exec = str(s4.get("upstream_m10_s2_execution", "")).strip() if s4 else ""
    s1_exec = str(s4.get("upstream_m10_s1_execution", "")).strip() if s4 else ""
    s0_exec = str(s4.get("upstream_m10_s0_execution", "")).strip() if s4 else ""
    if not m10i_exec:
        add_blocker(blockers, "M10-ST-B11", "S5", {"reason": "missing_m10i_execution_id", "upstream_s4_execution": s4_exec})
    if not s3_exec:
        add_blocker(blockers, "M10-ST-B11", "S5", {"reason": "missing_upstream_m10_s3_execution_in_s4_summary", "upstream_s4_execution": s4_exec})
    if not s2_exec:
        add_blocker(blockers, "M10-ST-B11", "S5", {"reason": "missing_upstream_m10_s2_execution_in_s4_summary", "upstream_s4_execution": s4_exec})
    if not s1_exec:
        add_blocker(blockers, "M10-ST-B11", "S5", {"reason": "missing_upstream_m10_s1_execution_in_s4_summary", "upstream_s4_execution": s4_exec})
    if not s0_exec:
        add_blocker(blockers, "M10-ST-B11", "S5", {"reason": "missing_upstream_m10_s0_execution_in_s4_summary", "upstream_s4_execution": s4_exec})

    s3 = loadj(OUT_ROOT / s3_exec / "stress" / "m10_execution_summary.json") if s3_exec else {}
    if s3_exec and not s3:
        add_blocker(blockers, "M10-ST-B11", "S5", {"reason": "upstream_s3_summary_missing", "upstream_s3_execution": s3_exec})
    elif s3_exec and (not bool(s3.get("overall_pass")) or str(s3.get("next_gate", "")) != "M10_ST_S4_READY"):
        add_blocker(
            blockers,
            "M10-ST-B11",
            "S5",
            {
                "reason": "upstream_s3_not_ready_for_m10j",
                "upstream_s3_execution": s3_exec,
                "summary": {
                    "overall_pass": s3.get("overall_pass"),
                    "next_gate": s3.get("next_gate"),
                    "open_blocker_count": s3.get("open_blocker_count"),
                },
            },
        )

    s2 = loadj(OUT_ROOT / s2_exec / "stress" / "m10_execution_summary.json") if s2_exec else {}
    if s2_exec and not s2:
        add_blocker(blockers, "M10-ST-B11", "S5", {"reason": "upstream_s2_summary_missing", "upstream_s2_execution": s2_exec})
    elif s2_exec and (not bool(s2.get("overall_pass")) or str(s2.get("next_gate", "")) != "M10_ST_S3_READY"):
        add_blocker(
            blockers,
            "M10-ST-B11",
            "S5",
            {
                "reason": "upstream_s2_not_ready_for_m10j",
                "upstream_s2_execution": s2_exec,
                "summary": {
                    "overall_pass": s2.get("overall_pass"),
                    "next_gate": s2.get("next_gate"),
                    "open_blocker_count": s2.get("open_blocker_count"),
                },
            },
        )

    s1 = loadj(OUT_ROOT / s1_exec / "stress" / "m10_execution_summary.json") if s1_exec else {}
    if s1_exec and not s1:
        add_blocker(blockers, "M10-ST-B11", "S5", {"reason": "upstream_s1_summary_missing", "upstream_s1_execution": s1_exec})
    elif s1_exec and (not bool(s1.get("overall_pass")) or str(s1.get("next_gate", "")) != "M10_ST_S2_READY"):
        add_blocker(
            blockers,
            "M10-ST-B11",
            "S5",
            {
                "reason": "upstream_s1_not_ready_for_m10j",
                "upstream_s1_execution": s1_exec,
                "summary": {
                    "overall_pass": s1.get("overall_pass"),
                    "next_gate": s1.get("next_gate"),
                    "open_blocker_count": s1.get("open_blocker_count"),
                },
            },
        )

    s0 = loadj(OUT_ROOT / s0_exec / "stress" / "m10_execution_summary.json") if s0_exec else {}
    if s0_exec and not s0:
        add_blocker(blockers, "M10-ST-B11", "S5", {"reason": "upstream_s0_summary_missing", "upstream_s0_execution": s0_exec})
    elif s0_exec and (not bool(s0.get("overall_pass")) or str(s0.get("next_gate", "")) != "M10_ST_S1_READY"):
        add_blocker(
            blockers,
            "M10-ST-B11",
            "S5",
            {
                "reason": "upstream_s0_not_ready_for_m10j",
                "upstream_s0_execution": s0_exec,
                "summary": {
                    "overall_pass": s0.get("overall_pass"),
                    "next_gate": s0.get("next_gate"),
                    "open_blocker_count": s0.get("open_blocker_count"),
                },
            },
        )

    m10a_exec = str(s0.get("m10a_execution_id", "")).strip() if s0 else ""
    m10b_exec = str(s0.get("m10b_execution_id", "")).strip() if s0 else ""
    m10c_exec = str(s1.get("m10c_execution_id", "")).strip() if s1 else ""
    m10d_exec = str(s1.get("m10d_execution_id", "")).strip() if s1 else ""
    m10e_exec = str(s2.get("m10e_execution_id", "")).strip() if s2 else ""
    m10f_exec = str(s2.get("m10f_execution_id", "")).strip() if s2 else ""
    m10g_exec = str(s3.get("m10g_execution_id", "")).strip() if s3 else ""
    m10h_exec = str(s3.get("m10h_execution_id", "")).strip() if s3 else ""
    required_ids = {
        "m10a_execution_id": m10a_exec,
        "m10b_execution_id": m10b_exec,
        "m10c_execution_id": m10c_exec,
        "m10d_execution_id": m10d_exec,
        "m10e_execution_id": m10e_exec,
        "m10f_execution_id": m10f_exec,
        "m10g_execution_id": m10g_exec,
        "m10h_execution_id": m10h_exec,
        "m10i_execution_id": m10i_exec,
    }
    missing_required_ids = [k for k, v in required_ids.items() if not str(v).strip()]
    if missing_required_ids:
        add_blocker(blockers, "M10-ST-B11", "S5", {"reason": "unresolved_upstream_execution_ids", "fields": missing_required_ids})

    platform_ids = {
        str(v).strip()
        for v in [
            s0.get("platform_run_id"),
            s1.get("platform_run_id"),
            s2.get("platform_run_id"),
            s3.get("platform_run_id"),
            s4.get("platform_run_id"),
        ]
        if str(v or "").strip()
    }
    if len(platform_ids) != 1:
        add_blocker(blockers, "M10-ST-B11", "S5", {"reason": "platform_run_scope_mismatch", "platform_run_ids": sorted(platform_ids)})
    platform_run_id = sorted(platform_ids)[0] if len(platform_ids) == 1 else ""
    scenario_ids = {
        str(v).strip()
        for v in [
            s0.get("scenario_run_id"),
            s1.get("scenario_run_id"),
            s2.get("scenario_run_id"),
            s3.get("scenario_run_id"),
            s4.get("scenario_run_id"),
        ]
        if str(v or "").strip()
    }
    if len(scenario_ids) != 1:
        add_blocker(blockers, "M10-ST-B11", "S5", {"reason": "scenario_run_scope_mismatch", "scenario_run_ids": sorted(scenario_ids)})
    scenario_run_id = sorted(scenario_ids)[0] if len(scenario_ids) == 1 else ""

    m10j_exec = ""
    m10j_summary: dict[str, Any] = {}
    m10j_exec_summary: dict[str, Any] = {}
    m10j_blocker_register: dict[str, Any] = {}
    m10j_budget_envelope: dict[str, Any] = {}
    m10j_cost_receipt: dict[str, Any] = {}
    if not blockers and Path("scripts/dev_substrate/m10j_closure_sync.py").exists():
        m10j_exec = f"m10j_stress_s5_{tok()}"
        m10j_local_root = out / "_m10j_local"
        rc, _, err = run(
            [
                "python",
                "scripts/dev_substrate/m10j_closure_sync.py",
                "--execution-id",
                m10j_exec,
                "--platform-run-id",
                platform_run_id,
                "--scenario-run-id",
                scenario_run_id,
                "--upstream-m10a-execution",
                m10a_exec,
                "--upstream-m10b-execution",
                m10b_exec,
                "--upstream-m10c-execution",
                m10c_exec,
                "--upstream-m10d-execution",
                m10d_exec,
                "--upstream-m10e-execution",
                m10e_exec,
                "--upstream-m10f-execution",
                m10f_exec,
                "--upstream-m10g-execution",
                m10g_exec,
                "--upstream-m10h-execution",
                m10h_exec,
                "--upstream-m10i-execution",
                m10i_exec,
                "--evidence-bucket",
                bucket,
                "--region",
                "eu-west-2",
                "--local-output-root",
                m10j_local_root.as_posix(),
                "--monthly-limit-amount",
                str(packet.get("M10_STRESS_MAX_SPEND_USD", 130)),
            ],
            timeout=1800,
        )
        if rc != 0:
            add_blocker(blockers, "M10-ST-B11", "S5", {"reason": "m10j_command_failed", "stderr": err.strip()[:300], "rc": rc})

        m10j_dir = m10j_local_root / m10j_exec
        m10j_summary = loadj(m10j_dir / "m10_execution_summary.json")
        m10j_exec_summary = loadj(m10j_dir / "m10j_execution_summary.json")
        m10j_blocker_register = loadj(m10j_dir / "m10j_blocker_register.json")
        m10j_budget_envelope = loadj(m10j_dir / "m10_phase_budget_envelope.json")
        m10j_cost_receipt = loadj(m10j_dir / "m10_phase_cost_outcome_receipt.json")

        if not m10j_exec_summary:
            add_blocker(blockers, "M10-ST-B11", "S5", {"reason": "m10j_execution_summary_missing"})
        if not m10j_budget_envelope:
            add_blocker(blockers, "M10-ST-B12", "S5", {"reason": "m10_phase_budget_envelope_missing"})
        if not m10j_cost_receipt:
            add_blocker(blockers, "M10-ST-B12", "S5", {"reason": "m10_phase_cost_outcome_receipt_missing"})

        source_blockers = m10j_blocker_register.get("blockers", []) if isinstance(m10j_blocker_register, dict) else []
        if isinstance(source_blockers, list):
            for sb in source_blockers:
                if not isinstance(sb, dict):
                    continue
                code = str(sb.get("code", "")).strip()
                message = str(sb.get("message", "")).strip()
                if code == "M10-B12":
                    add_blocker(blockers, "M10-ST-B12", "S5", {"reason": "m10j_blocker", "source_code": code, "message": message})
                elif code == "M10-B11":
                    add_blocker(blockers, "M10-ST-B11", "S5", {"reason": "m10j_blocker", "source_code": code, "message": message})

        if m10j_exec_summary and not (
            bool(m10j_exec_summary.get("overall_pass"))
            and str(m10j_exec_summary.get("verdict", "")) == "ADVANCE_TO_M11"
            and str(m10j_exec_summary.get("next_gate", "")) == "M11_READY"
        ):
            add_blocker(blockers, "M10-ST-B11", "S5", {"reason": "m10j_not_ready", "summary": m10j_exec_summary})

    if m10j_exec_summary:
        dumpj(out / "m10j_execution_summary.json", m10j_exec_summary)
    if m10j_blocker_register:
        dumpj(out / "m10j_blocker_register.json", m10j_blocker_register)
    if m10j_budget_envelope:
        dumpj(out / "m10_phase_budget_envelope.json", m10j_budget_envelope)
    if m10j_cost_receipt:
        dumpj(out / "m10_phase_cost_outcome_receipt.json", m10j_cost_receipt)

    runtime_locality_ok = bool(packet.get("M10_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY", True))
    dumpj(
        out / "m10_runtime_locality_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M10-ST-S5",
            "overall_pass": runtime_locality_ok,
            "require_remote_runtime_only": bool(packet.get("M10_STRESS_REQUIRE_REMOTE_RUNTIME_ONLY", True)),
            "runtime_execution_attempted": False,
            "runtime_execution_mode": "none_in_s5_validations",
        },
    )
    if not runtime_locality_ok:
        add_blocker(blockers, "M10-ST-B16", "S5", {"reason": "runtime_locality_policy_not_true"})

    refs = [
        f"evidence/dev_full/run_control/{m10a_exec}/m10a_execution_summary.json" if m10a_exec else "",
        f"evidence/dev_full/run_control/{m10b_exec}/m10b_execution_summary.json" if m10b_exec else "",
        f"evidence/dev_full/run_control/{m10c_exec}/m10c_execution_summary.json" if m10c_exec else "",
        f"evidence/dev_full/run_control/{m10d_exec}/m10d_execution_summary.json" if m10d_exec else "",
        f"evidence/dev_full/run_control/{m10e_exec}/m10e_execution_summary.json" if m10e_exec else "",
        f"evidence/dev_full/run_control/{m10f_exec}/m10f_execution_summary.json" if m10f_exec else "",
        f"evidence/dev_full/run_control/{m10g_exec}/m10g_execution_summary.json" if m10g_exec else "",
        f"evidence/dev_full/run_control/{m10h_exec}/m10h_execution_summary.json" if m10h_exec else "",
        f"evidence/dev_full/run_control/{m10i_exec}/m10i_execution_summary.json" if m10i_exec else "",
        f"evidence/dev_full/run_control/{m10j_exec}/m10j_execution_summary.json" if m10j_exec else "",
    ]
    source_guard_ok = len([b for b in blockers if b.get("id") in {"M10-ST-B12", "M10-ST-B16"}]) == 0
    dumpj(
        out / "m10_source_authority_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M10-ST-S5",
            "overall_pass": source_guard_ok,
            "authoritative_refs": refs,
            "evidence_bucket": bucket,
        },
    )

    realism_ok = bool(packet.get("M10_STRESS_DISALLOW_WAIVED_REALISM", True))
    if not realism_ok:
        add_blocker(blockers, "M10-ST-B17", "S5", {"reason": "realism_guard_not_true"})
    dumpj(
        out / "m10_realism_guard_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M10-ST-S5",
            "overall_pass": realism_ok,
            "disallow_waived_realism": bool(packet.get("M10_STRESS_DISALLOW_WAIVED_REALISM", True)),
        },
    )

    if not bool(packet.get("M10_STRESS_REQUIRE_DATA_ENGINE_BLACKBOX", True)):
        add_blocker(blockers, "M10-ST-B16", "S5", {"reason": "data_engine_blackbox_guard_not_true"})

    return finish(
        "S5",
        phase_execution_id,
        out,
        blockers,
        S5_ARTS,
        {
            "platform_run_id": platform_run_id,
            "scenario_run_id": scenario_run_id,
            "upstream_m10_s4_execution": s4_exec,
            "upstream_m10_s3_execution": s3_exec,
            "upstream_m10_s2_execution": s2_exec,
            "upstream_m10_s1_execution": s1_exec,
            "upstream_m10_s0_execution": s0_exec,
            "m10j_execution_id": m10j_exec,
            "m10a_execution_id": m10a_exec,
            "m10b_execution_id": m10b_exec,
            "m10c_execution_id": m10c_exec,
            "m10d_execution_id": m10d_exec,
            "m10e_execution_id": m10e_exec,
            "m10f_execution_id": m10f_exec,
            "m10g_execution_id": m10g_exec,
            "m10h_execution_id": m10h_exec,
            "m10i_execution_id": m10i_exec,
            "decisions": [
                "S5 executed M10.J closure sync and cost-outcome publication against strict upstream chain A..I.",
                "S5 enforced deterministic final closure posture (`ADVANCE_TO_M11`, `M11_READY`) with fail-closed blocker mapping for cost, parity, locality, and realism.",
            ],
            "advisories": advisories,
        },
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="M10 stress runner")
    ap.add_argument("--stage", required=True, choices=["S0", "S1", "S2", "S3", "S4", "S5"])
    ap.add_argument("--phase-execution-id", default="")
    ap.add_argument("--upstream-m9-s5-execution", default="")
    ap.add_argument("--upstream-m10-s0-execution", default="")
    ap.add_argument("--upstream-m10-s1-execution", default="")
    ap.add_argument("--upstream-m10-s2-execution", default="")
    ap.add_argument("--upstream-m10-s3-execution", default="")
    ap.add_argument("--upstream-m10-s4-execution", default="")
    args = ap.parse_args()

    phase_execution_id = args.phase_execution_id.strip()
    if not phase_execution_id:
        if args.stage == "S0":
            phase_execution_id = f"m10_stress_s0_{tok()}"
        elif args.stage == "S1":
            phase_execution_id = f"m10_stress_s1_{tok()}"
        elif args.stage == "S2":
            phase_execution_id = f"m10_stress_s2_{tok()}"
        elif args.stage == "S3":
            phase_execution_id = f"m10_stress_s3_{tok()}"
        elif args.stage == "S4":
            phase_execution_id = f"m10_stress_s4_{tok()}"
        elif args.stage == "S5":
            phase_execution_id = f"m10_stress_s5_{tok()}"

    if args.stage == "S0":
        upstream_m9_s5 = args.upstream_m9_s5_execution.strip()
        if not upstream_m9_s5:
            upstream_m9_s5, _ = latest_m9_s5()
        if not upstream_m9_s5:
            raise SystemExit("No upstream M9 S5 execution provided/found.")
        return run_s0(phase_execution_id, upstream_m9_s5)

    if args.stage == "S1":
        upstream_m10_s0 = args.upstream_m10_s0_execution.strip()
        if not upstream_m10_s0:
            upstream_m10_s0, _ = latest_s0()
        if not upstream_m10_s0:
            raise SystemExit("No upstream M10 S0 execution provided/found.")
        return run_s1(phase_execution_id, upstream_m10_s0)

    if args.stage == "S2":
        upstream_m10_s1 = args.upstream_m10_s1_execution.strip()
        if not upstream_m10_s1:
            upstream_m10_s1, _ = latest_s1()
        if not upstream_m10_s1:
            raise SystemExit("No upstream M10 S1 execution provided/found.")
        return run_s2(phase_execution_id, upstream_m10_s1)

    if args.stage == "S3":
        upstream_m10_s2 = args.upstream_m10_s2_execution.strip()
        if not upstream_m10_s2:
            upstream_m10_s2, _ = latest_s2()
        if not upstream_m10_s2:
            raise SystemExit("No upstream M10 S2 execution provided/found.")
        return run_s3(phase_execution_id, upstream_m10_s2)

    if args.stage == "S4":
        upstream_m10_s3 = args.upstream_m10_s3_execution.strip()
        if not upstream_m10_s3:
            upstream_m10_s3, _ = latest_s3()
        if not upstream_m10_s3:
            raise SystemExit("No upstream M10 S3 execution provided/found.")
        return run_s4(phase_execution_id, upstream_m10_s3)

    if args.stage == "S5":
        upstream_m10_s4 = args.upstream_m10_s4_execution.strip()
        if not upstream_m10_s4:
            upstream_m10_s4, _ = latest_s4()
        if not upstream_m10_s4:
            raise SystemExit("No upstream M10 S4 execution provided/found.")
        return run_s5(phase_execution_id, upstream_m10_s4)

    raise SystemExit("Unsupported stage")


if __name__ == "__main__":
    raise SystemExit(main())
