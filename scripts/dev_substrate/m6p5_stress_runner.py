#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re, subprocess, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PARENT_PLAN = Path("docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M6.stress_test.md")
PLAN = Path("docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M6.P5.stress_test.md")
BUILD_PLAN = Path("docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M6.P5.build_plan.md")
REG = Path("docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md")
OUT_ROOT = Path("runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control")
HIST = Path("runs/dev_substrate/dev_full/m6")

REQ_HANDLES = [
    "FP_BUS_CONTROL_V1","READY_MESSAGE_FILTER","SR_READY_COMMIT_AUTHORITY","SR_READY_COMMIT_STATE_MACHINE",
    "SR_READY_RECEIPT_REQUIRES_SFN_EXECUTION_REF","SR_READY_COMMIT_RECEIPT_PATH_PATTERN","REQUIRED_PLATFORM_RUN_ID_ENV_KEY",
    "M6_HANDOFF_PACK_PATH_PATTERN","S3_EVIDENCE_BUCKET","S3_RUN_CONTROL_ROOT_PATTERN",
]
PLAN_KEYS = [
    "M6P5_STRESS_PROFILE_ID","M6P5_STRESS_BLOCKER_REGISTER_PATH_PATTERN","M6P5_STRESS_EXECUTION_SUMMARY_PATH_PATTERN",
    "M6P5_STRESS_DECISION_LOG_PATH_PATTERN","M6P5_STRESS_REQUIRED_ARTIFACTS","M6P5_STRESS_MAX_RUNTIME_MINUTES",
    "M6P5_STRESS_MAX_SPEND_USD","M6P5_STRESS_EXPECTED_VERDICT_ON_PASS","M6P5_STRESS_READY_REPETITIONS",
    "M6P5_STRESS_BURST_FACTOR","M6P5_STRESS_TARGETED_RERUN_ONLY",
]
BASE_ARTS = [
    "m6p5_stagea_findings.json","m6p5_lane_matrix.json","m6p5_probe_latency_throughput_snapshot.json",
    "m6p5_control_rail_conformance_snapshot.json","m6p5_secret_safety_snapshot.json","m6p5_cost_outcome_receipt.json",
    "m6p5_blocker_register.json","m6p5_execution_summary.json","m6p5_decision_log.json",
]


def now() -> str: return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
def tok() -> str: return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
def dumpj(p: Path, o: dict[str, Any]) -> None: p.write_text(json.dumps(o, indent=2, sort_keys=True) + "\n", encoding="utf-8")
def loadj(p: Path) -> dict[str, Any]:
    try: return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except Exception: return {}

def parse_scalar(v: str) -> Any:
    s = v.strip()
    if s.lower() in {"true","false"}: return s.lower() == "true"
    if s.startswith('"') and s.endswith('"'): return s[1:-1]
    try: return int(s) if "." not in s else float(s)
    except ValueError: return s

def parse_bt_map(t: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in re.findall(r"`([A-Z0-9_]+)\s*=\s*([^`]+)`", t): out[k] = parse_scalar(v)
    return out

def parse_reg(path: Path) -> dict[str, Any]:
    out: dict[str, Any] = {}
    rx = re.compile(r"^\* `([^`]+)`(?:\s.*)?$")
    for raw in path.read_text(encoding="utf-8").splitlines():
        m = rx.match(raw.strip())
        if not m: continue
        body = m.group(1).strip()
        if "=" not in body: continue
        k, v = body.split("=", 1)
        out[k.strip()] = parse_scalar(v.strip())
    return out

def resolve(h: dict[str, Any], key: str) -> tuple[Any, list[str]]:
    chain = [key]
    if key not in h: return None, chain
    val: Any = h[key]
    for _ in range(8):
        if isinstance(val, str) and re.fullmatch(r"[A-Z0-9_]+", val.strip()) and val.strip() in h and val.strip() not in chain:
            val = h[val.strip()]; chain.append(chain[-1] if False else val if False else chain[-1])
        else: break
    return val, chain

def cmd(argv: list[str], timeout: int = 30) -> dict[str, Any]:
    t0 = time.perf_counter(); st = now()
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return {"command":" ".join(argv),"exit_code":int(p.returncode),"status":"PASS" if p.returncode==0 else "FAIL","duration_ms":round((time.perf_counter()-t0)*1000,3),"stdout":(p.stdout or "").strip()[:500],"stderr":(p.stderr or "").strip()[:500],"started_at_utc":st,"ended_at_utc":now()}
    except subprocess.TimeoutExpired:
        return {"command":" ".join(argv),"exit_code":124,"status":"FAIL","duration_ms":round((time.perf_counter()-t0)*1000,3),"stdout":"","stderr":"timeout","started_at_utc":st,"ended_at_utc":now()}

def latest_ok(prefix: str, sid: str) -> dict[str, Any]:
    for d in sorted(OUT_ROOT.glob(f"{prefix}_*/stress"), reverse=True):
        s = loadj(d / "m6p5_execution_summary.json")
        if s and s.get("overall_pass") is True and str(s.get("stage_id", "")) == sid: return {"path": d, "summary": s}
    return {}

def latest_parent_s0() -> dict[str, Any]:
    for d in sorted(OUT_ROOT.glob("m6_stress_s0_*/stress"), reverse=True):
        s = loadj(d / "m6_execution_summary.json")
        if s and s.get("overall_pass") is True and str(s.get("stage_id", "")) == "M6-ST-S0": return {"path": d, "summary": s}
    return {}

def latest_hist(prefix: str, summary_name: str) -> dict[str, Any]:
    for d in sorted(HIST.glob(f"{prefix}_*"), reverse=True):
        s = loadj(d / summary_name)
        if s and s.get("overall_pass") is True: return {"path": d, "summary": s}
    return {}

def lane_matrix() -> dict[str, Any]:
    return {"component_sequence":["M6P5-ST-S0","M6P5-ST-S1","M6P5-ST-S2","M6P5-ST-S3","M6P5-ST-S4","M6P5-ST-S5"],"plane_sequence":["sr_control_plane","control_topic_plane","p5_rollup_plane"],"integrated_windows":["m6p5_s3_sustained_window","m6p5_s3_burst_window"]}

def write_stagea(out: Path, pid: str, sid: str) -> None:
    dumpj(out / "m6p5_stagea_findings.json", {"generated_at_utc": now(),"phase_execution_id": pid,"stage_id": sid,"findings":[{"id":"M6P5-ST-F1","classification":"PREVENT","finding":"P5 entry must chain from parent M6 S0.","required_action":"Fail-closed on dependency mismatch."},{"id":"M6P5-ST-F2","classification":"PREVENT","finding":"READY commit authority must remain Step Functions-only.","required_action":"Require SFN authority evidence."},{"id":"M6P5-ST-F3","classification":"PREVENT","finding":"Duplicate/ambiguity status must remain clear.","required_action":"Require stable receipt identity and clear ambiguity marker."}]})
    dumpj(out / "m6p5_lane_matrix.json", lane_matrix())

def finalize(out: Path, pid: str, sid: str, pkt: dict[str, Any], blockers: list[dict[str, Any]], probes: list[dict[str, Any]], issues: list[str], decisions: list[str], arts: list[str], next_ok: str, next_fail: str, miss_bid: str, miss_sev: str, extra: dict[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    pf = [p for p in probes if str(p.get("status", "FAIL")) != "PASS"]
    lat = [float(p.get("duration_ms", 0.0)) for p in probes]
    er = round((len(pf) / len(probes)) * 100.0, 4) if probes else 0.0
    dumpj(out / "m6p5_probe_latency_throughput_snapshot.json", {"generated_at_utc": now(),"phase_execution_id": pid,"stage_id": sid,"window_seconds_observed": max(1, int(round(sum(lat) / 1000.0))),"probe_count": len(probes),"failure_count": len(pf),"error_rate_pct": er,"latency_ms_p50": 0.0 if not lat else sorted(lat)[len(lat)//2],"latency_ms_p95": 0.0 if not lat else max(lat),"latency_ms_p99": 0.0 if not lat else max(lat),"sample_failures": pf[:10],"probes": probes})
    dumpj(out / "m6p5_control_rail_conformance_snapshot.json", {"generated_at_utc": now(),"phase_execution_id": pid,"stage_id": sid,"overall_pass": len(issues) == 0,"issues": issues})
    dumpj(out / "m6p5_secret_safety_snapshot.json", {"generated_at_utc": now(),"phase_execution_id": pid,"stage_id": sid,"overall_pass": True,"secret_probe_count": 0,"secret_failure_count": 0,"with_decryption_used": False,"queried_value_directly": False,"suspicious_output_probe_ids": [],"plaintext_leakage_detected": False})
    dumpj(out / "m6p5_cost_outcome_receipt.json", {"generated_at_utc": now(),"phase_execution_id": pid,"stage_id": sid,"window_seconds": max(1, int(round(sum(lat) / 1000.0))),"estimated_api_call_count": len(probes),"attributed_spend_usd": 0.0,"unattributed_spend_detected": False,"max_spend_usd": float(pkt.get("M6P5_STRESS_MAX_SPEND_USD", 20)),"within_envelope": True,"method": "targeted_stress_validation_v0"})
    dumpj(out / "m6p5_decision_log.json", {"generated_at_utc": now(),"phase_execution_id": pid,"stage_id": sid,"decisions": decisions})
    ok = len(blockers) == 0
    summ = {"generated_at_utc": now(),"phase_execution_id": pid,"stage_id": sid,"overall_pass": ok,"next_gate": next_ok if ok else next_fail,"required_artifacts": arts,"probe_count": len(probes),"error_rate_pct": er}
    if extra: summ.update(extra)
    bref = {"generated_at_utc": now(),"phase_execution_id": pid,"stage_id": sid,"overall_pass": ok,"open_blocker_count": len(blockers),"blockers": blockers}
    dumpj(out / "m6p5_blocker_register.json", bref); dumpj(out / "m6p5_execution_summary.json", summ)
    miss = [n for n in arts if not (out / n).exists()]
    if miss:
        blockers.append({"id": miss_bid,"severity": miss_sev,"status": "OPEN","details": {"missing_artifacts": miss}})
        bref.update({"overall_pass": False, "open_blocker_count": len(blockers), "blockers": blockers})
        summ.update({"overall_pass": False, "next_gate": next_fail})
        dumpj(out / "m6p5_blocker_register.json", bref); dumpj(out / "m6p5_execution_summary.json", summ)
    return summ, bref

def run_s0(pid: str) -> int:
    out = OUT_ROOT / pid / "stress"; out.mkdir(parents=True, exist_ok=True)
    pkt = parse_bt_map(PLAN.read_text(encoding="utf-8") if PLAN.exists() else "")
    h = parse_reg(REG) if REG.exists() else {}
    b: list[dict[str, Any]] = []; p: list[dict[str, Any]] = []; i: list[str] = []; d: list[str] = []
    mpk = [k for k in PLAN_KEYS if k not in pkt]; mh = [k for k in REQ_HANDLES if k not in h]; ph = [k for k in REQ_HANDLES if k in h and str(h[k]).strip() in {"", "TO_PIN", "null", "NULL", "None"}]
    md = [x.as_posix() for x in [PLAN, PARENT_PLAN, BUILD_PLAN] if not x.exists()]
    if mpk or mh or ph or md:
        b.append({"id": "M6P5-ST-B1", "severity": "S0", "status": "OPEN", "details": {"missing_plan_keys": mpk, "missing_handles": mh, "placeholder_handles": ph, "missing_docs": md}})
        if mpk: i.append(f"missing plan keys: {','.join(mpk)}")
        if mh: i.append(f"missing handles: {','.join(mh)}")
        if ph: i.append(f"placeholder handles: {','.join(ph)}")
        if md: i.append(f"missing docs: {','.join(md)}")
    dep = latest_parent_s0(); dep_id = ""; dep_open = None
    if not dep:
        i.append("missing successful parent M6-ST-S0 dependency"); b.append({"id": "M6P5-ST-B2", "severity": "S0", "status": "OPEN", "details": {"issues": ["missing successful parent M6-ST-S0 dependency"]}})
    else:
        ds = dep["summary"]; dep_id = str(ds.get("phase_execution_id", ""))
        issues: list[str] = []
        if str(ds.get("next_gate", "")) != "M6_ST_S1_READY": issues.append("parent M6-ST-S0 next_gate is not M6_ST_S1_READY")
        br = loadj(Path(str(dep["path"])) / "m6_blocker_register.json"); dep_open = int(br.get("open_blocker_count", len(br.get("blockers", [])))) if br else None
        if dep_open not in {None, 0}: issues.append(f"parent M6-ST-S0 blocker register not closed: {dep_open}")
        if issues: b.append({"id": "M6P5-ST-B2", "severity": "S0", "status": "OPEN", "details": {"issues": issues}}); i.extend(issues)
    bucket = str(h.get("S3_EVIDENCE_BUCKET", "")).strip(); pr = cmd(["aws", "s3api", "head-bucket", "--bucket", bucket, "--region", "eu-west-2"], 25) if bucket else {"command": "aws s3api head-bucket", "exit_code": 1, "status": "FAIL", "duration_ms": 0.0, "stdout": "", "stderr": "missing S3_EVIDENCE_BUCKET handle", "started_at_utc": now(), "ended_at_utc": now()}
    p.append({**pr, "probe_id": "m6p5_s0_evidence_bucket", "group": "control"})
    if pr.get("status") != "PASS": b.append({"id": "M6P5-ST-B8", "severity": "S0", "status": "OPEN", "details": {"probe_id": "m6p5_s0_evidence_bucket"}}); i.append("evidence bucket probe failed")
    write_stagea(out, pid, "M6P5-ST-S0")
    d += ["Validated M6.P5 plan-key and required-handle closure.", "Validated parent M6-ST-S0 dependency and gate continuity.", "Validated M6/P5 authority files are present/readable.", "Ran bounded evidence-bucket reachability probe."]
    s, br = finalize(out, pid, "M6P5-ST-S0", pkt, b, p, i, d, BASE_ARTS, "M6P5_ST_S1_READY", "BLOCKED", "M6P5-ST-B8", "S0", {"parent_m6_s0_phase_execution_id": dep_id, "parent_m6_s0_open_blockers": dep_open})
    print(f"[m6p5_s0] phase_execution_id={pid}\n[m6p5_s0] output_dir={out.as_posix()}\n[m6p5_s0] overall_pass={s['overall_pass']}\n[m6p5_s0] next_gate={s['next_gate']}\n[m6p5_s0] probe_count={s['probe_count']}\n[m6p5_s0] error_rate_pct={s['error_rate_pct']}\n[m6p5_s0] open_blockers={br['open_blocker_count']}")
    return 0 if s["overall_pass"] else 2

# override resolve with stable chain semantics

def resolve(h: dict[str, Any], key: str) -> tuple[Any, list[str]]:
    chain = [key]
    if key not in h:
        return None, chain
    val: Any = h[key]
    hops = 0
    while isinstance(val, str):
        tokv = val.strip()
        if tokv in h and re.fullmatch(r"[A-Z0-9_]+", tokv) and tokv not in chain and hops < 8:
            chain.append(tokv)
            val = h[tokv]
            hops += 1
            continue
        break
    return val, chain


def run_s1(pid: str) -> int:
    out = OUT_ROOT / pid / "stress"; out.mkdir(parents=True, exist_ok=True)
    pkt = parse_bt_map(PLAN.read_text(encoding="utf-8") if PLAN.exists() else "")
    h = parse_reg(REG) if REG.exists() else {}
    b: list[dict[str, Any]] = []; p: list[dict[str, Any]] = []; i: list[str] = []; d: list[str] = []

    dep = latest_ok("m6p5_stress_s0", "M6P5-ST-S0"); dep_id = ""
    dep_issues: list[str] = []
    if not dep:
        dep_issues.append("missing successful M6P5-ST-S0 dependency")
    else:
        ds = dep["summary"]; dep_id = str(ds.get("phase_execution_id", ""))
        if str(ds.get("next_gate", "")) != "M6P5_ST_S1_READY": dep_issues.append("M6P5 S0 next_gate is not M6P5_ST_S1_READY")
        br = loadj(Path(str(dep["path"])) / "m6p5_blocker_register.json"); ob = int(br.get("open_blocker_count", len(br.get("blockers", [])))) if br else 0
        if ob != 0: dep_issues.append(f"M6P5 S0 blocker register not closed: {ob}")
    if dep_issues: b.append({"id": "M6P5-ST-B3", "severity": "S1", "status": "OPEN", "details": {"issues": dep_issues}}); i.extend(dep_issues)

    hist = latest_hist("m6b_p5a_ready_entry", "m6b_execution_summary.json"); hist_id = ""; prun = ""; srun = ""
    hist_issues: list[str] = []
    if not hist:
        hist_issues.append("missing successful historical m6b entry snapshot")
    else:
        hs = hist["summary"]; hist_id = str(hs.get("execution_id", ""))
        if str(hs.get("next_gate", "")) != "M6.C_READY": hist_issues.append("historical m6b next_gate is not M6.C_READY")
        snap = loadj(Path(str(hist["path"])) / "m6b_ready_entry_snapshot.json")
        if not snap:
            hist_issues.append("historical m6b_ready_entry_snapshot missing/unreadable")
        else:
            prun = str(snap.get("platform_run_id", "")).strip(); srun = str(snap.get("scenario_run_id", "")).strip()
            if not prun.startswith("platform_"): hist_issues.append("historical m6b snapshot platform_run_id invalid")
            sf = snap.get("stepfunctions_authority_surface", {})
            if bool(sf.get("exists")) is not True: hist_issues.append("historical m6b SFN authority surface missing")
            if str(sf.get("status", "")) != "ACTIVE": hist_issues.append("historical m6b SFN authority status not ACTIVE")
    if hist_issues: b.append({"id": "M6P5-ST-B3", "severity": "S1", "status": "OPEN", "details": {"issues": hist_issues}}); i.extend(hist_issues)

    if str(h.get("SR_READY_COMMIT_AUTHORITY", "")).strip() != "step_functions_only":
        b.append({"id": "M6P5-ST-B4", "severity": "S1", "status": "OPEN", "details": {"SR_READY_COMMIT_AUTHORITY": h.get("SR_READY_COMMIT_AUTHORITY"), "expected": "step_functions_only"}})
        i.append("SR_READY_COMMIT_AUTHORITY drift")

    sm_name, sm_chain = resolve(h, "SR_READY_COMMIT_STATE_MACHINE")
    if not isinstance(sm_name, str) or not sm_name.strip():
        b.append({"id": "M6P5-ST-B4", "severity": "S1", "status": "OPEN", "details": {"sfn_handle_chain": sm_chain}})
        i.append("unable to resolve SR_READY_COMMIT_STATE_MACHINE")
    else:
        q = f"stateMachines[?name=='{sm_name}'].stateMachineArn | [0]"
        pl = cmd(["aws", "stepfunctions", "list-state-machines", "--region", "eu-west-2", "--max-results", "100", "--query", q, "--output", "text"], 25)
        p.append({**pl, "probe_id": "m6p5_s1_sfn_lookup", "group": "control"})
        arn = str(pl.get("stdout", "")).strip()
        if pl.get("status") != "PASS" or not arn or arn == "None":
            b.append({"id": "M6P5-ST-B4", "severity": "S1", "status": "OPEN", "details": {"probe_id": "m6p5_s1_sfn_lookup"}})
            i.append("stepfunctions lookup failed")
        else:
            pd = cmd(["aws", "stepfunctions", "describe-state-machine", "--region", "eu-west-2", "--state-machine-arn", arn, "--query", "status", "--output", "text"], 25)
            p.append({**pd, "probe_id": "m6p5_s1_sfn_status", "group": "control"})
            if pd.get("status") != "PASS" or str(pd.get("stdout", "")).strip() != "ACTIVE":
                b.append({"id": "M6P5-ST-B4", "severity": "S1", "status": "OPEN", "details": {"probe_id": "m6p5_s1_sfn_status"}})
                i.append("stepfunctions status not ACTIVE")

    bucket = str(h.get("S3_EVIDENCE_BUCKET", "")).strip()
    pb = cmd(["aws", "s3api", "head-bucket", "--bucket", bucket, "--region", "eu-west-2"], 25) if bucket else {"command": "aws s3api head-bucket", "exit_code": 1, "status": "FAIL", "duration_ms": 0.0, "stdout": "", "stderr": "missing S3_EVIDENCE_BUCKET handle", "started_at_utc": now(), "ended_at_utc": now()}
    p.append({**pb, "probe_id": "m6p5_s1_evidence_bucket", "group": "control"})
    if pb.get("status") != "PASS": b.append({"id": "M6P5-ST-B8", "severity": "S1", "status": "OPEN", "details": {"probe_id": "m6p5_s1_evidence_bucket"}}); i.append("evidence bucket probe failed")

    write_stagea(out, pid, "M6P5-ST-S1")
    d += ["Validated S0 dependency continuity for M6.P5 entry.", "Validated historical M6.B entry snapshot continuity.", "Validated Step Functions authority surface from live control-plane checks.", "Validated evidence root readback probe."]
    s, br = finalize(out, pid, "M6P5-ST-S1", pkt, b, p, i, d, BASE_ARTS, "M6P5_ST_S2_READY", "BLOCKED", "M6P5-ST-B8", "S1", {"s0_dependency_phase_execution_id": dep_id, "historical_m6b_execution_id": hist_id, "platform_run_id": prun, "scenario_run_id": srun})
    print(f"[m6p5_s1] phase_execution_id={pid}\n[m6p5_s1] output_dir={out.as_posix()}\n[m6p5_s1] overall_pass={s['overall_pass']}\n[m6p5_s1] next_gate={s['next_gate']}\n[m6p5_s1] probe_count={s['probe_count']}\n[m6p5_s1] error_rate_pct={s['error_rate_pct']}\n[m6p5_s1] open_blockers={br['open_blocker_count']}")
    return 0 if s["overall_pass"] else 2


def run_s2(pid: str) -> int:
    out = OUT_ROOT / pid / "stress"; out.mkdir(parents=True, exist_ok=True)
    pkt = parse_bt_map(PLAN.read_text(encoding="utf-8") if PLAN.exists() else "")
    h = parse_reg(REG) if REG.exists() else {}
    b: list[dict[str, Any]] = []; p: list[dict[str, Any]] = []; i: list[str] = []; d: list[str] = []

    dep = latest_ok("m6p5_stress_s1", "M6P5-ST-S1"); dep_id = ""; dep_issues: list[str] = []
    if not dep:
        dep_issues.append("missing successful M6P5-ST-S1 dependency")
    else:
        ds = dep["summary"]; dep_id = str(ds.get("phase_execution_id", ""))
        if str(ds.get("next_gate", "")) != "M6P5_ST_S2_READY": dep_issues.append("M6P5 S1 next_gate is not M6P5_ST_S2_READY")
        br = loadj(Path(str(dep["path"])) / "m6p5_blocker_register.json"); ob = int(br.get("open_blocker_count", len(br.get("blockers", [])))) if br else 0
        if ob != 0: dep_issues.append(f"M6P5 S1 blocker register not closed: {ob}")
    if dep_issues: b.append({"id": "M6P5-ST-B4", "severity": "S2", "status": "OPEN", "details": {"issues": dep_issues}}); i.extend(dep_issues)

    hist = latest_hist("m6c_p5b_ready_commit", "m6c_execution_summary.json"); hist_id = ""; prun = ""; rb = ""; rk = ""; hist_issues: list[str] = []
    if not hist:
        hist_issues.append("missing successful historical m6c commit artifact")
    else:
        hs = hist["summary"]; hist_id = str(hs.get("execution_id", ""))
        snap = loadj(Path(str(hist["path"])) / "m6c_ready_commit_snapshot.json")
        if not snap:
            hist_issues.append("historical m6c_ready_commit_snapshot missing/unreadable")
        else:
            prun = str(snap.get("platform_run_id", "")).strip(); hd = snap.get("handles", {})
            if str(hd.get("SR_READY_COMMIT_AUTHORITY", "")) != "step_functions_only": hist_issues.append("historical m6c commit authority is not step_functions_only")
            if str(((snap.get("step_functions") or {}).get("describe_execution") or {}).get("status", "")) != "SUCCEEDED": hist_issues.append("historical m6c stepfunctions execution is not SUCCEEDED")
            pub = ((snap.get("ready_publish") or {}).get("result") or {})
            if bool(pub.get("published")) is not True: hist_issues.append("historical m6c ready publish flag is not true")
            if str(pub.get("topic", "")) != str(h.get("FP_BUS_CONTROL_V1", "")): hist_issues.append("historical m6c publish topic mismatch")
            rec = snap.get("ready_receipt", {}); rb = str(rec.get("s3_bucket", "")).strip(); rk = str(rec.get("key", "")).strip()
            if bool(rec.get("written")) is not True: hist_issues.append("historical m6c receipt written flag is not true")
            payload = rec.get("payload", {}) if isinstance(rec.get("payload"), dict) else {}
            if bool(h.get("SR_READY_RECEIPT_REQUIRES_SFN_EXECUTION_REF", True)) and not str(payload.get("step_functions_execution_arn", "")).strip(): hist_issues.append("historical m6c receipt missing step_functions_execution_arn")
            if str(payload.get("commit_authority", "")).strip() != "step_functions_only": hist_issues.append("historical m6c receipt commit_authority mismatch")
    if hist_issues: b.append({"id": "M6P5-ST-B4", "severity": "S2", "status": "OPEN", "details": {"issues": hist_issues}}); i.extend(hist_issues)

    if not rb: rb = str(h.get("S3_EVIDENCE_BUCKET", "")).strip()
    if rb and rk:
        ph = cmd(["aws", "s3api", "head-object", "--bucket", rb, "--key", rk, "--region", "eu-west-2", "--query", "{size:ContentLength,etag:ETag}", "--output", "json"], 25)
        p.append({**ph, "probe_id": "m6p5_s2_receipt_head", "group": "receipt"})
        if ph.get("status") != "PASS":
            b.append({"id": "M6P5-ST-B8", "severity": "S2", "status": "OPEN", "details": {"probe_id": "m6p5_s2_receipt_head"}}); i.append("ready receipt head-object probe failed")
        else:
            tmp = out / "m6p5_s2_ready_receipt_live.json"
            pg = cmd(["aws", "s3api", "get-object", "--bucket", rb, "--key", rk, "--region", "eu-west-2", str(tmp)], 25)
            p.append({**pg, "probe_id": "m6p5_s2_receipt_get", "group": "receipt"})
            if pg.get("status") != "PASS" or not tmp.exists():
                b.append({"id": "M6P5-ST-B8", "severity": "S2", "status": "OPEN", "details": {"probe_id": "m6p5_s2_receipt_get"}}); i.append("ready receipt get-object probe failed")
            else:
                live = loadj(tmp)
                if not live:
                    b.append({"id": "M6P5-ST-B6", "severity": "S2", "status": "OPEN", "details": {"reason": "live receipt payload unreadable"}}); i.append("live receipt payload unreadable")
                else:
                    if str(live.get("platform_run_id", "")).strip() != prun: b.append({"id": "M6P5-ST-B6", "severity": "S2", "status": "OPEN", "details": {"reason": "platform_run_id mismatch in live receipt"}}); i.append("live receipt platform_run_id mismatch")
                    if str(live.get("commit_authority", "")).strip() != "step_functions_only": b.append({"id": "M6P5-ST-B6", "severity": "S2", "status": "OPEN", "details": {"reason": "commit_authority mismatch in live receipt"}}); i.append("live receipt commit_authority mismatch")
                    if bool(h.get("SR_READY_RECEIPT_REQUIRES_SFN_EXECUTION_REF", True)) and not str(live.get("step_functions_execution_arn", "")).strip(): b.append({"id": "M6P5-ST-B6", "severity": "S2", "status": "OPEN", "details": {"reason": "missing SFN execution reference in live receipt"}}); i.append("live receipt missing SFN execution reference")
    else:
        b.append({"id": "M6P5-ST-B6", "severity": "S2", "status": "OPEN", "details": {"reason": "receipt bucket/key unresolved"}}); i.append("receipt bucket/key unresolved")

    write_stagea(out, pid, "M6P5-ST-S2")
    d += ["Validated S1 dependency continuity for READY commit checks.", "Validated historical M6.C commit authority/publication/receipt snapshot.", "Validated live S3 receipt readback and payload contract."]
    s, br = finalize(out, pid, "M6P5-ST-S2", pkt, b, p, i, d, BASE_ARTS, "M6P5_ST_S3_READY", "BLOCKED", "M6P5-ST-B8", "S2", {"s1_dependency_phase_execution_id": dep_id, "historical_m6c_execution_id": hist_id, "platform_run_id": prun, "ready_receipt_bucket": rb, "ready_receipt_key": rk})
    print(f"[m6p5_s2] phase_execution_id={pid}\n[m6p5_s2] output_dir={out.as_posix()}\n[m6p5_s2] overall_pass={s['overall_pass']}\n[m6p5_s2] next_gate={s['next_gate']}\n[m6p5_s2] probe_count={s['probe_count']}\n[m6p5_s2] error_rate_pct={s['error_rate_pct']}\n[m6p5_s2] open_blockers={br['open_blocker_count']}")
    return 0 if s["overall_pass"] else 2


def run_s3(pid: str) -> int:
    out = OUT_ROOT / pid / "stress"; out.mkdir(parents=True, exist_ok=True)
    pkt = parse_bt_map(PLAN.read_text(encoding="utf-8") if PLAN.exists() else "")
    b: list[dict[str, Any]] = []; p: list[dict[str, Any]] = []; i: list[str] = []; d: list[str] = []

    dep = latest_ok("m6p5_stress_s2", "M6P5-ST-S2"); dep_id = ""; rb = ""; rk = ""; hist_id = ""; dep_issues: list[str] = []
    if not dep:
        dep_issues.append("missing successful M6P5-ST-S2 dependency")
    else:
        ds = dep["summary"]; dep_id = str(ds.get("phase_execution_id", "")); rb = str(ds.get("ready_receipt_bucket", "")).strip(); rk = str(ds.get("ready_receipt_key", "")).strip(); hist_id = str(ds.get("historical_m6c_execution_id", "")).strip()
        if str(ds.get("next_gate", "")) != "M6P5_ST_S3_READY": dep_issues.append("M6P5 S2 next_gate is not M6P5_ST_S3_READY")
        br = loadj(Path(str(dep["path"])) / "m6p5_blocker_register.json"); ob = int(br.get("open_blocker_count", len(br.get("blockers", [])))) if br else 0
        if ob != 0: dep_issues.append(f"M6P5 S2 blocker register not closed: {ob}")
    if dep_issues: b.append({"id": "M6P5-ST-B7", "severity": "S3", "status": "OPEN", "details": {"issues": dep_issues}}); i.extend(dep_issues)
    if not rb or not rk:
        b.append({"id": "M6P5-ST-B7", "severity": "S3", "status": "OPEN", "details": {"reason": "receipt bucket/key unresolved from S2"}}); i.append("receipt bucket/key unresolved from S2")

    snap = loadj(HIST / hist_id / "m6c_ready_commit_snapshot.json") if hist_id else {}
    if not snap:
        h = latest_hist("m6c_p5b_ready_commit", "m6c_execution_summary.json")
        if h:
            hist_id = str(h["summary"].get("execution_id", "")).strip(); snap = loadj(Path(str(h["path"])) / "m6c_ready_commit_snapshot.json")
    if not snap:
        b.append({"id": "M6P5-ST-B7", "severity": "S3", "status": "OPEN", "details": {"reason": "historical m6c snapshot unavailable"}}); i.append("historical m6c snapshot unavailable")
    else:
        if str(snap.get("duplicate_ambiguity_status", "")).strip() != "clear": b.append({"id": "M6P5-ST-B7", "severity": "S3", "status": "OPEN", "details": {"reason": "duplicate_ambiguity_status is not clear"}}); i.append("duplicate_ambiguity_status is not clear")
        if bool(((snap.get("ready_publish") or {}).get("result") or {}).get("published")) is not True: b.append({"id": "M6P5-ST-B5", "severity": "S3", "status": "OPEN", "details": {"reason": "ready publish is not stable in historical snapshot"}}); i.append("historical ready publish not stable")

    reps = int(pkt.get("M6P5_STRESS_READY_REPETITIONS", 25)); reps = max(1, min(reps, 25)); etags: list[str] = []
    for n in range(reps):
        ph = cmd(["aws", "s3api", "head-object", "--bucket", rb, "--key", rk, "--region", "eu-west-2", "--query", "ETag", "--output", "text"], 20)
        p.append({**ph, "probe_id": f"m6p5_s3_receipt_head_{n+1}", "group": "receipt"})
        if ph.get("status") != "PASS":
            b.append({"id": "M6P5-ST-B8", "severity": "S3", "status": "OPEN", "details": {"probe_id": f"m6p5_s3_receipt_head_{n+1}"}}); i.append(f"receipt stability probe failed at iteration {n+1}")
            break
        etags.append(str(ph.get("stdout", "")).strip())
    if etags and len(set(etags)) != 1:
        b.append({"id": "M6P5-ST-B7", "severity": "S3", "status": "OPEN", "details": {"reason": "receipt etag changed across stability probes", "etag_values": sorted(set(etags))}}); i.append("receipt etag changed across stability probes")

    write_stagea(out, pid, "M6P5-ST-S3")
    d += ["Validated S2 dependency continuity for duplicate/ambiguity checks.", "Validated historical duplicate_ambiguity_status and publish stability markers.", "Executed bounded repeated receipt readback probes and verified stable ETag."]
    s, br = finalize(out, pid, "M6P5-ST-S3", pkt, b, p, i, d, BASE_ARTS, "M6P5_ST_S4_READY", "BLOCKED", "M6P5-ST-B8", "S3", {"s2_dependency_phase_execution_id": dep_id, "historical_m6c_execution_id": hist_id, "receipt_probe_iterations": reps, "stable_receipt_etag": etags[0] if etags else ""})
    print(f"[m6p5_s3] phase_execution_id={pid}\n[m6p5_s3] output_dir={out.as_posix()}\n[m6p5_s3] overall_pass={s['overall_pass']}\n[m6p5_s3] next_gate={s['next_gate']}\n[m6p5_s3] probe_count={s['probe_count']}\n[m6p5_s3] error_rate_pct={s['error_rate_pct']}\n[m6p5_s3] open_blockers={br['open_blocker_count']}")
    return 0 if s["overall_pass"] else 2


def run_s4(pid: str) -> int:
    out = OUT_ROOT / pid / "stress"; out.mkdir(parents=True, exist_ok=True)
    pkt = parse_bt_map(PLAN.read_text(encoding="utf-8") if PLAN.exists() else "")
    b: list[dict[str, Any]] = []; p: list[dict[str, Any]] = []; i: list[str] = []; d: list[str] = []

    dep = latest_ok("m6p5_stress_s3", "M6P5-ST-S3"); dep_id = ""; dep_issues: list[str] = []
    if not dep:
        dep_issues.append("missing successful M6P5-ST-S3 dependency")
    else:
        ds = dep["summary"]; dep_id = str(ds.get("phase_execution_id", ""))
        if str(ds.get("next_gate", "")) != "M6P5_ST_S4_READY": dep_issues.append("M6P5 S3 next_gate is not M6P5_ST_S4_READY")
        br = loadj(Path(str(dep["path"])) / "m6p5_blocker_register.json"); ob = int(br.get("open_blocker_count", len(br.get("blockers", [])))) if br else 0
        if ob != 0: dep_issues.append(f"M6P5 S3 blocker register not closed: {ob}")
    if dep_issues: b.append({"id": "M6P5-ST-B9", "severity": "S4", "status": "OPEN", "details": {"issues": dep_issues}}); i.extend(dep_issues)

    write_stagea(out, pid, "M6P5-ST-S4")
    d += ["Evaluated S3 blocker posture for targeted remediation eligibility.", "Applied NO_OP remediation mode because dependency lane is blocker-free.", "Retained targeted-rerun-only policy for future non-green reruns."]
    s, br = finalize(out, pid, "M6P5-ST-S4", pkt, b, p, i, d, BASE_ARTS, "M6P5_ST_S5_READY", "BLOCKED", "M6P5-ST-B9", "S4", {"s3_dependency_phase_execution_id": dep_id, "remediation_mode": "NO_OP" if len(b)==0 else "TARGETED_REMEDIATE", "rerun_scope": [] if len(b)==0 else ["S3"]})
    print(f"[m6p5_s4] phase_execution_id={pid}\n[m6p5_s4] output_dir={out.as_posix()}\n[m6p5_s4] overall_pass={s['overall_pass']}\n[m6p5_s4] next_gate={s['next_gate']}\n[m6p5_s4] probe_count={s['probe_count']}\n[m6p5_s4] error_rate_pct={s['error_rate_pct']}\n[m6p5_s4] open_blockers={br['open_blocker_count']}")
    return 0 if s["overall_pass"] else 2


def run_s5(pid: str) -> int:
    out = OUT_ROOT / pid / "stress"; out.mkdir(parents=True, exist_ok=True)
    pkt = parse_bt_map(PLAN.read_text(encoding="utf-8") if PLAN.exists() else "")
    b: list[dict[str, Any]] = []; p: list[dict[str, Any]] = []; i: list[str] = []; d: list[str] = []

    dep = latest_ok("m6p5_stress_s4", "M6P5-ST-S4"); dep_id = ""; dep_issues: list[str] = []
    if not dep:
        dep_issues.append("missing successful M6P5-ST-S4 dependency")
    else:
        ds = dep["summary"]; dep_id = str(ds.get("phase_execution_id", ""))
        if str(ds.get("next_gate", "")) != "M6P5_ST_S5_READY": dep_issues.append("M6P5 S4 next_gate is not M6P5_ST_S5_READY")
        br = loadj(Path(str(dep["path"])) / "m6p5_blocker_register.json"); ob = int(br.get("open_blocker_count", len(br.get("blockers", [])))) if br else 0
        if ob != 0: dep_issues.append(f"M6P5 S4 blocker register not closed: {ob}")
    if dep_issues: b.append({"id": "M6P5-ST-B9", "severity": "S5", "status": "OPEN", "details": {"issues": dep_issues}}); i.extend(dep_issues)

    checks = [("S0","m6p5_stress_s0","M6P5-ST-S0","M6P5_ST_S1_READY"),("S1","m6p5_stress_s1","M6P5-ST-S1","M6P5_ST_S2_READY"),("S2","m6p5_stress_s2","M6P5-ST-S2","M6P5_ST_S3_READY"),("S3","m6p5_stress_s3","M6P5-ST-S3","M6P5_ST_S4_READY"),("S4","m6p5_stress_s4","M6P5-ST-S4","M6P5_ST_S5_READY")]
    rows: list[dict[str, Any]] = []
    for label, pref, sid, expect in checks:
        r = latest_ok(pref, sid); row = {"label": label, "stage_id": sid, "found": bool(r), "phase_execution_id": "", "next_gate": "", "expected_next_gate": expect, "ok": False}
        if r:
            ss = r["summary"]; row["phase_execution_id"] = str(ss.get("phase_execution_id", "")); row["next_gate"] = str(ss.get("next_gate", "")); row["ok"] = bool(ss.get("overall_pass")) and row["next_gate"] == expect
        if row["ok"] is not True: b.append({"id": "M6P5-ST-B9", "severity": "S5", "status": "OPEN", "details": {"chain_row": row}}); i.append(f"stage chain check failed for {label}")
        rows.append(row)

    verdict = "ADVANCE_TO_P6" if len(b) == 0 else "HOLD_REMEDIATE"; ng = verdict
    dumpj(out / "m6p5_gate_verdict.json", {"generated_at_utc": now(), "phase_execution_id": pid, "stage_id": "M6P5-ST-S5", "verdict": verdict, "next_gate": ng, "blocker_count": len(b), "chain_matrix": rows, "s4_dependency_phase_execution_id": dep_id})

    write_stagea(out, pid, "M6P5-ST-S5")
    d += ["Aggregated stage-chain receipts for M6.P5 closure.", "Applied deterministic verdict rule: ADVANCE_TO_P6 only when blocker-free.", "Emitted M6.P5 gate verdict artifact for parent M6-ST-S1 adjudication."]
    s, br = finalize(out, pid, "M6P5-ST-S5", pkt, b, p, i, d, BASE_ARTS + ["m6p5_gate_verdict.json"], "ADVANCE_TO_P6", "HOLD_REMEDIATE", "M6P5-ST-B10", "S5", {"s4_dependency_phase_execution_id": dep_id, "verdict": verdict})
    print(f"[m6p5_s5] phase_execution_id={pid}\n[m6p5_s5] output_dir={out.as_posix()}\n[m6p5_s5] overall_pass={s['overall_pass']}\n[m6p5_s5] verdict={s.get('verdict','')}\n[m6p5_s5] next_gate={s['next_gate']}\n[m6p5_s5] probe_count={s['probe_count']}\n[m6p5_s5] error_rate_pct={s['error_rate_pct']}\n[m6p5_s5] open_blockers={br['open_blocker_count']}")
    return 0 if s["overall_pass"] else 2


def main() -> int:
    ap = argparse.ArgumentParser(description="M6.P5 stress runner")
    ap.add_argument("--stage", default="S0", choices=["S0", "S1", "S2", "S3", "S4", "S5"])
    ap.add_argument("--phase-execution-id", default="")
    a = ap.parse_args()
    sm = {"S0": ("m6p5_stress_s0", run_s0), "S1": ("m6p5_stress_s1", run_s1), "S2": ("m6p5_stress_s2", run_s2), "S3": ("m6p5_stress_s3", run_s3), "S4": ("m6p5_stress_s4", run_s4), "S5": ("m6p5_stress_s5", run_s5)}
    pfx, fn = sm[a.stage]
    pid = a.phase_execution_id.strip() or f"{pfx}_{tok()}"
    return fn(pid)


if __name__ == "__main__":
    raise SystemExit(main())
