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


def main() -> int:
    ap = argparse.ArgumentParser(description="M4 stress runner")
    ap.add_argument("--stage", default="S0", choices=["S0"])
    ap.add_argument("--phase-execution-id", default="")
    ap.add_argument("--output-root", default=str(OUT_ROOT))
    a = ap.parse_args()
    pfx = {"S0": "m4_stress_s0"}[a.stage]
    pid = a.phase_execution_id.strip() or f"{pfx}_{tok()}"
    root = Path(a.output_root)
    return run_s0(pid, root)


if __name__ == "__main__":
    raise SystemExit(main())
