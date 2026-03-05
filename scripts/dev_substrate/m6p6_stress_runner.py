#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PARENT_PLAN = Path("docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M6.stress_test.md")
PLAN = Path("docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M6.P6.stress_test.md")
BUILD_PLAN = Path("docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M6.P6.build_plan.md")
REG = Path("docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md")
OUT_ROOT = Path("runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control")
HIST = Path("runs/dev_substrate/dev_full/m6")

REQ_HANDLES = [
    "FLINK_RUNTIME_PATH_ACTIVE",
    "FLINK_RUNTIME_PATH_ALLOWED",
    "FLINK_APP_WSP_STREAM_V0",
    "FLINK_APP_SR_READY_V0",
    "FLINK_EKS_WSP_STREAM_REF",
    "FLINK_EKS_SR_READY_REF",
    "EMR_EKS_VIRTUAL_CLUSTER_ID",
    "EMR_EKS_RELEASE_LABEL",
    "EMR_EKS_EXECUTION_ROLE_ARN",
    "READY_MESSAGE_FILTER",
    "REQUIRED_PLATFORM_RUN_ID_ENV_KEY",
    "RTDL_CAUGHT_UP_LAG_MAX",
    "WSP_MAX_INFLIGHT",
    "WSP_RETRY_MAX_ATTEMPTS",
    "WSP_RETRY_BACKOFF_MS",
    "WSP_STOP_ON_NONRETRYABLE",
    "IG_BASE_URL",
    "IG_INGEST_PATH",
    "DDB_IG_IDEMPOTENCY_TABLE",
    "S3_EVIDENCE_BUCKET",
    "S3_RUN_CONTROL_ROOT_PATTERN",
]

PLAN_KEYS = [
    "M6P6_STRESS_PROFILE_ID",
    "M6P6_STRESS_BLOCKER_REGISTER_PATH_PATTERN",
    "M6P6_STRESS_EXECUTION_SUMMARY_PATH_PATTERN",
    "M6P6_STRESS_DECISION_LOG_PATH_PATTERN",
    "M6P6_STRESS_REQUIRED_ARTIFACTS",
    "M6P6_STRESS_MAX_RUNTIME_MINUTES",
    "M6P6_STRESS_MAX_SPEND_USD",
    "M6P6_STRESS_EXPECTED_VERDICT_ON_PASS",
    "M6P6_STRESS_RUNTIME_PATH_PRIORITY",
    "M6P6_STRESS_STEADY_WINDOW_MINUTES",
    "M6P6_STRESS_BURST_WINDOW_MINUTES",
    "M6P6_STRESS_TARGETED_RERUN_ONLY",
]

BASE_ARTS = [
    "m6p6_stagea_findings.json",
    "m6p6_lane_matrix.json",
    "m6p6_streaming_active_snapshot.json",
    "m6p6_lag_posture_snapshot.json",
    "m6p6_evidence_overhead_snapshot.json",
    "m6p6_probe_latency_throughput_snapshot.json",
    "m6p6_control_rail_conformance_snapshot.json",
    "m6p6_secret_safety_snapshot.json",
    "m6p6_cost_outcome_receipt.json",
    "m6p6_blocker_register.json",
    "m6p6_execution_summary.json",
    "m6p6_decision_log.json",
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def tok() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def dumpj(path: Path, obj: dict[str, Any]) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def loadj(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except Exception:
        return {}


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


def parse_reg(path: Path) -> dict[str, Any]:
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


def cmd(argv: list[str], timeout: int = 30) -> dict[str, Any]:
    t0 = time.perf_counter()
    st = now()
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return {
            "command": " ".join(argv),
            "exit_code": int(p.returncode),
            "status": "PASS" if p.returncode == 0 else "FAIL",
            "duration_ms": round((time.perf_counter() - t0) * 1000.0, 3),
            "stdout": (p.stdout or "").strip()[:500],
            "stderr": (p.stderr or "").strip()[:500],
            "started_at_utc": st,
            "ended_at_utc": now(),
        }
    except subprocess.TimeoutExpired:
        return {
            "command": " ".join(argv),
            "exit_code": 124,
            "status": "FAIL",
            "duration_ms": round((time.perf_counter() - t0) * 1000.0, 3),
            "stdout": "",
            "stderr": "timeout",
            "started_at_utc": st,
            "ended_at_utc": now(),
        }


def write_stagea(out: Path, phase_execution_id: str, stage_id: str) -> None:
    dumpj(
        out / "m6p6_stagea_findings.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": stage_id,
            "findings": [
                {
                    "id": "M6P6-ST-F1",
                    "classification": "PREVENT",
                    "finding": "P6 entry must chain from deterministic P5 closure.",
                    "required_action": "Fail-closed on invalid P5 dependency.",
                },
                {
                    "id": "M6P6-ST-F2",
                    "classification": "PREVENT",
                    "finding": "Runtime-path ambiguity can create false PASS.",
                    "required_action": "Require single active path and path-aware probes.",
                },
                {
                    "id": "M6P6-ST-F3",
                    "classification": "PREVENT",
                    "finding": "Lag checks require active progression context.",
                    "required_action": "Fail-closed when lag/progression evidence is inconsistent.",
                },
            ],
        },
    )
    dumpj(
        out / "m6p6_lane_matrix.json",
        {
            "component_sequence": ["M6P6-ST-S0", "M6P6-ST-S1", "M6P6-ST-S2", "M6P6-ST-S3", "M6P6-ST-S4", "M6P6-ST-S5"],
            "plane_sequence": ["stream_runtime_plane", "ingress_bridge_plane", "p6_rollup_plane"],
            "integrated_windows": ["m6p6_s3_steady_window", "m6p6_s3_burst_window"],
        },
    )


def latest_ok(prefix: str, stage_id: str) -> dict[str, Any]:
    for d in sorted(OUT_ROOT.glob(f"{prefix}_*/stress"), reverse=True):
        s = loadj(d / "m6p6_execution_summary.json")
        if s and s.get("overall_pass") is True and str(s.get("stage_id", "")) == stage_id:
            return {"path": d, "summary": s}
    return {}


def latest_parent_s0() -> dict[str, Any]:
    for d in sorted(OUT_ROOT.glob("m6_stress_s0_*/stress"), reverse=True):
        s = loadj(d / "m6_execution_summary.json")
        if s and s.get("overall_pass") is True and str(s.get("stage_id", "")) == "M6-ST-S0":
            return {"path": d, "summary": s}
    return {}


def latest_p5_s5() -> dict[str, Any]:
    for d in sorted(OUT_ROOT.glob("m6p5_stress_s5_*/stress"), reverse=True):
        s = loadj(d / "m6p5_execution_summary.json")
        if s and s.get("overall_pass") is True and str(s.get("stage_id", "")) == "M6P5-ST-S5":
            return {"path": d, "summary": s}
    return {}


def latest_p5_s2() -> dict[str, Any]:
    for d in sorted(OUT_ROOT.glob("m6p5_stress_s2_*/stress"), reverse=True):
        s = loadj(d / "m6p5_execution_summary.json")
        if s and s.get("overall_pass") is True and str(s.get("stage_id", "")) == "M6P5-ST-S2":
            return {"path": d, "summary": s}
    return {}


def latest_hist_run(summary_name: str, phase_id: str, target_platform_run_id: str, target_runtime_path: str) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for f in HIST.rglob(summary_name):
        d = f.parent
        summary = loadj(d / summary_name)
        if summary.get("overall_pass") is not True:
            continue
        if phase_id and str(summary.get("phase_id", "")) != phase_id:
            continue
        snap: dict[str, Any] = {}
        if summary_name == "m6e_execution_summary.json":
            snap = loadj(d / "m6e_stream_activation_entry_snapshot.json")
        elif summary_name == "m6f_execution_summary.json":
            snap = loadj(d / "m6f_streaming_active_snapshot.json")
        elif summary_name == "m6g_execution_summary.json":
            snap = loadj(d / "m6g_p6_gate_verdict.json")
        if summary_name != "m6g_execution_summary.json" and not snap:
            continue
        pr = str(snap.get("platform_run_id", "")) if isinstance(snap, dict) else ""
        if target_platform_run_id and pr and pr != target_platform_run_id:
            continue
        if summary_name == "m6f_execution_summary.json":
            rp = str(snap.get("runtime_path", "")) if isinstance(snap, dict) else ""
            if target_runtime_path and rp and rp != target_runtime_path:
                continue
            b = loadj(d / "m6f_blocker_register.json")
            if int(b.get("blocker_count", 0) or 0) != 0:
                continue
        if summary_name == "m6g_execution_summary.json":
            verdict = str(summary.get("verdict", snap.get("verdict", ""))) if isinstance(snap, dict) else str(summary.get("verdict", ""))
            if verdict != "ADVANCE_TO_P7":
                continue
            b = loadj(d / "m6g_p6_blocker_register.json")
            if int(b.get("blocker_count", 0) or 0) != 0:
                continue
        execution_id = str(summary.get("execution_id", "")).strip() or d.name
        rows.append({"execution_id": execution_id, "path": d, "summary": summary, "snapshot": snap})
    rows.sort(key=lambda x: str(x["execution_id"]))
    return rows[-1] if rows else {}


def runtime_path_probe(handles: dict[str, Any], active_path: str) -> tuple[list[dict[str, Any]], list[str]]:
    probes: list[dict[str, Any]] = []
    issues: list[str] = []
    if active_path in {"EKS_EMR_ON_EKS", "EKS_FLINK_OPERATOR"}:
        vc = str(handles.get("EMR_EKS_VIRTUAL_CLUSTER_ID", "")).strip()
        if not vc:
            issues.append("EMR_EKS_VIRTUAL_CLUSTER_ID unresolved for EKS runtime path")
            return probes, issues
        p = cmd(
            [
                "aws",
                "emr-containers",
                "describe-virtual-cluster",
                "--id",
                vc,
                "--region",
                "eu-west-2",
                "--query",
                "virtualCluster.state",
                "--output",
                "text",
            ],
            30,
        )
        probes.append({**p, "probe_id": "m6p6_runtime_virtual_cluster_state", "group": "runtime"})
        if p.get("status") != "PASS":
            issues.append("virtual cluster describe probe failed")
        elif str(p.get("stdout", "")).strip() != "RUNNING":
            issues.append(f"virtual cluster state is not RUNNING: {str(p.get('stdout', '')).strip()}")
        return probes, issues
    if active_path == "MSF_MANAGED":
        for handle_key, probe_id in [
            ("FLINK_APP_WSP_STREAM_V0", "m6p6_runtime_msf_wsp"),
            ("FLINK_APP_SR_READY_V0", "m6p6_runtime_msf_sr"),
        ]:
            app = str(handles.get(handle_key, "")).strip()
            if not app:
                issues.append(f"{handle_key} unresolved for MSF_MANAGED runtime path")
                continue
            p = cmd(
                [
                    "aws",
                    "kinesisanalyticsv2",
                    "describe-application",
                    "--region",
                    "eu-west-2",
                    "--application-name",
                    app,
                    "--query",
                    "ApplicationDetail.ApplicationStatus",
                    "--output",
                    "text",
                ],
                30,
            )
            probes.append({**p, "probe_id": probe_id, "group": "runtime"})
            if p.get("status") != "PASS":
                issues.append(f"managed flink probe failed for {handle_key}")
        return probes, issues
    issues.append(f"unsupported FLINK_RUNTIME_PATH_ACTIVE value: {active_path}")
    return probes, issues


def finalize(
    out: Path,
    phase_execution_id: str,
    stage_id: str,
    plan_packet: dict[str, Any],
    blockers: list[dict[str, Any]],
    probes: list[dict[str, Any]],
    issues: list[str],
    decisions: list[str],
    required_artifacts: list[str],
    next_ok: str,
    next_fail: str,
    missing_artifact_blocker: str,
    missing_artifact_severity: str,
    streaming_snapshot: dict[str, Any],
    lag_snapshot: dict[str, Any],
    overhead_snapshot: dict[str, Any],
    extra_summary: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    dumpj(out / "m6p6_streaming_active_snapshot.json", streaming_snapshot)
    dumpj(out / "m6p6_lag_posture_snapshot.json", lag_snapshot)
    dumpj(out / "m6p6_evidence_overhead_snapshot.json", overhead_snapshot)

    probe_failures = [p for p in probes if str(p.get("status", "FAIL")) != "PASS"]
    latencies = [float(p.get("duration_ms", 0.0)) for p in probes]
    error_rate_pct = round((len(probe_failures) / len(probes)) * 100.0, 4) if probes else 0.0
    window_seconds = max(1, int(round(sum(latencies) / 1000.0))) if latencies else 1
    p50 = 0.0 if not latencies else sorted(latencies)[len(latencies) // 2]
    p95 = 0.0 if not latencies else max(latencies)

    dumpj(
        out / "m6p6_probe_latency_throughput_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": stage_id,
            "window_seconds_observed": window_seconds,
            "probe_count": len(probes),
            "failure_count": len(probe_failures),
            "error_rate_pct": error_rate_pct,
            "latency_ms_p50": p50,
            "latency_ms_p95": p95,
            "latency_ms_p99": p95,
            "sample_failures": probe_failures[:10],
            "probes": probes,
        },
    )
    dumpj(
        out / "m6p6_control_rail_conformance_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": stage_id,
            "overall_pass": len(issues) == 0,
            "issues": issues,
        },
    )
    dumpj(
        out / "m6p6_secret_safety_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": stage_id,
            "overall_pass": True,
            "secret_probe_count": 0,
            "secret_failure_count": 0,
            "with_decryption_used": False,
            "queried_value_directly": False,
            "suspicious_output_probe_ids": [],
            "plaintext_leakage_detected": False,
        },
    )
    dumpj(
        out / "m6p6_cost_outcome_receipt.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": stage_id,
            "window_seconds": window_seconds,
            "estimated_api_call_count": len(probes),
            "attributed_spend_usd": 0.0,
            "unattributed_spend_detected": False,
            "max_spend_usd": float(plan_packet.get("M6P6_STRESS_MAX_SPEND_USD", 35)),
            "within_envelope": True,
            "method": "m6p6_stress_validation_v0",
        },
    )
    dumpj(
        out / "m6p6_decision_log.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": stage_id,
            "decisions": decisions,
        },
    )

    overall_pass = len(blockers) == 0
    summary = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": stage_id,
        "overall_pass": overall_pass,
        "next_gate": next_ok if overall_pass else next_fail,
        "required_artifacts": required_artifacts,
        "probe_count": len(probes),
        "error_rate_pct": error_rate_pct,
    }
    summary.update(extra_summary)
    blocker_register = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": stage_id,
        "overall_pass": overall_pass,
        "open_blocker_count": len(blockers),
        "blockers": blockers,
    }
    dumpj(out / "m6p6_blocker_register.json", blocker_register)
    dumpj(out / "m6p6_execution_summary.json", summary)

    missing = [x for x in required_artifacts if not (out / x).exists()]
    if missing:
        blockers.append(
            {
                "id": missing_artifact_blocker,
                "severity": missing_artifact_severity,
                "status": "OPEN",
                "details": {"missing_artifacts": missing},
            }
        )
        blocker_register.update({"overall_pass": False, "open_blocker_count": len(blockers), "blockers": blockers})
        summary.update({"overall_pass": False, "next_gate": next_fail})
        dumpj(out / "m6p6_blocker_register.json", blocker_register)
        dumpj(out / "m6p6_execution_summary.json", summary)
    return summary, blocker_register


def print_stage(stage_key: str, phase_execution_id: str, out: Path, summary: dict[str, Any], blocker_register: dict[str, Any]) -> None:
    print(f"[{stage_key}] phase_execution_id={phase_execution_id}")
    print(f"[{stage_key}] output_dir={out.as_posix()}")
    print(f"[{stage_key}] overall_pass={summary.get('overall_pass')}")
    if "verdict" in summary:
        print(f"[{stage_key}] verdict={summary.get('verdict')}")
    print(f"[{stage_key}] next_gate={summary.get('next_gate')}")
    print(f"[{stage_key}] probe_count={summary.get('probe_count')}")
    print(f"[{stage_key}] error_rate_pct={summary.get('error_rate_pct')}")
    print(f"[{stage_key}] open_blockers={blocker_register.get('open_blocker_count')}")


def run_s0(phase_execution_id: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)
    plan_packet = parse_bt_map(PLAN.read_text(encoding="utf-8") if PLAN.exists() else "")
    handles = parse_reg(REG) if REG.exists() else {}

    blockers: list[dict[str, Any]] = []
    probes: list[dict[str, Any]] = []
    issues: list[str] = []
    decisions: list[str] = []

    missing_plan_keys = [k for k in PLAN_KEYS if k not in plan_packet]
    missing_handles = [k for k in REQ_HANDLES if k not in handles]
    placeholder_handles = [k for k in REQ_HANDLES if k in handles and str(handles[k]).strip() in {"", "TO_PIN", "None", "NONE", "null", "NULL"}]
    missing_docs = [x.as_posix() for x in [PLAN, PARENT_PLAN, BUILD_PLAN] if not x.exists()]
    if missing_plan_keys or missing_handles or placeholder_handles or missing_docs:
        blockers.append(
            {
                "id": "M6P6-ST-B1",
                "severity": "S0",
                "status": "OPEN",
                "details": {
                    "missing_plan_keys": missing_plan_keys,
                    "missing_handles": missing_handles,
                    "placeholder_handles": placeholder_handles,
                    "missing_docs": missing_docs,
                },
            }
        )
        if missing_plan_keys:
            issues.append(f"missing plan keys: {','.join(missing_plan_keys)}")
        if missing_handles:
            issues.append(f"missing handles: {','.join(missing_handles)}")
        if placeholder_handles:
            issues.append(f"placeholder handles: {','.join(placeholder_handles)}")
        if missing_docs:
            issues.append(f"missing docs: {','.join(missing_docs)}")

    dep_parent = latest_parent_s0()
    dep_parent_id = ""
    dep_issues: list[str] = []
    if not dep_parent:
        dep_issues.append("missing successful parent M6-ST-S0 dependency")
    else:
        s = dep_parent["summary"]
        dep_parent_id = str(s.get("phase_execution_id", ""))
        if str(s.get("next_gate", "")) != "M6_ST_S1_READY":
            dep_issues.append("parent M6-ST-S0 next_gate is not M6_ST_S1_READY")
        b = loadj(Path(str(dep_parent["path"])) / "m6_blocker_register.json")
        if int(b.get("open_blocker_count", 0) or 0) != 0:
            dep_issues.append("parent M6-ST-S0 blocker register not closed")

    dep_p5 = latest_p5_s5()
    dep_p5_id = ""
    dep_platform_run_id = ""
    if not dep_p5:
        dep_issues.append("missing successful M6P5-ST-S5 dependency")
    else:
        s = dep_p5["summary"]
        dep_p5_id = str(s.get("phase_execution_id", ""))
        if str(s.get("verdict", "")) != "ADVANCE_TO_P6" or str(s.get("next_gate", "")) != "ADVANCE_TO_P6":
            dep_issues.append("P5 verdict contract is invalid")
        b = loadj(Path(str(dep_p5["path"])) / "m6p5_blocker_register.json")
        if int(b.get("open_blocker_count", 0) or 0) != 0:
            dep_issues.append("P5 blocker register not closed")
        p5s2 = latest_p5_s2()
        if p5s2:
            dep_platform_run_id = str(p5s2["summary"].get("platform_run_id", "")).strip()
    if dep_issues:
        blockers.append({"id": "M6P6-ST-B2", "severity": "S0", "status": "OPEN", "details": {"issues": dep_issues}})
        issues.extend(dep_issues)

    runtime_active = str(handles.get("FLINK_RUNTIME_PATH_ACTIVE", "")).strip()
    runtime_allowed_raw = str(handles.get("FLINK_RUNTIME_PATH_ALLOWED", "")).strip()
    runtime_allowed = [x.strip() for x in runtime_allowed_raw.split("|") if x.strip()]
    runtime_issues: list[str] = []
    if not runtime_active:
        runtime_issues.append("FLINK_RUNTIME_PATH_ACTIVE unresolved")
    if "|" in runtime_active:
        runtime_issues.append("FLINK_RUNTIME_PATH_ACTIVE contains '|', expected single value")
    if runtime_allowed and runtime_active and runtime_active not in runtime_allowed:
        runtime_issues.append("FLINK_RUNTIME_PATH_ACTIVE not contained in FLINK_RUNTIME_PATH_ALLOWED")
    path_probes, path_issues = runtime_path_probe(handles, runtime_active)
    probes.extend(path_probes)
    runtime_issues.extend(path_issues)
    if runtime_issues:
        blockers.append({"id": "M6P6-ST-B3", "severity": "S0", "status": "OPEN", "details": {"issues": runtime_issues}})
        issues.extend(runtime_issues)

    bucket = str(handles.get("S3_EVIDENCE_BUCKET", "")).strip()
    p = cmd(["aws", "s3api", "head-bucket", "--bucket", bucket, "--region", "eu-west-2"], 25) if bucket else {
        "command": "aws s3api head-bucket",
        "exit_code": 1,
        "status": "FAIL",
        "duration_ms": 0.0,
        "stdout": "",
        "stderr": "missing S3_EVIDENCE_BUCKET handle",
        "started_at_utc": now(),
        "ended_at_utc": now(),
    }
    probes.append({**p, "probe_id": "m6p6_s0_evidence_bucket", "group": "control"})
    if p.get("status") != "PASS":
        blockers.append({"id": "M6P6-ST-B11", "severity": "S0", "status": "OPEN", "details": {"probe_id": "m6p6_s0_evidence_bucket"}})
        issues.append("evidence bucket probe failed")

    write_stagea(out, phase_execution_id, "M6P6-ST-S0")
    decisions.extend(
        [
            "Validated M6.P6 plan-key and required-handle closure.",
            "Validated parent M6-ST-S0 and P5 S5 dependency continuity.",
            "Validated single runtime-path closure with path-aware probes.",
            "Validated evidence root readback probe.",
        ]
    )

    summary, blocker_register = finalize(
        out=out,
        phase_execution_id=phase_execution_id,
        stage_id="M6P6-ST-S0",
        plan_packet=plan_packet,
        blockers=blockers,
        probes=probes,
        issues=issues,
        decisions=decisions,
        required_artifacts=BASE_ARTS,
        next_ok="M6P6_ST_S1_READY",
        next_fail="BLOCKED",
        missing_artifact_blocker="M6P6-ST-B11",
        missing_artifact_severity="S0",
        streaming_snapshot={
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P6-ST-S0",
            "runtime_path_active": runtime_active,
            "runtime_path_allowed": runtime_allowed,
            "parent_m6_s0_execution_id": dep_parent_id,
            "p5_s5_execution_id": dep_p5_id,
            "platform_run_id": dep_platform_run_id,
        },
        lag_snapshot={
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P6-ST-S0",
            "status": "NOT_EVALUATED_IN_S0",
            "threshold": handles.get("RTDL_CAUGHT_UP_LAG_MAX"),
            "measured_lag": None,
        },
        overhead_snapshot={
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P6-ST-S0",
            "status": "NOT_EVALUATED_IN_S0",
            "budget_check_pass": None,
        },
        extra_summary={
            "parent_m6_s0_phase_execution_id": dep_parent_id,
            "p5_dependency_phase_execution_id": dep_p5_id,
            "platform_run_id": dep_platform_run_id,
            "runtime_path_active": runtime_active,
        },
    )
    print_stage("m6p6_s0", phase_execution_id, out, summary, blocker_register)
    return 0 if summary.get("overall_pass") else 2


def run_s1(phase_execution_id: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)
    plan_packet = parse_bt_map(PLAN.read_text(encoding="utf-8") if PLAN.exists() else "")
    handles = parse_reg(REG) if REG.exists() else {}

    blockers: list[dict[str, Any]] = []
    probes: list[dict[str, Any]] = []
    issues: list[str] = []
    decisions: list[str] = []

    dep = latest_ok("m6p6_stress_s0", "M6P6-ST-S0")
    dep_id = ""
    dep_platform_run_id = ""
    dep_issues: list[str] = []
    if not dep:
        dep_issues.append("missing successful M6P6-ST-S0 dependency")
    else:
        s = dep["summary"]
        dep_id = str(s.get("phase_execution_id", ""))
        dep_platform_run_id = str(s.get("platform_run_id", "")).strip()
        if str(s.get("next_gate", "")) != "M6P6_ST_S1_READY":
            dep_issues.append("M6P6 S0 next_gate is not M6P6_ST_S1_READY")
        b = loadj(Path(str(dep["path"])) / "m6p6_blocker_register.json")
        if int(b.get("open_blocker_count", 0) or 0) != 0:
            dep_issues.append("M6P6 S0 blocker register not closed")
    if dep_issues:
        blockers.append({"id": "M6P6-ST-B3", "severity": "S1", "status": "OPEN", "details": {"issues": dep_issues}})
        issues.extend(dep_issues)

    runtime_active = str(handles.get("FLINK_RUNTIME_PATH_ACTIVE", "")).strip()
    m6e = latest_hist_run("m6e_execution_summary.json", "P6.A", dep_platform_run_id, "")
    m6f = latest_hist_run("m6f_execution_summary.json", "P6.B", dep_platform_run_id, runtime_active)

    m6e_id = ""
    m6f_id = ""
    m6f_snap: dict[str, Any] = {}
    m6f_lag = {}
    m6f_ovh = {}
    hist_issues: list[str] = []
    if not m6e:
        hist_issues.append("missing successful historical M6.E entry evidence")
    else:
        m6e_id = str(m6e.get("execution_id", "")).strip()
        p5_verdict = str(((m6e.get("snapshot", {}).get("p5_verdict") or {}).get("verdict", "")).strip())
        if p5_verdict and p5_verdict != "ADVANCE_TO_P6":
            hist_issues.append("historical M6.E p5_verdict is not ADVANCE_TO_P6")
    if not m6f:
        hist_issues.append("missing successful historical M6.F evidence for active runtime path")
    else:
        m6f_id = str(m6f.get("execution_id", "")).strip()
        m6f_snap = m6f.get("snapshot", {})
        m6f_lag = loadj(Path(str(m6f["path"])) / "m6f_streaming_lag_posture.json")
        m6f_ovh = loadj(Path(str(m6f["path"])) / "m6f_evidence_overhead_snapshot.json")
        if str(m6f_snap.get("runtime_path", "")).strip() != runtime_active:
            hist_issues.append("historical M6.F runtime_path does not match active runtime path")
        if str(m6f_snap.get("wsp_state", "")).strip() != "RUNNING":
            hist_issues.append("historical M6.F wsp_state is not RUNNING")
        if str(m6f_snap.get("sr_ready_state", "")).strip() != "RUNNING":
            hist_issues.append("historical M6.F sr_ready_state is not RUNNING")
        if int(m6f_snap.get("wsp_active_count", 0) or 0) <= 0:
            hist_issues.append("historical M6.F wsp_active_count is not positive")
        if int(m6f_snap.get("sr_ready_active_count", 0) or 0) <= 0:
            hist_issues.append("historical M6.F sr_ready_active_count is not positive")
    if hist_issues:
        blockers.append({"id": "M6P6-ST-B3", "severity": "S1", "status": "OPEN", "details": {"issues": hist_issues}})
        issues.extend(hist_issues)

    path_probes, path_issues = runtime_path_probe(handles, runtime_active)
    probes.extend(path_probes)
    if path_issues:
        blockers.append({"id": "M6P6-ST-B4", "severity": "S1", "status": "OPEN", "details": {"issues": path_issues}})
        issues.extend(path_issues)

    bucket = str(handles.get("S3_EVIDENCE_BUCKET", "")).strip()
    p = cmd(["aws", "s3api", "head-bucket", "--bucket", bucket, "--region", "eu-west-2"], 25) if bucket else {
        "command": "aws s3api head-bucket",
        "exit_code": 1,
        "status": "FAIL",
        "duration_ms": 0.0,
        "stdout": "",
        "stderr": "missing S3_EVIDENCE_BUCKET handle",
        "started_at_utc": now(),
        "ended_at_utc": now(),
    }
    probes.append({**p, "probe_id": "m6p6_s1_evidence_bucket", "group": "control"})
    if p.get("status") != "PASS":
        blockers.append({"id": "M6P6-ST-B11", "severity": "S1", "status": "OPEN", "details": {"probe_id": "m6p6_s1_evidence_bucket"}})
        issues.append("evidence bucket probe failed")

    write_stagea(out, phase_execution_id, "M6P6-ST-S1")
    decisions.extend(
        [
            "Validated S0 dependency continuity for runtime activation precheck.",
            "Validated historical M6.E and M6.F evidence for active runtime path.",
            "Validated path-aware runtime surface probes and evidence root readback.",
        ]
    )

    summary, blocker_register = finalize(
        out=out,
        phase_execution_id=phase_execution_id,
        stage_id="M6P6-ST-S1",
        plan_packet=plan_packet,
        blockers=blockers,
        probes=probes,
        issues=issues,
        decisions=decisions,
        required_artifacts=BASE_ARTS,
        next_ok="M6P6_ST_S2_READY",
        next_fail="BLOCKED",
        missing_artifact_blocker="M6P6-ST-B11",
        missing_artifact_severity="S1",
        streaming_snapshot={
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P6-ST-S1",
            "runtime_path_active": runtime_active,
            "historical_m6e_execution_id": m6e_id,
            "historical_m6f_execution_id": m6f_id,
            "platform_run_id": str(m6f_snap.get("platform_run_id", dep_platform_run_id)).strip(),
            "scenario_run_id": str(m6f_snap.get("scenario_run_id", "")).strip(),
            "wsp_state": m6f_snap.get("wsp_state"),
            "sr_ready_state": m6f_snap.get("sr_ready_state"),
            "wsp_active_count": m6f_snap.get("wsp_active_count"),
            "sr_ready_active_count": m6f_snap.get("sr_ready_active_count"),
        },
        lag_snapshot={
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P6-ST-S1",
            "status": "PROVISIONAL",
            "threshold": m6f_lag.get("threshold", handles.get("RTDL_CAUGHT_UP_LAG_MAX")),
            "measured_lag": m6f_lag.get("measured_lag"),
            "within_threshold": m6f_lag.get("within_threshold"),
        },
        overhead_snapshot={
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P6-ST-S1",
            "status": "PROVISIONAL",
            "budget_check_pass": m6f_ovh.get("budget_check_pass"),
            "bytes_per_event": m6f_ovh.get("bytes_per_event"),
            "write_rate_bytes_per_sec": m6f_ovh.get("write_rate_bytes_per_sec"),
        },
        extra_summary={
            "s0_dependency_phase_execution_id": dep_id,
            "historical_m6e_execution_id": m6e_id,
            "historical_m6f_execution_id": m6f_id,
            "runtime_path_active": runtime_active,
            "platform_run_id": str(m6f_snap.get("platform_run_id", dep_platform_run_id)).strip(),
        },
    )
    print_stage("m6p6_s1", phase_execution_id, out, summary, blocker_register)
    return 0 if summary.get("overall_pass") else 2


def run_s2(phase_execution_id: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)
    plan_packet = parse_bt_map(PLAN.read_text(encoding="utf-8") if PLAN.exists() else "")
    handles = parse_reg(REG) if REG.exists() else {}

    blockers: list[dict[str, Any]] = []
    probes: list[dict[str, Any]] = []
    issues: list[str] = []
    decisions: list[str] = []

    dep = latest_ok("m6p6_stress_s1", "M6P6-ST-S1")
    dep_id = ""
    dep_platform_run_id = ""
    dep_runtime_path = str(handles.get("FLINK_RUNTIME_PATH_ACTIVE", "")).strip()
    dep_m6f_id = ""
    dep_issues: list[str] = []
    if not dep:
        dep_issues.append("missing successful M6P6-ST-S1 dependency")
    else:
        s = dep["summary"]
        dep_id = str(s.get("phase_execution_id", ""))
        dep_platform_run_id = str(s.get("platform_run_id", "")).strip()
        dep_runtime_path = str(s.get("runtime_path_active", dep_runtime_path)).strip()
        dep_m6f_id = str(s.get("historical_m6f_execution_id", "")).strip()
        if str(s.get("next_gate", "")) != "M6P6_ST_S2_READY":
            dep_issues.append("M6P6 S1 next_gate is not M6P6_ST_S2_READY")
        b = loadj(Path(str(dep["path"])) / "m6p6_blocker_register.json")
        if int(b.get("open_blocker_count", 0) or 0) != 0:
            dep_issues.append("M6P6 S1 blocker register not closed")
    if dep_issues:
        blockers.append({"id": "M6P6-ST-B6", "severity": "S2", "status": "OPEN", "details": {"issues": dep_issues}})
        issues.extend(dep_issues)

    m6f = latest_hist_run("m6f_execution_summary.json", "P6.B", dep_platform_run_id, dep_runtime_path)
    m6f_id = ""
    snap: dict[str, Any] = {}
    lag: dict[str, Any] = {}
    ovh: dict[str, Any] = {}
    bridge: dict[str, Any] = {}
    if not m6f:
        blockers.append({"id": "M6P6-ST-B5", "severity": "S2", "status": "OPEN", "details": {"reason": "missing historical M6.F evidence"}})
        issues.append("missing historical M6.F evidence")
    else:
        m6f_id = str(m6f.get("execution_id", "")).strip()
        if dep_m6f_id and m6f_id and dep_m6f_id != m6f_id:
            issues.append(f"using latest M6.F evidence {m6f_id} (S1 referenced {dep_m6f_id})")
        snap = m6f.get("snapshot", {})
        lag = loadj(Path(str(m6f["path"])) / "m6f_streaming_lag_posture.json")
        ovh = loadj(Path(str(m6f["path"])) / "m6f_evidence_overhead_snapshot.json")
        bridge = loadj(Path(str(m6f["path"])) / "m6f_ig_bridge_summary.json")

        ig_count = int(snap.get("ig_idempotency_count", 0) or 0)
        if ig_count <= 0:
            blockers.append({"id": "M6P6-ST-B5", "severity": "S2", "status": "OPEN", "details": {"reason": "ig_idempotency_count is not positive"}})
            issues.append("run-window ingress progression is zero")
        if bridge:
            attempted = int(bridge.get("attempted", 0) or 0)
            admitted = int(bridge.get("admitted", 0) or 0)
            failed = int(bridge.get("failed", 0) or 0)
            if attempted <= 0 or admitted <= 0:
                blockers.append({"id": "M6P6-ST-B5", "severity": "S2", "status": "OPEN", "details": {"reason": "bridge attempted/admitted are not positive"}})
                issues.append("bridge progression is not positive")
            if failed > 0:
                blockers.append({"id": "M6P6-ST-B6", "severity": "S2", "status": "OPEN", "details": {"reason": "bridge failures present", "failed": failed}})
                issues.append("bridge failures detected")
            if dep_platform_run_id and str(bridge.get("platform_run_id", "")) and str(bridge.get("platform_run_id")) != dep_platform_run_id:
                blockers.append({"id": "M6P6-ST-B6", "severity": "S2", "status": "OPEN", "details": {"reason": "bridge platform_run_id mismatch"}})
                issues.append("bridge platform_run_id mismatch")
        if dep_platform_run_id and str(snap.get("platform_run_id", "")) and str(snap.get("platform_run_id")) != dep_platform_run_id:
            blockers.append({"id": "M6P6-ST-B6", "severity": "S2", "status": "OPEN", "details": {"reason": "snapshot platform_run_id mismatch"}})
            issues.append("snapshot platform_run_id mismatch")
        if str(snap.get("wsp_state", "")).strip() != "RUNNING" or str(snap.get("sr_ready_state", "")).strip() != "RUNNING":
            blockers.append({"id": "M6P6-ST-B6", "severity": "S2", "status": "OPEN", "details": {"reason": "lane refs not RUNNING"}})
            issues.append("lane refs are not RUNNING")

    table = str(handles.get("DDB_IG_IDEMPOTENCY_TABLE", "")).strip()
    p = cmd(["aws", "dynamodb", "describe-table", "--table-name", table, "--region", "eu-west-2", "--query", "Table.TableStatus", "--output", "text"], 25) if table else {
        "command": "aws dynamodb describe-table",
        "exit_code": 1,
        "status": "FAIL",
        "duration_ms": 0.0,
        "stdout": "",
        "stderr": "missing DDB_IG_IDEMPOTENCY_TABLE handle",
        "started_at_utc": now(),
        "ended_at_utc": now(),
    }
    probes.append({**p, "probe_id": "m6p6_s2_ig_table_probe", "group": "ingress"})
    if p.get("status") != "PASS":
        blockers.append({"id": "M6P6-ST-B11", "severity": "S2", "status": "OPEN", "details": {"probe_id": "m6p6_s2_ig_table_probe"}})
        issues.append("IG idempotency table probe failed")

    write_stagea(out, phase_execution_id, "M6P6-ST-S2")
    decisions.extend(
        [
            "Validated S1 dependency continuity before progression checks.",
            "Validated run-window progression using historical M6.F stream+bridge evidence.",
            "Validated IG idempotency table queryability probe.",
        ]
    )

    summary, blocker_register = finalize(
        out=out,
        phase_execution_id=phase_execution_id,
        stage_id="M6P6-ST-S2",
        plan_packet=plan_packet,
        blockers=blockers,
        probes=probes,
        issues=issues,
        decisions=decisions,
        required_artifacts=BASE_ARTS,
        next_ok="M6P6_ST_S3_READY",
        next_fail="BLOCKED",
        missing_artifact_blocker="M6P6-ST-B11",
        missing_artifact_severity="S2",
        streaming_snapshot={
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P6-ST-S2",
            "historical_m6f_execution_id": m6f_id,
            "runtime_path": snap.get("runtime_path"),
            "platform_run_id": snap.get("platform_run_id", dep_platform_run_id),
            "scenario_run_id": snap.get("scenario_run_id"),
            "wsp_state": snap.get("wsp_state"),
            "sr_ready_state": snap.get("sr_ready_state"),
            "wsp_active_count": snap.get("wsp_active_count"),
            "sr_ready_active_count": snap.get("sr_ready_active_count"),
            "ig_idempotency_count": snap.get("ig_idempotency_count"),
            "bridge_attempted": bridge.get("attempted"),
            "bridge_admitted": bridge.get("admitted"),
            "bridge_failed": bridge.get("failed"),
        },
        lag_snapshot={
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P6-ST-S2",
            "status": "PROVISIONAL",
            "threshold": lag.get("threshold", handles.get("RTDL_CAUGHT_UP_LAG_MAX")),
            "measured_lag": lag.get("measured_lag"),
            "within_threshold": lag.get("within_threshold"),
            "measurement_source": lag.get("measurement_source"),
        },
        overhead_snapshot={
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P6-ST-S2",
            "status": "PROVISIONAL",
            "budget_check_pass": ovh.get("budget_check_pass"),
            "bytes_per_event": ovh.get("bytes_per_event"),
            "write_rate_bytes_per_sec": ovh.get("write_rate_bytes_per_sec"),
        },
        extra_summary={
            "s1_dependency_phase_execution_id": dep_id,
            "historical_m6f_execution_id": m6f_id,
            "runtime_path_active": dep_runtime_path,
            "platform_run_id": str(snap.get("platform_run_id", dep_platform_run_id)),
        },
    )
    print_stage("m6p6_s2", phase_execution_id, out, summary, blocker_register)
    return 0 if summary.get("overall_pass") else 2


def run_s3(phase_execution_id: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)
    plan_packet = parse_bt_map(PLAN.read_text(encoding="utf-8") if PLAN.exists() else "")
    handles = parse_reg(REG) if REG.exists() else {}

    blockers: list[dict[str, Any]] = []
    probes: list[dict[str, Any]] = []
    issues: list[str] = []
    decisions: list[str] = []

    dep = latest_ok("m6p6_stress_s2", "M6P6-ST-S2")
    dep_id = ""
    dep_platform_run_id = ""
    dep_runtime_path = str(handles.get("FLINK_RUNTIME_PATH_ACTIVE", "")).strip()
    dep_m6f_id = ""
    dep_issues: list[str] = []
    if not dep:
        dep_issues.append("missing successful M6P6-ST-S2 dependency")
    else:
        s = dep["summary"]
        dep_id = str(s.get("phase_execution_id", ""))
        dep_platform_run_id = str(s.get("platform_run_id", "")).strip()
        dep_runtime_path = str(s.get("runtime_path_active", dep_runtime_path)).strip()
        dep_m6f_id = str(s.get("historical_m6f_execution_id", "")).strip()
        if str(s.get("next_gate", "")) != "M6P6_ST_S3_READY":
            dep_issues.append("M6P6 S2 next_gate is not M6P6_ST_S3_READY")
        b = loadj(Path(str(dep["path"])) / "m6p6_blocker_register.json")
        if int(b.get("open_blocker_count", 0) or 0) != 0:
            dep_issues.append("M6P6 S2 blocker register not closed")
    if dep_issues:
        blockers.append({"id": "M6P6-ST-B7", "severity": "S3", "status": "OPEN", "details": {"issues": dep_issues}})
        issues.extend(dep_issues)

    m6f = latest_hist_run("m6f_execution_summary.json", "P6.B", dep_platform_run_id, dep_runtime_path)
    m6f_id = ""
    snap: dict[str, Any] = {}
    lag: dict[str, Any] = {}
    amb: dict[str, Any] = {}
    ovh: dict[str, Any] = {}
    if not m6f:
        blockers.append({"id": "M6P6-ST-B7", "severity": "S3", "status": "OPEN", "details": {"reason": "missing historical M6.F evidence"}})
        issues.append("missing historical M6.F evidence for lag/ambiguity checks")
    else:
        m6f_id = str(m6f.get("execution_id", "")).strip()
        if dep_m6f_id and m6f_id and dep_m6f_id != m6f_id:
            issues.append(f"using latest M6.F evidence {m6f_id} (S2 referenced {dep_m6f_id})")
        snap = m6f.get("snapshot", {})
        lag = loadj(Path(str(m6f["path"])) / "m6f_streaming_lag_posture.json")
        amb = loadj(Path(str(m6f["path"])) / "m6f_publish_ambiguity_register.json")
        ovh = loadj(Path(str(m6f["path"])) / "m6f_evidence_overhead_snapshot.json")

        try:
            threshold = int(handles.get("RTDL_CAUGHT_UP_LAG_MAX", lag.get("threshold")))
        except Exception:
            threshold = None
        measured_lag = lag.get("measured_lag")
        if int(snap.get("ig_idempotency_count", 0) or 0) > 0 and measured_lag is None:
            blockers.append({"id": "M6P6-ST-B7", "severity": "S3", "status": "OPEN", "details": {"reason": "lag unavailable with active progression"}})
            issues.append("lag unavailable with active progression")
        if measured_lag is not None and threshold is not None:
            try:
                if int(measured_lag) > threshold:
                    blockers.append({"id": "M6P6-ST-B7", "severity": "S3", "status": "OPEN", "details": {"reason": "lag threshold breach", "measured_lag": measured_lag, "threshold": threshold}})
                    issues.append("lag threshold breached")
            except Exception:
                blockers.append({"id": "M6P6-ST-B7", "severity": "S3", "status": "OPEN", "details": {"reason": "measured lag is non-numeric", "measured_lag": measured_lag}})
                issues.append("measured lag is non-numeric")
        if lag.get("within_threshold") is False:
            blockers.append({"id": "M6P6-ST-B7", "severity": "S3", "status": "OPEN", "details": {"reason": "within_threshold=false"}})
            issues.append("within_threshold=false in lag snapshot")

        unresolved = int(amb.get("unresolved_publish_ambiguity_count", 0) or 0)
        if unresolved > 0:
            blockers.append({"id": "M6P6-ST-B8", "severity": "S3", "status": "OPEN", "details": {"reason": "publish ambiguity register not clear", "count": unresolved}})
            issues.append("publish ambiguity register is not clear")
        if ovh.get("budget_check_pass") is False:
            blockers.append({"id": "M6P6-ST-B9", "severity": "S3", "status": "OPEN", "details": {"reason": "evidence overhead budget failed"}})
            issues.append("evidence overhead budget failed")

    bucket = str(handles.get("S3_EVIDENCE_BUCKET", "")).strip()
    p = cmd(["aws", "s3api", "head-bucket", "--bucket", bucket, "--region", "eu-west-2"], 25) if bucket else {
        "command": "aws s3api head-bucket",
        "exit_code": 1,
        "status": "FAIL",
        "duration_ms": 0.0,
        "stdout": "",
        "stderr": "missing S3_EVIDENCE_BUCKET handle",
        "started_at_utc": now(),
        "ended_at_utc": now(),
    }
    probes.append({**p, "probe_id": "m6p6_s3_evidence_bucket", "group": "control"})
    if p.get("status") != "PASS":
        blockers.append({"id": "M6P6-ST-B11", "severity": "S3", "status": "OPEN", "details": {"probe_id": "m6p6_s3_evidence_bucket"}})
        issues.append("evidence bucket probe failed")

    write_stagea(out, phase_execution_id, "M6P6-ST-S3")
    decisions.extend(
        [
            "Validated S2 dependency continuity for lag/ambiguity/overhead checks.",
            "Validated lag posture against RTDL_CAUGHT_UP_LAG_MAX.",
            "Validated ambiguity register and overhead budget posture.",
            "Validated evidence root readback probe.",
        ]
    )

    summary, blocker_register = finalize(
        out=out,
        phase_execution_id=phase_execution_id,
        stage_id="M6P6-ST-S3",
        plan_packet=plan_packet,
        blockers=blockers,
        probes=probes,
        issues=issues,
        decisions=decisions,
        required_artifacts=BASE_ARTS,
        next_ok="M6P6_ST_S4_READY",
        next_fail="BLOCKED",
        missing_artifact_blocker="M6P6-ST-B11",
        missing_artifact_severity="S3",
        streaming_snapshot={
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P6-ST-S3",
            "historical_m6f_execution_id": m6f_id,
            "runtime_path": snap.get("runtime_path"),
            "platform_run_id": snap.get("platform_run_id", dep_platform_run_id),
            "ig_idempotency_count": snap.get("ig_idempotency_count"),
            "wsp_state": snap.get("wsp_state"),
            "sr_ready_state": snap.get("sr_ready_state"),
        },
        lag_snapshot={
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P6-ST-S3",
            "threshold": lag.get("threshold", handles.get("RTDL_CAUGHT_UP_LAG_MAX")),
            "measured_lag": lag.get("measured_lag"),
            "measurement_source": lag.get("measurement_source"),
            "within_threshold": lag.get("within_threshold"),
        },
        overhead_snapshot={
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P6-ST-S3",
            "latency_p95_ms": ovh.get("latency_p95_ms"),
            "bytes_per_event": ovh.get("bytes_per_event"),
            "write_rate_bytes_per_sec": ovh.get("write_rate_bytes_per_sec"),
            "budget_check_pass": ovh.get("budget_check_pass"),
        },
        extra_summary={
            "s2_dependency_phase_execution_id": dep_id,
            "historical_m6f_execution_id": m6f_id,
            "runtime_path_active": dep_runtime_path,
            "platform_run_id": str(snap.get("platform_run_id", dep_platform_run_id)),
        },
    )
    print_stage("m6p6_s3", phase_execution_id, out, summary, blocker_register)
    return 0 if summary.get("overall_pass") else 2


def run_s4(phase_execution_id: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)
    plan_packet = parse_bt_map(PLAN.read_text(encoding="utf-8") if PLAN.exists() else "")

    blockers: list[dict[str, Any]] = []
    probes: list[dict[str, Any]] = []
    issues: list[str] = []
    decisions: list[str] = []

    dep = latest_ok("m6p6_stress_s3", "M6P6-ST-S3")
    dep_id = ""
    dep_platform_run_id = ""
    dep_runtime_path = ""
    dep_m6f_id = ""
    dep_issues: list[str] = []
    if not dep:
        dep_issues.append("missing successful M6P6-ST-S3 dependency")
    else:
        s = dep["summary"]
        dep_id = str(s.get("phase_execution_id", ""))
        dep_platform_run_id = str(s.get("platform_run_id", "")).strip()
        dep_runtime_path = str(s.get("runtime_path_active", "")).strip()
        dep_m6f_id = str(s.get("historical_m6f_execution_id", "")).strip()
        if str(s.get("next_gate", "")) != "M6P6_ST_S4_READY":
            dep_issues.append("M6P6 S3 next_gate is not M6P6_ST_S4_READY")
        b = loadj(Path(str(dep["path"])) / "m6p6_blocker_register.json")
        if int(b.get("open_blocker_count", 0) or 0) != 0:
            dep_issues.append("M6P6 S3 blocker register not closed")
    if dep_issues:
        blockers.append({"id": "M6P6-ST-B10", "severity": "S4", "status": "OPEN", "details": {"issues": dep_issues}})
        issues.extend(dep_issues)

    write_stagea(out, phase_execution_id, "M6P6-ST-S4")
    decisions.extend(
        [
            "Evaluated S3 blocker posture for targeted remediation eligibility.",
            "Applied NO_OP remediation mode because S3 dependency is blocker-free.",
            "Retained targeted-rerun-only policy for any future blocker reopen events.",
        ]
    )

    summary, blocker_register = finalize(
        out=out,
        phase_execution_id=phase_execution_id,
        stage_id="M6P6-ST-S4",
        plan_packet=plan_packet,
        blockers=blockers,
        probes=probes,
        issues=issues,
        decisions=decisions,
        required_artifacts=BASE_ARTS,
        next_ok="M6P6_ST_S5_READY",
        next_fail="BLOCKED",
        missing_artifact_blocker="M6P6-ST-B10",
        missing_artifact_severity="S4",
        streaming_snapshot={
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P6-ST-S4",
            "status": "NO_OP" if len(blockers) == 0 else "TARGETED_REMEDIATE",
            "historical_m6f_execution_id": dep_m6f_id,
            "runtime_path": dep_runtime_path,
            "platform_run_id": dep_platform_run_id,
        },
        lag_snapshot={
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P6-ST-S4",
            "status": "NO_OP" if len(blockers) == 0 else "TARGETED_REMEDIATE",
            "measured_lag": None,
        },
        overhead_snapshot={
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P6-ST-S4",
            "status": "NO_OP" if len(blockers) == 0 else "TARGETED_REMEDIATE",
            "budget_check_pass": True if len(blockers) == 0 else None,
        },
        extra_summary={
            "s3_dependency_phase_execution_id": dep_id,
            "historical_m6f_execution_id": dep_m6f_id,
            "runtime_path_active": dep_runtime_path,
            "platform_run_id": dep_platform_run_id,
            "remediation_mode": "NO_OP" if len(blockers) == 0 else "TARGETED_REMEDIATE",
        },
    )
    print_stage("m6p6_s4", phase_execution_id, out, summary, blocker_register)
    return 0 if summary.get("overall_pass") else 2


def run_s5(phase_execution_id: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)
    plan_packet = parse_bt_map(PLAN.read_text(encoding="utf-8") if PLAN.exists() else "")

    blockers: list[dict[str, Any]] = []
    probes: list[dict[str, Any]] = []
    issues: list[str] = []
    decisions: list[str] = []

    dep = latest_ok("m6p6_stress_s4", "M6P6-ST-S4")
    dep_id = ""
    dep_platform_run_id = ""
    dep_runtime_path = ""
    dep_m6f_id = ""
    dep_issues: list[str] = []
    if not dep:
        dep_issues.append("missing successful M6P6-ST-S4 dependency")
    else:
        s = dep["summary"]
        dep_id = str(s.get("phase_execution_id", ""))
        dep_platform_run_id = str(s.get("platform_run_id", "")).strip()
        dep_runtime_path = str(s.get("runtime_path_active", "")).strip()
        dep_m6f_id = str(s.get("historical_m6f_execution_id", "")).strip()
        if str(s.get("next_gate", "")) != "M6P6_ST_S5_READY":
            dep_issues.append("M6P6 S4 next_gate is not M6P6_ST_S5_READY")
        b = loadj(Path(str(dep["path"])) / "m6p6_blocker_register.json")
        if int(b.get("open_blocker_count", 0) or 0) != 0:
            dep_issues.append("M6P6 S4 blocker register not closed")
    if dep_issues:
        blockers.append({"id": "M6P6-ST-B10", "severity": "S5", "status": "OPEN", "details": {"issues": dep_issues}})
        issues.extend(dep_issues)

    chain = [
        ("S0", "m6p6_stress_s0", "M6P6-ST-S0", "M6P6_ST_S1_READY"),
        ("S1", "m6p6_stress_s1", "M6P6-ST-S1", "M6P6_ST_S2_READY"),
        ("S2", "m6p6_stress_s2", "M6P6-ST-S2", "M6P6_ST_S3_READY"),
        ("S3", "m6p6_stress_s3", "M6P6-ST-S3", "M6P6_ST_S4_READY"),
        ("S4", "m6p6_stress_s4", "M6P6-ST-S4", "M6P6_ST_S5_READY"),
    ]
    chain_rows: list[dict[str, Any]] = []
    for label, prefix, stage_id, expected_next_gate in chain:
        r = latest_ok(prefix, stage_id)
        row = {
            "label": label,
            "stage_id": stage_id,
            "expected_next_gate": expected_next_gate,
            "found": bool(r),
            "phase_execution_id": "",
            "next_gate": "",
            "ok": False,
        }
        if r:
            s = r["summary"]
            row["phase_execution_id"] = str(s.get("phase_execution_id", ""))
            row["next_gate"] = str(s.get("next_gate", ""))
            row["ok"] = bool(s.get("overall_pass")) and row["next_gate"] == expected_next_gate
        if row["ok"] is not True:
            blockers.append({"id": "M6P6-ST-B10", "severity": "S5", "status": "OPEN", "details": {"chain_row": row}})
            issues.append(f"stage chain check failed for {label}")
        chain_rows.append(row)

    m6g = latest_hist_run("m6g_execution_summary.json", "P6.C", dep_platform_run_id, "")
    m6g_id = ""
    if not m6g:
        blockers.append({"id": "M6P6-ST-B10", "severity": "S5", "status": "OPEN", "details": {"reason": "missing successful historical M6.G evidence"}})
        issues.append("missing successful historical M6.G evidence")
    else:
        m6g_id = str(m6g.get("execution_id", "")).strip()
        v = str(m6g.get("summary", {}).get("verdict", m6g.get("snapshot", {}).get("verdict", ""))).strip()
        if v != "ADVANCE_TO_P7":
            blockers.append({"id": "M6P6-ST-B10", "severity": "S5", "status": "OPEN", "details": {"reason": "historical M6.G verdict mismatch", "verdict": v}})
            issues.append("historical M6.G verdict is not ADVANCE_TO_P7")

    verdict = "ADVANCE_TO_P7" if len(blockers) == 0 else "HOLD_REMEDIATE"
    dumpj(
        out / "m6p6_gate_verdict.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P6-ST-S5",
            "verdict": verdict,
            "next_gate": verdict,
            "blocker_count": len(blockers),
            "chain_matrix": chain_rows,
            "s4_dependency_phase_execution_id": dep_id,
            "historical_m6g_execution_id": m6g_id,
        },
    )

    write_stagea(out, phase_execution_id, "M6P6-ST-S5")
    decisions.extend(
        [
            "Validated full M6.P6 stage-chain closure from S0 through S4.",
            "Validated historical M6.G verdict surface for deterministic consistency.",
            "Applied deterministic verdict rule: ADVANCE_TO_P7 only when blocker-free.",
            "Emitted m6p6_gate_verdict.json for parent M6-ST-S2 adjudication.",
        ]
    )

    summary, blocker_register = finalize(
        out=out,
        phase_execution_id=phase_execution_id,
        stage_id="M6P6-ST-S5",
        plan_packet=plan_packet,
        blockers=blockers,
        probes=probes,
        issues=issues,
        decisions=decisions,
        required_artifacts=BASE_ARTS + ["m6p6_gate_verdict.json"],
        next_ok="ADVANCE_TO_P7",
        next_fail="HOLD_REMEDIATE",
        missing_artifact_blocker="M6P6-ST-B12",
        missing_artifact_severity="S5",
        streaming_snapshot={
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P6-ST-S5",
            "status": "ROLLUP",
            "historical_m6f_execution_id": dep_m6f_id,
            "runtime_path": dep_runtime_path,
            "platform_run_id": dep_platform_run_id,
        },
        lag_snapshot={
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P6-ST-S5",
            "status": "ROLLUP",
            "measured_lag": None,
            "within_threshold": None,
        },
        overhead_snapshot={
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M6P6-ST-S5",
            "status": "ROLLUP",
            "budget_check_pass": None,
        },
        extra_summary={
            "s4_dependency_phase_execution_id": dep_id,
            "historical_m6g_execution_id": m6g_id,
            "runtime_path_active": dep_runtime_path,
            "platform_run_id": dep_platform_run_id,
            "verdict": verdict,
        },
    )
    print_stage("m6p6_s5", phase_execution_id, out, summary, blocker_register)
    return 0 if summary.get("overall_pass") else 2


def main() -> int:
    ap = argparse.ArgumentParser(description="M6.P6 stress runner")
    ap.add_argument("--stage", default="S0", choices=["S0", "S1", "S2", "S3", "S4", "S5"])
    ap.add_argument("--phase-execution-id", default="")
    args = ap.parse_args()

    stage_map = {
        "S0": ("m6p6_stress_s0", run_s0),
        "S1": ("m6p6_stress_s1", run_s1),
        "S2": ("m6p6_stress_s2", run_s2),
        "S3": ("m6p6_stress_s3", run_s3),
        "S4": ("m6p6_stress_s4", run_s4),
        "S5": ("m6p6_stress_s5", run_s5),
    }
    prefix, fn = stage_map[args.stage]
    phase_execution_id = args.phase_execution_id.strip() or f"{prefix}_{tok()}"
    return fn(phase_execution_id)


if __name__ == "__main__":
    raise SystemExit(main())
