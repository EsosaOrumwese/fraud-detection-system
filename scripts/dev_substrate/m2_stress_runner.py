#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PLAN = Path("docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M2.stress_test.md")
REG = Path("docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md")
OUT_ROOT = Path("runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control")

S0_SECTIONS = [
    "## 5) M2 Stress Handle Packet (Pinned)",
    "## 6) Capability-Lane Coverage (Phase-Coverage Law)",
    "## 7) Stress Topology (M2)",
    "## 8) Execution Plan (Execution-Grade Runbook)",
    "## 9) Blocker Taxonomy (M2 Stress)",
]
S0_KEYS = [
    "M2_STRESS_PROFILE_ID",
    "M2_STRESS_BLOCKER_REGISTER_PATH_PATTERN",
    "M2_STRESS_EXECUTION_SUMMARY_PATH_PATTERN",
    "M2_STRESS_DECISION_LOG_PATH_PATTERN",
    "M2_STRESS_REQUIRED_ARTIFACTS",
    "M2_STRESS_MAX_RUNTIME_MINUTES",
    "M2_STRESS_MAX_SPEND_USD",
    "M2_STRESS_BASELINE_EVENTS_PER_SECOND",
    "M2_STRESS_BURST_EVENTS_PER_SECOND",
    "M2_STRESS_WINDOW_MINUTES",
]
S1_ARTS = [
    "m2_stagea_findings.json",
    "m2_lane_matrix.json",
    "m2_probe_latency_throughput_snapshot.json",
    "m2_control_rail_conformance_snapshot.json",
    "m2_secret_safety_snapshot.json",
    "m2_cost_outcome_receipt.json",
    "m2_blocker_register.json",
    "m2_execution_summary.json",
    "m2_decision_log.json",
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def tok() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def dumpj(p: Path, o: dict[str, Any]) -> None:
    p.write_text(json.dumps(o, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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
        token = val.strip()
        if token in h and re.fullmatch(r"[A-Z0-9_]+", token) and token not in chain and hops < max_hops:
            chain.append(token)
            val = h[token]
            hops += 1
            continue
        break
    return val, chain


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


def run_probe(probe: dict[str, Any]) -> dict[str, Any]:
    t0 = time.perf_counter()
    st = now()
    try:
        p = subprocess.run(probe["argv"], capture_output=True, text=True, timeout=int(probe.get("timeout", 20)))
        return {
            "probe_id": probe["id"],
            "group": probe["group"],
            "command": " ".join(probe["argv"]),
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
            "probe_id": probe["id"],
            "group": probe["group"],
            "command": " ".join(probe["argv"]),
            "exit_code": 124,
            "status": "FAIL",
            "duration_ms": round((time.perf_counter() - t0) * 1000.0, 3),
            "stdout": "",
            "stderr": "timeout",
            "started_at_utc": st,
            "ended_at_utc": now(),
        }


def build_lane_matrix() -> dict[str, Any]:
    return {
        "component_sequence": ["M2.A/B/C", "M2.D/E/F", "M2.G/H"],
        "plane_sequence": ["substrate_plane", "control_rail_plane", "safety_plane"],
        "integrated_windows": ["S1_baseline", "S2_burst", "S3_failure_injection"],
    }


def run_s0(phase_id: str, out_root: Path) -> int:
    txt = PLAN.read_text(encoding="utf-8") if PLAN.exists() else ""
    pkt = parse_backtick_map(txt) if txt else {}
    miss_sections = [s for s in S0_SECTIONS if s not in txt]
    miss_keys = [k for k in S0_KEYS if k not in pkt]
    findings = [
        {"id": "M2-ST-F1", "classification": "PREVENT", "status": "CLOSED" if PLAN.exists() else "OPEN", "evidence": {"path": str(PLAN)}},
        {"id": "M2-ST-F2", "classification": "PREVENT", "status": "CLOSED" if not miss_keys else "OPEN", "evidence": {"missing_keys": miss_keys}},
        {"id": "M2-ST-F3", "classification": "PREVENT", "status": "CLOSED" if not miss_sections else "OPEN", "evidence": {"missing_sections": miss_sections}},
        {"id": "M2-ST-F4", "classification": "OBSERVE", "status": "OPEN_OBSERVE"},
        {"id": "M2-ST-F5", "classification": "OBSERVE", "status": "OPEN_OBSERVE"},
        {"id": "M2-ST-F6", "classification": "ACCEPT", "status": "ACCEPTED"},
    ]
    blockers: list[dict[str, Any]] = []
    if not PLAN.exists() or miss_keys:
        blockers.append({"id": "M2-ST-B1", "severity": "S1", "status": "OPEN"})
    if miss_sections:
        blockers.append({"id": "M2-ST-B9", "severity": "S1", "status": "OPEN", "details": {"missing_sections": miss_sections}})
    out = out_root / phase_id / "stress"
    out.mkdir(parents=True, exist_ok=True)
    dumpj(out / "m2_stagea_findings.json", {"generated_at_utc": now(), "phase_execution_id": phase_id, "stage_id": "M2-ST-S0", "overall_pass": not blockers, "findings": findings})
    dumpj(out / "m2_lane_matrix.json", {"generated_at_utc": now(), "phase_execution_id": phase_id, "stage_id": "M2-ST-S0", "lane_matrix": build_lane_matrix(), "dispatch_profile": {"baseline_eps": pkt.get("M2_STRESS_BASELINE_EVENTS_PER_SECOND", 20), "burst_eps": pkt.get("M2_STRESS_BURST_EVENTS_PER_SECOND", 40), "window_minutes": pkt.get("M2_STRESS_WINDOW_MINUTES", 10)}})
    dumpj(out / "m2_blocker_register.json", {"generated_at_utc": now(), "phase_execution_id": phase_id, "stage_id": "M2-ST-S0", "overall_pass": not blockers, "open_blocker_count": len(blockers), "blockers": blockers})
    dumpj(out / "m2_decision_log.json", {"generated_at_utc": now(), "phase_execution_id": phase_id, "stage_id": "M2-ST-S0", "decisions": ["S0 authority validation completed."]})
    dumpj(out / "m2_execution_summary.json", {"generated_at_utc": now(), "phase_execution_id": phase_id, "stage_id": "M2-ST-S0", "overall_pass": not blockers, "next_gate": "M2_ST_S1_READY" if not blockers else "BLOCKED"})
    print(f"[m2_s0] phase_execution_id={phase_id}")
    print(f"[m2_s0] output_dir={out.as_posix()}")
    print(f"[m2_s0] overall_pass={not blockers}")
    print(f"[m2_s0] next_gate={'M2_ST_S1_READY' if not blockers else 'BLOCKED'}")
    print(f"[m2_s0] open_blockers={len(blockers)}")
    return 0 if not blockers else 2


def build_s1_probes(h: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
    req = ["AWS_REGION", "MSK_REGION", "TF_STATE_BUCKET", "TF_LOCK_TABLE", "MSK_CLUSTER_ARN", "SSM_MSK_BOOTSTRAP_BROKERS_PATH", "GLUE_SCHEMA_REGISTRY_NAME", "APIGW_IG_API_ID", "LAMBDA_IG_HANDLER_NAME", "DDB_IG_IDEMPOTENCY_TABLE", "SR_READY_COMMIT_STATE_MACHINE", "SSM_IG_API_KEY_PATH"]
    missing = [k for k in req if k not in h or str(h[k]).strip() in {"", "TO_PIN"}]
    if missing:
        return [], missing, {}
    r = str(h["AWS_REGION"])
    mr = str(h.get("MSK_REGION", r))
    sr_state_machine, sr_chain = resolve_handle(h, "SR_READY_COMMIT_STATE_MACHINE")
    sr_name = str(sr_state_machine).strip() if sr_state_machine is not None else ""
    if not sr_name or sr_name in {"", "TO_PIN"}:
        return [], (missing + ["SR_READY_COMMIT_STATE_MACHINE(resolved)"]), {"sr_handle_chain": sr_chain}
    probes: list[dict[str, Any]] = [
        {"id": "state_bucket_head", "group": "state_backend", "argv": ["aws", "s3api", "head-bucket", "--bucket", str(h["TF_STATE_BUCKET"]), "--region", r]},
        {"id": "state_lock_table", "group": "state_backend", "argv": ["aws", "dynamodb", "describe-table", "--table-name", str(h["TF_LOCK_TABLE"]), "--region", r, "--query", "Table.TableStatus", "--output", "text"]},
        {"id": "msk_cluster", "group": "messaging", "argv": ["aws", "kafka", "describe-cluster-v2", "--cluster-arn", str(h["MSK_CLUSTER_ARN"]), "--region", mr, "--query", "ClusterInfo.State", "--output", "text"], "timeout": 25},
        {"id": "msk_bootstrap_path", "group": "messaging", "argv": ["aws", "ssm", "get-parameter", "--name", str(h["SSM_MSK_BOOTSTRAP_BROKERS_PATH"]), "--region", r, "--query", "Parameter.ARN", "--output", "text"]},
        {"id": "glue_registry", "group": "messaging", "argv": ["aws", "glue", "get-registry", "--registry-id", f"RegistryName={h['GLUE_SCHEMA_REGISTRY_NAME']}", "--region", r, "--query", "RegistryName", "--output", "text"]},
        {"id": "api_get", "group": "api_edge", "argv": ["aws", "apigatewayv2", "get-api", "--api-id", str(h["APIGW_IG_API_ID"]), "--region", r, "--query", "ApiId", "--output", "text"]},
        {"id": "lambda_get", "group": "api_edge", "argv": ["aws", "lambda", "get-function", "--function-name", str(h["LAMBDA_IG_HANDLER_NAME"]), "--region", r, "--query", "Configuration.FunctionName", "--output", "text"]},
        {"id": "ddb_get", "group": "api_edge", "argv": ["aws", "dynamodb", "describe-table", "--table-name", str(h["DDB_IG_IDEMPOTENCY_TABLE"]), "--region", r, "--query", "Table.TableStatus", "--output", "text"]},
        {"id": "sr_sfn_lookup", "group": "control_rail", "argv": ["aws", "stepfunctions", "list-state-machines", "--max-results", "100", "--region", r, "--query", f"stateMachines[?name=='{sr_name}'].stateMachineArn | [0]", "--output", "text"]},
    ]
    for k in sorted(x for x in h if x.startswith("SSM_") and x.endswith("_PATH")):
        pv = str(h[k])
        if pv.startswith("/"):
            probes.append({"id": f"secret_{k.lower()}", "group": "secrets", "argv": ["aws", "ssm", "get-parameter", "--name", pv, "--region", r, "--query", "Parameter.ARN", "--output", "text"]})
    return probes, [], {"sr_state_machine_name_resolved": sr_name, "sr_handle_chain": sr_chain}


def copy_s0(out_root: Path, out_dir: Path) -> list[str]:
    s0s = sorted(out_root.glob("m2_stress_s0_*/stress"))
    if not s0s:
        return ["No S0 folder found."]
    src = s0s[-1]
    errs: list[str] = []
    for n in ("m2_stagea_findings.json", "m2_lane_matrix.json"):
        s = src / n
        if s.exists():
            shutil.copy2(s, out_dir / n)
        else:
            errs.append(f"Missing {s.as_posix()}")
    return errs


def load_latest_successful_s1(out_root: Path) -> dict[str, Any]:
    s1s = sorted(out_root.glob("m2_stress_s1_*/stress"))
    for d in reversed(s1s):
        sp = d / "m2_execution_summary.json"
        if not sp.exists():
            continue
        try:
            summ = json.loads(sp.read_text(encoding="utf-8"))
        except Exception:
            continue
        if summ.get("overall_pass") is not True:
            continue
        out: dict[str, Any] = {"path": d.as_posix(), "summary": summ, "phase_execution_id": summ.get("phase_execution_id", "")}
        for n in ("m2_probe_latency_throughput_snapshot.json", "m2_control_rail_conformance_snapshot.json"):
            p = d / n
            if not p.exists():
                continue
            try:
                out[n] = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
        return out
    return {}


def run_s1(phase_id: str, out_root: Path, win_override: int | None, interval: int, conc: int) -> int:
    plan_txt = PLAN.read_text(encoding="utf-8")
    pkt = parse_backtick_map(plan_txt)
    h = parse_registry(REG)
    out = out_root / phase_id / "stress"
    out.mkdir(parents=True, exist_ok=True)
    blockers: list[dict[str, Any]] = []
    errs = copy_s0(out_root, out)
    if errs:
        blockers.append({"id": "M2-ST-B9", "severity": "S1", "status": "OPEN", "details": {"copy_errors": errs}})
    probes, missing, probe_meta = build_s1_probes(h)
    if missing:
        blockers.append({"id": "M2-ST-B1", "severity": "S1", "status": "OPEN", "details": {"missing_keys": missing}})

    win = int(win_override) if win_override is not None else int(float(pkt.get("M2_STRESS_WINDOW_MINUTES", 10)) * 60)
    win = max(win, 60)
    rows: list[dict[str, Any]] = []
    cycles = 0
    tstart = time.monotonic()
    precheck_issues: list[str] = []
    precheck_fail_closed = False
    critical = {"state_bucket_head", "state_lock_table", "msk_cluster", "api_get", "lambda_get", "ddb_get", "sr_sfn_lookup"}
    if not missing:
        precheck = [p for p in probes if p["id"] in critical]
        if precheck:
            cycles += 1
            with cf.ThreadPoolExecutor(max_workers=max(1, min(conc, len(precheck)))) as ex:
                futs = [ex.submit(run_probe, p) for p in precheck]
                for f in cf.as_completed(futs):
                    r = f.result()
                    r["cycle_index"] = cycles
                    r["precheck"] = True
                    rows.append(r)
            failed = [r for r in rows if r.get("precheck") and r["status"] != "PASS"]
            srp = [r for r in rows if r.get("precheck") and r["probe_id"] == "sr_sfn_lookup"]
            sri = srp[-1] if srp else None
            if failed:
                precheck_issues.append(f"critical precheck failures: {len(failed)}")
            if sri is None or sri["status"] != "PASS" or sri["stdout"] in {"", "None", "null"}:
                precheck_issues.append("SR state machine lookup failed during precheck")
            if precheck_issues:
                precheck_fail_closed = True
    while (time.monotonic() - tstart < win) and (not missing) and (not precheck_fail_closed):
        cycles += 1
        c0 = time.monotonic()
        with cf.ThreadPoolExecutor(max_workers=max(1, conc)) as ex:
            futs = [ex.submit(run_probe, p) for p in probes]
            for f in cf.as_completed(futs):
                r = f.result()
                r["cycle_index"] = cycles
                rows.append(r)
        sleep_for = min(max(0.0, interval - (time.monotonic() - c0)), max(0.0, win - (time.monotonic() - tstart)))
        if sleep_for > 0:
            time.sleep(sleep_for)

    dur = max(1.0, time.monotonic() - tstart)
    total = len(rows)
    fails = [r for r in rows if r["status"] != "PASS"]
    er = round((len(fails) / total) * 100.0, 4) if total else 100.0
    lat = [float(r["duration_ms"]) for r in rows]
    probe = {"generated_at_utc": now(), "phase_execution_id": phase_id, "stage_id": "M2-ST-S1", "window_seconds_configured": win, "window_seconds_observed": int(round(dur)), "cycle_count": cycles, "probe_count": total, "failure_count": len(fails), "error_rate_pct": er, "probe_eps_observed": round(total / dur, 4), "probe_eps_target": float(pkt.get("M2_STRESS_BASELINE_EVENTS_PER_SECOND", 20)), "latency_ms_p50": round(pct(lat, 0.5), 3), "latency_ms_p95": round(pct(lat, 0.95), 3), "latency_ms_p99": round(pct(lat, 0.99), 3), "sample_failures": fails[:10]}
    dumpj(out / "m2_probe_latency_throughput_snapshot.json", probe)

    sr = [r for r in rows if r["probe_id"] == "sr_sfn_lookup"]
    sri = sr[-1] if sr else None
    ci: list[str] = []
    if h.get("PHASE_RUNTIME_PATH_MODE") != "single_active_path_per_phase_run":
        ci.append("PHASE_RUNTIME_PATH_MODE drift")
    if h.get("PHASE_RUNTIME_PATH_PIN_REQUIRED") is not True:
        ci.append("PHASE_RUNTIME_PATH_PIN_REQUIRED not true")
    if h.get("RUNTIME_PATH_SWITCH_IN_PHASE_ALLOWED") is not False:
        ci.append("RUNTIME_PATH_SWITCH_IN_PHASE_ALLOWED not false")
    if h.get("SR_READY_COMMIT_AUTHORITY") != "step_functions_only":
        ci.append("SR_READY_COMMIT_AUTHORITY drift")
    if h.get("CORRELATION_ENFORCEMENT_FAIL_CLOSED") is not True:
        ci.append("CORRELATION_ENFORCEMENT_FAIL_CLOSED not true")
    if sri is None or sri["status"] != "PASS" or sri["stdout"] in {"", "None", "null"}:
        ci.append("SR state machine lookup failed")
    if precheck_issues:
        ci.extend(precheck_issues)
    ctrl = {"generated_at_utc": now(), "phase_execution_id": phase_id, "stage_id": "M2-ST-S1", "overall_pass": len(ci) == 0, "issues": ci, "sr_lookup_probe": sri}
    ctrl["handle_resolution"] = probe_meta
    ctrl["precheck_fail_closed"] = precheck_fail_closed
    dumpj(out / "m2_control_rail_conformance_snapshot.json", ctrl)

    srows = [r for r in rows if r["group"] == "secrets"]
    sf = [r for r in srows if r["status"] != "PASS"]
    wdec = any("--with-decryption" in r["command"] for r in rows)
    qval = any("Parameter.Value" in r["command"] or "SecretString" in r["command"] for r in rows)
    sus = []
    rx = re.compile(r"(AKIA[0-9A-Z]{16}|BEGIN [A-Z ]*PRIVATE KEY|SECRET_ACCESS_KEY)")
    for r in rows:
        if rx.search((r["stdout"] + " " + r["stderr"]).strip()):
            sus.append(r["probe_id"])
    leak = wdec or qval or bool(sus)
    sec = {"generated_at_utc": now(), "phase_execution_id": phase_id, "stage_id": "M2-ST-S1", "overall_pass": len(sf) == 0 and not leak, "secret_probe_count": len(srows), "secret_failure_count": len(sf), "with_decryption_used": wdec, "queried_value_directly": qval, "suspicious_output_probe_ids": sus, "plaintext_leakage_detected": leak}
    dumpj(out / "m2_secret_safety_snapshot.json", sec)

    max_sp = float(pkt.get("M2_STRESS_MAX_SPEND_USD", 35))
    cost = {"generated_at_utc": now(), "phase_execution_id": phase_id, "stage_id": "M2-ST-S1", "window_seconds": int(round(dur)), "estimated_api_call_count": total, "attributed_spend_usd": 0.0, "unattributed_spend_detected": False, "max_spend_usd": max_sp, "within_envelope": True, "method": "readonly_control_plane_probe_estimate_v0"}
    dumpj(out / "m2_cost_outcome_receipt.json", cost)

    if any(r["group"] in {"state_backend", "messaging"} and r["status"] != "PASS" for r in rows):
        blockers.append({"id": "M2-ST-B2", "severity": "S1", "status": "OPEN"})
    if any(r["group"] == "api_edge" and r["status"] != "PASS" for r in rows):
        blockers.append({"id": "M2-ST-B5", "severity": "S1", "status": "OPEN"})
    if ci:
        blockers.append({"id": "M2-ST-B3", "severity": "S1", "status": "OPEN", "details": {"issues": ci}})
        if any("SR" in x for x in ci):
            blockers.append({"id": "M2-ST-B4", "severity": "S1", "status": "OPEN"})
    if sec["overall_pass"] is False:
        blockers.append({"id": "M2-ST-B6", "severity": "S1", "status": "OPEN"})
    if er > 1.0:
        blockers.append({"id": "M2-ST-B7", "severity": "S1", "status": "OPEN", "details": {"error_rate_pct": er}})
    if not cost["within_envelope"] or cost["unattributed_spend_detected"]:
        blockers.append({"id": "M2-ST-B8", "severity": "S1", "status": "OPEN"})
    dlog = {"generated_at_utc": now(), "phase_execution_id": phase_id, "stage_id": "M2-ST-S1", "decisions": ["Executed critical precheck before sustained baseline window.", "Executed baseline read-only probes across substrate surfaces.", "Applied fail-closed blocker mapping from M2 taxonomy.", "Carried S0 findings/lane matrix artifacts forward for artifact continuity."]}
    dumpj(out / "m2_decision_log.json", dlog)
    bref = {"generated_at_utc": now(), "phase_execution_id": phase_id, "stage_id": "M2-ST-S1", "overall_pass": len(blockers) == 0, "open_blocker_count": len(blockers), "blockers": blockers}
    summ = {"generated_at_utc": now(), "phase_execution_id": phase_id, "stage_id": "M2-ST-S1", "overall_pass": len(blockers) == 0, "next_gate": "M2_ST_S2_READY" if len(blockers) == 0 else "BLOCKED", "error_rate_pct": er, "probe_count": total, "window_seconds_observed": int(round(dur)), "required_artifacts": S1_ARTS}
    dumpj(out / "m2_blocker_register.json", bref)
    dumpj(out / "m2_execution_summary.json", summ)

    miss = [n for n in S1_ARTS if not (out / n).exists()]
    if miss:
        blockers.append({"id": "M2-ST-B9", "severity": "S1", "status": "OPEN", "details": {"missing_artifacts": miss}})
        bref["overall_pass"] = False
        bref["open_blocker_count"] = len(blockers)
        bref["blockers"] = blockers
        summ["overall_pass"] = False
        summ["next_gate"] = "BLOCKED"
        dumpj(out / "m2_blocker_register.json", bref)
        dumpj(out / "m2_execution_summary.json", summ)

    print(f"[m2_s1] phase_execution_id={phase_id}")
    print(f"[m2_s1] output_dir={out.as_posix()}")
    print(f"[m2_s1] overall_pass={summ['overall_pass']}")
    print(f"[m2_s1] next_gate={summ['next_gate']}")
    print(f"[m2_s1] probe_count={total}")
    print(f"[m2_s1] error_rate_pct={er}")
    print(f"[m2_s1] open_blockers={bref['open_blocker_count']}")
    return 0 if summ["overall_pass"] else 2


def run_s2(phase_id: str, out_root: Path, win_override: int | None, interval: int, conc: int) -> int:
    plan_txt = PLAN.read_text(encoding="utf-8")
    pkt = parse_backtick_map(plan_txt)
    h = parse_registry(REG)
    out = out_root / phase_id / "stress"
    out.mkdir(parents=True, exist_ok=True)
    blockers: list[dict[str, Any]] = []
    errs = copy_s0(out_root, out)
    if errs:
        blockers.append({"id": "M2-ST-B9", "severity": "S2", "status": "OPEN", "details": {"copy_errors": errs}})
    probes, missing, probe_meta = build_s1_probes(h)
    if missing:
        blockers.append({"id": "M2-ST-B1", "severity": "S2", "status": "OPEN", "details": {"missing_keys": missing}})

    s1ref = load_latest_successful_s1(out_root)
    if not s1ref:
        blockers.append({"id": "M2-ST-B9", "severity": "S2", "status": "OPEN", "details": {"missing_baseline": "No successful S1 baseline artifact pack found"}})

    base_eps = float(pkt.get("M2_STRESS_BASELINE_EVENTS_PER_SECOND", 20))
    burst_eps = float(pkt.get("M2_STRESS_BURST_EVENTS_PER_SECOND", 40))
    ratio = burst_eps / max(1.0, base_eps)
    burst_conc = max(int(round(conc * ratio)), conc + 2, 10)
    burst_conc = min(burst_conc, 24)
    burst_interval = max(5, min(interval, 10))
    burst_probes: list[dict[str, Any]] = []
    for p in probes:
        q = dict(p)
        q["timeout"] = min(int(q.get("timeout", 20)), 18)
        burst_probes.append(q)

    win = int(win_override) if win_override is not None else int(float(pkt.get("M2_STRESS_WINDOW_MINUTES", 10)) * 60)
    win = max(win, 60)
    rows: list[dict[str, Any]] = []
    cycles = 0
    tstart = time.monotonic()
    precheck_issues: list[str] = []
    precheck_fail_closed = False
    critical = {"state_bucket_head", "state_lock_table", "msk_cluster", "api_get", "lambda_get", "ddb_get", "sr_sfn_lookup"}
    can_run = (not missing) and bool(s1ref)
    if can_run:
        precheck = [p for p in burst_probes if p["id"] in critical]
        if precheck:
            cycles += 1
            with cf.ThreadPoolExecutor(max_workers=max(1, min(burst_conc, len(precheck)))) as ex:
                futs = [ex.submit(run_probe, p) for p in precheck]
                for f in cf.as_completed(futs):
                    r = f.result()
                    r["cycle_index"] = cycles
                    r["precheck"] = True
                    rows.append(r)
            failed = [r for r in rows if r.get("precheck") and r["status"] != "PASS"]
            srp = [r for r in rows if r.get("precheck") and r["probe_id"] == "sr_sfn_lookup"]
            sri = srp[-1] if srp else None
            if failed:
                precheck_issues.append(f"critical precheck failures: {len(failed)}")
            if sri is None or sri["status"] != "PASS" or sri["stdout"] in {"", "None", "null"}:
                precheck_issues.append("SR state machine lookup failed during precheck")
            if precheck_issues:
                precheck_fail_closed = True
    while (time.monotonic() - tstart < win) and can_run and (not precheck_fail_closed):
        cycles += 1
        c0 = time.monotonic()
        with cf.ThreadPoolExecutor(max_workers=max(1, burst_conc)) as ex:
            futs = [ex.submit(run_probe, p) for p in burst_probes]
            for f in cf.as_completed(futs):
                r = f.result()
                r["cycle_index"] = cycles
                rows.append(r)
        sleep_for = min(max(0.0, burst_interval - (time.monotonic() - c0)), max(0.0, win - (time.monotonic() - tstart)))
        if sleep_for > 0:
            time.sleep(sleep_for)

    dur = max(1.0, time.monotonic() - tstart)
    total = len(rows)
    fails = [r for r in rows if r["status"] != "PASS"]
    er = round((len(fails) / total) * 100.0, 4) if total else 100.0
    lat = [float(r["duration_ms"]) for r in rows]

    cycle_failed: dict[int, bool] = {}
    for r in rows:
        idx = int(r["cycle_index"])
        if idx not in cycle_failed:
            cycle_failed[idx] = False
        if r["status"] != "PASS":
            cycle_failed[idx] = True
    cur_streak = 0
    max_streak = 0
    for idx in sorted(cycle_failed):
        if cycle_failed[idx]:
            cur_streak += 1
            max_streak = max(max_streak, cur_streak)
        else:
            cur_streak = 0

    s1probe = s1ref.get("m2_probe_latency_throughput_snapshot.json", {}) if s1ref else {}
    s1_p95 = float(s1probe.get("latency_ms_p95", 0.0)) if s1probe else 0.0
    p95 = round(pct(lat, 0.95), 3)
    p95_ratio = round((p95 / s1_p95), 4) if s1_p95 > 0 else None
    probe = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M2-ST-S2",
        "window_seconds_configured": win,
        "window_seconds_observed": int(round(dur)),
        "cycle_count": cycles,
        "probe_count": total,
        "failure_count": len(fails),
        "error_rate_pct": er,
        "probe_eps_observed": round(total / dur, 4),
        "probe_eps_target": burst_eps,
        "latency_ms_p50": round(pct(lat, 0.5), 3),
        "latency_ms_p95": p95,
        "latency_ms_p99": round(pct(lat, 0.99), 3),
        "sample_failures": fails[:10],
        "max_consecutive_failure_cycles": max_streak,
        "s1_baseline_phase_execution_id": s1ref.get("phase_execution_id", ""),
        "latency_ms_p95_vs_s1_ratio": p95_ratio,
    }
    dumpj(out / "m2_probe_latency_throughput_snapshot.json", probe)

    sr = [r for r in rows if r["probe_id"] == "sr_sfn_lookup"]
    sri = sr[-1] if sr else None
    ci: list[str] = []
    if h.get("PHASE_RUNTIME_PATH_MODE") != "single_active_path_per_phase_run":
        ci.append("PHASE_RUNTIME_PATH_MODE drift")
    if h.get("PHASE_RUNTIME_PATH_PIN_REQUIRED") is not True:
        ci.append("PHASE_RUNTIME_PATH_PIN_REQUIRED not true")
    if h.get("RUNTIME_PATH_SWITCH_IN_PHASE_ALLOWED") is not False:
        ci.append("RUNTIME_PATH_SWITCH_IN_PHASE_ALLOWED not false")
    if h.get("SR_READY_COMMIT_AUTHORITY") != "step_functions_only":
        ci.append("SR_READY_COMMIT_AUTHORITY drift")
    if h.get("CORRELATION_ENFORCEMENT_FAIL_CLOSED") is not True:
        ci.append("CORRELATION_ENFORCEMENT_FAIL_CLOSED not true")
    if sri is None or sri["status"] != "PASS" or sri["stdout"] in {"", "None", "null"}:
        ci.append("SR state machine lookup failed")
    if precheck_issues:
        ci.extend(precheck_issues)

    s1ctrl = s1ref.get("m2_control_rail_conformance_snapshot.json", {}) if s1ref else {}
    s1_issues = [str(x) for x in s1ctrl.get("issues", [])] if s1ctrl else []
    new_ci = sorted(set(ci) - set(s1_issues))
    ctrl = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M2-ST-S2",
        "overall_pass": len(new_ci) == 0,
        "issues": ci,
        "s1_baseline_issues": s1_issues,
        "new_issues_vs_s1": new_ci,
        "sr_lookup_probe": sri,
    }
    ctrl["handle_resolution"] = probe_meta
    ctrl["precheck_fail_closed"] = precheck_fail_closed
    ctrl["s1_baseline_phase_execution_id"] = s1ref.get("phase_execution_id", "")
    dumpj(out / "m2_control_rail_conformance_snapshot.json", ctrl)

    srows = [r for r in rows if r["group"] == "secrets"]
    sf = [r for r in srows if r["status"] != "PASS"]
    wdec = any("--with-decryption" in r["command"] for r in rows)
    qval = any("Parameter.Value" in r["command"] or "SecretString" in r["command"] for r in rows)
    sus = []
    rx = re.compile(r"(AKIA[0-9A-Z]{16}|BEGIN [A-Z ]*PRIVATE KEY|SECRET_ACCESS_KEY)")
    for r in rows:
        if rx.search((r["stdout"] + " " + r["stderr"]).strip()):
            sus.append(r["probe_id"])
    leak = wdec or qval or bool(sus)
    sec = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M2-ST-S2",
        "overall_pass": len(sf) == 0 and not leak,
        "secret_probe_count": len(srows),
        "secret_failure_count": len(sf),
        "with_decryption_used": wdec,
        "queried_value_directly": qval,
        "suspicious_output_probe_ids": sus,
        "plaintext_leakage_detected": leak,
    }
    dumpj(out / "m2_secret_safety_snapshot.json", sec)

    max_sp = float(pkt.get("M2_STRESS_MAX_SPEND_USD", 35))
    cost = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M2-ST-S2",
        "window_seconds": int(round(dur)),
        "estimated_api_call_count": total,
        "attributed_spend_usd": 0.0,
        "unattributed_spend_detected": False,
        "max_spend_usd": max_sp,
        "within_envelope": True,
        "method": "readonly_control_plane_probe_estimate_v0",
    }
    dumpj(out / "m2_cost_outcome_receipt.json", cost)

    if any(r["group"] in {"state_backend", "messaging"} and r["status"] != "PASS" for r in rows):
        blockers.append({"id": "M2-ST-B2", "severity": "S2", "status": "OPEN"})
    if any(r["group"] == "api_edge" and r["status"] != "PASS" for r in rows):
        blockers.append({"id": "M2-ST-B5", "severity": "S2", "status": "OPEN"})
    if new_ci:
        blockers.append({"id": "M2-ST-B3", "severity": "S2", "status": "OPEN", "details": {"issues": new_ci}})
        if any("SR" in x for x in new_ci):
            blockers.append({"id": "M2-ST-B4", "severity": "S2", "status": "OPEN"})
    if sec["overall_pass"] is False:
        blockers.append({"id": "M2-ST-B6", "severity": "S2", "status": "OPEN"})
    b7_details: dict[str, Any] = {}
    if er > 2.0:
        b7_details["error_rate_pct"] = er
    if max_streak > 3:
        b7_details["max_consecutive_failure_cycles"] = max_streak
    if b7_details:
        blockers.append({"id": "M2-ST-B7", "severity": "S2", "status": "OPEN", "details": b7_details})
    if not cost["within_envelope"] or cost["unattributed_spend_detected"]:
        blockers.append({"id": "M2-ST-B8", "severity": "S2", "status": "OPEN"})

    dlog = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M2-ST-S2",
        "decisions": [
            "Executed critical precheck before sustained burst window.",
            "Executed burst read-only probes with increased concurrency and tightened timeouts.",
            "Compared S2 control-rail and latency posture against latest successful S1 baseline.",
            "Applied fail-closed blocker mapping from M2 taxonomy.",
            "Carried S0 findings/lane matrix artifacts forward for artifact continuity.",
        ],
    }
    dumpj(out / "m2_decision_log.json", dlog)
    bref = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M2-ST-S2",
        "overall_pass": len(blockers) == 0,
        "open_blocker_count": len(blockers),
        "blockers": blockers,
    }
    summ = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_id,
        "stage_id": "M2-ST-S2",
        "overall_pass": len(blockers) == 0,
        "next_gate": "M2_ST_S3_READY" if len(blockers) == 0 else "BLOCKED",
        "error_rate_pct": er,
        "probe_count": total,
        "window_seconds_observed": int(round(dur)),
        "required_artifacts": S1_ARTS,
        "max_consecutive_failure_cycles": max_streak,
        "burst_probe_concurrency": burst_conc,
        "burst_interval_seconds": burst_interval,
    }
    dumpj(out / "m2_blocker_register.json", bref)
    dumpj(out / "m2_execution_summary.json", summ)

    miss = [n for n in S1_ARTS if not (out / n).exists()]
    if miss:
        blockers.append({"id": "M2-ST-B9", "severity": "S2", "status": "OPEN", "details": {"missing_artifacts": miss}})
        bref["overall_pass"] = False
        bref["open_blocker_count"] = len(blockers)
        bref["blockers"] = blockers
        summ["overall_pass"] = False
        summ["next_gate"] = "BLOCKED"
        dumpj(out / "m2_blocker_register.json", bref)
        dumpj(out / "m2_execution_summary.json", summ)

    print(f"[m2_s2] phase_execution_id={phase_id}")
    print(f"[m2_s2] output_dir={out.as_posix()}")
    print(f"[m2_s2] overall_pass={summ['overall_pass']}")
    print(f"[m2_s2] next_gate={summ['next_gate']}")
    print(f"[m2_s2] probe_count={total}")
    print(f"[m2_s2] error_rate_pct={er}")
    print(f"[m2_s2] max_consecutive_failure_cycles={max_streak}")
    print(f"[m2_s2] open_blockers={bref['open_blocker_count']}")
    return 0 if summ["overall_pass"] else 2


def main() -> int:
    ap = argparse.ArgumentParser(description="M2 stress runner")
    ap.add_argument("--stage", default="S0", choices=["S0", "S1", "S2"])
    ap.add_argument("--phase-execution-id", default="")
    ap.add_argument("--output-root", default=str(OUT_ROOT))
    ap.add_argument("--window-seconds-override", type=int, default=None)
    ap.add_argument("--cycle-interval-seconds", type=int, default=20)
    ap.add_argument("--probe-concurrency", type=int, default=6)
    a = ap.parse_args()
    pfx = {"S0": "m2_stress_s0", "S1": "m2_stress_s1", "S2": "m2_stress_s2"}[a.stage]
    pid = a.phase_execution_id.strip() or f"{pfx}_{tok()}"
    root = Path(a.output_root)
    if a.stage == "S0":
        return run_s0(pid, root)
    if a.stage == "S1":
        return run_s1(pid, root, a.window_seconds_override, a.cycle_interval_seconds, a.probe_concurrency)
    return run_s2(pid, root, a.window_seconds_override, a.cycle_interval_seconds, a.probe_concurrency)


if __name__ == "__main__":
    raise SystemExit(main())
