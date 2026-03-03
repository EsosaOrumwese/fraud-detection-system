#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PLAN = Path("docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M4.stress_test.md")
REG = Path("docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md")
OUT_ROOT = Path("runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control")

S0_REQ_HANDLES = [
    "PHASE_RUNTIME_PATH_MODE",
    "PHASE_RUNTIME_PATH_PIN_REQUIRED",
    "RUNTIME_PATH_SWITCH_IN_PHASE_ALLOWED",
    "RUNTIME_DEFAULT_STREAM_ENGINE",
    "RUNTIME_DEFAULT_INGRESS_EDGE",
    "RUNTIME_EKS_USE_POLICY",
    "FLINK_RUNTIME_MODE",
    "FLINK_APP_RTDL_IEG_OFP_V0",
    "MSK_CLUSTER_ARN",
    "SSM_MSK_BOOTSTRAP_BROKERS_PATH",
    "APIGW_IG_API_ID",
    "LAMBDA_IG_HANDLER_NAME",
    "DDB_IG_IDEMPOTENCY_TABLE",
    "SFN_PLATFORM_RUN_ORCHESTRATOR_V0",
    "SR_READY_COMMIT_AUTHORITY",
    "REQUIRED_PLATFORM_RUN_ID_ENV_KEY",
    "S3_EVIDENCE_BUCKET",
    "CLOUDWATCH_LOG_GROUP_PREFIX",
    "OTEL_ENABLED",
    "CORRELATION_REQUIRED_FIELDS",
    "CORRELATION_HEADERS_REQUIRED",
    "CORRELATION_ENFORCEMENT_FAIL_CLOSED",
]

S0_PLAN_KEYS = [
    "M4_STRESS_PROFILE_ID",
    "M4_STRESS_BLOCKER_REGISTER_PATH_PATTERN",
    "M4_STRESS_EXECUTION_SUMMARY_PATH_PATTERN",
    "M4_STRESS_DECISION_LOG_PATH_PATTERN",
    "M4_STRESS_REQUIRED_ARTIFACTS",
    "M4_STRESS_MAX_RUNTIME_MINUTES",
    "M4_STRESS_MAX_SPEND_USD",
    "M4_STRESS_STARTUP_BUDGET_SECONDS",
    "M4_STRESS_STEADY_WINDOW_MINUTES",
    "M4_STRESS_BURST_WINDOW_MINUTES",
    "M4_STRESS_RECOVERY_BUDGET_SECONDS",
    "M4_STRESS_EXPECTED_NEXT_GATE_ON_PASS",
]

S0_ARTS = [
    "m4_stagea_findings.json",
    "m4_lane_matrix.json",
    "m4_probe_latency_throughput_snapshot.json",
    "m4_control_rail_conformance_snapshot.json",
    "m4_secret_safety_snapshot.json",
    "m4_cost_outcome_receipt.json",
    "m4_blocker_register.json",
    "m4_execution_summary.json",
    "m4_decision_log.json",
]
S1_ARTS = S0_ARTS
S2_ARTS = S0_ARTS


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
    rx = re.compile(r"^\* `([^`]+)\s*=\s*([^`]+)`(?:\s.*)?$")
    out: dict[str, Any] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        m = rx.match(raw.strip())
        if m:
            out[m.group(1).strip()] = parse_scalar(m.group(2))
    return out


def resolve_handle(h: dict[str, Any], key: str, max_hops: int = 8) -> tuple[Any, list[str]]:
    chain = [key]
    if key not in h:
        return None, chain
    val: Any = h[key]
    hops = 0
    while isinstance(val, str):
        tokv = val.strip()
        if tokv in h and re.fullmatch(r"[A-Z0-9_]+", tokv) and tokv not in chain and hops < max_hops:
            chain.append(tokv)
            val = h[tokv]
            hops += 1
            continue
        break
    return val, chain


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


def load_latest_successful_m3_s5(out_root: Path) -> dict[str, Any]:
    runs = sorted(out_root.glob("m3_stress_s5_*/stress"))
    for d in reversed(runs):
        sp = d / "m3_execution_summary.json"
        if not sp.exists():
            continue
        try:
            summ = json.loads(sp.read_text(encoding="utf-8"))
        except Exception:
            continue
        if summ.get("overall_pass") is not True:
            continue
        if str(summ.get("stage_id", "")) != "M3-ST-S5":
            continue
        return {"path": d.as_posix(), "summary": summ}
    return {}


def load_latest_successful_stage(out_root: Path, run_prefix: str, stage_id: str) -> dict[str, Any]:
    runs = sorted(out_root.glob(f"{run_prefix}*/stress"))
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
        if str(summ.get("stage_id", "")) != stage_id:
            continue
        return {"path": d.as_posix(), "summary": summ}
    return {}


def copy_stagea_from_stage(out_root: Path, out_dir: Path, run_prefix: str, stage_id: str) -> list[str]:
    ref = load_latest_successful_stage(out_root, run_prefix, stage_id)
    if not ref:
        return [f"No successful {stage_id} folder found."]
    src = Path(str(ref["path"]))
    errs: list[str] = []
    for n in ("m4_stagea_findings.json", "m4_lane_matrix.json"):
        s = src / n
        if s.exists():
            out_dir.joinpath(n).write_bytes(s.read_bytes())
        else:
            errs.append(f"Missing {s.as_posix()}")
    return errs


def pct(vals: list[float], q: float) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    if len(s) == 1:
        return float(s[0])
    k = (len(s) - 1) * q
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    if lo == hi:
        return float(s[lo])
    return float(s[lo] * (hi - k) + s[hi] * (k - lo))


def load_json_safe(path: Path) -> dict[str, Any]:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {}


def run_named_probe(probe_id: str, group: str, cmd: list[str], timeout: int = 25) -> dict[str, Any]:
    r = run_cmd(cmd, timeout=timeout)
    r["probe_id"] = probe_id
    r["group"] = group
    return r


def build_lane_matrix() -> dict[str, Any]:
    return {
        "component_sequence": ["M4.A/B", "M4.C/D/E", "M4.F/G/H/I/J"],
        "plane_sequence": ["runtime_path_plane", "runtime_health_plane", "continuity_recovery_plane"],
        "integrated_windows": ["S1_startup_baseline", "S2_steady_dependency", "S3_failure_recovery"],
    }


def run_s0(phase_id: str, out_root: Path) -> int:
    t0 = time.perf_counter()
    out = out_root / phase_id / "stress"
    out.mkdir(parents=True, exist_ok=True)

    txt = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    pkt = parse_backtick_map(txt) if txt else {}
    h = parse_registry(REG) if REG.exists() else {}

    missing_plan_keys = [k for k in S0_PLAN_KEYS if k not in pkt]
    missing_handles = [k for k in S0_REQ_HANDLES if k not in h]
    placeholder_handles = [k for k in S0_REQ_HANDLES if k in h and str(h[k]).strip() in {"", "TO_PIN"}]

    runtime_path_issues: list[str] = []
    if h.get("PHASE_RUNTIME_PATH_MODE") != "single_active_path_per_phase_run":
        runtime_path_issues.append("PHASE_RUNTIME_PATH_MODE drift")
    if h.get("PHASE_RUNTIME_PATH_PIN_REQUIRED") is not True:
        runtime_path_issues.append("PHASE_RUNTIME_PATH_PIN_REQUIRED not true")
    if h.get("RUNTIME_PATH_SWITCH_IN_PHASE_ALLOWED") is not False:
        runtime_path_issues.append("RUNTIME_PATH_SWITCH_IN_PHASE_ALLOWED not false")

    corr_issues: list[str] = []
    req_corr_fields = {"platform_run_id", "scenario_run_id", "phase_id", "event_id", "runtime_lane", "trace_id"}
    req_corr_headers = {"traceparent", "tracestate", "x-fp-platform-run-id", "x-fp-phase-id", "x-fp-event-id"}
    corr_fields = [x.strip() for x in str(h.get("CORRELATION_REQUIRED_FIELDS", "")).split(",") if x.strip()]
    corr_headers = [x.strip() for x in str(h.get("CORRELATION_HEADERS_REQUIRED", "")).split(",") if x.strip()]
    miss_fields = sorted(req_corr_fields - set(corr_fields))
    miss_headers = sorted(req_corr_headers - set(corr_headers))
    if miss_fields:
        corr_issues.append(f"missing correlation required fields: {','.join(miss_fields)}")
    if miss_headers:
        corr_issues.append(f"missing correlation required headers: {','.join(miss_headers)}")
    if h.get("CORRELATION_ENFORCEMENT_FAIL_CLOSED") is not True:
        corr_issues.append("CORRELATION_ENFORCEMENT_FAIL_CLOSED not true")

    m3 = load_latest_successful_m3_s5(out_root)
    m3s = m3.get("summary", {}) if m3 else {}
    m3_gate_ok = bool(m3) and str(m3s.get("next_gate", "")) == "M4_READY" and str(m3s.get("m4_readiness_recommendation", "")) == "GO"

    region = str(h.get("AWS_REGION", "eu-west-2"))
    msk_region = str(h.get("MSK_REGION", region))
    flink_runtime_active = str(h.get("FLINK_RUNTIME_PATH_ACTIVE", "")).strip()
    flink_runtime_allowed = {x.strip() for x in str(h.get("FLINK_RUNTIME_PATH_ALLOWED", "")).split("|") if x.strip()}
    if flink_runtime_active and flink_runtime_allowed and flink_runtime_active not in flink_runtime_allowed:
        runtime_path_issues.append(f"FLINK_RUNTIME_PATH_ACTIVE drift:{flink_runtime_active}")
    sfn_name, sfn_chain = resolve_handle(h, "SFN_PLATFORM_RUN_ORCHESTRATOR_V0")
    sfn_name_s = str(sfn_name).strip() if sfn_name is not None else ""
    bucket = str(h.get("S3_EVIDENCE_BUCKET", "")).strip()
    api_id = str(h.get("APIGW_IG_API_ID", "")).strip()
    lambda_name = str(h.get("LAMBDA_IG_HANDLER_NAME", "")).strip()
    ddb_table = str(h.get("DDB_IG_IDEMPOTENCY_TABLE", "")).strip()
    msk_arn = str(h.get("MSK_CLUSTER_ARN", "")).strip()

    checks: list[dict[str, Any]] = []
    sfn_check = run_cmd(
        [
            "aws",
            "stepfunctions",
            "list-state-machines",
            "--max-results",
            "100",
            "--region",
            region,
            "--query",
            f"stateMachines[?name=='{sfn_name_s}'].stateMachineArn | [0]",
            "--output",
            "text",
        ],
        timeout=30,
    ) if sfn_name_s else {"status": "FAIL", "exit_code": 1, "stdout": "", "stderr": "missing SFN handle", "duration_ms": 0.0, "command": ""}
    checks.append({"id": "M4S0-V6-SFN-SURFACE", **sfn_check})

    bucket_check = run_cmd(["aws", "s3api", "head-bucket", "--bucket", bucket, "--region", region], timeout=20) if bucket else {"status": "FAIL", "exit_code": 1, "stdout": "", "stderr": "missing S3_EVIDENCE_BUCKET handle", "duration_ms": 0.0, "command": ""}
    checks.append({"id": "M4S0-V7-EVIDENCE-BUCKET", **bucket_check})

    api_check = run_cmd(["aws", "apigatewayv2", "get-api", "--api-id", api_id, "--region", region, "--query", "ApiId", "--output", "text"], timeout=25) if api_id else {"status": "FAIL", "exit_code": 1, "stdout": "", "stderr": "missing APIGW_IG_API_ID handle", "duration_ms": 0.0, "command": ""}
    checks.append({"id": "M4S0-V8-APIGW-SURFACE", **api_check})

    lambda_check = run_cmd(["aws", "lambda", "get-function", "--function-name", lambda_name, "--region", region, "--query", "Configuration.FunctionName", "--output", "text"], timeout=25) if lambda_name else {"status": "FAIL", "exit_code": 1, "stdout": "", "stderr": "missing LAMBDA_IG_HANDLER_NAME handle", "duration_ms": 0.0, "command": ""}
    checks.append({"id": "M4S0-V8-LAMBDA-SURFACE", **lambda_check})

    ddb_check = run_cmd(["aws", "dynamodb", "describe-table", "--table-name", ddb_table, "--region", region, "--query", "Table.TableStatus", "--output", "text"], timeout=25) if ddb_table else {"status": "FAIL", "exit_code": 1, "stdout": "", "stderr": "missing DDB_IG_IDEMPOTENCY_TABLE handle", "duration_ms": 0.0, "command": ""}
    checks.append({"id": "M4S0-V8-DDB-SURFACE", **ddb_check})

    msk_check = run_cmd(["aws", "kafka", "describe-cluster-v2", "--cluster-arn", msk_arn, "--region", msk_region, "--query", "ClusterInfo.State", "--output", "text"], timeout=30) if msk_arn else {"status": "FAIL", "exit_code": 1, "stdout": "", "stderr": "missing MSK_CLUSTER_ARN handle", "duration_ms": 0.0, "command": ""}
    checks.append({"id": "M4S0-V8-MSK-SURFACE", **msk_check})

    control_issues: list[str] = []
    if str(h.get("SR_READY_COMMIT_AUTHORITY", "")) != "step_functions_only":
        control_issues.append("SR_READY_COMMIT_AUTHORITY drift")
    if sfn_check.get("status") != "PASS" or str(sfn_check.get("stdout", "")).strip() in {"", "None", "null"}:
        control_issues.append("orchestrator state machine surface query failed")
    if bucket_check.get("status") != "PASS":
        control_issues.append("evidence bucket reachability failed")
    if api_check.get("status") != "PASS":
        control_issues.append("API Gateway runtime surface query failed")
    if lambda_check.get("status") != "PASS":
        control_issues.append("Lambda runtime surface query failed")
    if ddb_check.get("status") != "PASS":
        control_issues.append("DynamoDB runtime surface query failed")
    if msk_check.get("status") != "PASS":
        control_issues.append("MSK runtime surface query failed")

    blockers: list[dict[str, Any]] = []
    issues: list[str] = []
    if missing_plan_keys or missing_handles or placeholder_handles:
        issues.append("required plan keys/handles unresolved")
        blockers.append(
            {
                "id": "M4-ST-B1",
                "severity": "S0",
                "status": "OPEN",
                "details": {
                    "missing_plan_keys": missing_plan_keys,
                    "missing_handles": missing_handles,
                    "placeholder_handles": placeholder_handles,
                },
            }
        )
    if runtime_path_issues:
        issues.extend(runtime_path_issues)
        blockers.append({"id": "M4-ST-B2", "severity": "S0", "status": "OPEN", "details": {"issues": runtime_path_issues}})
    if control_issues:
        issues.extend(control_issues)
        blockers.append({"id": "M4-ST-B3", "severity": "S0", "status": "OPEN", "details": {"issues": control_issues}})
    if corr_issues:
        issues.extend(corr_issues)
        blockers.append({"id": "M4-ST-B4", "severity": "S0", "status": "OPEN", "details": {"issues": corr_issues}})
    if not m3_gate_ok:
        issues.append("M3 S5 handoff gate invalid/missing")
        blockers.append(
            {
                "id": "M4-ST-B9",
                "severity": "S0",
                "status": "OPEN",
                "details": {
                    "m3_s5_found": bool(m3),
                    "m3_s5_path": m3.get("path", ""),
                    "m3_s5_summary": m3s,
                    "expected": {"next_gate": "M4_READY", "m4_readiness_recommendation": "GO"},
                },
            }
        )

    findings = [
        {"id": "M4-ST-F1", "classification": "PREVENT", "status": "CLOSED" if PLAN.exists() else "OPEN", "evidence": {"path": str(PLAN)}},
        {"id": "M4-ST-F2", "classification": "PREVENT", "status": "CLOSED" if not missing_handles and not placeholder_handles else "OPEN", "evidence": {"missing_handles": missing_handles, "placeholder_handles": placeholder_handles}},
        {"id": "M4-ST-F3", "classification": "PREVENT", "status": "CLOSED" if m3_gate_ok else "OPEN", "evidence": {"m3_s5_path": m3.get("path", "")}},
        {"id": "M4-ST-F4", "classification": "OBSERVE", "status": "OPEN_OBSERVE"},
        {"id": "M4-ST-F5", "classification": "OBSERVE", "status": "OPEN_OBSERVE"},
        {"id": "M4-ST-F6", "classification": "OBSERVE", "status": "OPEN_OBSERVE"},
        {"id": "M4-ST-F7", "classification": "ACCEPT", "status": "ACCEPTED" if m3_gate_ok else "OPEN"},
    ]

    dumpj(
        out / "m4_stagea_findings.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_id,
            "stage_id": "M4-ST-S0",
            "overall_pass": len(blockers) == 0,
            "findings": findings,
        },
    )
    dumpj(
        out / "m4_lane_matrix.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_id,
            "stage_id": "M4-ST-S0",
            "lane_matrix": build_lane_matrix(),
            "dispatch_profile": {
                "startup_budget_seconds": pkt.get("M4_STRESS_STARTUP_BUDGET_SECONDS", 900),
                "steady_window_minutes": pkt.get("M4_STRESS_STEADY_WINDOW_MINUTES", 10),
                "burst_window_minutes": pkt.get("M4_STRESS_BURST_WINDOW_MINUTES", 5),
                "recovery_budget_seconds": pkt.get("M4_STRESS_RECOVERY_BUDGET_SECONDS", 300),
            },
        },
    )

    dur_s = max(1, int(round(time.perf_counter() - t0)))
    probe_count = len(checks)
    fail_count = sum(1 for c in checks if c.get("status") != "PASS")
    dumpj(
        out / "m4_probe_latency_throughput_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_id,
            "stage_id": "M4-ST-S0",
            "window_seconds_observed": dur_s,
            "probe_count": probe_count,
            "failure_count": fail_count,
            "error_rate_pct": round((fail_count / probe_count) * 100.0, 4) if probe_count else 0.0,
            "checks": checks,
            "runtime_path_law_issues": runtime_path_issues,
            "correlation_contract_issues": corr_issues,
            "m3_dependency_summary": m3s,
            "sfn_handle_chain": sfn_chain,
            "sfn_name_resolved": sfn_name_s,
        },
    )
    dumpj(
        out / "m4_control_rail_conformance_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_id,
            "stage_id": "M4-ST-S0",
            "overall_pass": len(control_issues) == 0 and len(runtime_path_issues) == 0 and len(corr_issues) == 0 and m3_gate_ok,
            "issues": sorted(set(control_issues + runtime_path_issues + corr_issues + ([] if m3_gate_ok else ["M3 S5 handoff gate invalid"]))),
            "sfn_lookup_probe": sfn_check,
            "evidence_bucket_probe": bucket_check,
            "runtime_surface_probes": {
                "api_gateway": api_check,
                "lambda": lambda_check,
                "dynamodb": ddb_check,
                "msk": msk_check,
            },
            "m3_s5_handoff_summary": m3s,
            "sfn_handle_chain": sfn_chain,
        },
    )
    dumpj(
        out / "m4_secret_safety_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_id,
            "stage_id": "M4-ST-S0",
            "overall_pass": True,
            "secret_probe_count": 0,
            "secret_failure_count": 0,
            "with_decryption_used": False,
            "queried_value_directly": False,
            "suspicious_output_probe_ids": [],
            "plaintext_leakage_detected": False,
        },
    )
    max_sp = float(pkt.get("M4_STRESS_MAX_SPEND_USD", 40))
    dumpj(
        out / "m4_cost_outcome_receipt.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_id,
            "stage_id": "M4-ST-S0",
            "window_seconds": dur_s,
            "attributed_spend_usd": 0.0,
            "unattributed_spend_detected": False,
            "max_spend_usd": max_sp,
            "within_envelope": True,
            "method": "readonly_m4_authority_gate_v0",
        },
    )
    dumpj(
        out / "m4_decision_log.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_id,
            "stage_id": "M4-ST-S0",
            "decisions": [
                "Validated required M4 handles and M4 stress plan-key packet.",
                "Validated runtime-path law and correlation contract anchors.",
                "Validated latest successful M3 S5 handoff gate for M4 entry.",
                "Executed orchestrator/evidence/runtime-surface control-plane checks.",
                "Applied fail-closed blocker mapping for M4 S0.",
            ],
        },
    )

    bref = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M4-ST-S0",
        "overall_pass": len(blockers) == 0,
        "open_blocker_count": len(blockers),
        "blockers": blockers,
    }
    summ = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M4-ST-S0",
        "overall_pass": len(blockers) == 0,
        "next_gate": "M4_ST_S1_READY" if len(blockers) == 0 else "BLOCKED",
        "required_artifacts": S0_ARTS,
        "issue_count": len(issues),
        "m3_s5_phase_execution_id": str(m3s.get("phase_execution_id", "")),
    }
    dumpj(out / "m4_blocker_register.json", bref)
    dumpj(out / "m4_execution_summary.json", summ)

    miss = [n for n in S0_ARTS if not (out / n).exists()]
    if miss:
        blockers.append({"id": "M4-ST-B9", "severity": "S0", "status": "OPEN", "details": {"missing_artifacts": miss}})
        bref["overall_pass"] = False
        bref["open_blocker_count"] = len(blockers)
        bref["blockers"] = blockers
        summ["overall_pass"] = False
        summ["next_gate"] = "BLOCKED"
        dumpj(out / "m4_blocker_register.json", bref)
        dumpj(out / "m4_execution_summary.json", summ)

    print(f"[m4_s0] phase_execution_id={phase_id}")
    print(f"[m4_s0] output_dir={out.as_posix()}")
    print(f"[m4_s0] overall_pass={summ['overall_pass']}")
    print(f"[m4_s0] next_gate={summ['next_gate']}")
    print(f"[m4_s0] open_blockers={bref['open_blocker_count']}")
    return 0 if summ["overall_pass"] else 2


def run_s1(phase_id: str, out_root: Path, win_override: int | None, interval: int, conc_override: int) -> int:
    t0 = time.perf_counter()
    out = out_root / phase_id / "stress"
    out.mkdir(parents=True, exist_ok=True)

    txt = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    pkt = parse_backtick_map(txt) if txt else {}
    h = parse_registry(REG) if REG.exists() else {}
    blockers: list[dict[str, Any]] = []

    copy_errs = copy_stagea_from_stage(out_root, out, "m4_stress_s0_", "M4-ST-S0")
    if copy_errs:
        blockers.append({"id": "M4-ST-B9", "severity": "S1", "status": "OPEN", "details": {"copy_errors": copy_errs}})

    s0 = load_latest_successful_stage(out_root, "m4_stress_s0_", "M4-ST-S0")
    if not s0:
        blockers.append({"id": "M4-ST-B9", "severity": "S1", "status": "OPEN", "details": {"missing_dependency": "successful M4 S0"}})

    missing_plan_keys = [k for k in S0_PLAN_KEYS if k not in pkt]
    missing_handles = [k for k in S0_REQ_HANDLES if k not in h]
    placeholder_handles = [k for k in S0_REQ_HANDLES if k in h and str(h[k]).strip() in {"", "TO_PIN"}]
    if missing_plan_keys or missing_handles or placeholder_handles:
        blockers.append(
            {
                "id": "M4-ST-B1",
                "severity": "S1",
                "status": "OPEN",
                "details": {
                    "missing_plan_keys": missing_plan_keys,
                    "missing_handles": missing_handles,
                    "placeholder_handles": placeholder_handles,
                },
            }
        )

    runtime_path_issues: list[str] = []
    if h.get("PHASE_RUNTIME_PATH_MODE") != "single_active_path_per_phase_run":
        runtime_path_issues.append("PHASE_RUNTIME_PATH_MODE drift")
    if h.get("PHASE_RUNTIME_PATH_PIN_REQUIRED") is not True:
        runtime_path_issues.append("PHASE_RUNTIME_PATH_PIN_REQUIRED not true")
    if h.get("RUNTIME_PATH_SWITCH_IN_PHASE_ALLOWED") is not False:
        runtime_path_issues.append("RUNTIME_PATH_SWITCH_IN_PHASE_ALLOWED not false")

    corr_issues: list[str] = []
    req_corr_fields = {"platform_run_id", "scenario_run_id", "phase_id", "event_id", "runtime_lane", "trace_id"}
    req_corr_headers = {"traceparent", "tracestate", "x-fp-platform-run-id", "x-fp-phase-id", "x-fp-event-id"}
    corr_fields = [x.strip() for x in str(h.get("CORRELATION_REQUIRED_FIELDS", "")).split(",") if x.strip()]
    corr_headers = [x.strip() for x in str(h.get("CORRELATION_HEADERS_REQUIRED", "")).split(",") if x.strip()]
    miss_fields = sorted(req_corr_fields - set(corr_fields))
    miss_headers = sorted(req_corr_headers - set(corr_headers))
    if miss_fields:
        corr_issues.append(f"missing correlation required fields: {','.join(miss_fields)}")
    if miss_headers:
        corr_issues.append(f"missing correlation required headers: {','.join(miss_headers)}")
    if h.get("CORRELATION_ENFORCEMENT_FAIL_CLOSED") is not True:
        corr_issues.append("CORRELATION_ENFORCEMENT_FAIL_CLOSED not true")

    region = str(h.get("AWS_REGION", "eu-west-2"))
    msk_region = str(h.get("MSK_REGION", region))
    flink_runtime_active = str(h.get("FLINK_RUNTIME_PATH_ACTIVE", "")).strip()
    flink_runtime_allowed = {x.strip() for x in str(h.get("FLINK_RUNTIME_PATH_ALLOWED", "")).split("|") if x.strip()}
    if flink_runtime_active and flink_runtime_allowed and flink_runtime_active not in flink_runtime_allowed:
        runtime_path_issues.append(f"FLINK_RUNTIME_PATH_ACTIVE drift:{flink_runtime_active}")
    sfn_name, sfn_chain = resolve_handle(h, "SFN_PLATFORM_RUN_ORCHESTRATOR_V0")
    sfn_name_s = str(sfn_name).strip() if sfn_name is not None else ""
    bucket = str(h.get("S3_EVIDENCE_BUCKET", "")).strip()
    api_id = str(h.get("APIGW_IG_API_ID", "")).strip()
    lambda_name = str(h.get("LAMBDA_IG_HANDLER_NAME", "")).strip()
    ddb_table = str(h.get("DDB_IG_IDEMPOTENCY_TABLE", "")).strip()
    msk_arn = str(h.get("MSK_CLUSTER_ARN", "")).strip()
    flink_app = str(h.get("FLINK_APP_RTDL_IEG_OFP_V0", "")).strip()
    emr_vc_id = str(h.get("EMR_EKS_VIRTUAL_CLUSTER_ID", "")).strip()
    eks_cluster = str(h.get("EKS_CLUSTER_NAME", "")).strip()

    probes: list[dict[str, Any]] = [
        {
            "id": "s1_sfn_lookup",
            "group": "control",
            "cmd": [
                "aws",
                "stepfunctions",
                "list-state-machines",
                "--max-results",
                "100",
                "--region",
                region,
                "--query",
                f"stateMachines[?name=='{sfn_name_s}'].stateMachineArn | [0]",
                "--output",
                "text",
            ],
            "timeout": 30,
            "required": bool(sfn_name_s),
            "missing_msg": "missing SFN handle",
        },
        {
            "id": "s1_evidence_bucket",
            "group": "control",
            "cmd": ["aws", "s3api", "head-bucket", "--bucket", bucket, "--region", region],
            "timeout": 20,
            "required": bool(bucket),
            "missing_msg": "missing S3_EVIDENCE_BUCKET handle",
        },
        {
            "id": "s1_api_gateway",
            "group": "runtime",
            "cmd": ["aws", "apigatewayv2", "get-api", "--api-id", api_id, "--region", region, "--query", "ApiId", "--output", "text"],
            "timeout": 25,
            "required": bool(api_id),
            "missing_msg": "missing APIGW_IG_API_ID handle",
        },
        {
            "id": "s1_lambda",
            "group": "runtime",
            "cmd": ["aws", "lambda", "get-function", "--function-name", lambda_name, "--region", region, "--query", "Configuration.FunctionName", "--output", "text"],
            "timeout": 25,
            "required": bool(lambda_name),
            "missing_msg": "missing LAMBDA_IG_HANDLER_NAME handle",
        },
        {
            "id": "s1_ddb",
            "group": "runtime",
            "cmd": ["aws", "dynamodb", "describe-table", "--table-name", ddb_table, "--region", region, "--query", "Table.TableStatus", "--output", "text"],
            "timeout": 25,
            "required": bool(ddb_table),
            "missing_msg": "missing DDB_IG_IDEMPOTENCY_TABLE handle",
        },
        {
            "id": "s1_msk",
            "group": "runtime",
            "cmd": ["aws", "kafka", "describe-cluster-v2", "--cluster-arn", msk_arn, "--region", msk_region, "--query", "ClusterInfo.State", "--output", "text"],
            "timeout": 30,
            "required": bool(msk_arn),
            "missing_msg": "missing MSK_CLUSTER_ARN handle",
        },
    ]
    if flink_runtime_active == "MSF_MANAGED":
        probes.append(
            {
                "id": "s1_flink_msf_app",
                "group": "runtime",
                "cmd": ["aws", "kinesisanalyticsv2", "describe-application", "--application-name", flink_app, "--region", region, "--query", "ApplicationDetail.ApplicationStatus", "--output", "text"],
                "timeout": 30,
                "required": bool(flink_app) and flink_app not in {"legacy_deferred_not_active", "LEGACY_DEFERRED_NOT_ACTIVE"},
                "missing_msg": "missing/legacy FLINK_APP_RTDL_IEG_OFP_V0 handle",
            }
        )
    elif flink_runtime_active == "EKS_FLINK_OPERATOR":
        probes.append(
            {
                "id": "s1_flink_eks_virtual_cluster",
                "group": "runtime",
                "cmd": ["aws", "emr-containers", "describe-virtual-cluster", "--id", emr_vc_id, "--region", region, "--query", "virtualCluster.state", "--output", "text"],
                "timeout": 30,
                "required": bool(emr_vc_id),
                "missing_msg": "missing EMR_EKS_VIRTUAL_CLUSTER_ID handle",
            }
        )
        probes.append(
            {
                "id": "s1_flink_eks_cluster",
                "group": "runtime",
                "cmd": ["aws", "eks", "describe-cluster", "--name", eks_cluster, "--region", region, "--query", "cluster.status", "--output", "text"],
                "timeout": 30,
                "required": bool(eks_cluster),
                "missing_msg": "missing EKS_CLUSTER_NAME handle",
            }
        )
        probes.append(
            {
                "id": "s1_flink_eks_job_surface",
                "group": "runtime",
                "cmd": ["aws", "emr-containers", "list-job-runs", "--virtual-cluster-id", emr_vc_id, "--region", region, "--max-results", "1", "--query", "jobRuns[0].id", "--output", "text"],
                "timeout": 30,
                "required": bool(emr_vc_id),
                "missing_msg": "missing EMR_EKS_VIRTUAL_CLUSTER_ID handle",
            }
        )
    else:
        runtime_path_issues.append(f"unsupported FLINK_RUNTIME_PATH_ACTIVE:{flink_runtime_active or 'UNSET'}")

    rows: list[dict[str, Any]] = []
    tstart = time.monotonic()
    cycles = 0
    startup_ready_seconds: int | None = None
    startup_budget_seconds = int(pkt.get("M4_STRESS_STARTUP_BUDGET_SECONDS", 900))
    precheck_issues: list[str] = []
    precheck_fail_closed = False

    def execute_cycle(cycle_idx: int, precheck: bool = False) -> tuple[list[dict[str, Any]], bool]:
        cycle_rows: list[dict[str, Any]] = []
        all_pass = True
        with cf.ThreadPoolExecutor(max_workers=max(1, min(conc_override if conc_override > 0 else len(probes), len(probes)))) as ex:
            futs = []
            for p in probes:
                if p["required"]:
                    futs.append(ex.submit(run_named_probe, str(p["id"]), str(p["group"]), list(p["cmd"]), int(p["timeout"])))
                else:
                    cycle_rows.append(
                        {
                            "probe_id": str(p["id"]),
                            "group": str(p["group"]),
                            "command": " ".join(list(p["cmd"])),
                            "exit_code": 1,
                            "status": "FAIL",
                            "duration_ms": 0.0,
                            "stdout": "",
                            "stderr": str(p["missing_msg"]),
                            "started_at_utc": now(),
                            "ended_at_utc": now(),
                            "cycle_index": cycle_idx,
                            "precheck": precheck,
                        }
                    )
                    all_pass = False
            for f in cf.as_completed(futs):
                rr = f.result()
                rr["cycle_index"] = cycle_idx
                rr["precheck"] = precheck
                cycle_rows.append(rr)
                if str(rr.get("status", "FAIL")) != "PASS":
                    all_pass = False
        return cycle_rows, all_pass

    cycles += 1
    pre_rows, pre_all_pass = execute_cycle(cycles, precheck=True)
    rows.extend(pre_rows)
    if pre_all_pass:
        startup_ready_seconds = max(1, int(round(time.monotonic() - tstart)))
    else:
        precheck_fail_closed = True
        precheck_issues.append("critical precheck failed before steady window")
        if startup_ready_seconds is None:
            precheck_issues.append("startup ready state not reached")

    win = int(win_override) if win_override is not None else int(float(pkt.get("M4_STRESS_STEADY_WINDOW_MINUTES", 10)) * 60)
    win = max(60, win)
    cycle_interval = max(1, interval)
    if not precheck_fail_closed:
        while time.monotonic() - tstart < win:
            cycles += 1
            c0 = time.monotonic()
            cycle_rows, all_pass = execute_cycle(cycles, precheck=False)
            rows.extend(cycle_rows)
            if all_pass and startup_ready_seconds is None:
                startup_ready_seconds = max(1, int(round(time.monotonic() - tstart)))
            sleep_for = min(max(0.0, cycle_interval - (time.monotonic() - c0)), max(0.0, win - (time.monotonic() - tstart)))
            if sleep_for > 0:
                time.sleep(sleep_for)

    startup_issues: list[str] = []
    if startup_ready_seconds is None:
        startup_issues.append("startup ready state not reached")
    elif startup_ready_seconds > startup_budget_seconds:
        startup_issues.append(f"startup budget exceeded: ready={startup_ready_seconds}s budget={startup_budget_seconds}s")

    control_issues: list[str] = []
    if str(h.get("SR_READY_COMMIT_AUTHORITY", "")) != "step_functions_only":
        control_issues.append("SR_READY_COMMIT_AUTHORITY drift")
    control_issues.extend(runtime_path_issues)
    control_issues.extend(corr_issues)
    control_issues.extend(precheck_issues)
    fail_counts: dict[str, int] = {}
    for r in rows:
        pid = str(r.get("probe_id", ""))
        if str(r.get("status", "FAIL")) != "PASS":
            fail_counts[pid] = fail_counts.get(pid, 0) + 1
    for pid, cnt in sorted(fail_counts.items()):
        control_issues.append(f"{pid} failures: {cnt}")

    s0_path = Path(str(s0.get("path", ""))) if s0 else Path("")
    s0_ctrl = load_json_safe(s0_path / "m4_control_rail_conformance_snapshot.json") if s0 else {}
    s0_issues = [str(x) for x in s0_ctrl.get("issues", [])] if s0_ctrl else []
    new_ci = sorted(set(control_issues) - set(s0_issues))

    total = len(rows)
    fails = [r for r in rows if str(r.get("status", "FAIL")) != "PASS"]
    er = round((len(fails) / total) * 100.0, 4) if total else 100.0
    lat = [float(r.get("duration_ms", 0.0)) for r in rows]
    cycle_failed: dict[int, bool] = {}
    for r in rows:
        idx = int(r.get("cycle_index", 0))
        if idx not in cycle_failed:
            cycle_failed[idx] = False
        if str(r.get("status", "FAIL")) != "PASS":
            cycle_failed[idx] = True
    cur_streak = 0
    max_streak = 0
    for idx in sorted(cycle_failed):
        if cycle_failed[idx]:
            cur_streak += 1
            max_streak = max(max_streak, cur_streak)
        else:
            cur_streak = 0

    if startup_issues:
        blockers.append({"id": "M4-ST-B2", "severity": "S1", "status": "OPEN", "details": {"issues": startup_issues + runtime_path_issues}})
    b3_markers = ["s1_sfn_lookup", "s1_evidence_bucket", "s1_api_gateway", "s1_lambda", "s1_ddb", "s1_msk", "s1_flink_", "SR_READY_COMMIT_AUTHORITY"]
    b3_issues = [x for x in new_ci if any(y in x for y in b3_markers)]
    if b3_issues:
        blockers.append({"id": "M4-ST-B3", "severity": "S1", "status": "OPEN", "details": {"issues": sorted(set(b3_issues))}})
    b4_issues = [x for x in new_ci if "correlation" in x]
    if b4_issues:
        blockers.append({"id": "M4-ST-B4", "severity": "S1", "status": "OPEN", "details": {"issues": sorted(set(b4_issues))}})
    b5_details: dict[str, Any] = {}
    if er > 2.0:
        b5_details["error_rate_pct"] = er
    if max_streak > 3:
        b5_details["max_consecutive_failure_cycles"] = max_streak
    if b5_details:
        blockers.append({"id": "M4-ST-B5", "severity": "S1", "status": "OPEN", "details": b5_details})

    wdec = any("--with-decryption" in str(r.get("command", "")) for r in rows)
    qval = any("Parameter.Value" in str(r.get("command", "")) or "SecretString" in str(r.get("command", "")) for r in rows)
    sus: list[str] = []
    rx = re.compile(r"(AKIA[0-9A-Z]{16}|BEGIN [A-Z ]*PRIVATE KEY|SECRET_ACCESS_KEY)")
    for r in rows:
        if rx.search((str(r.get("stdout", "")) + " " + str(r.get("stderr", ""))).strip()):
            sus.append(str(r.get("probe_id", "")))
    leak = wdec or qval or bool(sus)
    if leak:
        blockers.append({"id": "M4-ST-B6", "severity": "S1", "status": "OPEN", "details": {"issues": ["plaintext leakage signal detected"]}})

    dur_s = max(1, int(round(time.monotonic() - tstart)))
    max_sp = float(pkt.get("M4_STRESS_MAX_SPEND_USD", 40))
    cost_within = True
    if not cost_within:
        blockers.append({"id": "M4-ST-B8", "severity": "S1", "status": "OPEN"})

    probe = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M4-ST-S1",
        "window_seconds_configured": win,
        "window_seconds_observed": dur_s,
        "cycle_count": cycles,
        "probe_count": total,
        "failure_count": len(fails),
        "error_rate_pct": er,
        "probe_eps_observed": round(total / max(1.0, float(dur_s)), 4),
        "latency_ms_p50": round(pct(lat, 0.5), 3),
        "latency_ms_p95": round(pct(lat, 0.95), 3),
        "latency_ms_p99": round(pct(lat, 0.99), 3),
        "sample_failures": fails[:10],
        "max_consecutive_failure_cycles": max_streak,
        "startup_ready_seconds": startup_ready_seconds,
        "startup_budget_seconds": startup_budget_seconds,
        "startup_issues": startup_issues,
        "s0_baseline_phase_execution_id": s0.get("summary", {}).get("phase_execution_id", "") if s0 else "",
        "precheck_fail_closed": precheck_fail_closed,
        "sfn_handle_chain": sfn_chain,
        "sfn_name_resolved": sfn_name_s,
    }
    dumpj(out / "m4_probe_latency_throughput_snapshot.json", probe)

    ctrl = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M4-ST-S1",
        "overall_pass": len(new_ci) == 0 and len(startup_issues) == 0,
        "issues": control_issues,
        "s0_baseline_issues": s0_issues,
        "new_issues_vs_s0": new_ci,
        "s0_dependency_summary": s0.get("summary", {}) if s0 else {},
        "probe_failure_counts": fail_counts,
        "sfn_handle_chain": sfn_chain,
    }
    dumpj(out / "m4_control_rail_conformance_snapshot.json", ctrl)

    sec = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M4-ST-S1",
        "overall_pass": not leak,
        "secret_probe_count": 0,
        "secret_failure_count": 0,
        "with_decryption_used": wdec,
        "queried_value_directly": qval,
        "suspicious_output_probe_ids": sus,
        "plaintext_leakage_detected": leak,
    }
    dumpj(out / "m4_secret_safety_snapshot.json", sec)

    cost = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M4-ST-S1",
        "window_seconds": dur_s,
        "estimated_api_call_count": total,
        "attributed_spend_usd": 0.0,
        "unattributed_spend_detected": False,
        "max_spend_usd": max_sp,
        "within_envelope": cost_within,
        "method": "readonly_startup_baseline_probe_v0",
    }
    dumpj(out / "m4_cost_outcome_receipt.json", cost)

    dlog = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M4-ST-S1",
        "decisions": [
            "Validated S0 continuity and carried Stage-A artifacts forward.",
            "Executed critical precheck before steady startup/readiness window.",
            "Executed steady-window runtime readiness probes across active surfaces.",
            "Compared S1 control posture against latest successful S0 baseline.",
            "Applied fail-closed blocker mapping for M4 S1.",
        ],
    }
    dumpj(out / "m4_decision_log.json", dlog)

    bref = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M4-ST-S1",
        "overall_pass": len(blockers) == 0,
        "open_blocker_count": len(blockers),
        "blockers": blockers,
    }
    summ = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M4-ST-S1",
        "overall_pass": len(blockers) == 0,
        "next_gate": "M4_ST_S2_READY" if len(blockers) == 0 else "BLOCKED",
        "required_artifacts": S1_ARTS,
        "probe_count": total,
        "error_rate_pct": er,
        "startup_ready_seconds": startup_ready_seconds,
        "startup_budget_seconds": startup_budget_seconds,
    }
    dumpj(out / "m4_blocker_register.json", bref)
    dumpj(out / "m4_execution_summary.json", summ)

    miss = [n for n in S1_ARTS if not (out / n).exists()]
    if miss:
        blockers.append({"id": "M4-ST-B9", "severity": "S1", "status": "OPEN", "details": {"missing_artifacts": miss}})
        bref["overall_pass"] = False
        bref["open_blocker_count"] = len(blockers)
        bref["blockers"] = blockers
        summ["overall_pass"] = False
        summ["next_gate"] = "BLOCKED"
        dumpj(out / "m4_blocker_register.json", bref)
        dumpj(out / "m4_execution_summary.json", summ)

    print(f"[m4_s1] phase_execution_id={phase_id}")
    print(f"[m4_s1] output_dir={out.as_posix()}")
    print(f"[m4_s1] overall_pass={summ['overall_pass']}")
    print(f"[m4_s1] next_gate={summ['next_gate']}")
    print(f"[m4_s1] probe_count={total}")
    print(f"[m4_s1] error_rate_pct={er}")
    print(f"[m4_s1] startup_ready_seconds={startup_ready_seconds}")
    print(f"[m4_s1] open_blockers={bref['open_blocker_count']}")
    return 0 if summ["overall_pass"] else 2


def run_s2(phase_id: str, out_root: Path, win_override: int | None, interval: int, conc_override: int) -> int:
    out = out_root / phase_id / "stress"
    out.mkdir(parents=True, exist_ok=True)

    txt = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    pkt = parse_backtick_map(txt) if txt else {}
    h = parse_registry(REG) if REG.exists() else {}
    blockers: list[dict[str, Any]] = []

    copy_errs = copy_stagea_from_stage(out_root, out, "m4_stress_s1_", "M4-ST-S1")
    if copy_errs:
        blockers.append({"id": "M4-ST-B9", "severity": "S2", "status": "OPEN", "details": {"copy_errors": copy_errs}})

    s1 = load_latest_successful_stage(out_root, "m4_stress_s1_", "M4-ST-S1")
    if not s1:
        blockers.append({"id": "M4-ST-B9", "severity": "S2", "status": "OPEN", "details": {"missing_dependency": "successful M4 S1"}})

    missing_plan_keys = [k for k in S0_PLAN_KEYS if k not in pkt]
    missing_handles = [k for k in S0_REQ_HANDLES if k not in h]
    placeholder_handles = [k for k in S0_REQ_HANDLES if k in h and str(h[k]).strip() in {"", "TO_PIN"}]
    if missing_plan_keys or missing_handles or placeholder_handles:
        blockers.append(
            {
                "id": "M4-ST-B1",
                "severity": "S2",
                "status": "OPEN",
                "details": {
                    "missing_plan_keys": missing_plan_keys,
                    "missing_handles": missing_handles,
                    "placeholder_handles": placeholder_handles,
                },
            }
        )

    runtime_path_issues: list[str] = []
    if h.get("PHASE_RUNTIME_PATH_MODE") != "single_active_path_per_phase_run":
        runtime_path_issues.append("PHASE_RUNTIME_PATH_MODE drift")
    if h.get("PHASE_RUNTIME_PATH_PIN_REQUIRED") is not True:
        runtime_path_issues.append("PHASE_RUNTIME_PATH_PIN_REQUIRED not true")
    if h.get("RUNTIME_PATH_SWITCH_IN_PHASE_ALLOWED") is not False:
        runtime_path_issues.append("RUNTIME_PATH_SWITCH_IN_PHASE_ALLOWED not false")

    corr_issues: list[str] = []
    req_corr_fields = {"platform_run_id", "scenario_run_id", "phase_id", "event_id", "runtime_lane", "trace_id"}
    req_corr_headers = {"traceparent", "tracestate", "x-fp-platform-run-id", "x-fp-phase-id", "x-fp-event-id"}
    corr_fields = [x.strip() for x in str(h.get("CORRELATION_REQUIRED_FIELDS", "")).split(",") if x.strip()]
    corr_headers = [x.strip() for x in str(h.get("CORRELATION_HEADERS_REQUIRED", "")).split(",") if x.strip()]
    miss_fields = sorted(req_corr_fields - set(corr_fields))
    miss_headers = sorted(req_corr_headers - set(corr_headers))
    if miss_fields:
        corr_issues.append(f"missing correlation required fields: {','.join(miss_fields)}")
    if miss_headers:
        corr_issues.append(f"missing correlation required headers: {','.join(miss_headers)}")
    if h.get("CORRELATION_ENFORCEMENT_FAIL_CLOSED") is not True:
        corr_issues.append("CORRELATION_ENFORCEMENT_FAIL_CLOSED not true")

    region = str(h.get("AWS_REGION", "eu-west-2"))
    msk_region = str(h.get("MSK_REGION", region))
    flink_runtime_active = str(h.get("FLINK_RUNTIME_PATH_ACTIVE", "")).strip()
    flink_runtime_allowed = {x.strip() for x in str(h.get("FLINK_RUNTIME_PATH_ALLOWED", "")).split("|") if x.strip()}
    if flink_runtime_active and flink_runtime_allowed and flink_runtime_active not in flink_runtime_allowed:
        runtime_path_issues.append(f"FLINK_RUNTIME_PATH_ACTIVE drift:{flink_runtime_active}")
    sfn_name, sfn_chain = resolve_handle(h, "SFN_PLATFORM_RUN_ORCHESTRATOR_V0")
    sfn_name_s = str(sfn_name).strip() if sfn_name is not None else ""
    bucket = str(h.get("S3_EVIDENCE_BUCKET", "")).strip()
    api_id = str(h.get("APIGW_IG_API_ID", "")).strip()
    lambda_name = str(h.get("LAMBDA_IG_HANDLER_NAME", "")).strip()
    ddb_table = str(h.get("DDB_IG_IDEMPOTENCY_TABLE", "")).strip()
    msk_arn = str(h.get("MSK_CLUSTER_ARN", "")).strip()
    flink_app = str(h.get("FLINK_APP_RTDL_IEG_OFP_V0", "")).strip()
    emr_vc_id = str(h.get("EMR_EKS_VIRTUAL_CLUSTER_ID", "")).strip()
    eks_cluster = str(h.get("EKS_CLUSTER_NAME", "")).strip()

    probes: list[dict[str, Any]] = [
        {
            "id": "s2_sfn_lookup",
            "group": "control",
            "cmd": [
                "aws",
                "stepfunctions",
                "list-state-machines",
                "--max-results",
                "100",
                "--region",
                region,
                "--query",
                f"stateMachines[?name=='{sfn_name_s}'].stateMachineArn | [0]",
                "--output",
                "text",
            ],
            "timeout": 30,
            "required": bool(sfn_name_s),
            "missing_msg": "missing SFN handle",
        },
        {
            "id": "s2_evidence_bucket",
            "group": "control",
            "cmd": ["aws", "s3api", "head-bucket", "--bucket", bucket, "--region", region],
            "timeout": 20,
            "required": bool(bucket),
            "missing_msg": "missing S3_EVIDENCE_BUCKET handle",
        },
        {
            "id": "s2_api_gateway",
            "group": "runtime",
            "cmd": ["aws", "apigatewayv2", "get-api", "--api-id", api_id, "--region", region, "--query", "ApiId", "--output", "text"],
            "timeout": 25,
            "required": bool(api_id),
            "missing_msg": "missing APIGW_IG_API_ID handle",
        },
        {
            "id": "s2_lambda",
            "group": "runtime",
            "cmd": ["aws", "lambda", "get-function", "--function-name", lambda_name, "--region", region, "--query", "Configuration.FunctionName", "--output", "text"],
            "timeout": 25,
            "required": bool(lambda_name),
            "missing_msg": "missing LAMBDA_IG_HANDLER_NAME handle",
        },
        {
            "id": "s2_ddb",
            "group": "runtime",
            "cmd": ["aws", "dynamodb", "describe-table", "--table-name", ddb_table, "--region", region, "--query", "Table.TableStatus", "--output", "text"],
            "timeout": 25,
            "required": bool(ddb_table),
            "missing_msg": "missing DDB_IG_IDEMPOTENCY_TABLE handle",
        },
        {
            "id": "s2_msk",
            "group": "runtime",
            "cmd": ["aws", "kafka", "describe-cluster-v2", "--cluster-arn", msk_arn, "--region", msk_region, "--query", "ClusterInfo.State", "--output", "text"],
            "timeout": 30,
            "required": bool(msk_arn),
            "missing_msg": "missing MSK_CLUSTER_ARN handle",
        },
    ]
    if flink_runtime_active == "MSF_MANAGED":
        probes.append(
            {
                "id": "s2_flink_msf_app",
                "group": "runtime",
                "cmd": ["aws", "kinesisanalyticsv2", "describe-application", "--application-name", flink_app, "--region", region, "--query", "ApplicationDetail.ApplicationStatus", "--output", "text"],
                "timeout": 30,
                "required": bool(flink_app) and flink_app not in {"legacy_deferred_not_active", "LEGACY_DEFERRED_NOT_ACTIVE"},
                "missing_msg": "missing/legacy FLINK_APP_RTDL_IEG_OFP_V0 handle",
            }
        )
    elif flink_runtime_active == "EKS_FLINK_OPERATOR":
        probes.append(
            {
                "id": "s2_flink_eks_virtual_cluster",
                "group": "runtime",
                "cmd": ["aws", "emr-containers", "describe-virtual-cluster", "--id", emr_vc_id, "--region", region, "--query", "virtualCluster.state", "--output", "text"],
                "timeout": 30,
                "required": bool(emr_vc_id),
                "missing_msg": "missing EMR_EKS_VIRTUAL_CLUSTER_ID handle",
            }
        )
        probes.append(
            {
                "id": "s2_flink_eks_cluster",
                "group": "runtime",
                "cmd": ["aws", "eks", "describe-cluster", "--name", eks_cluster, "--region", region, "--query", "cluster.status", "--output", "text"],
                "timeout": 30,
                "required": bool(eks_cluster),
                "missing_msg": "missing EKS_CLUSTER_NAME handle",
            }
        )
        probes.append(
            {
                "id": "s2_flink_eks_job_surface",
                "group": "runtime",
                "cmd": ["aws", "emr-containers", "list-job-runs", "--virtual-cluster-id", emr_vc_id, "--region", region, "--max-results", "1", "--query", "jobRuns[0].id", "--output", "text"],
                "timeout": 30,
                "required": bool(emr_vc_id),
                "missing_msg": "missing EMR_EKS_VIRTUAL_CLUSTER_ID handle",
            }
        )
    else:
        runtime_path_issues.append(f"unsupported FLINK_RUNTIME_PATH_ACTIVE:{flink_runtime_active or 'UNSET'}")

    rows: list[dict[str, Any]] = []
    tstart = time.monotonic()
    cycles = 0
    entry_ready_seconds: int | None = None
    precheck_issues: list[str] = []
    precheck_fail_closed = False

    def execute_cycle(cycle_idx: int, mode: str, precheck: bool = False) -> tuple[list[dict[str, Any]], bool]:
        cycle_rows: list[dict[str, Any]] = []
        all_pass = True
        with cf.ThreadPoolExecutor(max_workers=max(1, min(conc_override if conc_override > 0 else len(probes), len(probes)))) as ex:
            futs = []
            for p in probes:
                if p["required"]:
                    futs.append(ex.submit(run_named_probe, str(p["id"]), str(p["group"]), list(p["cmd"]), int(p["timeout"])))
                else:
                    cycle_rows.append(
                        {
                            "probe_id": str(p["id"]),
                            "group": str(p["group"]),
                            "command": " ".join(list(p["cmd"])),
                            "exit_code": 1,
                            "status": "FAIL",
                            "duration_ms": 0.0,
                            "stdout": "",
                            "stderr": str(p["missing_msg"]),
                            "started_at_utc": now(),
                            "ended_at_utc": now(),
                            "cycle_index": cycle_idx,
                            "precheck": precheck,
                            "window_mode": mode,
                        }
                    )
                    all_pass = False
            for f in cf.as_completed(futs):
                rr = f.result()
                rr["cycle_index"] = cycle_idx
                rr["precheck"] = precheck
                rr["window_mode"] = mode
                cycle_rows.append(rr)
                if str(rr.get("status", "FAIL")) != "PASS":
                    all_pass = False
        return cycle_rows, all_pass

    cycles += 1
    pre_rows, pre_all_pass = execute_cycle(cycles, "precheck", precheck=True)
    rows.extend(pre_rows)
    if pre_all_pass:
        entry_ready_seconds = max(1, int(round(time.monotonic() - tstart)))
    else:
        precheck_fail_closed = True
        precheck_issues.append("critical precheck failed before steady/burst windows")

    steady_seconds = int(win_override) if win_override is not None else int(float(pkt.get("M4_STRESS_STEADY_WINDOW_MINUTES", 10)) * 60)
    steady_seconds = max(60, steady_seconds)
    burst_seconds = max(30, int(float(pkt.get("M4_STRESS_BURST_WINDOW_MINUTES", 5)) * 60))
    interval_steady = max(1, interval)
    interval_burst = max(1, interval_steady // 2)
    window_label_counts = {"steady": 0, "burst": 0}

    if not precheck_fail_closed:
        tsteady = time.monotonic()
        while time.monotonic() - tsteady < steady_seconds:
            cycles += 1
            c0 = time.monotonic()
            cycle_rows, all_pass = execute_cycle(cycles, "steady", precheck=False)
            rows.extend(cycle_rows)
            window_label_counts["steady"] += 1
            if all_pass and entry_ready_seconds is None:
                entry_ready_seconds = max(1, int(round(time.monotonic() - tstart)))
            sleep_for = min(max(0.0, interval_steady - (time.monotonic() - c0)), max(0.0, steady_seconds - (time.monotonic() - tsteady)))
            if sleep_for > 0:
                time.sleep(sleep_for)

        tburst = time.monotonic()
        while time.monotonic() - tburst < burst_seconds:
            cycles += 1
            c0 = time.monotonic()
            cycle_rows, all_pass = execute_cycle(cycles, "burst", precheck=False)
            rows.extend(cycle_rows)
            window_label_counts["burst"] += 1
            if all_pass and entry_ready_seconds is None:
                entry_ready_seconds = max(1, int(round(time.monotonic() - tstart)))
            sleep_for = min(max(0.0, interval_burst - (time.monotonic() - c0)), max(0.0, burst_seconds - (time.monotonic() - tburst)))
            if sleep_for > 0:
                time.sleep(sleep_for)

    s2_entry_issues: list[str] = []
    if entry_ready_seconds is None:
        s2_entry_issues.append("s2 entry readiness not reached")

    control_issues: list[str] = []
    if str(h.get("SR_READY_COMMIT_AUTHORITY", "")) != "step_functions_only":
        control_issues.append("SR_READY_COMMIT_AUTHORITY drift")
    control_issues.extend(runtime_path_issues)
    control_issues.extend(corr_issues)
    control_issues.extend(precheck_issues)
    fail_counts: dict[str, int] = {}
    for r in rows:
        pid = str(r.get("probe_id", ""))
        if str(r.get("status", "FAIL")) != "PASS":
            fail_counts[pid] = fail_counts.get(pid, 0) + 1
    for pid, cnt in sorted(fail_counts.items()):
        control_issues.append(f"{pid} failures: {cnt}")

    s1_path = Path(str(s1.get("path", ""))) if s1 else Path("")
    s1_ctrl = load_json_safe(s1_path / "m4_control_rail_conformance_snapshot.json") if s1 else {}
    s1_probe = load_json_safe(s1_path / "m4_probe_latency_throughput_snapshot.json") if s1 else {}
    s1_issues = [str(x) for x in s1_ctrl.get("issues", [])] if s1_ctrl else []
    new_ci = sorted(set(control_issues) - set(s1_issues))

    total = len(rows)
    fails = [r for r in rows if str(r.get("status", "FAIL")) != "PASS"]
    er = round((len(fails) / total) * 100.0, 4) if total else 100.0
    lat = [float(r.get("duration_ms", 0.0)) for r in rows]
    cycle_failed: dict[int, bool] = {}
    for r in rows:
        idx = int(r.get("cycle_index", 0))
        if idx not in cycle_failed:
            cycle_failed[idx] = False
        if str(r.get("status", "FAIL")) != "PASS":
            cycle_failed[idx] = True
    cur_streak = 0
    max_streak = 0
    for idx in sorted(cycle_failed):
        if cycle_failed[idx]:
            cur_streak += 1
            max_streak = max(max_streak, cur_streak)
        else:
            cur_streak = 0

    s1_error_rate = float(s1_probe.get("error_rate_pct", 0.0)) if s1_probe else 0.0
    s1_max_streak = int(s1_probe.get("max_consecutive_failure_cycles", 0)) if s1_probe else 0

    if runtime_path_issues or s2_entry_issues:
        blockers.append({"id": "M4-ST-B2", "severity": "S2", "status": "OPEN", "details": {"issues": runtime_path_issues + s2_entry_issues}})
    b3_markers = ["s2_sfn_lookup", "s2_evidence_bucket", "s2_api_gateway", "s2_lambda", "s2_ddb", "s2_msk", "s2_flink_", "SR_READY_COMMIT_AUTHORITY"]
    b3_issues = [x for x in new_ci if any(y in x for y in b3_markers)]
    if b3_issues:
        blockers.append({"id": "M4-ST-B3", "severity": "S2", "status": "OPEN", "details": {"issues": sorted(set(b3_issues))}})
    b4_issues = [x for x in new_ci if "correlation" in x]
    if b4_issues:
        blockers.append({"id": "M4-ST-B4", "severity": "S2", "status": "OPEN", "details": {"issues": sorted(set(b4_issues))}})

    b5_details: dict[str, Any] = {}
    if er > 2.0:
        b5_details["error_rate_pct"] = er
    if max_streak > 3:
        b5_details["max_consecutive_failure_cycles"] = max_streak
    if er > (s1_error_rate + 1.0):
        b5_details["error_rate_regression_vs_s1"] = {"s1": s1_error_rate, "s2": er}
    if max_streak > max(3, s1_max_streak + 1):
        b5_details["failure_streak_regression_vs_s1"] = {"s1": s1_max_streak, "s2": max_streak}
    if b5_details:
        blockers.append({"id": "M4-ST-B5", "severity": "S2", "status": "OPEN", "details": b5_details})

    wdec = any("--with-decryption" in str(r.get("command", "")) for r in rows)
    qval = any("Parameter.Value" in str(r.get("command", "")) or "SecretString" in str(r.get("command", "")) for r in rows)
    sus: list[str] = []
    rx = re.compile(r"(AKIA[0-9A-Z]{16}|BEGIN [A-Z ]*PRIVATE KEY|SECRET_ACCESS_KEY)")
    for r in rows:
        if rx.search((str(r.get("stdout", "")) + " " + str(r.get("stderr", ""))).strip()):
            sus.append(str(r.get("probe_id", "")))
    leak = wdec or qval or bool(sus)
    if leak:
        blockers.append({"id": "M4-ST-B6", "severity": "S2", "status": "OPEN", "details": {"issues": ["plaintext leakage signal detected"]}})

    dur_s = max(1, int(round(time.monotonic() - tstart)))
    max_sp = float(pkt.get("M4_STRESS_MAX_SPEND_USD", 40))
    cost_within = True
    if not cost_within:
        blockers.append({"id": "M4-ST-B8", "severity": "S2", "status": "OPEN"})

    probe = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M4-ST-S2",
        "steady_window_seconds_configured": steady_seconds,
        "burst_window_seconds_configured": burst_seconds,
        "window_seconds_observed": dur_s,
        "cycle_count": cycles,
        "window_cycle_counts": window_label_counts,
        "probe_count": total,
        "failure_count": len(fails),
        "error_rate_pct": er,
        "probe_eps_observed": round(total / max(1.0, float(dur_s)), 4),
        "latency_ms_p50": round(pct(lat, 0.5), 3),
        "latency_ms_p95": round(pct(lat, 0.95), 3),
        "latency_ms_p99": round(pct(lat, 0.99), 3),
        "sample_failures": fails[:10],
        "max_consecutive_failure_cycles": max_streak,
        "entry_ready_seconds": entry_ready_seconds,
        "precheck_fail_closed": precheck_fail_closed,
        "s1_baseline_phase_execution_id": s1.get("summary", {}).get("phase_execution_id", "") if s1 else "",
        "s1_baseline_error_rate_pct": s1_error_rate,
        "s1_baseline_max_consecutive_failure_cycles": s1_max_streak,
        "sfn_handle_chain": sfn_chain,
        "sfn_name_resolved": sfn_name_s,
    }
    dumpj(out / "m4_probe_latency_throughput_snapshot.json", probe)

    ctrl = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M4-ST-S2",
        "overall_pass": len(new_ci) == 0 and len(runtime_path_issues) == 0 and len(s2_entry_issues) == 0,
        "issues": control_issues,
        "s1_baseline_issues": s1_issues,
        "new_issues_vs_s1": new_ci,
        "s1_dependency_summary": s1.get("summary", {}) if s1 else {},
        "probe_failure_counts": fail_counts,
        "sfn_handle_chain": sfn_chain,
    }
    dumpj(out / "m4_control_rail_conformance_snapshot.json", ctrl)

    sec = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M4-ST-S2",
        "overall_pass": not leak,
        "secret_probe_count": 0,
        "secret_failure_count": 0,
        "with_decryption_used": wdec,
        "queried_value_directly": qval,
        "suspicious_output_probe_ids": sus,
        "plaintext_leakage_detected": leak,
    }
    dumpj(out / "m4_secret_safety_snapshot.json", sec)

    cost = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M4-ST-S2",
        "window_seconds": dur_s,
        "estimated_api_call_count": total,
        "attributed_spend_usd": 0.0,
        "unattributed_spend_detected": False,
        "max_spend_usd": max_sp,
        "within_envelope": cost_within,
        "method": "readonly_steady_burst_dependency_probe_v0",
    }
    dumpj(out / "m4_cost_outcome_receipt.json", cost)

    dlog = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M4-ST-S2",
        "decisions": [
            "Validated S1 continuity and carried Stage-A artifacts forward.",
            "Executed critical precheck before steady and burst windows.",
            "Executed path-aware dependency probes across steady and burst windows.",
            "Compared S2 control and instability posture against latest successful S1 baseline.",
            "Applied fail-closed blocker mapping for M4 S2.",
        ],
    }
    dumpj(out / "m4_decision_log.json", dlog)

    bref = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M4-ST-S2",
        "overall_pass": len(blockers) == 0,
        "open_blocker_count": len(blockers),
        "blockers": blockers,
    }
    summ = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M4-ST-S2",
        "overall_pass": len(blockers) == 0,
        "next_gate": "M4_ST_S3_READY" if len(blockers) == 0 else "BLOCKED",
        "required_artifacts": S2_ARTS,
        "probe_count": total,
        "error_rate_pct": er,
        "entry_ready_seconds": entry_ready_seconds,
        "s1_baseline_phase_execution_id": s1.get("summary", {}).get("phase_execution_id", "") if s1 else "",
    }
    dumpj(out / "m4_blocker_register.json", bref)
    dumpj(out / "m4_execution_summary.json", summ)

    miss = [n for n in S2_ARTS if not (out / n).exists()]
    if miss:
        blockers.append({"id": "M4-ST-B9", "severity": "S2", "status": "OPEN", "details": {"missing_artifacts": miss}})
        bref["overall_pass"] = False
        bref["open_blocker_count"] = len(blockers)
        bref["blockers"] = blockers
        summ["overall_pass"] = False
        summ["next_gate"] = "BLOCKED"
        dumpj(out / "m4_blocker_register.json", bref)
        dumpj(out / "m4_execution_summary.json", summ)

    print(f"[m4_s2] phase_execution_id={phase_id}")
    print(f"[m4_s2] output_dir={out.as_posix()}")
    print(f"[m4_s2] overall_pass={summ['overall_pass']}")
    print(f"[m4_s2] next_gate={summ['next_gate']}")
    print(f"[m4_s2] probe_count={total}")
    print(f"[m4_s2] error_rate_pct={er}")
    print(f"[m4_s2] entry_ready_seconds={entry_ready_seconds}")
    print(f"[m4_s2] open_blockers={bref['open_blocker_count']}")
    return 0 if summ["overall_pass"] else 2


def main() -> int:
    ap = argparse.ArgumentParser(description="M4 stress runner")
    ap.add_argument("--stage", default="S0", choices=["S0", "S1", "S2"])
    ap.add_argument("--phase-execution-id", default="")
    ap.add_argument("--output-root", default=str(OUT_ROOT))
    ap.add_argument("--window-seconds", type=int, default=None)
    ap.add_argument("--interval-seconds", type=int, default=10)
    ap.add_argument("--probe-concurrency", type=int, default=0)
    a = ap.parse_args()
    pfx = {"S0": "m4_stress_s0", "S1": "m4_stress_s1", "S2": "m4_stress_s2"}[a.stage]
    pid = a.phase_execution_id.strip() or f"{pfx}_{tok()}"
    root = Path(a.output_root)
    if a.stage == "S0":
        return run_s0(pid, root)
    if a.stage == "S1":
        return run_s1(pid, root, a.window_seconds, a.interval_seconds, a.probe_concurrency)
    return run_s2(pid, root, a.window_seconds, a.interval_seconds, a.probe_concurrency)


if __name__ == "__main__":
    raise SystemExit(main())
