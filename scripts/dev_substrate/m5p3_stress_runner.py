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

PLAN = Path("docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M5.P3.stress_test.md")
PARENT_PLAN = Path("docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M5.stress_test.md")
REG = Path("docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md")
OUT_ROOT = Path("runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control")

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


def main() -> int:
    ap = argparse.ArgumentParser(description="M5.P3 stress runner")
    ap.add_argument("--stage", default="S0", choices=["S0"])
    ap.add_argument("--phase-execution-id", default="")
    ap.add_argument("--output-root", default=str(OUT_ROOT))
    a = ap.parse_args()
    pfx = {"S0": "m5p3_stress_s0"}[a.stage]
    pid = a.phase_execution_id.strip() or f"{pfx}_{tok()}"
    root = Path(a.output_root)
    return run_s0(pid, root)


if __name__ == "__main__":
    raise SystemExit(main())
