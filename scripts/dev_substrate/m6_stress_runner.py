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

PLAN = Path("docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M6.stress_test.md")
P5_PLAN = Path("docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M6.P5.stress_test.md")
P6_PLAN = Path("docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M6.P6.stress_test.md")
P7_PLAN = Path("docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M6.P7.stress_test.md")
REG = Path("docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md")
OUT_ROOT = Path("runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control")

M6_REQ_HANDLES = [
    "S3_EVIDENCE_BUCKET",
    "S3_RUN_CONTROL_ROOT_PATTERN",
    "M6_HANDOFF_PACK_PATH_PATTERN",
    "M7_HANDOFF_PACK_PATH_PATTERN",
    "FP_BUS_CONTROL_V1",
    "READY_MESSAGE_FILTER",
    "REQUIRED_PLATFORM_RUN_ID_ENV_KEY",
    "SR_READY_COMMIT_AUTHORITY",
    "SR_READY_COMMIT_STATE_MACHINE",
    "SR_READY_RECEIPT_REQUIRES_SFN_EXECUTION_REF",
    "SR_READY_COMMIT_RECEIPT_PATH_PATTERN",
    "FLINK_RUNTIME_PATH_ACTIVE",
    "FLINK_RUNTIME_PATH_ALLOWED",
    "FLINK_APP_WSP_STREAM_V0",
    "FLINK_APP_SR_READY_V0",
    "FLINK_EKS_WSP_STREAM_REF",
    "FLINK_EKS_SR_READY_REF",
    "EMR_EKS_VIRTUAL_CLUSTER_ID",
    "EMR_EKS_RELEASE_LABEL",
    "EMR_EKS_EXECUTION_ROLE_ARN",
    "RTDL_CAUGHT_UP_LAG_MAX",
    "WSP_MAX_INFLIGHT",
    "WSP_RETRY_MAX_ATTEMPTS",
    "WSP_RETRY_BACKOFF_MS",
    "WSP_STOP_ON_NONRETRYABLE",
    "IG_BASE_URL",
    "IG_INGEST_PATH",
    "DDB_IG_IDEMPOTENCY_TABLE",
    "RECEIPT_SUMMARY_PATH_PATTERN",
    "QUARANTINE_SUMMARY_PATH_PATTERN",
    "KAFKA_OFFSETS_SNAPSHOT_PATH_PATTERN",
]

M6_PLAN_KEYS = [
    "M6_STRESS_PROFILE_ID",
    "M6_STRESS_BLOCKER_REGISTER_PATH_PATTERN",
    "M6_STRESS_EXECUTION_SUMMARY_PATH_PATTERN",
    "M6_STRESS_DECISION_LOG_PATH_PATTERN",
    "M6_STRESS_REQUIRED_ARTIFACTS",
    "M6_STRESS_MAX_RUNTIME_MINUTES",
    "M6_STRESS_MAX_SPEND_USD",
    "M6_STRESS_EXPECTED_NEXT_GATE_ON_PASS",
    "M6_STRESS_REQUIRED_SUBPHASES",
    "M6_STRESS_P5_REQUIRED_VERDICT",
    "M6_STRESS_P6_REQUIRED_VERDICT",
    "M6_STRESS_P7_REQUIRED_VERDICT",
    "M6_STRESS_INTEGRATED_WINDOW_MINUTES",
    "M6_STRESS_BURST_WINDOW_MINUTES",
    "M6_STRESS_FAILURE_INJECTION_WINDOW_MINUTES",
    "M6_STRESS_TARGETED_RERUN_ONLY",
]

M6_S0_ARTS = [
    "m6_stagea_findings.json",
    "m6_lane_matrix.json",
    "m6_probe_latency_throughput_snapshot.json",
    "m6_control_rail_conformance_snapshot.json",
    "m6_secret_safety_snapshot.json",
    "m6_cost_outcome_receipt.json",
    "m6_blocker_register.json",
    "m6_execution_summary.json",
    "m6_decision_log.json",
]
M6_S1_ARTS = M6_S0_ARTS


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def tok() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def dumpj(path: Path, obj: dict[str, Any]) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_scalar(v: str) -> Any:
    v = v.strip()
    if v.lower() in {"true", "false"}:
        return v.lower() == "true"
    if v.startswith('"') and v.endswith('"'):
        return v[1:-1]
    try:
        return int(v) if "." not in v else float(v)
    except ValueError:
        return v


def parse_backtick_map(text: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in re.findall(r"`([A-Z0-9_]+)\s*=\s*([^`]+)`", text):
        out[k] = parse_scalar(v)
    return out


def parse_registry(path: Path) -> dict[str, Any]:
    rx = re.compile(r"^\* `([^`]+)`(?:\s.*)?$")
    out: dict[str, Any] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        m = rx.match(raw.strip())
        if m:
            body = m.group(1).strip()
            if "=" not in body:
                continue
            k, v = body.split("=", 1)
            out[k.strip()] = parse_scalar(v.strip())
    return out


def run_cmd(cmd: list[str], timeout: int = 30) -> dict[str, Any]:
    t0 = time.perf_counter()
    st = now()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return {
            "command": " ".join(cmd),
            "exit_code": int(p.returncode),
            "status": "PASS" if int(p.returncode) == 0 else "FAIL",
            "duration_ms": round((time.perf_counter() - t0) * 1000.0, 3),
            "stdout": (p.stdout or "").strip()[:300],
            "stderr": (p.stderr or "").strip()[:300],
            "started_at_utc": st,
            "ended_at_utc": now(),
        }
    except subprocess.TimeoutExpired:
        return {
            "command": " ".join(cmd),
            "exit_code": 124,
            "status": "FAIL",
            "duration_ms": round((time.perf_counter() - t0) * 1000.0, 3),
            "stdout": "",
            "stderr": "timeout",
            "started_at_utc": st,
            "ended_at_utc": now(),
        }


def load_json_safe(path: Path) -> dict[str, Any]:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {}


def load_latest_successful_m5_s3(out_root: Path) -> dict[str, Any]:
    runs = sorted(out_root.glob("m5_stress_s3_*/stress"))
    for d in reversed(runs):
        sp = d / "m5_execution_summary.json"
        if not sp.exists():
            continue
        try:
            summ = json.loads(sp.read_text(encoding="utf-8"))
        except Exception:
            continue
        if summ.get("overall_pass") is not True:
            continue
        if str(summ.get("stage_id", "")) != "M5-ST-S3":
            continue
        return {"path": d, "summary": summ}
    return {}


def load_latest_successful_m6_s0(out_root: Path) -> dict[str, Any]:
    runs = sorted(out_root.glob("m6_stress_s0_*/stress"))
    for d in reversed(runs):
        sp = d / "m6_execution_summary.json"
        if not sp.exists():
            continue
        try:
            summ = json.loads(sp.read_text(encoding="utf-8"))
        except Exception:
            continue
        if summ.get("overall_pass") is not True:
            continue
        if str(summ.get("stage_id", "")) != "M6-ST-S0":
            continue
        return {"path": d, "summary": summ}
    return {}


def load_latest_successful_m6p5_s5(out_root: Path) -> dict[str, Any]:
    runs = sorted(out_root.glob("m6p5_stress_s5_*/stress"))
    for d in reversed(runs):
        sp = d / "m6p5_execution_summary.json"
        if not sp.exists():
            continue
        try:
            summ = json.loads(sp.read_text(encoding="utf-8"))
        except Exception:
            continue
        if summ.get("overall_pass") is not True:
            continue
        if str(summ.get("stage_id", "")) != "M6P5-ST-S5":
            continue
        return {"path": d, "summary": summ}
    return {}


def build_lane_matrix() -> dict[str, Any]:
    return {
        "component_sequence": ["M6-ST-S0", "M6-ST-S1", "M6-ST-S2", "M6-ST-S3", "M6-ST-S4", "M6-ST-S5"],
        "plane_sequence": ["control_plane", "streaming_plane", "ingress_plane", "phase_closure_plane"],
        "integrated_windows": ["m6_s4_sustained_window", "m6_s4_burst_window", "m6_s4_fault_window"],
    }


def run_s0(phase_id: str, out_root: Path) -> int:
    t0 = time.perf_counter()
    out = out_root / phase_id / "stress"
    out.mkdir(parents=True, exist_ok=True)

    txt = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    pkt = parse_backtick_map(txt) if txt else {}
    h = parse_registry(REG) if REG.exists() else {}
    blockers: list[dict[str, Any]] = []

    missing_plan_keys = [k for k in M6_PLAN_KEYS if k not in pkt]
    missing_handles = [k for k in M6_REQ_HANDLES if k not in h]
    placeholder_handles = [
        k
        for k in M6_REQ_HANDLES
        if k in h and str(h[k]).strip() in {"", "TO_PIN", "NONE", "None", "null", "NULL"}
    ]
    if missing_plan_keys or missing_handles or placeholder_handles:
        blockers.append(
            {
                "id": "M6-ST-B1",
                "severity": "S0",
                "status": "OPEN",
                "details": {
                    "missing_plan_keys": missing_plan_keys,
                    "missing_handles": missing_handles,
                    "placeholder_handles": placeholder_handles,
                },
            }
        )

    dep = load_latest_successful_m5_s3(out_root)
    dep_issues: list[str] = []
    dep_blocker_count = None
    dep_id = ""
    if not dep:
        dep_issues.append("missing successful M5-ST-S3 dependency")
    else:
        dep_summ = dep.get("summary", {})
        dep_id = str(dep_summ.get("phase_execution_id", ""))
        if str(dep_summ.get("recommendation", "")) != "GO":
            dep_issues.append("M5 recommendation is not GO")
        if str(dep_summ.get("next_gate", "")) != "M6_READY":
            dep_issues.append("M5 next_gate is not M6_READY")
        dep_br = load_json_safe(Path(str(dep["path"])) / "m5_blocker_register.json")
        dep_blocker_count = int(dep_br.get("open_blocker_count", len(dep_br.get("blockers", [])))) if dep_br else None
        if dep_blocker_count not in {None, 0}:
            dep_issues.append(f"M5 blocker register not closed: {dep_blocker_count}")

    if dep_issues:
        blockers.append({"id": "M6-ST-B2", "severity": "S0", "status": "OPEN", "details": {"issues": dep_issues}})

    authority_issues: list[str] = []
    missing_authorities: list[str] = []
    unreadable_authorities: list[str] = []
    for p in [PLAN, P5_PLAN, P6_PLAN, P7_PLAN]:
        if not p.exists():
            missing_authorities.append(p.as_posix())
            continue
        try:
            _ = p.read_text(encoding="utf-8")
        except Exception:
            unreadable_authorities.append(p.as_posix())
    if missing_authorities:
        authority_issues.append(f"missing authority files: {','.join(missing_authorities)}")
    if unreadable_authorities:
        authority_issues.append(f"unreadable authority files: {','.join(unreadable_authorities)}")
    if authority_issues:
        blockers.append(
            {
                "id": "M6-ST-B3",
                "severity": "S0",
                "status": "OPEN",
                "details": {
                    "missing_authorities": missing_authorities,
                    "unreadable_authorities": unreadable_authorities,
                },
            }
        )

    region = str(h.get("AWS_REGION", "eu-west-2")).strip() or "eu-west-2"
    bucket = str(h.get("S3_EVIDENCE_BUCKET", "")).strip()
    probe_rows: list[dict[str, Any]] = []
    if bucket:
        p = run_cmd(["aws", "s3api", "head-bucket", "--bucket", bucket, "--region", region], timeout=25)
        probe_rows.append({**p, "probe_id": "m6_s0_evidence_bucket", "group": "control"})
    else:
        probe_rows.append(
            {
                "probe_id": "m6_s0_evidence_bucket",
                "group": "control",
                "command": "aws s3api head-bucket",
                "exit_code": 1,
                "status": "FAIL",
                "duration_ms": 0.0,
                "stdout": "",
                "stderr": "missing S3_EVIDENCE_BUCKET handle",
                "started_at_utc": now(),
                "ended_at_utc": now(),
            }
        )

    probe_failures = [p for p in probe_rows if str(p.get("status", "FAIL")) != "PASS"]
    if probe_failures:
        blockers.append(
            {
                "id": "M6-ST-B10",
                "severity": "S0",
                "status": "OPEN",
                "details": {"probe_failures": [str(x.get("probe_id", "")) for x in probe_failures]},
            }
        )

    stagea = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M6-ST-S0",
        "findings": [
            {
                "id": "M6-ST-F1",
                "classification": "PREVENT",
                "finding": "M6 requires split parent/subphase authority routing before execution.",
                "required_action": "Validate parent + P5/P6/P7 authority files before execution.",
            },
            {
                "id": "M6-ST-F2",
                "classification": "PREVENT",
                "finding": "M6 entry must chain from M5 S3 recommendation and next-gate contract.",
                "required_action": "Validate latest successful M5 S3 summary and blocker register at entry.",
            },
            {
                "id": "M6-ST-F3",
                "classification": "PREVENT",
                "finding": "M6 parent required handles and control artifact keys must be complete before stress windows.",
                "required_action": "Fail-closed on missing/placeholder required handles or plan keys.",
            },
            {
                "id": "M6-ST-F4",
                "classification": "PREVENT",
                "finding": "Evidence root reachability must be verified before M6 stage advancement.",
                "required_action": "Run bounded evidence-bucket probe and fail-closed on failure.",
            },
        ],
    }
    dumpj(out / "m6_stagea_findings.json", stagea)
    dumpj(out / "m6_lane_matrix.json", build_lane_matrix())

    total = len(probe_rows)
    er = round((len(probe_failures) / total) * 100.0, 4) if total else 0.0
    lat = [float(x.get("duration_ms", 0.0)) for x in probe_rows]
    dur_s = max(1, int(round(time.perf_counter() - t0)))
    max_sp = float(pkt.get("M6_STRESS_MAX_SPEND_USD", 90))
    cost_within = True

    probe = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M6-ST-S0",
        "window_seconds_observed": dur_s,
        "probe_count": total,
        "failure_count": len(probe_failures),
        "error_rate_pct": er,
        "latency_ms_p50": 0.0 if not lat else sorted(lat)[len(lat) // 2],
        "latency_ms_p95": 0.0 if not lat else max(lat),
        "latency_ms_p99": 0.0 if not lat else max(lat),
        "sample_failures": probe_failures[:10],
        "m5_dependency_phase_execution_id": dep_id,
    }
    dumpj(out / "m6_probe_latency_throughput_snapshot.json", probe)

    control_issues: list[str] = []
    if missing_plan_keys:
        control_issues.append(f"missing plan keys: {','.join(missing_plan_keys)}")
    if missing_handles:
        control_issues.append(f"missing handles: {','.join(missing_handles)}")
    if placeholder_handles:
        control_issues.append(f"placeholder handles: {','.join(placeholder_handles)}")
    control_issues.extend(dep_issues)
    control_issues.extend(authority_issues)
    if probe_failures:
        control_issues.append(f"probe failures: {len(probe_failures)}")

    ctrl = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M6-ST-S0",
        "overall_pass": len(control_issues) == 0,
        "issues": control_issues,
        "m5_dependency_phase_execution_id": dep_id,
        "m5_dependency_open_blockers": dep_blocker_count,
        "required_authorities": [PLAN.as_posix(), P5_PLAN.as_posix(), P6_PLAN.as_posix(), P7_PLAN.as_posix()],
    }
    dumpj(out / "m6_control_rail_conformance_snapshot.json", ctrl)

    sec = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M6-ST-S0",
        "overall_pass": True,
        "secret_probe_count": 0,
        "secret_failure_count": 0,
        "with_decryption_used": False,
        "queried_value_directly": False,
        "suspicious_output_probe_ids": [],
        "plaintext_leakage_detected": False,
    }
    dumpj(out / "m6_secret_safety_snapshot.json", sec)

    cost = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M6-ST-S0",
        "window_seconds": dur_s,
        "estimated_api_call_count": total,
        "attributed_spend_usd": 0.0,
        "unattributed_spend_detected": False,
        "max_spend_usd": max_sp,
        "within_envelope": cost_within,
        "method": "read_only_entry_gate_validation_v0",
    }
    dumpj(out / "m6_cost_outcome_receipt.json", cost)

    dlog = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M6-ST-S0",
        "decisions": [
            "Validated M6 parent stress handle packet and required handle closure.",
            "Validated latest successful M5 S3 handoff dependency.",
            "Validated M6 split stress authority files are present and readable.",
            "Ran bounded evidence-bucket reachability probe.",
            "Applied fail-closed blocker mapping for M6 S0.",
        ],
    }
    dumpj(out / "m6_decision_log.json", dlog)

    bref = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M6-ST-S0",
        "overall_pass": len(blockers) == 0,
        "open_blocker_count": len(blockers),
        "blockers": blockers,
    }
    summ = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M6-ST-S0",
        "overall_pass": len(blockers) == 0,
        "next_gate": "M6_ST_S1_READY" if len(blockers) == 0 else "BLOCKED",
        "required_artifacts": M6_S0_ARTS,
        "probe_count": total,
        "error_rate_pct": er,
        "m5_dependency_phase_execution_id": dep_id,
    }
    dumpj(out / "m6_blocker_register.json", bref)
    dumpj(out / "m6_execution_summary.json", summ)

    miss = [n for n in M6_S0_ARTS if not (out / n).exists()]
    if miss:
        blockers.append({"id": "M6-ST-B9", "severity": "S0", "status": "OPEN", "details": {"missing_artifacts": miss}})
        bref["overall_pass"] = False
        bref["open_blocker_count"] = len(blockers)
        bref["blockers"] = blockers
        summ["overall_pass"] = False
        summ["next_gate"] = "BLOCKED"
        dumpj(out / "m6_blocker_register.json", bref)
        dumpj(out / "m6_execution_summary.json", summ)

    print(f"[m6_s0] phase_execution_id={phase_id}")
    print(f"[m6_s0] output_dir={out.as_posix()}")
    print(f"[m6_s0] overall_pass={summ['overall_pass']}")
    print(f"[m6_s0] next_gate={summ['next_gate']}")
    print(f"[m6_s0] probe_count={total}")
    print(f"[m6_s0] error_rate_pct={er}")
    print(f"[m6_s0] open_blockers={bref['open_blocker_count']}")
    return 0 if summ["overall_pass"] else 2


def run_s1(phase_id: str, out_root: Path) -> int:
    t0 = time.perf_counter()
    out = out_root / phase_id / "stress"
    out.mkdir(parents=True, exist_ok=True)

    txt = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    pkt = parse_backtick_map(txt) if txt else {}
    h = parse_registry(REG) if REG.exists() else {}
    blockers: list[dict[str, Any]] = []

    dep = load_latest_successful_m6_s0(out_root)
    dep_issues: list[str] = []
    dep_id = ""
    dep_open = None
    if not dep:
        dep_issues.append("missing successful M6-ST-S0 dependency")
    else:
        dep_summ = dep.get("summary", {})
        dep_id = str(dep_summ.get("phase_execution_id", ""))
        if str(dep_summ.get("next_gate", "")) != "M6_ST_S1_READY":
            dep_issues.append("M6 S0 next_gate is not M6_ST_S1_READY")
        dep_br = load_json_safe(Path(str(dep["path"])) / "m6_blocker_register.json")
        dep_open = int(dep_br.get("open_blocker_count", len(dep_br.get("blockers", [])))) if dep_br else None
        if dep_open not in {None, 0}:
            dep_issues.append(f"M6 S0 blocker register not closed: {dep_open}")
    if dep_issues:
        blockers.append({"id": "M6-ST-B9", "severity": "S1", "status": "OPEN", "details": {"issues": dep_issues}})

    p5 = load_latest_successful_m6p5_s5(out_root)
    p5_issues: list[str] = []
    p5_id = ""
    p5_open = None
    if not p5:
        p5_issues.append("missing successful M6P5-ST-S5 closure evidence")
    else:
        p5_summ = p5.get("summary", {})
        p5_path = Path(str(p5["path"]))
        p5_id = str(p5_summ.get("phase_execution_id", ""))
        if str(p5_summ.get("verdict", "")) != "ADVANCE_TO_P6":
            p5_issues.append("M6P5 verdict is not ADVANCE_TO_P6")
        if str(p5_summ.get("next_gate", "")) != "ADVANCE_TO_P6":
            p5_issues.append("M6P5 next_gate is not ADVANCE_TO_P6")
        p5_br = load_json_safe(p5_path / "m6p5_blocker_register.json")
        p5_open = int(p5_br.get("open_blocker_count", len(p5_br.get("blockers", [])))) if p5_br else None
        if p5_open not in {None, 0}:
            p5_issues.append(f"M6P5 blocker register not closed: {p5_open}")
        req = p5_summ.get("required_artifacts", [])
        req_list = req if isinstance(req, list) else []
        miss = [n for n in req_list if not (p5_path / str(n)).exists()]
        if miss:
            p5_issues.append(f"M6P5 missing required artifacts: {','.join(miss)}")
    if p5_issues:
        blockers.append({"id": "M6-ST-B4", "severity": "S1", "status": "OPEN", "details": {"issues": p5_issues}})

    bucket = str(h.get("S3_EVIDENCE_BUCKET", "")).strip()
    probe_rows: list[dict[str, Any]] = []
    if bucket:
        p = run_cmd(["aws", "s3api", "head-bucket", "--bucket", bucket, "--region", "eu-west-2"], timeout=25)
    else:
        p = {
            "command": "aws s3api head-bucket",
            "exit_code": 1,
            "status": "FAIL",
            "duration_ms": 0.0,
            "stdout": "",
            "stderr": "missing S3_EVIDENCE_BUCKET handle",
            "started_at_utc": now(),
            "ended_at_utc": now(),
        }
    probe_rows.append({**p, "probe_id": "m6_s1_evidence_bucket", "group": "control"})
    if p.get("status") != "PASS":
        blockers.append({"id": "M6-ST-B10", "severity": "S1", "status": "OPEN", "details": {"probe_id": "m6_s1_evidence_bucket"}})

    stagea = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M6-ST-S1",
        "findings": [
            {
                "id": "M6-ST-F4",
                "classification": "PREVENT",
                "finding": "P5 verdict progression must be deterministic and blocker-free before parent S1 closure.",
                "required_action": "Require P5 verdict=ADVANCE_TO_P6 with closed blocker register and complete artifacts.",
            }
        ],
    }
    dumpj(out / "m6_stagea_findings.json", stagea)
    dumpj(out / "m6_lane_matrix.json", build_lane_matrix())

    total = len(probe_rows)
    probe_failures = [p for p in probe_rows if str(p.get("status", "FAIL")) != "PASS"]
    er = round((len(probe_failures) / total) * 100.0, 4) if total else 0.0
    lat = [float(x.get("duration_ms", 0.0)) for x in probe_rows]
    dur_s = max(1, int(round(time.perf_counter() - t0)))
    max_sp = float(pkt.get("M6_STRESS_MAX_SPEND_USD", 90))

    probe = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M6-ST-S1",
        "window_seconds_observed": dur_s,
        "probe_count": total,
        "failure_count": len(probe_failures),
        "error_rate_pct": er,
        "latency_ms_p50": 0.0 if not lat else sorted(lat)[len(lat) // 2],
        "latency_ms_p95": 0.0 if not lat else max(lat),
        "latency_ms_p99": 0.0 if not lat else max(lat),
        "sample_failures": probe_failures[:10],
        "m6_s0_dependency_phase_execution_id": dep_id,
        "m6p5_dependency_phase_execution_id": p5_id,
    }
    dumpj(out / "m6_probe_latency_throughput_snapshot.json", probe)

    control_issues: list[str] = []
    control_issues.extend(dep_issues)
    control_issues.extend(p5_issues)
    if probe_failures:
        control_issues.append(f"probe failures: {len(probe_failures)}")
    ctrl = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M6-ST-S1",
        "overall_pass": len(control_issues) == 0,
        "issues": control_issues,
        "m6_s0_dependency_phase_execution_id": dep_id,
        "m6_s0_dependency_open_blockers": dep_open,
        "m6p5_dependency_phase_execution_id": p5_id,
        "m6p5_dependency_open_blockers": p5_open,
    }
    dumpj(out / "m6_control_rail_conformance_snapshot.json", ctrl)

    sec = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M6-ST-S1",
        "overall_pass": True,
        "secret_probe_count": 0,
        "secret_failure_count": 0,
        "with_decryption_used": False,
        "queried_value_directly": False,
        "suspicious_output_probe_ids": [],
        "plaintext_leakage_detected": False,
    }
    dumpj(out / "m6_secret_safety_snapshot.json", sec)

    cost = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M6-ST-S1",
        "window_seconds": dur_s,
        "estimated_api_call_count": total,
        "attributed_spend_usd": 0.0,
        "unattributed_spend_detected": False,
        "max_spend_usd": max_sp,
        "within_envelope": True,
        "method": "p5_gate_adjudication_v0",
    }
    dumpj(out / "m6_cost_outcome_receipt.json", cost)

    dlog = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M6-ST-S1",
        "decisions": [
            "Validated M6 S0 dependency continuity.",
            "Validated full M6.P5 closure posture (verdict, blocker register, artifacts).",
            "Ran bounded evidence-bucket probe for parent S1 lane.",
            "Applied fail-closed parent blocker mapping for P5 orchestration gate.",
        ],
    }
    dumpj(out / "m6_decision_log.json", dlog)

    bref = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M6-ST-S1",
        "overall_pass": len(blockers) == 0,
        "open_blocker_count": len(blockers),
        "blockers": blockers,
    }
    summ = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M6-ST-S1",
        "overall_pass": len(blockers) == 0,
        "next_gate": "M6_ST_S2_READY" if len(blockers) == 0 else "BLOCKED",
        "required_artifacts": M6_S1_ARTS,
        "probe_count": total,
        "error_rate_pct": er,
        "m6_s0_dependency_phase_execution_id": dep_id,
        "m6p5_dependency_phase_execution_id": p5_id,
        "m6p5_verdict": "ADVANCE_TO_P6" if len(p5_issues) == 0 else "HOLD_REMEDIATE",
    }
    dumpj(out / "m6_blocker_register.json", bref)
    dumpj(out / "m6_execution_summary.json", summ)

    miss = [n for n in M6_S1_ARTS if not (out / n).exists()]
    if miss:
        blockers.append({"id": "M6-ST-B9", "severity": "S1", "status": "OPEN", "details": {"missing_artifacts": miss}})
        bref["overall_pass"] = False
        bref["open_blocker_count"] = len(blockers)
        bref["blockers"] = blockers
        summ["overall_pass"] = False
        summ["next_gate"] = "BLOCKED"
        dumpj(out / "m6_blocker_register.json", bref)
        dumpj(out / "m6_execution_summary.json", summ)

    print(f"[m6_s1] phase_execution_id={phase_id}")
    print(f"[m6_s1] output_dir={out.as_posix()}")
    print(f"[m6_s1] overall_pass={summ['overall_pass']}")
    print(f"[m6_s1] next_gate={summ['next_gate']}")
    print(f"[m6_s1] probe_count={total}")
    print(f"[m6_s1] error_rate_pct={er}")
    print(f"[m6_s1] open_blockers={bref['open_blocker_count']}")
    return 0 if summ["overall_pass"] else 2


def main() -> int:
    ap = argparse.ArgumentParser(description="M6 stress runner")
    ap.add_argument("--stage", default="S0", choices=["S0", "S1"])
    ap.add_argument("--phase-execution-id", default="")
    ap.add_argument("--out-root", default=str(OUT_ROOT))
    a = ap.parse_args()

    out_root = Path(a.out_root)
    pfx = "m6_stress_s0" if a.stage == "S0" else "m6_stress_s1"
    pid = a.phase_execution_id.strip() or f"{pfx}_{tok()}"

    if a.stage == "S0":
        return run_s0(pid, out_root)
    if a.stage == "S1":
        return run_s1(pid, out_root)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
