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
    else:
        next_gate = "HOLD_REMEDIATE"
    verdict = "GO" if overall_pass else "HOLD_REMEDIATE"

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


def main() -> int:
    ap = argparse.ArgumentParser(description="M10 stress runner")
    ap.add_argument("--stage", required=True, choices=["S0"])
    ap.add_argument("--phase-execution-id", default="")
    ap.add_argument("--upstream-m9-s5-execution", default="")
    args = ap.parse_args()

    phase_execution_id = args.phase_execution_id.strip()
    if not phase_execution_id:
        phase_execution_id = f"m10_stress_s0_{tok()}"

    upstream_m9_s5 = args.upstream_m9_s5_execution.strip()
    if not upstream_m9_s5:
        upstream_m9_s5, _ = latest_m9_s5()
    if not upstream_m9_s5:
        raise SystemExit("No upstream M9 S5 execution provided/found.")

    return run_s0(phase_execution_id, upstream_m9_s5)


if __name__ == "__main__":
    raise SystemExit(main())
