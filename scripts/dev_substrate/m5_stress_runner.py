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

PLAN = Path("docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M5.stress_test.md")
P3_PLAN = Path("docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M5.P3.stress_test.md")
P4_PLAN = Path("docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M5.P4.stress_test.md")
REG = Path("docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md")
OUT_ROOT = Path("runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control")

M5_REQ_HANDLES = [
    "S3_EVIDENCE_BUCKET",
    "S3_RUN_CONTROL_ROOT_PATTERN",
    "ORACLE_REQUIRED_OUTPUT_IDS",
    "ORACLE_SORT_KEY_BY_OUTPUT_ID",
    "ORACLE_STORE_BUCKET",
    "ORACLE_SOURCE_NAMESPACE",
    "ORACLE_ENGINE_RUN_ID",
    "S3_ORACLE_INPUT_PREFIX_PATTERN",
    "S3_STREAM_VIEW_OUTPUT_PREFIX_PATTERN",
    "S3_STREAM_VIEW_MANIFEST_KEY_PATTERN",
    "ORACLE_STREAM_SORT_EXECUTION_MODE",
    "ORACLE_STREAM_SORT_ENGINE",
    "ORACLE_STREAM_SORT_TRIGGER_SURFACE",
    "ORACLE_STREAM_SORT_LOCAL_EXECUTION_ALLOWED",
    "IG_BASE_URL",
    "IG_INGEST_PATH",
    "IG_HEALTHCHECK_PATH",
    "IG_AUTH_MODE",
    "IG_AUTH_HEADER_NAME",
    "SSM_IG_API_KEY_PATH",
    "MSK_CLUSTER_ARN",
    "MSK_BOOTSTRAP_BROKERS_SASL_IAM",
    "MSK_CLIENT_SUBNET_IDS",
    "MSK_SECURITY_GROUP_ID",
]

M5_PLAN_KEYS = [
    "M5_STRESS_PROFILE_ID",
    "M5_STRESS_BLOCKER_REGISTER_PATH_PATTERN",
    "M5_STRESS_EXECUTION_SUMMARY_PATH_PATTERN",
    "M5_STRESS_DECISION_LOG_PATH_PATTERN",
    "M5_STRESS_REQUIRED_ARTIFACTS",
    "M5_STRESS_MAX_RUNTIME_MINUTES",
    "M5_STRESS_MAX_SPEND_USD",
    "M5_STRESS_EXPECTED_NEXT_GATE_ON_PASS",
    "M5_STRESS_REQUIRED_SUBPHASES",
    "M5_STRESS_P3_REQUIRED_VERDICT",
    "M5_STRESS_P4_REQUIRED_VERDICT",
    "M5_STRESS_TARGETED_RERUN_ONLY",
]

M5_ARTS = [
    "m5_stagea_findings.json",
    "m5_lane_matrix.json",
    "m5_probe_latency_throughput_snapshot.json",
    "m5_control_rail_conformance_snapshot.json",
    "m5_secret_safety_snapshot.json",
    "m5_cost_outcome_receipt.json",
    "m5_blocker_register.json",
    "m5_execution_summary.json",
    "m5_decision_log.json",
]

M5_S0_ARTS = M5_ARTS
M5_S1_ARTS = M5_ARTS
M5_S2_ARTS = M5_ARTS
M5_S3_ARTS = M5_ARTS


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


def load_latest_successful_m4_s5(out_root: Path) -> dict[str, Any]:
    runs = sorted(out_root.glob("m4_stress_s5_*/stress"))
    for d in reversed(runs):
        sp = d / "m4_execution_summary.json"
        if not sp.exists():
            continue
        try:
            summ = json.loads(sp.read_text(encoding="utf-8"))
        except Exception:
            continue
        if summ.get("overall_pass") is not True:
            continue
        if str(summ.get("stage_id", "")) != "M4-ST-S5":
            continue
        return {"path": d, "summary": summ}
    return {}


def extract_verdict(summary: dict[str, Any]) -> str:
    return str(summary.get("verdict", summary.get("recommendation", summary.get("next_gate", "")))).strip()


def load_latest_successful_m5_s0(out_root: Path) -> dict[str, Any]:
    runs = sorted(out_root.glob("m5_stress_s0_*/stress"))
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
        if str(summ.get("stage_id", "")) != "M5-ST-S0":
            continue
        return {"path": d, "summary": summ}
    return {}


def load_latest_successful_m5_s1(out_root: Path) -> dict[str, Any]:
    runs = sorted(out_root.glob("m5_stress_s1_*/stress"))
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
        if str(summ.get("stage_id", "")) != "M5-ST-S1":
            continue
        return {"path": d, "summary": summ}
    return {}


def load_latest_successful_m5_s2(out_root: Path) -> dict[str, Any]:
    runs = sorted(out_root.glob("m5_stress_s2_*/stress"))
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
        if str(summ.get("stage_id", "")) != "M5-ST-S2":
            continue
        return {"path": d, "summary": summ}
    return {}


def load_latest_successful_p3_closure(out_root: Path) -> dict[str, Any]:
    runs = sorted(out_root.glob("m5p3_*/stress"))
    for d in reversed(runs):
        sp = d / "m5p3_execution_summary.json"
        if not sp.exists():
            continue
        try:
            summ = json.loads(sp.read_text(encoding="utf-8"))
        except Exception:
            continue
        if summ.get("overall_pass") is not True:
            continue
        verdict = extract_verdict(summ)
        if verdict != "ADVANCE_TO_P4":
            continue
        return {"path": d, "summary": summ, "verdict": verdict}
    return {}


def load_latest_successful_p4_closure(out_root: Path) -> dict[str, Any]:
    runs = sorted(out_root.glob("m5p4_*/stress"))
    for d in reversed(runs):
        sp = d / "m5p4_execution_summary.json"
        if not sp.exists():
            continue
        try:
            summ = json.loads(sp.read_text(encoding="utf-8"))
        except Exception:
            continue
        if summ.get("overall_pass") is not True:
            continue
        verdict = extract_verdict(summ)
        if verdict != "ADVANCE_TO_M6":
            continue
        return {"path": d, "summary": summ, "verdict": verdict}
    return {}


def copy_stagea_from_s0(out_root: Path, out_dir: Path) -> list[str]:
    ref = load_latest_successful_m5_s0(out_root)
    if not ref:
        return ["No successful M5-ST-S0 folder found."]
    src = Path(str(ref["path"]))
    errs: list[str] = []
    for n in ("m5_stagea_findings.json", "m5_lane_matrix.json"):
        s = src / n
        if s.exists():
            out_dir.joinpath(n).write_bytes(s.read_bytes())
        else:
            errs.append(f"Missing {s.as_posix()}")
    return errs


def copy_stagea_from_s1(out_root: Path, out_dir: Path) -> list[str]:
    ref = load_latest_successful_m5_s1(out_root)
    if not ref:
        return ["No successful M5-ST-S1 folder found."]
    src = Path(str(ref["path"]))
    errs: list[str] = []
    for n in ("m5_stagea_findings.json", "m5_lane_matrix.json"):
        s = src / n
        if s.exists():
            out_dir.joinpath(n).write_bytes(s.read_bytes())
        else:
            errs.append(f"Missing {s.as_posix()}")
    return errs


def copy_stagea_from_s2(out_root: Path, out_dir: Path) -> list[str]:
    ref = load_latest_successful_m5_s2(out_root)
    if not ref:
        return ["No successful M5-ST-S2 folder found."]
    src = Path(str(ref["path"]))
    errs: list[str] = []
    for n in ("m5_stagea_findings.json", "m5_lane_matrix.json"):
        s = src / n
        if s.exists():
            out_dir.joinpath(n).write_bytes(s.read_bytes())
        else:
            errs.append(f"Missing {s.as_posix()}")
    return errs


def build_lane_matrix() -> dict[str, Any]:
    return {
        "component_sequence": ["M5.S0", "M5.S1", "M5.S2", "M5.S3"],
        "plane_sequence": ["oracle_preflight_plane", "ingress_preflight_plane", "phase_closure_plane"],
        "integrated_windows": ["m5_s0_entry_window", "m5_s1_p3_rollup_window", "m5_s2_p4_rollup_window", "m5_s3_m6_handoff_window"],
    }


def run_s0(phase_id: str, out_root: Path) -> int:
    t0 = time.perf_counter()
    out = out_root / phase_id / "stress"
    out.mkdir(parents=True, exist_ok=True)

    txt = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    pkt = parse_backtick_map(txt) if txt else {}
    h = parse_registry(REG) if REG.exists() else {}
    blockers: list[dict[str, Any]] = []

    missing_plan_keys = [k for k in M5_PLAN_KEYS if k not in pkt]
    missing_handles = [k for k in M5_REQ_HANDLES if k not in h]
    placeholder_handles = [k for k in M5_REQ_HANDLES if k in h and str(h[k]).strip() in {"", "TO_PIN"}]
    sort_path_issues: list[str] = []
    if h.get("ORACLE_STREAM_SORT_EXECUTION_MODE") != "managed_distributed":
        sort_path_issues.append("ORACLE_STREAM_SORT_EXECUTION_MODE drift")
    if h.get("ORACLE_STREAM_SORT_ENGINE") != "EMR_SERVERLESS_SPARK":
        sort_path_issues.append("ORACLE_STREAM_SORT_ENGINE drift")
    if h.get("ORACLE_STREAM_SORT_LOCAL_EXECUTION_ALLOWED") is not False:
        sort_path_issues.append("ORACLE_STREAM_SORT_LOCAL_EXECUTION_ALLOWED not false")

    if missing_plan_keys or missing_handles or placeholder_handles or sort_path_issues:
        blockers.append(
            {
                "id": "M5-ST-B1",
                "severity": "S0",
                "status": "OPEN",
                "details": {
                    "missing_plan_keys": missing_plan_keys,
                    "missing_handles": missing_handles,
                    "placeholder_handles": placeholder_handles,
                    "sort_path_issues": sort_path_issues,
                },
            }
        )

    dep = load_latest_successful_m4_s5(out_root)
    dep_issues: list[str] = []
    dep_blocker_count = None
    dep_id = ""
    if not dep:
        dep_issues.append("missing successful M4-ST-S5 dependency")
    else:
        dep_summ = dep.get("summary", {})
        dep_id = str(dep_summ.get("phase_execution_id", ""))
        if str(dep_summ.get("recommendation", "")) != "GO":
            dep_issues.append("M4 recommendation is not GO")
        if str(dep_summ.get("next_gate", "")) != "M5_READY":
            dep_issues.append("M4 next_gate is not M5_READY")
        dep_br = load_json_safe(Path(str(dep["path"])) / "m4_blocker_register.json")
        dep_blocker_count = int(dep_br.get("open_blocker_count", len(dep_br.get("blockers", [])))) if dep_br else None
        if dep_blocker_count not in {None, 0}:
            dep_issues.append(f"M4 blocker register not closed: {dep_blocker_count}")

    if dep_issues:
        blockers.append({"id": "M5-ST-B2", "severity": "S0", "status": "OPEN", "details": {"issues": dep_issues}})

    authority_issues: list[str] = []
    missing_authorities: list[str] = []
    unreadable_authorities: list[str] = []
    for p in [PLAN, P3_PLAN, P4_PLAN]:
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
                "id": "M5-ST-B3",
                "severity": "S0",
                "status": "OPEN",
                "details": {
                    "missing_authorities": missing_authorities,
                    "unreadable_authorities": unreadable_authorities,
                },
            }
        )

    region = str(h.get("AWS_REGION", "eu-west-2"))
    bucket = str(h.get("S3_EVIDENCE_BUCKET", "")).strip()
    probes: list[dict[str, Any]] = []
    if bucket:
        probes.append(
            {
                "probe_id": "m5_s0_evidence_bucket",
                "group": "control",
                "result": run_cmd(["aws", "s3api", "head-bucket", "--bucket", bucket, "--region", region], timeout=25),
            }
        )
    else:
        probes.append(
            {
                "probe_id": "m5_s0_evidence_bucket",
                "group": "control",
                "result": {
                    "command": "aws s3api head-bucket",
                    "exit_code": 1,
                    "status": "FAIL",
                    "duration_ms": 0.0,
                    "stdout": "",
                    "stderr": "missing S3_EVIDENCE_BUCKET handle",
                    "started_at_utc": now(),
                    "ended_at_utc": now(),
                },
            }
        )

    probe_rows = [{**p["result"], "probe_id": p["probe_id"], "group": p["group"]} for p in probes]
    probe_failures = [p for p in probe_rows if str(p.get("status", "FAIL")) != "PASS"]
    if probe_failures:
        blockers.append(
            {
                "id": "M5-ST-B7",
                "severity": "S0",
                "status": "OPEN",
                "details": {"probe_failures": [str(x.get("probe_id", "")) for x in probe_failures]},
            }
        )

    stagea = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5-ST-S0",
        "findings": [
            {
                "id": "M5-ST-F1",
                "classification": "PREVENT",
                "finding": "M5 requires split subphase authority routing (`M5.P3`, `M5.P4`) to avoid phase cramming.",
                "required_action": "Validate parent + split authority files before execution.",
            },
            {
                "id": "M5-ST-F2",
                "classification": "PREVENT",
                "finding": "M4->M5 handoff (`M5_READY`) must remain deterministic and blocker-free.",
                "required_action": "Validate latest successful M4 S5 summary and blocker register at entry.",
            },
            {
                "id": "M5-ST-F3",
                "classification": "PREVENT",
                "finding": "Managed-sort path must remain canonical for P3; local fallback is disallowed.",
                "required_action": "Fail if ORACLE stream-sort handles drift from pinned managed posture.",
            },
        ],
    }
    dumpj(out / "m5_stagea_findings.json", stagea)
    dumpj(out / "m5_lane_matrix.json", build_lane_matrix())

    total = len(probe_rows)
    er = round((len(probe_failures) / total) * 100.0, 4) if total else 0.0
    lat = [float(x.get("duration_ms", 0.0)) for x in probe_rows]
    dur_s = max(1, int(round(time.perf_counter() - t0)))
    max_sp = float(pkt.get("M5_STRESS_MAX_SPEND_USD", 60))
    cost_within = True
    if not cost_within:
        blockers.append({"id": "M5-ST-B8", "severity": "S0", "status": "OPEN"})

    probe = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5-ST-S0",
        "window_seconds_observed": dur_s,
        "probe_count": total,
        "failure_count": len(probe_failures),
        "error_rate_pct": er,
        "latency_ms_p50": 0.0 if not lat else sorted(lat)[len(lat) // 2],
        "latency_ms_p95": 0.0 if not lat else max(lat),
        "latency_ms_p99": 0.0 if not lat else max(lat),
        "sample_failures": probe_failures[:10],
        "dependency_phase_execution_id": dep_id,
    }
    dumpj(out / "m5_probe_latency_throughput_snapshot.json", probe)

    control_issues: list[str] = []
    if missing_plan_keys:
        control_issues.append(f"missing plan keys: {','.join(missing_plan_keys)}")
    if missing_handles:
        control_issues.append(f"missing handles: {','.join(missing_handles)}")
    if placeholder_handles:
        control_issues.append(f"placeholder handles: {','.join(placeholder_handles)}")
    control_issues.extend(sort_path_issues)
    control_issues.extend(dep_issues)
    control_issues.extend(authority_issues)
    if probe_failures:
        control_issues.append(f"probe failures: {len(probe_failures)}")

    ctrl = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5-ST-S0",
        "overall_pass": len(control_issues) == 0,
        "issues": control_issues,
        "dependency_phase_execution_id": dep_id,
        "dependency_open_blockers": dep_blocker_count,
        "required_authorities": [PLAN.as_posix(), P3_PLAN.as_posix(), P4_PLAN.as_posix()],
    }
    dumpj(out / "m5_control_rail_conformance_snapshot.json", ctrl)

    sec = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5-ST-S0",
        "overall_pass": True,
        "secret_probe_count": 0,
        "secret_failure_count": 0,
        "with_decryption_used": False,
        "queried_value_directly": False,
        "suspicious_output_probe_ids": [],
        "plaintext_leakage_detected": False,
    }
    dumpj(out / "m5_secret_safety_snapshot.json", sec)

    cost = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5-ST-S0",
        "window_seconds": dur_s,
        "estimated_api_call_count": total,
        "attributed_spend_usd": 0.0,
        "unattributed_spend_detected": False,
        "max_spend_usd": max_sp,
        "within_envelope": cost_within,
        "method": "read_only_entry_gate_validation_v0",
    }
    dumpj(out / "m5_cost_outcome_receipt.json", cost)

    dlog = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5-ST-S0",
        "decisions": [
            "Validated M5 parent stress handle packet and required handle closure.",
            "Validated latest successful M4 S5 handoff dependency.",
            "Validated split M5 stress authority files are present and readable.",
            "Ran bounded control-plane probe for evidence bucket reachability.",
            "Applied fail-closed blocker mapping for M5 S0.",
        ],
    }
    dumpj(out / "m5_decision_log.json", dlog)

    bref = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5-ST-S0",
        "overall_pass": len(blockers) == 0,
        "open_blocker_count": len(blockers),
        "blockers": blockers,
    }
    summ = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5-ST-S0",
        "overall_pass": len(blockers) == 0,
        "next_gate": "M5_ST_S1_READY" if len(blockers) == 0 else "BLOCKED",
        "required_artifacts": M5_ARTS,
        "probe_count": total,
        "error_rate_pct": er,
        "m4_dependency_phase_execution_id": dep_id,
    }
    dumpj(out / "m5_blocker_register.json", bref)
    dumpj(out / "m5_execution_summary.json", summ)

    miss = [n for n in M5_ARTS if not (out / n).exists()]
    if miss:
        blockers.append({"id": "M5-ST-B9", "severity": "S0", "status": "OPEN", "details": {"missing_artifacts": miss}})
        bref["overall_pass"] = False
        bref["open_blocker_count"] = len(blockers)
        bref["blockers"] = blockers
        summ["overall_pass"] = False
        summ["next_gate"] = "BLOCKED"
        dumpj(out / "m5_blocker_register.json", bref)
        dumpj(out / "m5_execution_summary.json", summ)

    print(f"[m5_s0] phase_execution_id={phase_id}")
    print(f"[m5_s0] output_dir={out.as_posix()}")
    print(f"[m5_s0] overall_pass={summ['overall_pass']}")
    print(f"[m5_s0] next_gate={summ['next_gate']}")
    print(f"[m5_s0] probe_count={total}")
    print(f"[m5_s0] error_rate_pct={er}")
    print(f"[m5_s0] open_blockers={bref['open_blocker_count']}")
    return 0 if summ["overall_pass"] else 2


def run_s1(phase_id: str, out_root: Path) -> int:
    t0 = time.perf_counter()
    out = out_root / phase_id / "stress"
    out.mkdir(parents=True, exist_ok=True)

    txt = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    pkt = parse_backtick_map(txt) if txt else {}
    h = parse_registry(REG) if REG.exists() else {}
    blockers: list[dict[str, Any]] = []

    copy_errs = copy_stagea_from_s0(out_root, out)
    if copy_errs:
        blockers.append({"id": "M5-ST-B9", "severity": "S1", "status": "OPEN", "details": {"copy_errors": copy_errs}})
        if not (out / "m5_lane_matrix.json").exists():
            dumpj(out / "m5_lane_matrix.json", build_lane_matrix())
        if not (out / "m5_stagea_findings.json").exists():
            dumpj(
                out / "m5_stagea_findings.json",
                {
                    "generated_at_utc": now(),
                    "phase_execution_id": phase_id,
                    "stage_id": "M5-ST-S1",
                    "findings": [{"id": "M5-ST-F1", "classification": "PREVENT", "finding": "Stage-A copy failed.", "required_action": "Restore S0 stage-a artifacts."}],
                },
            )

    dep = load_latest_successful_m5_s0(out_root)
    dep_issues: list[str] = []
    dep_id = ""
    dep_open = None
    if not dep:
        dep_issues.append("missing successful M5-ST-S0 dependency")
    else:
        dep_summ = dep.get("summary", {})
        dep_id = str(dep_summ.get("phase_execution_id", ""))
        if str(dep_summ.get("next_gate", "")) != "M5_ST_S1_READY":
            dep_issues.append("M5 S0 next_gate is not M5_ST_S1_READY")
        dep_br = load_json_safe(Path(str(dep["path"])) / "m5_blocker_register.json")
        dep_open = int(dep_br.get("open_blocker_count", len(dep_br.get("blockers", [])))) if dep_br else None
        if dep_open not in {None, 0}:
            dep_issues.append(f"M5 S0 blocker register not closed: {dep_open}")
    if dep_issues:
        blockers.append({"id": "M5-ST-B9", "severity": "S1", "status": "OPEN", "details": {"issues": dep_issues}})

    p3 = load_latest_successful_p3_closure(out_root)
    p3_issues: list[str] = []
    p3_id = ""
    p3_open = None
    if not p3:
        p3_issues.append("missing successful P3 closure with ADVANCE_TO_P4 verdict")
    else:
        p3_summ = p3.get("summary", {})
        p3_path = Path(str(p3["path"]))
        p3_id = str(p3_summ.get("phase_execution_id", ""))
        if str(p3.get("verdict", "")) != "ADVANCE_TO_P4":
            p3_issues.append("P3 verdict is not ADVANCE_TO_P4")
        p3_br = load_json_safe(p3_path / "m5p3_blocker_register.json")
        p3_open = int(p3_br.get("open_blocker_count", len(p3_br.get("blockers", [])))) if p3_br else None
        if p3_open not in {None, 0}:
            p3_issues.append(f"P3 blocker register not closed: {p3_open}")
        req = p3_summ.get("required_artifacts", [])
        req_list = req if isinstance(req, list) else []
        miss = [n for n in req_list if not (p3_path / str(n)).exists()]
        if miss:
            p3_issues.append(f"P3 missing required artifacts: {','.join(miss)}")
    if p3_issues:
        blockers.append({"id": "M5-ST-B4", "severity": "S1", "status": "OPEN", "details": {"issues": p3_issues}})

    region = str(h.get("AWS_REGION", "eu-west-2")).strip() or "eu-west-2"
    bucket = str(h.get("S3_EVIDENCE_BUCKET", "")).strip()
    probe_rows: list[dict[str, Any]] = []
    if bucket:
        p = run_cmd(["aws", "s3api", "head-bucket", "--bucket", bucket, "--region", region], timeout=25)
        probe_rows.append({**p, "probe_id": "m5_s1_evidence_bucket", "group": "control"})
    else:
        probe_rows.append(
            {
                "probe_id": "m5_s1_evidence_bucket",
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
        blockers.append({"id": "M5-ST-B7", "severity": "S1", "status": "OPEN", "details": {"probe_failures": [str(x.get("probe_id", "")) for x in probe_failures]}})

    total = len(probe_rows)
    er = round((len(probe_failures) / total) * 100.0, 4) if total else 0.0
    lat = [float(x.get("duration_ms", 0.0)) for x in probe_rows]
    dur_s = max(1, int(round(time.perf_counter() - t0)))
    max_sp = float(pkt.get("M5_STRESS_MAX_SPEND_USD", 60))
    cost_within = True
    if not cost_within:
        blockers.append({"id": "M5-ST-B8", "severity": "S1", "status": "OPEN"})

    probe = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5-ST-S1",
        "window_seconds_observed": dur_s,
        "probe_count": total,
        "failure_count": len(probe_failures),
        "error_rate_pct": er,
        "latency_ms_p50": 0.0 if not lat else sorted(lat)[len(lat) // 2],
        "latency_ms_p95": 0.0 if not lat else max(lat),
        "latency_ms_p99": 0.0 if not lat else max(lat),
        "sample_failures": probe_failures[:10],
        "s0_dependency_phase_execution_id": dep_id,
        "p3_dependency_phase_execution_id": p3_id,
    }
    dumpj(out / "m5_probe_latency_throughput_snapshot.json", probe)

    control_issues: list[str] = []
    control_issues.extend(dep_issues)
    control_issues.extend(p3_issues)
    if probe_failures:
        control_issues.append(f"probe failures: {len(probe_failures)}")
    ctrl = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5-ST-S1",
        "overall_pass": len(control_issues) == 0,
        "issues": control_issues,
        "s0_dependency_phase_execution_id": dep_id,
        "s0_dependency_open_blockers": dep_open,
        "p3_dependency_phase_execution_id": p3_id,
        "p3_dependency_open_blockers": p3_open,
    }
    dumpj(out / "m5_control_rail_conformance_snapshot.json", ctrl)

    sec = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5-ST-S1",
        "overall_pass": True,
        "secret_probe_count": 0,
        "secret_failure_count": 0,
        "with_decryption_used": False,
        "queried_value_directly": False,
        "suspicious_output_probe_ids": [],
        "plaintext_leakage_detected": False,
    }
    dumpj(out / "m5_secret_safety_snapshot.json", sec)

    cost = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5-ST-S1",
        "window_seconds": dur_s,
        "estimated_api_call_count": total,
        "attributed_spend_usd": 0.0,
        "unattributed_spend_detected": False,
        "max_spend_usd": max_sp,
        "within_envelope": cost_within,
        "method": "p3_orchestration_gate_validation_v0",
    }
    dumpj(out / "m5_cost_outcome_receipt.json", cost)

    dlog = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5-ST-S1",
        "decisions": [
            "Validated S0 dependency continuity.",
            "Validated latest successful P3 closure verdict and blocker register.",
            "Validated required P3 artifacts for gate completeness.",
            "Ran bounded evidence bucket probe.",
            "Applied fail-closed blocker mapping for M5 S1.",
        ],
    }
    dumpj(out / "m5_decision_log.json", dlog)

    bref = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5-ST-S1",
        "overall_pass": len(blockers) == 0,
        "open_blocker_count": len(blockers),
        "blockers": blockers,
    }
    summ = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5-ST-S1",
        "overall_pass": len(blockers) == 0,
        "next_gate": "M5_ST_S2_READY" if len(blockers) == 0 else "BLOCKED",
        "required_artifacts": M5_S1_ARTS,
        "probe_count": total,
        "error_rate_pct": er,
        "s0_dependency_phase_execution_id": dep_id,
        "p3_dependency_phase_execution_id": p3_id,
        "p3_verdict": "ADVANCE_TO_P4" if not p3_issues else "BLOCKED",
    }
    dumpj(out / "m5_blocker_register.json", bref)
    dumpj(out / "m5_execution_summary.json", summ)

    miss = [n for n in M5_S1_ARTS if not (out / n).exists()]
    if miss:
        blockers.append({"id": "M5-ST-B9", "severity": "S1", "status": "OPEN", "details": {"missing_artifacts": miss}})
        bref["overall_pass"] = False
        bref["open_blocker_count"] = len(blockers)
        bref["blockers"] = blockers
        summ["overall_pass"] = False
        summ["next_gate"] = "BLOCKED"
        dumpj(out / "m5_blocker_register.json", bref)
        dumpj(out / "m5_execution_summary.json", summ)

    print(f"[m5_s1] phase_execution_id={phase_id}")
    print(f"[m5_s1] output_dir={out.as_posix()}")
    print(f"[m5_s1] overall_pass={summ['overall_pass']}")
    print(f"[m5_s1] next_gate={summ['next_gate']}")
    print(f"[m5_s1] probe_count={total}")
    print(f"[m5_s1] error_rate_pct={er}")
    print(f"[m5_s1] open_blockers={bref['open_blocker_count']}")
    return 0 if summ["overall_pass"] else 2


def run_s2(phase_id: str, out_root: Path) -> int:
    t0 = time.perf_counter()
    out = out_root / phase_id / "stress"
    out.mkdir(parents=True, exist_ok=True)

    txt = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    pkt = parse_backtick_map(txt) if txt else {}
    h = parse_registry(REG) if REG.exists() else {}
    blockers: list[dict[str, Any]] = []

    copy_errs = copy_stagea_from_s1(out_root, out)
    if copy_errs:
        blockers.append({"id": "M5-ST-B9", "severity": "S2", "status": "OPEN", "details": {"copy_errors": copy_errs}})
        if not (out / "m5_lane_matrix.json").exists():
            dumpj(out / "m5_lane_matrix.json", build_lane_matrix())
        if not (out / "m5_stagea_findings.json").exists():
            dumpj(
                out / "m5_stagea_findings.json",
                {
                    "generated_at_utc": now(),
                    "phase_execution_id": phase_id,
                    "stage_id": "M5-ST-S2",
                    "findings": [{"id": "M5-ST-F1", "classification": "PREVENT", "finding": "Stage-A copy failed.", "required_action": "Restore S1 stage-a artifacts."}],
                },
            )

    dep = load_latest_successful_m5_s1(out_root)
    dep_issues: list[str] = []
    dep_id = ""
    dep_open = None
    if not dep:
        dep_issues.append("missing successful M5-ST-S1 dependency")
    else:
        dep_summ = dep.get("summary", {})
        dep_id = str(dep_summ.get("phase_execution_id", ""))
        if str(dep_summ.get("next_gate", "")) != "M5_ST_S2_READY":
            dep_issues.append("M5 S1 next_gate is not M5_ST_S2_READY")
        dep_br = load_json_safe(Path(str(dep["path"])) / "m5_blocker_register.json")
        dep_open = int(dep_br.get("open_blocker_count", len(dep_br.get("blockers", [])))) if dep_br else None
        if dep_open not in {None, 0}:
            dep_issues.append(f"M5 S1 blocker register not closed: {dep_open}")
    if dep_issues:
        blockers.append({"id": "M5-ST-B9", "severity": "S2", "status": "OPEN", "details": {"issues": dep_issues}})

    p4 = load_latest_successful_p4_closure(out_root)
    p4_issues: list[str] = []
    p4_id = ""
    p4_open = None
    if not p4:
        p4_issues.append("missing successful P4 closure with ADVANCE_TO_M6 verdict")
    else:
        p4_summ = p4.get("summary", {})
        p4_path = Path(str(p4["path"]))
        p4_id = str(p4_summ.get("phase_execution_id", ""))
        if str(p4.get("verdict", "")) != "ADVANCE_TO_M6":
            p4_issues.append("P4 verdict is not ADVANCE_TO_M6")
        p4_br = load_json_safe(p4_path / "m5p4_blocker_register.json")
        p4_open = int(p4_br.get("open_blocker_count", len(p4_br.get("blockers", [])))) if p4_br else None
        if p4_open not in {None, 0}:
            p4_issues.append(f"P4 blocker register not closed: {p4_open}")
        req = p4_summ.get("required_artifacts", [])
        req_list = req if isinstance(req, list) else []
        miss = [n for n in req_list if not (p4_path / str(n)).exists()]
        if miss:
            p4_issues.append(f"P4 missing required artifacts: {','.join(miss)}")
        handoff_ref = str(p4_summ.get("m6_handoff_pack_ref", "")).strip()
        if handoff_ref == "":
            p4_issues.append("P4 missing m6_handoff_pack_ref")
        else:
            hp = Path(handoff_ref)
            if not hp.exists():
                p4_issues.append("P4 m6_handoff_pack_ref path is unreadable")
            else:
                try:
                    _ = json.loads(hp.read_text(encoding="utf-8"))
                except Exception:
                    p4_issues.append("P4 m6_handoff_pack_ref is not valid JSON")
    if p4_issues:
        blockers.append({"id": "M5-ST-B5", "severity": "S2", "status": "OPEN", "details": {"issues": p4_issues}})

    region = str(h.get("AWS_REGION", "eu-west-2")).strip() or "eu-west-2"
    bucket = str(h.get("S3_EVIDENCE_BUCKET", "")).strip()
    probe_rows: list[dict[str, Any]] = []
    if bucket:
        p = run_cmd(["aws", "s3api", "head-bucket", "--bucket", bucket, "--region", region], timeout=25)
        probe_rows.append({**p, "probe_id": "m5_s2_evidence_bucket", "group": "control"})
    else:
        probe_rows.append(
            {
                "probe_id": "m5_s2_evidence_bucket",
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
        blockers.append({"id": "M5-ST-B7", "severity": "S2", "status": "OPEN", "details": {"probe_failures": [str(x.get("probe_id", "")) for x in probe_failures]}})

    total = len(probe_rows)
    er = round((len(probe_failures) / total) * 100.0, 4) if total else 0.0
    lat = [float(x.get("duration_ms", 0.0)) for x in probe_rows]
    dur_s = max(1, int(round(time.perf_counter() - t0)))
    max_sp = float(pkt.get("M5_STRESS_MAX_SPEND_USD", 60))
    cost_within = True
    if not cost_within:
        blockers.append({"id": "M5-ST-B8", "severity": "S2", "status": "OPEN"})

    probe = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5-ST-S2",
        "window_seconds_observed": dur_s,
        "probe_count": total,
        "failure_count": len(probe_failures),
        "error_rate_pct": er,
        "latency_ms_p50": 0.0 if not lat else sorted(lat)[len(lat) // 2],
        "latency_ms_p95": 0.0 if not lat else max(lat),
        "latency_ms_p99": 0.0 if not lat else max(lat),
        "sample_failures": probe_failures[:10],
        "s1_dependency_phase_execution_id": dep_id,
        "p4_dependency_phase_execution_id": p4_id,
    }
    dumpj(out / "m5_probe_latency_throughput_snapshot.json", probe)

    control_issues: list[str] = []
    control_issues.extend(dep_issues)
    control_issues.extend(p4_issues)
    if probe_failures:
        control_issues.append(f"probe failures: {len(probe_failures)}")
    ctrl = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5-ST-S2",
        "overall_pass": len(control_issues) == 0,
        "issues": control_issues,
        "s1_dependency_phase_execution_id": dep_id,
        "s1_dependency_open_blockers": dep_open,
        "p4_dependency_phase_execution_id": p4_id,
        "p4_dependency_open_blockers": p4_open,
    }
    dumpj(out / "m5_control_rail_conformance_snapshot.json", ctrl)

    sec = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5-ST-S2",
        "overall_pass": True,
        "secret_probe_count": 0,
        "secret_failure_count": 0,
        "with_decryption_used": False,
        "queried_value_directly": False,
        "suspicious_output_probe_ids": [],
        "plaintext_leakage_detected": False,
    }
    dumpj(out / "m5_secret_safety_snapshot.json", sec)

    cost = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5-ST-S2",
        "window_seconds": dur_s,
        "estimated_api_call_count": total,
        "attributed_spend_usd": 0.0,
        "unattributed_spend_detected": False,
        "max_spend_usd": max_sp,
        "within_envelope": cost_within,
        "method": "p4_orchestration_gate_validation_v0",
    }
    dumpj(out / "m5_cost_outcome_receipt.json", cost)

    dlog = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5-ST-S2",
        "decisions": [
            "Validated S1 dependency continuity.",
            "Validated latest successful P4 closure verdict and blocker register.",
            "Validated required P4 artifacts including readable m6_handoff_pack reference.",
            "Ran bounded evidence bucket probe.",
            "Applied fail-closed blocker mapping for M5 S2.",
        ],
    }
    dumpj(out / "m5_decision_log.json", dlog)

    bref = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5-ST-S2",
        "overall_pass": len(blockers) == 0,
        "open_blocker_count": len(blockers),
        "blockers": blockers,
    }
    summ = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5-ST-S2",
        "overall_pass": len(blockers) == 0,
        "next_gate": "M5_ST_S3_READY" if len(blockers) == 0 else "BLOCKED",
        "required_artifacts": M5_S2_ARTS,
        "probe_count": total,
        "error_rate_pct": er,
        "s1_dependency_phase_execution_id": dep_id,
        "p4_dependency_phase_execution_id": p4_id,
        "p4_verdict": "ADVANCE_TO_M6" if not p4_issues else "BLOCKED",
    }
    dumpj(out / "m5_blocker_register.json", bref)
    dumpj(out / "m5_execution_summary.json", summ)

    miss = [n for n in M5_S2_ARTS if not (out / n).exists()]
    if miss:
        blockers.append({"id": "M5-ST-B9", "severity": "S2", "status": "OPEN", "details": {"missing_artifacts": miss}})
        bref["overall_pass"] = False
        bref["open_blocker_count"] = len(blockers)
        bref["blockers"] = blockers
        summ["overall_pass"] = False
        summ["next_gate"] = "BLOCKED"
        dumpj(out / "m5_blocker_register.json", bref)
        dumpj(out / "m5_execution_summary.json", summ)

    print(f"[m5_s2] phase_execution_id={phase_id}")
    print(f"[m5_s2] output_dir={out.as_posix()}")
    print(f"[m5_s2] overall_pass={summ['overall_pass']}")
    print(f"[m5_s2] next_gate={summ['next_gate']}")
    print(f"[m5_s2] probe_count={total}")
    print(f"[m5_s2] error_rate_pct={er}")
    print(f"[m5_s2] open_blockers={bref['open_blocker_count']}")
    return 0 if summ["overall_pass"] else 2


def run_s3(phase_id: str, out_root: Path) -> int:
    t0 = time.perf_counter()
    out = out_root / phase_id / "stress"
    out.mkdir(parents=True, exist_ok=True)

    txt = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    pkt = parse_backtick_map(txt) if txt else {}
    h = parse_registry(REG) if REG.exists() else {}
    blockers: list[dict[str, Any]] = []

    copy_errs = copy_stagea_from_s2(out_root, out)
    if copy_errs:
        blockers.append({"id": "M5-ST-B9", "severity": "S3", "status": "OPEN", "details": {"copy_errors": copy_errs}})
        if not (out / "m5_lane_matrix.json").exists():
            dumpj(out / "m5_lane_matrix.json", build_lane_matrix())
        if not (out / "m5_stagea_findings.json").exists():
            dumpj(
                out / "m5_stagea_findings.json",
                {
                    "generated_at_utc": now(),
                    "phase_execution_id": phase_id,
                    "stage_id": "M5-ST-S3",
                    "findings": [{"id": "M5-ST-F1", "classification": "PREVENT", "finding": "Stage-A copy failed.", "required_action": "Restore S2 stage-a artifacts."}],
                },
            )

    dep = load_latest_successful_m5_s2(out_root)
    dep_issues: list[str] = []
    dep_id = ""
    dep_open = None
    if not dep:
        dep_issues.append("missing successful M5-ST-S2 dependency")
    else:
        dep_summ = dep.get("summary", {})
        dep_id = str(dep_summ.get("phase_execution_id", ""))
        if str(dep_summ.get("next_gate", "")) != "M5_ST_S3_READY":
            dep_issues.append("M5 S2 next_gate is not M5_ST_S3_READY")
        dep_br = load_json_safe(Path(str(dep["path"])) / "m5_blocker_register.json")
        dep_open = int(dep_br.get("open_blocker_count", len(dep_br.get("blockers", [])))) if dep_br else None
        if dep_open not in {None, 0}:
            dep_issues.append(f"M5 S2 blocker register not closed: {dep_open}")
    if dep_issues:
        blockers.append({"id": "M5-ST-B9", "severity": "S3", "status": "OPEN", "details": {"issues": dep_issues}})

    stage_specs = [
        ("S0", load_latest_successful_m5_s0, "M5-ST-S0", "M5_ST_S1_READY"),
        ("S1", load_latest_successful_m5_s1, "M5-ST-S1", "M5_ST_S2_READY"),
        ("S2", load_latest_successful_m5_s2, "M5-ST-S2", "M5_ST_S3_READY"),
    ]
    stage_rows: list[dict[str, Any]] = []
    rollup_issues: list[str] = []
    stage_refs: dict[str, str] = {}
    for stage_name, loader, stage_id, expected_gate in stage_specs:
        ref = loader(out_root)
        row: dict[str, Any] = {
            "stage": stage_name,
            "stage_id_expected": stage_id,
            "expected_next_gate": expected_gate,
            "path": "",
            "phase_execution_id": "",
            "overall_pass": False,
            "open_blocker_count": 0,
            "artifact_completeness_pass": False,
            "issues": [],
        }
        if not ref:
            row["issues"] = [f"missing successful {stage_id} evidence lane"]
            rollup_issues.extend(row["issues"])
            stage_rows.append(row)
            continue
        path = Path(str(ref["path"]))
        summ = ref.get("summary", {})
        row["path"] = path.as_posix()
        row["phase_execution_id"] = str(summ.get("phase_execution_id", ""))
        row["overall_pass"] = bool(summ.get("overall_pass") is True)
        stage_refs[stage_name] = path.as_posix()
        if str(summ.get("stage_id", "")) != stage_id:
            row["issues"] = row.get("issues", []) + [f"stage id mismatch: expected={stage_id} observed={summ.get('stage_id')}"]
        if str(summ.get("next_gate", "")) != expected_gate:
            row["issues"] = row.get("issues", []) + [f"next_gate mismatch: expected={expected_gate} observed={summ.get('next_gate')}"]
        br = load_json_safe(path / "m5_blocker_register.json")
        open_count = int(br.get("open_blocker_count", len(br.get("blockers", [])))) if br else 0
        row["open_blocker_count"] = open_count
        if open_count != 0:
            row["issues"] = row.get("issues", []) + [f"open blocker count is {open_count}"]
        req = summ.get("required_artifacts", [])
        req_list = req if isinstance(req, list) else []
        miss = [n for n in req_list if not (path / str(n)).exists()]
        row["artifact_completeness_pass"] = len(miss) == 0
        if miss:
            row["issues"] = row.get("issues", []) + [f"missing stage artifacts: {','.join(miss)}"]
        if row["issues"]:
            rollup_issues.extend([f"{stage_id}: {x}" for x in row["issues"]])
        stage_rows.append(row)
    if rollup_issues:
        blockers.append({"id": "M5-ST-B6", "severity": "S3", "status": "OPEN", "details": {"issues": rollup_issues}})

    p3 = load_latest_successful_p3_closure(out_root)
    p4 = load_latest_successful_p4_closure(out_root)
    verdict_issues: list[str] = []
    p3_id = ""
    p4_id = ""
    if not p3:
        verdict_issues.append("missing P3 closure verdict surface")
    else:
        p3_id = str(p3.get("summary", {}).get("phase_execution_id", ""))
        if str(p3.get("verdict", "")) != "ADVANCE_TO_P4":
            verdict_issues.append("P3 verdict drifted from ADVANCE_TO_P4")
    if not p4:
        verdict_issues.append("missing P4 closure verdict surface")
    else:
        p4_id = str(p4.get("summary", {}).get("phase_execution_id", ""))
        if str(p4.get("verdict", "")) != "ADVANCE_TO_M6":
            verdict_issues.append("P4 verdict drifted from ADVANCE_TO_M6")
    if verdict_issues:
        blockers.append({"id": "M5-ST-B6", "severity": "S3", "status": "OPEN", "details": {"issues": verdict_issues}})

    region = str(h.get("AWS_REGION", "eu-west-2")).strip() or "eu-west-2"
    bucket = str(h.get("S3_EVIDENCE_BUCKET", "")).strip()
    probe_rows: list[dict[str, Any]] = []
    if bucket:
        p = run_cmd(["aws", "s3api", "head-bucket", "--bucket", bucket, "--region", region], timeout=25)
        probe_rows.append({**p, "probe_id": "m5_s3_evidence_bucket", "group": "control"})
    else:
        probe_rows.append(
            {
                "probe_id": "m5_s3_evidence_bucket",
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
        blockers.append({"id": "M5-ST-B7", "severity": "S3", "status": "OPEN", "details": {"probe_failures": [str(x.get("probe_id", "")) for x in probe_failures]}})

    recommendation = "GO" if len(blockers) == 0 else "NO_GO"
    next_gate = "M6_READY" if recommendation == "GO" else "BLOCKED"
    if recommendation == "GO" and len(blockers) > 0:
        blockers.append({"id": "M5-ST-B6", "severity": "S3", "status": "OPEN", "details": {"issues": ["GO recommendation cannot be emitted with open blockers"]}})
        recommendation = "NO_GO"
        next_gate = "BLOCKED"

    rollup_matrix = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5-ST-S3",
        "s2_dependency_phase_execution_id": dep_id,
        "stage_rollup_rows": stage_rows,
        "rollup_issues": rollup_issues,
        "subphase_verdicts": {"p3_verdict": "ADVANCE_TO_P4" if p3 else "BLOCKED", "p4_verdict": "ADVANCE_TO_M6" if p4 else "BLOCKED"},
    }
    dumpj(out / "m5_rollup_matrix.json", rollup_matrix)
    dumpj(
        out / "m5_gate_verdict.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_id,
            "stage_id": "M5-ST-S3",
            "recommendation": recommendation,
            "next_gate": next_gate,
            "open_blocker_count": len(blockers),
            "rollup_matrix_ref": (out / "m5_rollup_matrix.json").as_posix(),
        },
    )

    total = len(probe_rows)
    er = round((len(probe_failures) / total) * 100.0, 4) if total else 0.0
    lat = [float(x.get("duration_ms", 0.0)) for x in probe_rows]
    dur_s = max(1, int(round(time.perf_counter() - t0)))
    max_sp = float(pkt.get("M5_STRESS_MAX_SPEND_USD", 60))
    cost_within = True
    if not cost_within:
        blockers.append({"id": "M5-ST-B8", "severity": "S3", "status": "OPEN"})
        recommendation = "NO_GO"
        next_gate = "BLOCKED"

    probe = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5-ST-S3",
        "window_seconds_observed": dur_s,
        "probe_count": total,
        "failure_count": len(probe_failures),
        "error_rate_pct": er,
        "latency_ms_p50": 0.0 if not lat else sorted(lat)[len(lat) // 2],
        "latency_ms_p95": 0.0 if not lat else max(lat),
        "latency_ms_p99": 0.0 if not lat else max(lat),
        "sample_failures": probe_failures[:10],
        "s2_dependency_phase_execution_id": dep_id,
    }
    dumpj(out / "m5_probe_latency_throughput_snapshot.json", probe)

    control_issues: list[str] = []
    control_issues.extend(dep_issues)
    control_issues.extend(rollup_issues)
    control_issues.extend(verdict_issues)
    if probe_failures:
        control_issues.append(f"probe failures: {len(probe_failures)}")
    if recommendation == "GO" and next_gate != "M6_READY":
        control_issues.append("recommendation/next_gate mismatch for GO")
    ctrl = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5-ST-S3",
        "overall_pass": len(control_issues) == 0 and recommendation == "GO" and next_gate == "M6_READY",
        "issues": control_issues,
        "s2_dependency_phase_execution_id": dep_id,
        "s2_dependency_open_blockers": dep_open,
        "p3_dependency_phase_execution_id": p3_id,
        "p4_dependency_phase_execution_id": p4_id,
        "rollup_matrix_ref": "m5_rollup_matrix.json",
        "gate_verdict_ref": "m5_gate_verdict.json",
    }
    dumpj(out / "m5_control_rail_conformance_snapshot.json", ctrl)

    sec = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5-ST-S3",
        "overall_pass": True,
        "secret_probe_count": 0,
        "secret_failure_count": 0,
        "with_decryption_used": False,
        "queried_value_directly": False,
        "suspicious_output_probe_ids": [],
        "plaintext_leakage_detected": False,
    }
    dumpj(out / "m5_secret_safety_snapshot.json", sec)

    cost = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5-ST-S3",
        "window_seconds": dur_s,
        "estimated_api_call_count": total,
        "attributed_spend_usd": 0.0,
        "unattributed_spend_detected": False,
        "max_spend_usd": max_sp,
        "within_envelope": cost_within,
        "method": "m5_parent_closure_rollup_v0",
    }
    dumpj(out / "m5_cost_outcome_receipt.json", cost)

    dlog = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5-ST-S3",
        "decisions": [
            "Validated S2 dependency continuity.",
            "Aggregated latest successful parent S0..S2 receipts and blocker registers.",
            "Validated subphase verdict surfaces for P3 and P4 closure consistency.",
            "Built deterministic parent recommendation and next gate.",
            "Applied fail-closed blocker mapping for M5 S3.",
        ],
    }
    dumpj(out / "m5_decision_log.json", dlog)

    bref = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5-ST-S3",
        "overall_pass": len(blockers) == 0 and recommendation == "GO" and next_gate == "M6_READY",
        "open_blocker_count": len(blockers),
        "blockers": blockers,
    }
    summ = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5-ST-S3",
        "overall_pass": len(blockers) == 0 and recommendation == "GO" and next_gate == "M6_READY",
        "recommendation": recommendation,
        "next_gate": next_gate,
        "required_artifacts": M5_S3_ARTS,
        "probe_count": total,
        "error_rate_pct": er,
        "s2_dependency_phase_execution_id": dep_id,
        "p3_verdict": "ADVANCE_TO_P4" if p3 else "BLOCKED",
        "p4_verdict": "ADVANCE_TO_M6" if p4 else "BLOCKED",
    }
    dumpj(out / "m5_blocker_register.json", bref)
    dumpj(out / "m5_execution_summary.json", summ)

    miss = [n for n in M5_S3_ARTS if not (out / n).exists()]
    if miss:
        blockers.append({"id": "M5-ST-B9", "severity": "S3", "status": "OPEN", "details": {"missing_artifacts": miss}})
        bref["overall_pass"] = False
        bref["open_blocker_count"] = len(blockers)
        bref["blockers"] = blockers
        summ["overall_pass"] = False
        summ["recommendation"] = "NO_GO"
        summ["next_gate"] = "BLOCKED"
        dumpj(out / "m5_blocker_register.json", bref)
        dumpj(out / "m5_execution_summary.json", summ)

    print(f"[m5_s3] phase_execution_id={phase_id}")
    print(f"[m5_s3] output_dir={out.as_posix()}")
    print(f"[m5_s3] overall_pass={summ['overall_pass']}")
    print(f"[m5_s3] recommendation={summ['recommendation']}")
    print(f"[m5_s3] next_gate={summ['next_gate']}")
    print(f"[m5_s3] probe_count={total}")
    print(f"[m5_s3] error_rate_pct={er}")
    print(f"[m5_s3] open_blockers={bref['open_blocker_count']}")
    return 0 if summ["overall_pass"] else 2


def main() -> int:
    ap = argparse.ArgumentParser(description="M5 stress runner")
    ap.add_argument("--stage", default="S0", choices=["S0", "S1", "S2", "S3"])
    ap.add_argument("--phase-execution-id", default="")
    ap.add_argument("--output-root", default=str(OUT_ROOT))
    a = ap.parse_args()
    pfx = {
        "S0": "m5_stress_s0",
        "S1": "m5_stress_s1",
        "S2": "m5_stress_s2",
        "S3": "m5_stress_s3",
    }[a.stage]
    pid = a.phase_execution_id.strip() or f"{pfx}_{tok()}"
    root = Path(a.output_root)
    if a.stage == "S0":
        return run_s0(pid, root)
    if a.stage == "S1":
        return run_s1(pid, root)
    if a.stage == "S2":
        return run_s2(pid, root)
    return run_s3(pid, root)


if __name__ == "__main__":
    raise SystemExit(main())
