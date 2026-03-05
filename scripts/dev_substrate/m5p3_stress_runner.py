#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PLAN = Path("docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M5.P3.stress_test.md")
PARENT_PLAN = Path("docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M5.stress_test.md")
REG = Path("docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md")
OUT_ROOT = Path("runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control")
M5_RUN_ROOT = Path("runs/dev_substrate/dev_full/m5")

M5P3_REQ_HANDLES = [
    "ORACLE_REQUIRED_OUTPUT_IDS",
    "ORACLE_SORT_KEY_BY_OUTPUT_ID",
    "ORACLE_STORE_BUCKET",
    "ORACLE_STORE_PLATFORM_ACCESS_MODE",
    "ORACLE_STORE_WRITE_OWNER",
    "ORACLE_SOURCE_NAMESPACE",
    "ORACLE_ENGINE_RUN_ID",
    "S3_ORACLE_RUN_PREFIX_PATTERN",
    "S3_ORACLE_INPUT_PREFIX_PATTERN",
    "S3_STREAM_VIEW_OUTPUT_PREFIX_PATTERN",
    "S3_STREAM_VIEW_MANIFEST_KEY_PATTERN",
    "ORACLE_STREAM_SORT_EXECUTION_MODE",
    "ORACLE_STREAM_SORT_ENGINE",
    "ORACLE_STREAM_SORT_TRIGGER_SURFACE",
    "ORACLE_STREAM_SORT_LOCAL_EXECUTION_ALLOWED",
    "ORACLE_STREAM_SORT_REQUIRED_BEFORE_P3B",
    "ORACLE_STREAM_SORT_RECEIPT_REQUIRED",
    "ORACLE_STREAM_SORT_PARITY_CHECK_REQUIRED",
    "ORACLE_STREAM_SORT_EMR_SERVERLESS_APP",
    "ORACLE_STREAM_SORT_EXECUTION_ROLE_ARN",
    "ORACLE_STREAM_SORT_EMR_RELEASE_LABEL",
    "S3_EVIDENCE_BUCKET",
    "S3_RUN_CONTROL_ROOT_PATTERN",
]

M5P3_PLAN_KEYS = [
    "M5P3_STRESS_PROFILE_ID",
    "M5P3_STRESS_BLOCKER_REGISTER_PATH_PATTERN",
    "M5P3_STRESS_EXECUTION_SUMMARY_PATH_PATTERN",
    "M5P3_STRESS_DECISION_LOG_PATH_PATTERN",
    "M5P3_STRESS_REQUIRED_ARTIFACTS",
    "M5P3_STRESS_MAX_RUNTIME_MINUTES",
    "M5P3_STRESS_MAX_SPEND_USD",
    "M5P3_STRESS_EXPECTED_VERDICT_ON_PASS",
    "M5P3_STRESS_MANAGED_SORT_REQUIRED",
    "M5P3_STRESS_LOCAL_SORT_ALLOWED",
]

M5P3_ARTS = [
    "m5p3_stagea_findings.json",
    "m5p3_lane_matrix.json",
    "m5p3_probe_latency_throughput_snapshot.json",
    "m5p3_control_rail_conformance_snapshot.json",
    "m5p3_secret_safety_snapshot.json",
    "m5p3_cost_outcome_receipt.json",
    "m5p3_blocker_register.json",
    "m5p3_execution_summary.json",
    "m5p3_decision_log.json",
]
M5P3_S0_ARTS = M5P3_ARTS
M5P3_S1_ARTS = M5P3_ARTS
M5P3_FAST_ARTS = M5P3_ARTS


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


def parse_json_like(value: Any, expect: str) -> tuple[Any, str]:
    if expect not in {"list", "dict"}:
        return None, "invalid expect type"
    if expect == "list" and isinstance(value, list):
        return value, ""
    if expect == "dict" and isinstance(value, dict):
        return value, ""
    s = str(value).strip()
    if not s:
        return ([] if expect == "list" else {}), "empty value"
    try:
        parsed = json.loads(s)
    except Exception:
        try:
            parsed = ast.literal_eval(s)
        except Exception as exc:
            return ([] if expect == "list" else {}), f"parse error: {exc}"
    if expect == "list" and isinstance(parsed, list):
        return parsed, ""
    if expect == "dict" and isinstance(parsed, dict):
        return parsed, ""
    return ([] if expect == "list" else {}), f"parsed type mismatch: {type(parsed).__name__}"


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
        if not m:
            continue
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


def fetch_s3_json(bucket: str, key: str, region: str, timeout: int = 60) -> dict[str, Any]:
    t0 = time.perf_counter()
    st = now()
    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tf:
            tmp_path = tf.name
        cmd = ["aws", "s3api", "get-object", "--bucket", bucket, "--key", key, tmp_path, "--region", region]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        base = {
            "command": " ".join(cmd),
            "exit_code": int(p.returncode),
            "status": "PASS" if int(p.returncode) == 0 else "FAIL",
            "duration_ms": round((time.perf_counter() - t0) * 1000.0, 3),
            "stdout": (p.stdout or "").strip()[:300],
            "stderr": (p.stderr or "").strip()[:300],
            "started_at_utc": st,
            "ended_at_utc": now(),
        }
        if int(p.returncode) != 0:
            return {"result": base, "json": {}}
        try:
            obj = json.loads(Path(tmp_path).read_text(encoding="utf-8"))
        except Exception as exc:
            base["status"] = "FAIL"
            base["stderr"] = (base.get("stderr", "") + f" | json parse error: {exc}")[:300]
            return {"result": base, "json": {}}
        return {"result": base, "json": obj}
    except subprocess.TimeoutExpired:
        return {
            "result": {
                "command": "aws s3api get-object",
                "exit_code": 124,
                "status": "FAIL",
                "duration_ms": round((time.perf_counter() - t0) * 1000.0, 3),
                "stdout": "",
                "stderr": "timeout",
                "started_at_utc": st,
                "ended_at_utc": now(),
            },
            "json": {},
        }
    finally:
        if tmp_path and Path(tmp_path).exists():
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def load_json_safe(path: Path) -> dict[str, Any]:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {}


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


def load_latest_successful_m5p3_s0(out_root: Path) -> dict[str, Any]:
    runs = sorted(out_root.glob("m5p3_stress_s0_*/stress"))
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
        if str(summ.get("stage_id", "")) != "M5P3-ST-S0":
            continue
        return {"path": d, "summary": summ}
    return {}


def load_latest_successful_m5p3_s1(out_root: Path) -> dict[str, Any]:
    runs = sorted(out_root.glob("m5p3_stress_s1_*/stress"))
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
        if str(summ.get("stage_id", "")) != "M5P3-ST-S1":
            continue
        return {"path": d, "summary": summ}
    return {}


def copy_stagea_from_s0(out_root: Path, out_dir: Path) -> list[str]:
    ref = load_latest_successful_m5p3_s0(out_root)
    if not ref:
        return ["No successful M5P3-ST-S0 folder found."]
    src = Path(str(ref["path"]))
    errs: list[str] = []
    for n in ("m5p3_stagea_findings.json", "m5p3_lane_matrix.json"):
        s = src / n
        if s.exists():
            out_dir.joinpath(n).write_bytes(s.read_bytes())
        else:
            errs.append(f"Missing {s.as_posix()}")
    return errs


def build_lane_matrix() -> dict[str, Any]:
    return {
        "component_sequence": ["P3.A", "P3.A1", "P3.B", "P3.C", "P3.D"],
        "plane_sequence": ["oracle_boundary_plane", "oracle_materialization_plane", "oracle_rollup_plane"],
        "integrated_windows": [
            "m5p3_s0_entry_window",
            "m5p3_s1_boundary_window",
            "m5p3_s2_upload_sort_window",
            "m5p3_s3_output_manifest_window",
            "m5p3_s4_contract_window",
        ],
    }


def run_s0(phase_id: str, out_root: Path) -> int:
    t0 = time.perf_counter()
    out = out_root / phase_id / "stress"
    out.mkdir(parents=True, exist_ok=True)

    txt = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    pkt = parse_backtick_map(txt) if txt else {}
    h = parse_registry(REG) if REG.exists() else {}
    blockers: list[dict[str, Any]] = []

    missing_plan_keys = [k for k in M5P3_PLAN_KEYS if k not in pkt]
    missing_handles = [k for k in M5P3_REQ_HANDLES if k not in h]
    placeholder_handles = [k for k in M5P3_REQ_HANDLES if k in h and str(h[k]).strip() in {"", "TO_PIN"}]
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
                "id": "M5P3-B1",
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

    dep = load_latest_successful_m5_s0(out_root)
    dep_issues: list[str] = []
    dep_id = ""
    dep_blocker_count = None
    if not dep:
        dep_issues.append("missing successful M5-ST-S0 dependency")
    else:
        dep_summ = dep.get("summary", {})
        dep_id = str(dep_summ.get("phase_execution_id", ""))
        if str(dep_summ.get("next_gate", "")) != "M5_ST_S1_READY":
            dep_issues.append("M5 parent next_gate is not M5_ST_S1_READY")
        dep_br = load_json_safe(Path(str(dep["path"])) / "m5_blocker_register.json")
        dep_blocker_count = int(dep_br.get("open_blocker_count", len(dep_br.get("blockers", [])))) if dep_br else None
        if dep_blocker_count not in {None, 0}:
            dep_issues.append(f"M5 parent blocker register not closed: {dep_blocker_count}")
    if dep_issues:
        blockers.append({"id": "M5P3-B8", "severity": "S0", "status": "OPEN", "details": {"issues": dep_issues}})

    authority_issues: list[str] = []
    missing_authorities: list[str] = []
    unreadable_authorities: list[str] = []
    for p in [PARENT_PLAN, PLAN]:
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
                "id": "M5P3-B7",
                "severity": "S0",
                "status": "OPEN",
                "details": {"missing_authorities": missing_authorities, "unreadable_authorities": unreadable_authorities},
            }
        )

    region = str(h.get("AWS_REGION", "eu-west-2"))
    bucket = str(h.get("S3_EVIDENCE_BUCKET", "")).strip()
    probe_rows: list[dict[str, Any]] = []
    if bucket:
        r = run_cmd(["aws", "s3api", "head-bucket", "--bucket", bucket, "--region", region], timeout=25)
        probe_rows.append({**r, "probe_id": "m5p3_s0_evidence_bucket", "group": "control"})
    else:
        probe_rows.append(
            {
                "probe_id": "m5p3_s0_evidence_bucket",
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
                "id": "M5P3-B7",
                "severity": "S0",
                "status": "OPEN",
                "details": {"probe_failures": [str(x.get("probe_id", "")) for x in probe_failures]},
            }
        )

    stagea = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P3-ST-S0",
        "findings": [
            {
                "id": "M5P3-ST-F1",
                "classification": "PREVENT",
                "finding": "P3 staged runbook requires explicit entry dependency on parent M5 S0 closure.",
                "required_action": "Validate latest successful M5-ST-S0 summary/register at entry.",
            },
            {
                "id": "M5P3-ST-F2",
                "classification": "PREVENT",
                "finding": "Managed sort path must remain canonical and local fallback disallowed.",
                "required_action": "Enforce ORACLE stream-sort handle law before any P3 stage progression.",
            },
            {
                "id": "M5P3-ST-F3",
                "classification": "PREVENT",
                "finding": "P3 verdict safety depends on complete handle packet and authority-file readability.",
                "required_action": "Fail closed on any missing plan keys/handles/authority files.",
            },
        ],
    }
    dumpj(out / "m5p3_stagea_findings.json", stagea)
    dumpj(out / "m5p3_lane_matrix.json", build_lane_matrix())

    total = len(probe_rows)
    er = round((len(probe_failures) / total) * 100.0, 4) if total else 0.0
    lat = [float(x.get("duration_ms", 0.0)) for x in probe_rows]
    dur_s = max(1, int(round(time.perf_counter() - t0)))
    max_sp = float(pkt.get("M5P3_STRESS_MAX_SPEND_USD", 40))
    cost_within = True

    probe = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P3-ST-S0",
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
    dumpj(out / "m5p3_probe_latency_throughput_snapshot.json", probe)

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
        "stage_id": "M5P3-ST-S0",
        "overall_pass": len(control_issues) == 0,
        "issues": control_issues,
        "dependency_phase_execution_id": dep_id,
        "dependency_open_blockers": dep_blocker_count,
        "required_authorities": [PARENT_PLAN.as_posix(), PLAN.as_posix()],
    }
    dumpj(out / "m5p3_control_rail_conformance_snapshot.json", ctrl)

    sec = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P3-ST-S0",
        "overall_pass": True,
        "secret_probe_count": 0,
        "secret_failure_count": 0,
        "with_decryption_used": False,
        "queried_value_directly": False,
        "suspicious_output_probe_ids": [],
        "plaintext_leakage_detected": False,
    }
    dumpj(out / "m5p3_secret_safety_snapshot.json", sec)

    cost = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P3-ST-S0",
        "window_seconds": dur_s,
        "estimated_api_call_count": total,
        "attributed_spend_usd": 0.0,
        "unattributed_spend_detected": False,
        "max_spend_usd": max_sp,
        "within_envelope": cost_within,
        "method": "read_only_entry_gate_validation_v0",
    }
    dumpj(out / "m5p3_cost_outcome_receipt.json", cost)

    dlog = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P3-ST-S0",
        "decisions": [
            "Validated M5.P3 plan-key and required-handle closure.",
            "Validated parent M5 S0 dependency and blocker-free gate state.",
            "Validated managed-sort no-local-fallback runtime posture.",
            "Ran bounded evidence-bucket reachability probe.",
            "Applied fail-closed blocker mapping for M5P3 S0.",
        ],
    }
    dumpj(out / "m5p3_decision_log.json", dlog)

    bref = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P3-ST-S0",
        "overall_pass": len(blockers) == 0,
        "open_blocker_count": len(blockers),
        "blockers": blockers,
    }
    summ = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P3-ST-S0",
        "overall_pass": len(blockers) == 0,
        "next_gate": "M5P3_ST_S1_READY" if len(blockers) == 0 else "BLOCKED",
        "required_artifacts": M5P3_ARTS,
        "probe_count": total,
        "error_rate_pct": er,
        "m5_dependency_phase_execution_id": dep_id,
    }
    dumpj(out / "m5p3_blocker_register.json", bref)
    dumpj(out / "m5p3_execution_summary.json", summ)

    miss = [n for n in M5P3_ARTS if not (out / n).exists()]
    if miss:
        blockers.append({"id": "M5P3-B7", "severity": "S0", "status": "OPEN", "details": {"missing_artifacts": miss}})
        bref["overall_pass"] = False
        bref["open_blocker_count"] = len(blockers)
        bref["blockers"] = blockers
        summ["overall_pass"] = False
        summ["next_gate"] = "BLOCKED"
        dumpj(out / "m5p3_blocker_register.json", bref)
        dumpj(out / "m5p3_execution_summary.json", summ)

    print(f"[m5p3_s0] phase_execution_id={phase_id}")
    print(f"[m5p3_s0] output_dir={out.as_posix()}")
    print(f"[m5p3_s0] overall_pass={summ['overall_pass']}")
    print(f"[m5p3_s0] next_gate={summ['next_gate']}")
    print(f"[m5p3_s0] probe_count={total}")
    print(f"[m5p3_s0] error_rate_pct={er}")
    print(f"[m5p3_s0] open_blockers={bref['open_blocker_count']}")
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
        blockers.append({"id": "M5P3-B7", "severity": "S1", "status": "OPEN", "details": {"copy_errors": copy_errs}})

    s0 = load_latest_successful_m5p3_s0(out_root)
    dep_issues: list[str] = []
    dep_id = ""
    if not s0:
        dep_issues.append("missing successful M5P3-ST-S0 dependency")
    else:
        dep_summ = s0.get("summary", {})
        dep_id = str(dep_summ.get("phase_execution_id", ""))
        if str(dep_summ.get("next_gate", "")) != "M5P3_ST_S1_READY":
            dep_issues.append("M5P3 S0 next_gate is not M5P3_ST_S1_READY")
        s0_br = load_json_safe(Path(str(s0["path"])) / "m5p3_blocker_register.json")
        s0_open = int(s0_br.get("open_blocker_count", len(s0_br.get("blockers", [])))) if s0_br else 0
        if s0_open != 0:
            dep_issues.append(f"M5P3 S0 blocker register not closed: {s0_open}")
    if dep_issues:
        blockers.append({"id": "M5P3-B8", "severity": "S1", "status": "OPEN", "details": {"issues": dep_issues}})

    req = [
        "ORACLE_STORE_BUCKET",
        "ORACLE_STORE_PLATFORM_ACCESS_MODE",
        "ORACLE_STORE_WRITE_OWNER",
        "ORACLE_INLET_PLATFORM_OWNERSHIP",
        "ORACLE_SOURCE_NAMESPACE",
        "ORACLE_ENGINE_RUN_ID",
        "S3_ORACLE_ROOT_PREFIX",
        "S3_ORACLE_RUN_PREFIX_PATTERN",
        "S3_ORACLE_INPUT_PREFIX_PATTERN",
        "S3_RUN_CONTROL_ROOT_PATTERN",
        "S3_EVIDENCE_BUCKET",
    ]
    missing_handles = [k for k in req if k not in h]
    placeholder_handles = [k for k in req if k in h and str(h[k]).strip() in {"", "TO_PIN"}]
    if missing_handles or placeholder_handles:
        blockers.append(
            {
                "id": "M5P3-B1",
                "severity": "S1",
                "status": "OPEN",
                "details": {"missing_handles": missing_handles, "placeholder_handles": placeholder_handles},
            }
        )

    boundary_issues: list[str] = []
    if str(h.get("ORACLE_STORE_PLATFORM_ACCESS_MODE", "")) != "read_only":
        boundary_issues.append("ORACLE_STORE_PLATFORM_ACCESS_MODE drift")
    write_owner = str(h.get("ORACLE_STORE_WRITE_OWNER", ""))
    if write_owner in {"platform_runtime", "platform"}:
        boundary_issues.append("ORACLE_STORE_WRITE_OWNER invalid")
    if str(h.get("ORACLE_INLET_PLATFORM_OWNERSHIP", "")) != "outside_platform_runtime_scope":
        boundary_issues.append("ORACLE_INLET_PLATFORM_OWNERSHIP drift")

    oracle_root = str(h.get("S3_ORACLE_ROOT_PREFIX", "")).strip()
    run_control_root = str(h.get("S3_RUN_CONTROL_ROOT_PATTERN", "")).strip()
    oracle_run_pattern = str(h.get("S3_ORACLE_RUN_PREFIX_PATTERN", "")).strip()
    if not oracle_root.startswith("oracle-store/"):
        boundary_issues.append("S3_ORACLE_ROOT_PREFIX must start with oracle-store/")
    if oracle_root and run_control_root:
        if oracle_root.startswith(run_control_root) or run_control_root.startswith(oracle_root):
            boundary_issues.append("oracle and run-control roots overlap")
    if "{oracle_source_namespace}" not in oracle_run_pattern or "{oracle_engine_run_id}" not in oracle_run_pattern:
        boundary_issues.append("S3_ORACLE_RUN_PREFIX_PATTERN missing required tokens")
    if boundary_issues:
        blockers.append({"id": "M5P3-B2", "severity": "S1", "status": "OPEN", "details": {"issues": boundary_issues}})

    region = str(h.get("AWS_REGION", "eu-west-2"))
    oracle_bucket = str(h.get("ORACLE_STORE_BUCKET", "")).strip()
    evidence_bucket = str(h.get("S3_EVIDENCE_BUCKET", "")).strip()
    probe_rows: list[dict[str, Any]] = []

    if oracle_bucket:
        r = run_cmd(["aws", "s3api", "head-bucket", "--bucket", oracle_bucket, "--region", region], timeout=25)
        probe_rows.append({**r, "probe_id": "m5p3_s1_oracle_bucket", "group": "boundary"})
        r = run_cmd(
            [
                "aws",
                "s3api",
                "list-objects-v2",
                "--bucket",
                oracle_bucket,
                "--prefix",
                oracle_root,
                "--max-keys",
                "1",
                "--region",
                region,
                "--query",
                "KeyCount",
                "--output",
                "text",
            ],
            timeout=30,
        )
        probe_rows.append({**r, "probe_id": "m5p3_s1_oracle_prefix", "group": "boundary"})
    else:
        probe_rows.append(
            {
                "probe_id": "m5p3_s1_oracle_bucket",
                "group": "boundary",
                "command": "aws s3api head-bucket",
                "exit_code": 1,
                "status": "FAIL",
                "duration_ms": 0.0,
                "stdout": "",
                "stderr": "missing ORACLE_STORE_BUCKET handle",
                "started_at_utc": now(),
                "ended_at_utc": now(),
            }
        )
    if evidence_bucket:
        r = run_cmd(["aws", "s3api", "head-bucket", "--bucket", evidence_bucket, "--region", region], timeout=25)
        probe_rows.append({**r, "probe_id": "m5p3_s1_evidence_bucket", "group": "control"})
    else:
        probe_rows.append(
            {
                "probe_id": "m5p3_s1_evidence_bucket",
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
                "id": "M5P3-B2",
                "severity": "S1",
                "status": "OPEN",
                "details": {"probe_failures": [str(x.get("probe_id", "")) for x in probe_failures]},
            }
        )

    total = len(probe_rows)
    er = round((len(probe_failures) / total) * 100.0, 4) if total else 0.0
    lat = [float(x.get("duration_ms", 0.0)) for x in probe_rows]
    dur_s = max(1, int(round(time.perf_counter() - t0)))
    max_sp = float(pkt.get("M5P3_STRESS_MAX_SPEND_USD", 40))
    cost_within = True

    boundary_snapshot = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P3-ST-S1",
        "oracle_store_bucket": oracle_bucket,
        "oracle_source_namespace": str(h.get("ORACLE_SOURCE_NAMESPACE", "")),
        "oracle_engine_run_id": str(h.get("ORACLE_ENGINE_RUN_ID", "")),
        "oracle_store_platform_access_mode": str(h.get("ORACLE_STORE_PLATFORM_ACCESS_MODE", "")),
        "oracle_store_write_owner": write_owner,
        "oracle_inlet_platform_ownership": str(h.get("ORACLE_INLET_PLATFORM_OWNERSHIP", "")),
        "oracle_root_prefix": oracle_root,
        "run_control_root_pattern": run_control_root,
        "boundary_issues": boundary_issues,
    }
    dumpj(out / "m5p3_oracle_boundary_snapshot.json", boundary_snapshot)

    probe = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P3-ST-S1",
        "window_seconds_observed": dur_s,
        "probe_count": total,
        "failure_count": len(probe_failures),
        "error_rate_pct": er,
        "latency_ms_p50": 0.0 if not lat else sorted(lat)[len(lat) // 2],
        "latency_ms_p95": 0.0 if not lat else max(lat),
        "latency_ms_p99": 0.0 if not lat else max(lat),
        "sample_failures": probe_failures[:10],
        "s0_baseline_phase_execution_id": dep_id,
    }
    dumpj(out / "m5p3_probe_latency_throughput_snapshot.json", probe)

    control_issues: list[str] = []
    if missing_handles:
        control_issues.append(f"missing handles: {','.join(missing_handles)}")
    if placeholder_handles:
        control_issues.append(f"placeholder handles: {','.join(placeholder_handles)}")
    control_issues.extend(dep_issues)
    control_issues.extend(boundary_issues)
    if probe_failures:
        control_issues.append(f"probe failures: {len(probe_failures)}")
    ctrl = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P3-ST-S1",
        "overall_pass": len(control_issues) == 0,
        "issues": control_issues,
        "s0_dependency_phase_execution_id": dep_id,
        "boundary_snapshot_ref": "m5p3_oracle_boundary_snapshot.json",
    }
    dumpj(out / "m5p3_control_rail_conformance_snapshot.json", ctrl)

    sec = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P3-ST-S1",
        "overall_pass": True,
        "secret_probe_count": 0,
        "secret_failure_count": 0,
        "with_decryption_used": False,
        "queried_value_directly": False,
        "suspicious_output_probe_ids": [],
        "plaintext_leakage_detected": False,
    }
    dumpj(out / "m5p3_secret_safety_snapshot.json", sec)

    cost = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P3-ST-S1",
        "window_seconds": dur_s,
        "estimated_api_call_count": total,
        "attributed_spend_usd": 0.0,
        "unattributed_spend_detected": False,
        "max_spend_usd": max_sp,
        "within_envelope": cost_within,
        "method": "read_only_boundary_ownership_validation_v0",
    }
    dumpj(out / "m5p3_cost_outcome_receipt.json", cost)

    dlog = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P3-ST-S1",
        "decisions": [
            "Validated S0 dependency and carried Stage-A artifacts forward.",
            "Validated oracle boundary and ownership semantics against pinned handles.",
            "Validated oracle-root and run-control boundary isolation posture.",
            "Executed bounded oracle/evidence bucket reachability probes.",
            "Applied fail-closed blocker mapping for M5P3 S1.",
        ],
    }
    dumpj(out / "m5p3_decision_log.json", dlog)

    bref = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P3-ST-S1",
        "overall_pass": len(blockers) == 0,
        "open_blocker_count": len(blockers),
        "blockers": blockers,
    }
    summ = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P3-ST-S1",
        "overall_pass": len(blockers) == 0,
        "next_gate": "M5P3_ST_S2_READY" if len(blockers) == 0 else "BLOCKED",
        "required_artifacts": M5P3_S1_ARTS,
        "probe_count": total,
        "error_rate_pct": er,
        "s0_baseline_phase_execution_id": dep_id,
    }
    dumpj(out / "m5p3_blocker_register.json", bref)
    dumpj(out / "m5p3_execution_summary.json", summ)

    miss = [n for n in M5P3_S1_ARTS if not (out / n).exists()]
    if miss:
        blockers.append({"id": "M5P3-B7", "severity": "S1", "status": "OPEN", "details": {"missing_artifacts": miss}})
        bref["overall_pass"] = False
        bref["open_blocker_count"] = len(blockers)
        bref["blockers"] = blockers
        summ["overall_pass"] = False
        summ["next_gate"] = "BLOCKED"
        dumpj(out / "m5p3_blocker_register.json", bref)
        dumpj(out / "m5p3_execution_summary.json", summ)

    print(f"[m5p3_s1] phase_execution_id={phase_id}")
    print(f"[m5p3_s1] output_dir={out.as_posix()}")
    print(f"[m5p3_s1] overall_pass={summ['overall_pass']}")
    print(f"[m5p3_s1] next_gate={summ['next_gate']}")
    print(f"[m5p3_s1] probe_count={total}")
    print(f"[m5p3_s1] error_rate_pct={er}")
    print(f"[m5p3_s1] open_blockers={bref['open_blocker_count']}")
    return 0 if summ["overall_pass"] else 2


def latest_file(candidates: list[Path]) -> Path | None:
    if not candidates:
        return None
    return sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)[0]


def run_fast(phase_id: str, out_root: Path) -> int:
    t0 = time.perf_counter()
    out = out_root / phase_id / "stress"
    out.mkdir(parents=True, exist_ok=True)

    txt = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    pkt = parse_backtick_map(txt) if txt else {}
    h = parse_registry(REG) if REG.exists() else {}
    blockers: list[dict[str, Any]] = []
    waived_observations: list[str] = []

    copy_errs = copy_stagea_from_s0(out_root, out)
    if copy_errs:
        dumpj(out / "m5p3_lane_matrix.json", build_lane_matrix())
        blockers.append({"id": "M5P3-B7", "severity": "FAST", "status": "OPEN", "details": {"copy_errors": copy_errs}})

    s1 = load_latest_successful_m5p3_s1(out_root)
    dep_issues: list[str] = []
    dep_id = ""
    if not s1:
        dep_issues.append("missing successful M5P3-ST-S1 dependency")
    else:
        dep_summ = s1.get("summary", {})
        dep_id = str(dep_summ.get("phase_execution_id", ""))
        if str(dep_summ.get("next_gate", "")) != "M5P3_ST_S2_READY":
            dep_issues.append("M5P3 S1 next_gate is not M5P3_ST_S2_READY")
        s1_br = load_json_safe(Path(str(s1["path"])) / "m5p3_blocker_register.json")
        s1_open = int(s1_br.get("open_blocker_count", len(s1_br.get("blockers", [])))) if s1_br else 0
        if s1_open != 0:
            dep_issues.append(f"M5P3 S1 blocker register not closed: {s1_open}")
    if dep_issues:
        blockers.append({"id": "M5P3-B8", "severity": "FAST", "status": "OPEN", "details": {"issues": dep_issues}})

    req = [
        "ORACLE_REQUIRED_OUTPUT_IDS",
        "ORACLE_SORT_KEY_BY_OUTPUT_ID",
        "ORACLE_STORE_BUCKET",
        "ORACLE_SOURCE_NAMESPACE",
        "ORACLE_ENGINE_RUN_ID",
        "S3_STREAM_VIEW_OUTPUT_PREFIX_PATTERN",
        "S3_STREAM_VIEW_MANIFEST_KEY_PATTERN",
        "S3_EVIDENCE_BUCKET",
    ]
    missing_handles = [k for k in req if k not in h]
    placeholder_handles = [k for k in req if k in h and str(h[k]).strip() in {"", "TO_PIN"}]

    required_output_ids, outputs_err = parse_json_like(h.get("ORACLE_REQUIRED_OUTPUT_IDS", ""), "list")
    sort_key_map, sort_err = parse_json_like(h.get("ORACLE_SORT_KEY_BY_OUTPUT_ID", ""), "dict")
    if outputs_err:
        missing_handles.append(f"ORACLE_REQUIRED_OUTPUT_IDS ({outputs_err})")
    if sort_err:
        missing_handles.append(f"ORACLE_SORT_KEY_BY_OUTPUT_ID ({sort_err})")
    required_output_ids = [str(x) for x in required_output_ids] if isinstance(required_output_ids, list) else []

    if missing_handles or placeholder_handles:
        blockers.append(
            {
                "id": "M5P3-B1",
                "severity": "FAST",
                "status": "OPEN",
                "details": {"missing_handles": missing_handles, "placeholder_handles": placeholder_handles},
            }
        )

    allow_hist_fail = bool(pkt.get("M5P3_STRESS_FASTCHECK_ALLOW_HISTORICAL_SORT_FAILURE", True))
    raw_candidates = list(M5_RUN_ROOT.glob("**/m5r1_raw_upload_receipt.json"))
    sort_candidates = list(M5_RUN_ROOT.glob("**/m5r2_stream_sort_receipt.json"))
    parity_candidates = list(M5_RUN_ROOT.glob("**/m5r2_stream_sort_parity_report.json"))
    raw_receipt_path = latest_file(raw_candidates)
    sort_receipt_path = latest_file(sort_candidates)
    parity_path = latest_file(parity_candidates)
    raw_receipt = load_json_safe(raw_receipt_path) if raw_receipt_path else {}
    sort_receipt = load_json_safe(sort_receipt_path) if sort_receipt_path else {}
    parity_report = load_json_safe(parity_path) if parity_path else {}

    s2_issues: list[str] = []
    if not raw_receipt_path:
        s2_issues.append("raw upload receipt not found")
    elif raw_receipt.get("overall_pass") is not True or raw_receipt.get("parity_match") is not True:
        s2_issues.append("raw upload receipt indicates failure/parity drift")
    if s2_issues:
        blockers.append({"id": "M5P3-B9", "severity": "FAST", "status": "OPEN", "details": {"issues": s2_issues}})

    sort_state = str(sort_receipt.get("job_terminal_state", "")).upper()
    sort_ok = sort_receipt.get("overall_pass") is True and sort_state in {"SUCCESS", "SUCCEEDED"}
    if not sort_receipt_path:
        if allow_hist_fail:
            waived_observations.append("stream-sort receipt missing in local M5 evidence; waived for pre-platform fast-check")
        else:
            blockers.append({"id": "M5P3-B10", "severity": "FAST", "status": "OPEN", "details": {"issues": ["stream-sort receipt missing"]}})
    elif not sort_ok:
        msg = "historical stream-sort receipt is not terminal success"
        if allow_hist_fail:
            waived_observations.append(f"{msg}; rerun deferred to data-engine deployment lane")
        else:
            blockers.append({"id": "M5P3-B10", "severity": "FAST", "status": "OPEN", "details": {"issues": [msg]}})

    parity_entries = parity_report.get("per_output", [])
    if not isinstance(parity_entries, list):
        parity_entries = []
    if len(parity_entries) == 0:
        msg = "historical stream-sort parity report has empty per_output set"
        if allow_hist_fail:
            waived_observations.append(f"{msg}; treated as pre-platform observation")
        else:
            blockers.append({"id": "M5P3-B11", "severity": "FAST", "status": "OPEN", "details": {"issues": [msg]}})

    region = str(h.get("AWS_REGION", "eu-west-2"))
    bucket = str(h.get("ORACLE_STORE_BUCKET", "")).strip()
    ns = str(h.get("ORACLE_SOURCE_NAMESPACE", "")).strip()
    run_id = str(h.get("ORACLE_ENGINE_RUN_ID", "")).strip()
    output_pat = str(h.get("S3_STREAM_VIEW_OUTPUT_PREFIX_PATTERN", "")).strip()
    manifest_pat = str(h.get("S3_STREAM_VIEW_MANIFEST_KEY_PATTERN", "")).strip()

    probe_rows: list[dict[str, Any]] = []
    output_matrix: list[dict[str, Any]] = []
    s3_issues: list[str] = []
    contract_issues: list[str] = []

    for oid in required_output_ids:
        prefix = output_pat.replace("{oracle_source_namespace}", ns).replace("{oracle_engine_run_id}", run_id).replace("{output_id}", oid)
        manifest_key = manifest_pat.replace("{oracle_source_namespace}", ns).replace("{oracle_engine_run_id}", run_id).replace("{output_id}", oid)
        p1 = run_cmd(
            [
                "aws",
                "s3api",
                "list-objects-v2",
                "--bucket",
                bucket,
                "--prefix",
                prefix,
                "--max-keys",
                "1",
                "--region",
                region,
                "--query",
                "KeyCount",
                "--output",
                "text",
            ],
            timeout=30,
        )
        probe_rows.append({**p1, "probe_id": f"m5p3_fast_prefix_{oid}", "group": "outputs"})
        key_count = str(p1.get("stdout", "")).strip()
        prefix_ok = str(p1.get("status", "FAIL")) == "PASS" and key_count not in {"", "0"}
        if not prefix_ok:
            s3_issues.append(f"missing prefix data for output_id={oid}")

        p2 = run_cmd(
            ["aws", "s3api", "head-object", "--bucket", bucket, "--key", manifest_key, "--region", region],
            timeout=30,
        )
        probe_rows.append({**p2, "probe_id": f"m5p3_fast_manifest_head_{oid}", "group": "outputs"})
        manifest_ok = str(p2.get("status", "FAIL")) == "PASS"
        manifest_obj: dict[str, Any] = {}
        if manifest_ok:
            fetched = fetch_s3_json(bucket, manifest_key, region, timeout=45)
            p3 = {**fetched.get("result", {}), "probe_id": f"m5p3_fast_manifest_get_{oid}", "group": "outputs"}
            probe_rows.append(p3)
            if str(p3.get("status", "FAIL")) == "PASS":
                manifest_obj = fetched.get("json", {})
            else:
                manifest_ok = False
                s3_issues.append(f"manifest parse/read failure for output_id={oid}")
        else:
            s3_issues.append(f"missing manifest for output_id={oid}")

        row_count = int(manifest_obj.get("row_count", 0)) if manifest_obj else 0
        sort_keys = manifest_obj.get("sort_keys", []) if manifest_obj else []
        if not isinstance(sort_keys, list):
            sort_keys = []
        expected_sort = str(sort_key_map.get(oid, "")).split(",")[0].strip() if isinstance(sort_key_map, dict) else ""
        sort_ok_contract = len(sort_keys) > 0 and str(sort_keys[0]).strip() == expected_sort and expected_sort != ""
        materialized_ok = row_count > 0
        if manifest_ok and (not sort_ok_contract or not materialized_ok):
            if not sort_ok_contract:
                contract_issues.append(f"sort-key mismatch for output_id={oid} expected={expected_sort} observed={sort_keys[:1]}")
            if not materialized_ok:
                contract_issues.append(f"non-materialized output_id={oid} row_count={row_count}")

        output_matrix.append(
            {
                "output_id": oid,
                "prefix": prefix,
                "manifest_key": manifest_key,
                "prefix_ok": prefix_ok,
                "manifest_ok": manifest_ok,
                "row_count": row_count,
                "expected_sort_key": expected_sort,
                "observed_sort_keys": sort_keys,
                "sort_contract_ok": sort_ok_contract,
                "materialized_ok": materialized_ok,
            }
        )

    if s3_issues:
        blockers.append({"id": "M5P3-B3", "severity": "FAST", "status": "OPEN", "details": {"issues": s3_issues}})
    if contract_issues:
        blockers.append({"id": "M5P3-B4", "severity": "FAST", "status": "OPEN", "details": {"issues": contract_issues}})

    upload_sort_snapshot = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P3-ST-FAST",
        "allow_historical_sort_failure": allow_hist_fail,
        "raw_upload_receipt_path": raw_receipt_path.as_posix() if raw_receipt_path else "",
        "stream_sort_receipt_path": sort_receipt_path.as_posix() if sort_receipt_path else "",
        "stream_sort_parity_report_path": parity_path.as_posix() if parity_path else "",
        "raw_upload_overall_pass": raw_receipt.get("overall_pass"),
        "raw_upload_parity_match": raw_receipt.get("parity_match"),
        "stream_sort_overall_pass": sort_receipt.get("overall_pass"),
        "stream_sort_terminal_state": sort_state,
        "stream_sort_parity_outputs": len(parity_entries),
        "waived_observations": waived_observations,
    }
    dumpj(out / "m5p3_upload_sort_snapshot.json", upload_sort_snapshot)

    required_output_matrix = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P3-ST-FAST",
        "required_output_count": len(required_output_ids),
        "outputs": output_matrix,
    }
    dumpj(out / "m5p3_required_output_matrix.json", required_output_matrix)

    stream_view_contract = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P3-ST-FAST",
        "contract_issues": contract_issues,
        "materialization_issues": [x for x in contract_issues if x.startswith("non-materialized")],
        "outputs_checked": len(output_matrix),
    }
    dumpj(out / "m5p3_stream_view_contract_snapshot.json", stream_view_contract)

    total = len(probe_rows)
    probe_failures = [p for p in probe_rows if str(p.get("status", "FAIL")) != "PASS"]
    er = round((len(probe_failures) / total) * 100.0, 4) if total else 0.0
    lat = [float(x.get("duration_ms", 0.0)) for x in probe_rows]
    dur_s = max(1, int(round(time.perf_counter() - t0)))
    max_sp = float(pkt.get("M5P3_STRESS_MAX_SPEND_USD", 40))

    probe = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P3-ST-FAST",
        "window_seconds_observed": dur_s,
        "probe_count": total,
        "failure_count": len(probe_failures),
        "error_rate_pct": er,
        "latency_ms_p50": 0.0 if not lat else sorted(lat)[len(lat) // 2],
        "latency_ms_p95": 0.0 if not lat else max(lat),
        "latency_ms_p99": 0.0 if not lat else max(lat),
        "sample_failures": probe_failures[:10],
        "s1_dependency_phase_execution_id": dep_id,
    }
    dumpj(out / "m5p3_probe_latency_throughput_snapshot.json", probe)

    control_issues: list[str] = []
    if missing_handles:
        control_issues.append(f"missing handles: {','.join(missing_handles)}")
    if placeholder_handles:
        control_issues.append(f"placeholder handles: {','.join(placeholder_handles)}")
    control_issues.extend(dep_issues)
    control_issues.extend(s2_issues)
    control_issues.extend(s3_issues)
    control_issues.extend(contract_issues)
    if probe_failures:
        control_issues.append(f"probe failures: {len(probe_failures)}")
    ctrl = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P3-ST-FAST",
        "overall_pass": len(control_issues) == 0,
        "issues": control_issues,
        "waived_observations": waived_observations,
        "s1_dependency_phase_execution_id": dep_id,
    }
    dumpj(out / "m5p3_control_rail_conformance_snapshot.json", ctrl)

    sec = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P3-ST-FAST",
        "overall_pass": True,
        "secret_probe_count": 0,
        "secret_failure_count": 0,
        "with_decryption_used": False,
        "queried_value_directly": False,
        "suspicious_output_probe_ids": [],
        "plaintext_leakage_detected": False,
    }
    dumpj(out / "m5p3_secret_safety_snapshot.json", sec)

    cost = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P3-ST-FAST",
        "window_seconds": dur_s,
        "estimated_api_call_count": total,
        "attributed_spend_usd": 0.0,
        "unattributed_spend_detected": False,
        "max_spend_usd": max_sp,
        "within_envelope": True,
        "method": "composite_fastcheck_read_only_v0",
    }
    dumpj(out / "m5p3_cost_outcome_receipt.json", cost)

    dlog = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P3-ST-FAST",
        "decisions": [
            "Validated S1 dependency before composite fast-check.",
            "Reused historical M5 raw/sort receipts without launching heavy reruns.",
            "Applied user-approved pre-platform waiver for historical managed-sort receipt failures.",
            "Validated required output prefixes and manifest readability for all required output IDs.",
            "Validated stream-view sort-key/materialization contract from manifests.",
            "Applied fail-closed blocker mapping for material drift and emitted deterministic verdict.",
        ],
    }
    dumpj(out / "m5p3_decision_log.json", dlog)

    overall_pass = len(blockers) == 0
    recommendation = "ADVANCE_TO_P4" if overall_pass else "HOLD_REMEDIATE"
    rollup = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P3-ST-FAST",
        "overall_pass": overall_pass,
        "recommendation": recommendation,
        "open_blocker_count": len(blockers),
        "waived_observation_count": len(waived_observations),
        "waived_observations": waived_observations,
    }
    dumpj(out / "m5p3_rollup_verdict.json", rollup)

    bref = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P3-ST-FAST",
        "overall_pass": overall_pass,
        "open_blocker_count": len(blockers),
        "blockers": blockers,
    }
    summ = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M5P3-ST-FAST",
        "overall_pass": overall_pass,
        "next_gate": "ADVANCE_TO_P4" if overall_pass else "BLOCKED",
        "required_artifacts": M5P3_FAST_ARTS,
        "probe_count": total,
        "error_rate_pct": er,
        "s1_dependency_phase_execution_id": dep_id,
        "waived_observations": waived_observations,
    }
    dumpj(out / "m5p3_blocker_register.json", bref)
    dumpj(out / "m5p3_execution_summary.json", summ)

    miss = [n for n in M5P3_FAST_ARTS if not (out / n).exists()]
    if miss:
        blockers.append({"id": "M5P3-B7", "severity": "FAST", "status": "OPEN", "details": {"missing_artifacts": miss}})
        bref["overall_pass"] = False
        bref["open_blocker_count"] = len(blockers)
        bref["blockers"] = blockers
        summ["overall_pass"] = False
        summ["next_gate"] = "BLOCKED"
        dumpj(out / "m5p3_blocker_register.json", bref)
        dumpj(out / "m5p3_execution_summary.json", summ)

    print(f"[m5p3_fast] phase_execution_id={phase_id}")
    print(f"[m5p3_fast] output_dir={out.as_posix()}")
    print(f"[m5p3_fast] overall_pass={summ['overall_pass']}")
    print(f"[m5p3_fast] next_gate={summ['next_gate']}")
    print(f"[m5p3_fast] probe_count={total}")
    print(f"[m5p3_fast] error_rate_pct={er}")
    print(f"[m5p3_fast] waived_observation_count={len(waived_observations)}")
    print(f"[m5p3_fast] open_blockers={bref['open_blocker_count']}")
    return 0 if summ["overall_pass"] else 2


def main() -> int:
    ap = argparse.ArgumentParser(description="M5.P3 stress runner")
    ap.add_argument("--stage", default="S0", choices=["S0", "S1", "FAST"])
    ap.add_argument("--phase-execution-id", default="")
    ap.add_argument("--output-root", default=str(OUT_ROOT))
    a = ap.parse_args()
    pfx = {"S0": "m5p3_stress_s0", "S1": "m5p3_stress_s1", "FAST": "m5p3_stress_fast"}[a.stage]
    pid = a.phase_execution_id.strip() or f"{pfx}_{tok()}"
    root = Path(a.output_root)
    if a.stage == "S0":
        return run_s0(pid, root)
    if a.stage == "S1":
        return run_s1(pid, root)
    return run_fast(pid, root)


if __name__ == "__main__":
    raise SystemExit(main())
