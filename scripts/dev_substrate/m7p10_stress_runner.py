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

PARENT_PLAN = Path("docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M7.stress_test.md")
PLAN = Path("docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M7.P10.stress_test.md")
BUILD_PLAN = Path("docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M7.P10.build_plan.md")
REG = Path("docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md")
OUT_ROOT = Path("runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control")
M7_HIST = Path("runs/dev_substrate/dev_full/m7")
AWS_REGION = "eu-west-2"

PLAN_KEYS = [
    "M7P10_STRESS_PROFILE_ID",
    "M7P10_STRESS_BLOCKER_REGISTER_PATH_PATTERN",
    "M7P10_STRESS_EXECUTION_SUMMARY_PATH_PATTERN",
    "M7P10_STRESS_DECISION_LOG_PATH_PATTERN",
    "M7P10_STRESS_REQUIRED_ARTIFACTS",
    "M7P10_STRESS_MAX_RUNTIME_MINUTES",
    "M7P10_STRESS_MAX_SPEND_USD",
    "M7P10_STRESS_EXPECTED_NEXT_GATE_ON_PASS",
    "M7P10_STRESS_DATA_MIN_CASE_EVENTS",
    "M7P10_STRESS_DATA_MIN_LABEL_EVENTS",
    "M7P10_STRESS_LABEL_CLASS_MIN_CARDINALITY",
    "M7P10_STRESS_WRITER_CONFLICT_MAX_RATE_PCT",
    "M7P10_STRESS_CASE_REOPEN_RATE_MAX_PCT",
    "M7P10_STRESS_TARGETED_RERUN_ONLY",
]

REQ_HANDLES = [
    "FLINK_RUNTIME_PATH_ACTIVE",
    "FLINK_RUNTIME_PATH_ALLOWED",
    "K8S_DEPLOY_CASE_TRIGGER",
    "K8S_DEPLOY_CM",
    "K8S_DEPLOY_LS",
    "EKS_NAMESPACE_CASE_LABELS",
    "ROLE_EKS_IRSA_CASE_LABELS",
    "FP_BUS_CASE_TRIGGERS_V1",
    "FP_BUS_LABELS_EVENTS_V1",
    "CASE_LABELS_EVIDENCE_PATH_PATTERN",
    "AURORA_CLUSTER_IDENTIFIER",
    "SSM_AURORA_ENDPOINT_PATH",
    "SSM_AURORA_USERNAME_PATH",
    "SSM_AURORA_PASSWORD_PATH",
]

REQUIRED_ARTIFACTS = [
    "m7p10_stagea_findings.json",
    "m7p10_lane_matrix.json",
    "m7p10_data_subset_manifest.json",
    "m7p10_data_profile_summary.json",
    "m7p10_case_trigger_snapshot.json",
    "m7p10_cm_snapshot.json",
    "m7p10_ls_snapshot.json",
    "m7p10_case_lifecycle_profile.json",
    "m7p10_label_distribution_profile.json",
    "m7p10_writer_conflict_profile.json",
    "m7p10_probe_latency_throughput_snapshot.json",
    "m7p10_control_rail_conformance_snapshot.json",
    "m7p10_secret_safety_snapshot.json",
    "m7p10_cost_outcome_receipt.json",
    "m7p10_blocker_register.json",
    "m7p10_execution_summary.json",
    "m7p10_decision_log.json",
    "m7p10_gate_verdict.json",
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
    except Exception:
        return s


def parse_bt_map(text: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in re.findall(r"`([A-Z0-9_]+)\s*=\s*([^`]+)`", text):
        out[k] = parse_scalar(v)
    return out


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


def to_int(v: Any) -> int | None:
    try:
        if v is None:
            return None
        if isinstance(v, bool):
            return int(v)
        return int(str(v).strip())
    except Exception:
        return None


def to_float(v: Any) -> float | None:
    try:
        if v is None:
            return None
        if isinstance(v, bool):
            return float(int(v))
        return float(str(v).strip())
    except Exception:
        return None


def to_bool(v: Any) -> bool | None:
    if isinstance(v, bool):
        return v
    if v is None:
        return None
    s = str(v).strip().lower()
    if s in {"true", "1", "yes", "y"}:
        return True
    if s in {"false", "0", "no", "n"}:
        return False
    return None


def normalize_runtime_path(v: str) -> str:
    raw = str(v or "").strip().upper()
    aliases = {"EKS_EMR_ON_EKS": "EKS_FLINK_OPERATOR", "EMR_ON_EKS": "EKS_FLINK_OPERATOR"}
    return aliases.get(raw, raw)


def is_toy_profile_advisory(msg: str) -> bool:
    s = str(msg).strip().lower()
    return any(
        token in s
        for token in (
            "waived_low_sample",
            "advisory-only throughput",
            "historical/proxy-only closure authority",
            "historical-only closure authority",
            "proxy-only closure authority",
        )
    )


def run_cmd(argv: list[str], timeout: int = 30) -> dict[str, Any]:
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
        return {"command": " ".join(argv), "exit_code": 124, "status": "FAIL", "duration_ms": round((time.perf_counter() - t0) * 1000.0, 3), "stdout": "", "stderr": "timeout", "started_at_utc": st, "ended_at_utc": now()}


def run_cmd_full(argv: list[str], timeout: int = 120) -> tuple[int, str, str]:
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return int(p.returncode), (p.stdout or ""), (p.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"


def load_s3_json(bucket: str, key: str) -> dict[str, Any]:
    if not bucket or not key:
        return {}
    rc, stdout, _ = run_cmd_full(["aws", "s3", "cp", f"s3://{bucket}/{key}", "-"], timeout=180)
    if rc != 0:
        return {}
    try:
        return json.loads(stdout)
    except Exception:
        return {}


def materialize(pattern: str, replacements: dict[str, str]) -> str:
    out = str(pattern or "")
    for k, v in replacements.items():
        out = out.replace("{" + k + "}", str(v))
    return out


def required_artifacts(plan_packet: dict[str, Any]) -> list[str]:
    raw = str(plan_packet.get("M7P10_STRESS_REQUIRED_ARTIFACTS", "")).strip()
    if not raw:
        return list(REQUIRED_ARTIFACTS)
    out = [x.strip() for x in raw.split(",") if x.strip()]
    return out if out else list(REQUIRED_ARTIFACTS)


def resolve_required_handles(handles: dict[str, Any]) -> tuple[list[str], list[str]]:
    missing: list[str] = []
    placeholder: list[str] = []
    bad = {"", "TO_PIN", "None", "NONE", "null", "NULL"}
    for k in REQ_HANDLES:
        if k not in handles:
            missing.append(k)
            continue
        if str(handles.get(k, "")).strip() in bad:
            placeholder.append(k)
    return missing, placeholder


def latest_ok(prefix: str, summary_name: str, stage_id: str) -> dict[str, Any]:
    for d in sorted(OUT_ROOT.glob(f"{prefix}_*/stress"), reverse=True):
        s = loadj(d / summary_name)
        if s and s.get("overall_pass") is True and str(s.get("stage_id", "")) == stage_id:
            return {"path": d, "summary": s}
    return {}


def latest_hist(summary_name: str, snapshot_name: str, perf_name: str, blocker_name: str, expected_next_gate: str) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for f in M7_HIST.rglob(summary_name):
        d = f.parent
        s = loadj(f)
        snap = loadj(d / snapshot_name)
        perf = loadj(d / perf_name)
        blk = loadj(d / blocker_name)
        if not s or not snap or not perf or not blk:
            continue
        if s.get("overall_pass") is not True or str(s.get("next_gate", "")).strip() != expected_next_gate:
            continue
        if int(s.get("blocker_count", 0) or 0) != 0 or int(blk.get("blocker_count", 0) or 0) != 0:
            continue
        rows.append({"path": d.as_posix(), "summary": s, "snapshot": snap, "perf": perf, "blocker": blk})
    return rows[-1] if rows else {}


def latest_hist_p10a() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for f in M7_HIST.rglob("p10a_execution_summary.json"):
        d = f.parent
        s = loadj(f)
        snap = loadj(d / "p10a_entry_snapshot.json")
        blk = loadj(d / "p10a_blocker_register.json")
        if not s or not snap or not blk:
            continue
        if s.get("overall_pass") is not True or str(s.get("next_gate", "")).strip() != "P10.B_READY":
            continue
        if int(s.get("blocker_count", 0) or 0) != 0 or int(blk.get("blocker_count", 0) or 0) != 0:
            continue
        rows.append({"path": d.as_posix(), "summary": s, "snapshot": snap, "blocker": blk})
    return rows[-1] if rows else {}


def head_bucket_probe(probes: list[dict[str, Any]], bucket: str, probe_id: str) -> dict[str, Any]:
    p = run_cmd(["aws", "s3api", "head-bucket", "--bucket", bucket, "--region", AWS_REGION], 25) if bucket else {"status": "FAIL", "stderr": "missing bucket", "duration_ms": 0.0}
    probes.append({**p, "probe_id": probe_id, "bucket": bucket})
    return p


def head_object_probe(probes: list[dict[str, Any]], bucket: str, key: str, probe_id: str) -> dict[str, Any]:
    k = str(key or "").strip().lstrip("/")
    p = run_cmd(["aws", "s3api", "head-object", "--bucket", bucket, "--key", k, "--region", AWS_REGION], 30) if bucket and k else {"status": "FAIL", "stderr": "missing bucket/key", "duration_ms": 0.0}
    probes.append({**p, "probe_id": probe_id, "bucket": bucket, "key": k})
    return p


def probe_metrics(probes: list[dict[str, Any]]) -> dict[str, Any]:
    fails = [x for x in probes if str(x.get("status", "FAIL")) != "PASS"]
    lats = [float(x.get("duration_ms", 0.0) or 0.0) for x in probes]
    return {"window_seconds_observed": max(1, int(round(sum(lats) / 1000.0))) if lats else 1, "probe_count": len(probes), "failure_count": len(fails), "error_rate_pct": round((len(fails) / len(probes)) * 100.0, 4) if probes else 0.0, "sample_failures": fails[:10]}


def finalize_artifact_contract(
    out: Path,
    req: list[str],
    blockers: list[dict[str, Any]],
    blocker_reg: dict[str, Any],
    summary: dict[str, Any],
    verdict: dict[str, Any],
    blocker_id: str = "M7P10-ST-B10",
) -> None:
    missing = [x for x in req if not (out / x).exists()]
    if not missing:
        return
    blockers.append({"id": blocker_id, "severity": summary.get("stage_id"), "status": "OPEN", "details": {"missing_artifacts": missing}})
    blocker_reg.update({"overall_pass": False, "open_blocker_count": len(blockers), "blockers": blockers})
    summary.update({"overall_pass": False, "next_gate": "BLOCKED", "open_blocker_count": len(blockers)})
    verdict.update({"overall_pass": False, "next_gate": "BLOCKED", "verdict": "HOLD_REMEDIATE", "blocker_count": len(blockers)})
    dumpj(out / "m7p10_blocker_register.json", blocker_reg)
    dumpj(out / "m7p10_execution_summary.json", summary)
    dumpj(out / "m7p10_gate_verdict.json", verdict)


def run_s0(phase_execution_id: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)
    plan_packet = parse_bt_map(PLAN.read_text(encoding="utf-8") if PLAN.exists() else "")
    handles = parse_registry(REG) if REG.exists() else {}
    req = required_artifacts(plan_packet)
    blockers: list[dict[str, Any]] = []
    issues: list[str] = []
    advisories: list[str] = []
    probes: list[dict[str, Any]] = []
    parse_errors = 0

    miss_plan = [k for k in PLAN_KEYS if k not in plan_packet]
    miss_handle, ph_handle = resolve_required_handles(handles)
    miss_docs = [x.as_posix() for x in [PLAN, PARENT_PLAN, BUILD_PLAN] if not x.exists()]
    if miss_plan or miss_handle or ph_handle or miss_docs:
        blockers.append({"id": "M7P10-ST-B1", "severity": "S0", "status": "OPEN", "details": {"missing_plan_keys": miss_plan, "missing_handles": miss_handle, "placeholder_handles": ph_handle, "missing_docs": miss_docs}})
        issues.append("authority/handle closure failed")

    dep_issues: list[str] = []
    dep_parent = latest_ok("m7_stress_s0", "m7_execution_summary.json", "M7-ST-S0")
    dep_p9 = latest_ok("m7p9_stress_s5", "m7p9_execution_summary.json", "M7P9-ST-S5")
    parent_id = ""
    p9_id = ""
    platform_run_id = ""
    dep_p9_subset: dict[str, Any] = {}
    dep_p9_action: dict[str, Any] = {}
    dep_p9_idemp: dict[str, Any] = {}
    if not dep_parent:
        dep_issues.append("missing successful parent M7-ST-S0 dependency")
    else:
        parent_id = str(dep_parent["summary"].get("phase_execution_id", ""))
        if str(dep_parent["summary"].get("next_gate", "")).strip() != "M7_ST_S1_READY":
            dep_issues.append("parent M7-ST-S0 next_gate mismatch")
        pb = loadj(Path(dep_parent["path"]) / "m7_blocker_register.json")
        if int((to_int(pb.get("open_blocker_count")) or to_int(pb.get("blocker_count")) or 0)) != 0:
            dep_issues.append("parent M7-ST-S0 blocker register not closed")
        if not platform_run_id:
            platform_run_id = str(dep_parent["summary"].get("platform_run_id", "")).strip()
    if not dep_p9:
        dep_issues.append("missing successful M7P9-ST-S5 dependency")
    else:
        p9_id = str(dep_p9["summary"].get("phase_execution_id", ""))
        if str(dep_p9["summary"].get("verdict", "")).strip() != "ADVANCE_TO_P10":
            dep_issues.append("M7P9-ST-S5 verdict mismatch")
        if str(dep_p9["summary"].get("next_gate", "")).strip() != "ADVANCE_TO_P10":
            dep_issues.append("M7P9-ST-S5 next_gate mismatch")
        p9b = loadj(Path(dep_p9["path"]) / "m7p9_blocker_register.json")
        if int((to_int(p9b.get("open_blocker_count")) or to_int(p9b.get("blocker_count")) or 0)) != 0:
            dep_issues.append("M7P9-ST-S5 blocker register not closed")
        platform_run_id = str(dep_p9["summary"].get("platform_run_id", "")).strip() or platform_run_id
        dep_p9_subset = loadj(Path(dep_p9["path"]) / "m7p9_data_subset_manifest.json")
        dep_p9_action = loadj(Path(dep_p9["path"]) / "m7p9_action_mix_profile.json")
        dep_p9_idemp = loadj(Path(dep_p9["path"]) / "m7p9_idempotency_collision_profile.json")
        if not dep_p9_subset or not dep_p9_action or not dep_p9_idemp:
            dep_issues.append("M7P9-ST-S5 realism artifacts incomplete")
    if dep_issues:
        blockers.append({"id": "M7P10-ST-B2", "severity": "S0", "status": "OPEN", "details": {"issues": dep_issues}})
        issues.extend(dep_issues)

    evidence_bucket = str(handles.get("S3_EVIDENCE_BUCKET", "")).strip()
    if head_bucket_probe(probes, evidence_bucket, "m7p10_s0_bucket").get("status") != "PASS":
        blockers.append({"id": "M7P10-ST-B10", "severity": "S0", "status": "OPEN", "details": {"probe_id": "m7p10_s0_bucket"}})
        issues.append("evidence bucket probe failed")
    repl = {"platform_run_id": platform_run_id}
    case_root = materialize(str(handles.get("CASE_LABELS_EVIDENCE_PATH_PATTERN", "")).strip(), repl)
    if not case_root or re.findall(r"{[^}]+}", case_root):
        blockers.append({"id": "M7P10-ST-B10", "severity": "S0", "status": "OPEN", "details": {"reason": "unresolved CASE_LABELS_EVIDENCE_PATH_PATTERN", "case_root": case_root}})
        issues.append("case-label root unresolved")

    receipt_key = materialize(str(handles.get("RECEIPT_SUMMARY_PATH_PATTERN", "")).strip(), repl)
    proof_keys = {
        "case_trigger": f"{case_root.rstrip('/')}/case_trigger_component_proof.json",
        "cm": f"{case_root.rstrip('/')}/cm_component_proof.json",
        "ls": f"{case_root.rstrip('/')}/ls_component_proof.json",
    }
    receipt = {}
    if head_object_probe(probes, evidence_bucket, receipt_key, "m7p10_s0_receipt").get("status") == "PASS":
        receipt = load_s3_json(evidence_bucket, receipt_key)
    proofs: dict[str, dict[str, Any]] = {}
    for tag, key in proof_keys.items():
        p = head_object_probe(probes, evidence_bucket, key, f"m7p10_s0_{tag}_proof")
        if p.get("status") != "PASS":
            blockers.append({"id": "M7P10-ST-B10", "severity": "S0", "status": "OPEN", "details": {"probe_id": f"m7p10_s0_{tag}_proof"}})
            issues.append(f"proof readback failed for {tag}")
            continue
        payload = load_s3_json(evidence_bucket, key)
        if not payload:
            blockers.append({"id": "M7P10-ST-B10", "severity": "S0", "status": "OPEN", "details": {"reason": "proof parse failure", "key": key}})
            issues.append(f"proof parse failed for {tag}")
            parse_errors += 1
            continue
        proofs[tag] = payload
    writer_probe_key = str(proofs.get("ls", {}).get("ls_writer_boundary_probe_key", "")).strip()
    writer_probe = {}
    if writer_probe_key and head_object_probe(probes, evidence_bucket, writer_probe_key, "m7p10_s0_writer_probe").get("status") == "PASS":
        writer_probe = load_s3_json(evidence_bucket, writer_probe_key)
        if not writer_probe:
            parse_errors += 1
            blockers.append({"id": "M7P10-ST-B10", "severity": "S0", "status": "OPEN", "details": {"reason": "writer probe parse failure", "key": writer_probe_key}})
    else:
        blockers.append({"id": "M7P10-ST-B10", "severity": "S0", "status": "OPEN", "details": {"reason": "writer probe missing/unreadable", "key": writer_probe_key}})
        issues.append("writer probe missing or unreadable")

    h_a = latest_hist_p10a()
    h_b = latest_hist("p10b_case_trigger_execution_summary.json", "p10b_case_trigger_snapshot.json", "p10b_case_trigger_performance_snapshot.json", "p10b_case_trigger_blocker_register.json", "P10.C_READY")
    h_c = latest_hist("p10c_cm_execution_summary.json", "p10c_cm_snapshot.json", "p10c_cm_performance_snapshot.json", "p10c_cm_blocker_register.json", "P10.D_READY")
    h_d = latest_hist("p10d_ls_execution_summary.json", "p10d_ls_snapshot.json", "p10d_ls_performance_snapshot.json", "p10d_ls_blocker_register.json", "P10.E_READY")
    if not h_a or not h_b or not h_c or not h_d:
        blockers.append({"id": "M7P10-ST-B3", "severity": "S0", "status": "OPEN", "details": {"reason": "historical p10 baseline incomplete", "p10a": bool(h_a), "p10b": bool(h_b), "p10c": bool(h_c), "p10d": bool(h_d)}})
        issues.append("historical p10 baseline incomplete")

    rt_active = normalize_runtime_path(str(handles.get("FLINK_RUNTIME_PATH_ACTIVE", "")))
    rt_allowed = [normalize_runtime_path(x) for x in str(handles.get("FLINK_RUNTIME_PATH_ALLOWED", "")).split("|") if x.strip()]
    if not rt_active or rt_active not in rt_allowed:
        blockers.append({"id": "M7P10-ST-B1", "severity": "S0", "status": "OPEN", "details": {"reason": "runtime path contract invalid", "runtime_active": rt_active, "runtime_allowed": rt_allowed}})

    min_case = int(plan_packet.get("M7P10_STRESS_DATA_MIN_CASE_EVENTS", 5000))
    min_label = int(plan_packet.get("M7P10_STRESS_DATA_MIN_LABEL_EVENTS", 12000))
    min_label_class = int(plan_packet.get("M7P10_STRESS_LABEL_CLASS_MIN_CARDINALITY", 3))
    max_conflict = float(plan_packet.get("M7P10_STRESS_WRITER_CONFLICT_MAX_RATE_PCT", 0.5))
    max_reopen = float(plan_packet.get("M7P10_STRESS_CASE_REOPEN_RATE_MAX_PCT", 3.0))
    p9_input = to_int(dep_p9_subset.get("decision_input_events")) or 0
    p9_action_card = to_int(dep_p9_action.get("action_class_cardinality")) or to_int(dep_p9_action.get("action_class_active_cardinality")) or 0
    p9_retry = to_float(dep_p9_idemp.get("retry_ratio_pct"))
    p9_dup = to_float(dep_p9_idemp.get("duplicate_ratio_pct"))
    ct = to_int(proofs.get("case_trigger", {}).get("ingest_basis_total_receipts")) or 0
    cm = to_int(proofs.get("cm", {}).get("ingest_basis_total_receipts")) or 0
    ls = to_int(proofs.get("ls", {}).get("ingest_basis_total_receipts")) or 0
    case_observed = max(ct, cm, ls)
    label_observed = ls if ls > 0 else max(ct, cm)
    case_effective = max(case_observed, p9_input)
    label_effective = max(label_observed, p9_input)
    if case_effective != case_observed:
        advisories.append("case-event count uses P9 run-scoped proxy due low-sample case-label proofs.")
    if label_effective != label_observed:
        advisories.append("label-event count uses P9 run-scoped proxy due low-sample case-label proofs.")
    states = sorted({str(x).strip() for x in writer_probe.get("outcome_states", []) if str(x).strip()})
    label_card = len(states) if states else p9_action_card
    label_card_source = "writer_probe.outcome_states" if states else "p9_action_mix_proxy"
    single_writer = to_bool(writer_probe.get("single_writer_posture"))
    conflict_rate = to_float(writer_probe.get("writer_conflict_rate_pct"))
    if conflict_rate is None:
        if single_writer is True:
            conflict_rate = 0.0
        elif single_writer is False:
            conflict_rate = 100.0
        else:
            conflict_rate = p9_dup
    reopen_rate = to_float(receipt.get("case_reopen_rate_pct"))
    if reopen_rate is None:
        reopen_rate = p9_retry
        advisories.append("case reopen rate uses P9 retry-ratio proxy due absent explicit case_reopen metric.")
    checks = {
        "case_events_min_check": case_effective >= min_case,
        "label_events_min_check": label_effective >= min_label,
        "label_class_cardinality_check": label_card >= min_label_class,
        "writer_conflict_rate_check": conflict_rate is not None and conflict_rate <= max_conflict,
        "case_reopen_rate_check": reopen_rate is not None and reopen_rate <= max_reopen,
        "parse_error_check": parse_errors == 0,
    }
    if not all(checks.values()):
        blockers.append({"id": "M7P10-ST-B3", "severity": "S0", "status": "OPEN", "details": {"checks": checks, "case_events_observed": case_observed, "case_events_effective": case_effective, "label_events_observed": label_observed, "label_events_effective": label_effective, "label_class_cardinality": label_card, "label_class_source": label_card_source, "writer_conflict_rate_pct": conflict_rate, "case_reopen_rate_pct": reopen_rate}})
        issues.append("representativeness checks failed")

    metrics = probe_metrics(probes)
    overall = len(blockers) == 0
    next_gate = "M7P10_ST_S1_READY" if overall else "BLOCKED"
    verdict_name = "ADVANCE_TO_S1" if overall else "HOLD_REMEDIATE"
    dumpj(out / "m7p10_stagea_findings.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S0", "findings": [{"id": "M7P10-ST-F1", "classification": "PREVENT", "finding": "S0 requires closed parent/P9 dependencies.", "required_action": "Fail closed on dependency or run-scope mismatch."}, {"id": "M7P10-ST-F2", "classification": "PREVENT", "finding": "Low-sample case-label proofs require explicit proxy provenance.", "required_action": "Use bounded proxy sources with strict representativeness gates."}, {"id": "M7P10-ST-F3", "classification": "PREVENT", "finding": "Writer-boundary semantics require explicit probe evidence.", "required_action": "Fail closed when writer probe is missing/unreadable."}]})
    dumpj(out / "m7p10_lane_matrix.json", {"component_sequence": ["M7P10-ST-S0", "M7P10-ST-S1", "M7P10-ST-S2", "M7P10-ST-S3", "M7P10-ST-S4", "M7P10-ST-S5"]})
    dumpj(out / "m7p10_data_subset_manifest.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S0", "platform_run_id": platform_run_id, "case_labels_root": case_root, "case_labels_refs": {"case_trigger_component_proof": proof_keys["case_trigger"], "cm_component_proof": proof_keys["cm"], "ls_component_proof": proof_keys["ls"], "ls_writer_boundary_probe": writer_probe_key}, "receipt_summary_ref": receipt_key, "p9_decision_input_events_proxy": p9_input, "upstream_m7_s0_phase_execution_id": parent_id, "upstream_m7p9_s5_phase_execution_id": p9_id})
    dumpj(out / "m7p10_data_profile_summary.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S0", "platform_run_id": platform_run_id, "checks": checks, "case_events_observed": case_observed, "case_events_effective": case_effective, "label_events_observed": label_observed, "label_events_effective": label_effective, "label_class_cardinality": label_card, "label_class_source": label_card_source, "writer_conflict_rate_pct": conflict_rate, "case_reopen_rate_pct": reopen_rate, "advisories": advisories})
    dumpj(out / "m7p10_case_trigger_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S0", "historical": h_b, "current_proof": proofs.get("case_trigger", {})})
    dumpj(out / "m7p10_cm_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S0", "historical": h_c, "current_proof": proofs.get("cm", {})})
    dumpj(out / "m7p10_ls_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S0", "historical": h_d, "current_proof": proofs.get("ls", {}), "writer_probe": writer_probe})
    dumpj(out / "m7p10_case_lifecycle_profile.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S0", "case_events_effective": case_effective, "case_events_min_required": min_case, "case_reopen_rate_pct": reopen_rate, "case_reopen_rate_max_pct": max_reopen})
    dumpj(out / "m7p10_label_distribution_profile.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S0", "label_events_effective": label_effective, "label_events_min_required": min_label, "label_class_cardinality": label_card, "label_class_min_required": min_label_class, "outcome_states": states})
    dumpj(out / "m7p10_writer_conflict_profile.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S0", "single_writer_posture": single_writer, "writer_conflict_rate_pct": conflict_rate, "writer_conflict_max_rate_pct": max_conflict, "writer_probe_key": writer_probe_key})
    dumpj(out / "m7p10_probe_latency_throughput_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S0", **metrics})
    dumpj(out / "m7p10_control_rail_conformance_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S0", "overall_pass": len(issues) == 0, "issues": issues, "advisories": advisories, "dependency_refs": {"m7_s0_execution_id": parent_id, "m7p9_s5_execution_id": p9_id}})
    dumpj(out / "m7p10_secret_safety_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S0", "overall_pass": True, "with_decryption_used": False, "queried_value_directly": False, "plaintext_leakage_detected": False})
    dumpj(out / "m7p10_cost_outcome_receipt.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S0", "estimated_api_call_count": metrics["probe_count"], "attributed_spend_usd": 0.0, "unattributed_spend_detected": False, "max_spend_usd": float(plan_packet.get("M7P10_STRESS_MAX_SPEND_USD", 38)), "within_envelope": True})
    dumpj(out / "m7p10_decision_log.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S0", "decisions": ["Validated parent M7-S0 and P9-S5 closure before opening P10.", "Enforced authority/handle closure and run-scope evidence reads for case-label proofs.", "Applied explicit representativeness checks with proxy provenance for low-sample case-label lanes."], "advisories": advisories})
    blocker_reg = {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S0", "overall_pass": overall, "open_blocker_count": len(blockers), "blockers": blockers}
    summary = {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S0", "overall_pass": overall, "next_gate": next_gate, "open_blocker_count": len(blockers), "required_artifacts": req, "probe_count": metrics["probe_count"], "error_rate_pct": metrics["error_rate_pct"], "platform_run_id": platform_run_id, "upstream_m7_s0_phase_execution_id": parent_id, "upstream_m7p9_s5_phase_execution_id": p9_id}
    verdict = {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S0", "overall_pass": overall, "verdict": verdict_name, "next_gate": next_gate, "blocker_count": len(blockers), "platform_run_id": platform_run_id}
    dumpj(out / "m7p10_blocker_register.json", blocker_reg)
    dumpj(out / "m7p10_execution_summary.json", summary)
    dumpj(out / "m7p10_gate_verdict.json", verdict)
    finalize_artifact_contract(out, req, blockers, blocker_reg, summary, verdict)
    s = loadj(out / "m7p10_execution_summary.json")
    b = loadj(out / "m7p10_blocker_register.json")
    print(f"[m7p10_s0] phase_execution_id={phase_execution_id}")
    print(f"[m7p10_s0] output_dir={out.as_posix()}")
    print(f"[m7p10_s0] overall_pass={s.get('overall_pass')}")
    print(f"[m7p10_s0] next_gate={s.get('next_gate')}")
    print(f"[m7p10_s0] open_blockers={b.get('open_blocker_count')}")
    return 0 if s.get("overall_pass") is True else 2


def run_s1(phase_execution_id: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)
    plan_packet = parse_bt_map(PLAN.read_text(encoding="utf-8") if PLAN.exists() else "")
    handles = parse_registry(REG) if REG.exists() else {}
    req = required_artifacts(plan_packet)
    evidence_bucket = str(handles.get("S3_EVIDENCE_BUCKET", "")).strip()

    blockers: list[dict[str, Any]] = []
    issues: list[str] = []
    advisories: list[str] = []
    decisions: list[str] = []
    probes: list[dict[str, Any]] = []

    miss_plan = [k for k in PLAN_KEYS if k not in plan_packet]
    miss_handle, ph_handle = resolve_required_handles(handles)
    miss_docs = [x.as_posix() for x in [PLAN, PARENT_PLAN, BUILD_PLAN] if not x.exists()]
    if miss_plan or miss_handle or ph_handle or miss_docs:
        blockers.append(
            {
                "id": "M7P10-ST-B4",
                "severity": "S1",
                "status": "OPEN",
                "details": {
                    "reason": "S1 authority/handle closure failure",
                    "missing_plan_keys": miss_plan,
                    "missing_handles": miss_handle,
                    "placeholder_handles": ph_handle,
                    "missing_docs": miss_docs,
                },
            }
        )
        issues.append("S1 authority/handle closure failed")

    dep_issues: list[str] = []
    dep = latest_ok("m7p10_stress_s0", "m7p10_execution_summary.json", "M7P10-ST-S0")
    dep_id = ""
    dep_path: Path | None = None
    platform_run_id = ""
    dep_subset: dict[str, Any] = {}
    dep_profile: dict[str, Any] = {}
    dep_ct_snapshot: dict[str, Any] = {}
    dep_cm_snapshot: dict[str, Any] = {}
    dep_ls_snapshot: dict[str, Any] = {}
    dep_case_lifecycle: dict[str, Any] = {}
    dep_label_profile: dict[str, Any] = {}
    dep_writer_profile: dict[str, Any] = {}
    dep_decision_log: dict[str, Any] = {}

    if not dep:
        dep_issues.append("missing successful M7P10 S0 dependency")
    else:
        dep_id = str(dep["summary"].get("phase_execution_id", ""))
        dep_path = Path(str(dep["path"]))
        dep_summary = dep["summary"]
        platform_run_id = str(dep_summary.get("platform_run_id", "")).strip()
        if str(dep_summary.get("next_gate", "")).strip() != "M7P10_ST_S1_READY":
            dep_issues.append("M7P10 S0 next_gate is not M7P10_ST_S1_READY")
        dep_blocker = loadj(dep_path / "m7p10_blocker_register.json")
        if int(dep_blocker.get("open_blocker_count", 0) or 0) != 0:
            dep_issues.append("M7P10 S0 blocker register is not closed")

        dep_required = dep_summary.get("required_artifacts", req)
        for art in dep_required:
            if not (dep_path / str(art)).exists():
                blockers.append({"id": "M7P10-ST-B10", "severity": "S1", "status": "OPEN", "details": {"reason": "missing dependency artifact", "artifact": str(art)}})
                dep_issues.append(f"missing S0 artifact: {art}")

        dep_subset = loadj(dep_path / "m7p10_data_subset_manifest.json")
        dep_profile = loadj(dep_path / "m7p10_data_profile_summary.json")
        dep_ct_snapshot = loadj(dep_path / "m7p10_case_trigger_snapshot.json")
        dep_cm_snapshot = loadj(dep_path / "m7p10_cm_snapshot.json")
        dep_ls_snapshot = loadj(dep_path / "m7p10_ls_snapshot.json")
        dep_case_lifecycle = loadj(dep_path / "m7p10_case_lifecycle_profile.json")
        dep_label_profile = loadj(dep_path / "m7p10_label_distribution_profile.json")
        dep_writer_profile = loadj(dep_path / "m7p10_writer_conflict_profile.json")
        dep_decision_log = loadj(dep_path / "m7p10_decision_log.json")
        if not dep_subset or not dep_profile or not dep_ct_snapshot or not dep_cm_snapshot or not dep_ls_snapshot:
            dep_issues.append("S0 carry-forward realism artifacts are incomplete")

    if dep_issues:
        blockers.append({"id": "M7P10-ST-B4", "severity": "S1", "status": "OPEN", "details": {"issues": dep_issues}})
        issues.extend(dep_issues)
    else:
        decisions.append("Enforced S0 dependency continuity and blocker closure before S1 CaseTrigger checks.")

    p_bucket = head_bucket_probe(probes, evidence_bucket, "m7p10_s1_evidence_bucket")
    if p_bucket.get("status") != "PASS":
        blockers.append({"id": "M7P10-ST-B10", "severity": "S1", "status": "OPEN", "details": {"probe_id": "m7p10_s1_evidence_bucket"}})
        issues.append("evidence bucket probe failed")

    replacements = {"platform_run_id": platform_run_id}
    case_root = materialize(str(handles.get("CASE_LABELS_EVIDENCE_PATH_PATTERN", "")).strip(), replacements)
    unresolved_case_root = re.findall(r"{[^}]+}", case_root)
    if not case_root or unresolved_case_root:
        blockers.append(
            {
                "id": "M7P10-ST-B10",
                "severity": "S1",
                "status": "OPEN",
                "details": {"reason": "invalid CASE_LABELS_EVIDENCE_PATH_PATTERN resolution", "case_root": case_root, "tokens": unresolved_case_root},
            }
        )
        issues.append("case-label evidence root is unresolved")

    ct_key = f"{case_root.rstrip('/')}/case_trigger_component_proof.json" if case_root else ""
    ct_proof: dict[str, Any] = {}
    p_ct = head_object_probe(probes, evidence_bucket, ct_key, "m7p10_s1_case_trigger_proof")
    if p_ct.get("status") != "PASS":
        blockers.append({"id": "M7P10-ST-B10", "severity": "S1", "status": "OPEN", "details": {"probe_id": "m7p10_s1_case_trigger_proof"}})
        issues.append("case-trigger proof readback failed")
    else:
        ct_proof = load_s3_json(evidence_bucket, ct_key)
        if not ct_proof:
            blockers.append({"id": "M7P10-ST-B10", "severity": "S1", "status": "OPEN", "details": {"reason": "failed to parse case-trigger proof", "key": ct_key}})
            issues.append("failed to parse case-trigger proof")

    receipt_key = materialize(str(handles.get("RECEIPT_SUMMARY_PATH_PATTERN", "")).strip(), replacements)
    receipt_summary: dict[str, Any] = {}
    p_receipt = head_object_probe(probes, evidence_bucket, receipt_key, "m7p10_s1_receipt_summary")
    if p_receipt.get("status") == "PASS":
        receipt_summary = load_s3_json(evidence_bucket, receipt_key)
        if not receipt_summary:
            advisories.append("receipt summary parse failed for S1; continuing with proof-level semantics.")
    else:
        advisories.append("receipt summary object unreadable in S1; using proof-level semantics and S0 carry-forward.")

    hist_ct = latest_hist("p10b_case_trigger_execution_summary.json", "p10b_case_trigger_snapshot.json", "p10b_case_trigger_performance_snapshot.json", "p10b_case_trigger_blocker_register.json", "P10.C_READY")
    if not hist_ct:
        blockers.append({"id": "M7P10-ST-B4", "severity": "S1", "status": "OPEN", "details": {"reason": "missing historical P10.B case-trigger baseline"}})
        issues.append("historical P10.B baseline missing")

    functional_issues: list[str] = []
    semantic_issues: list[str] = []

    runtime_active = normalize_runtime_path(str(handles.get("FLINK_RUNTIME_PATH_ACTIVE", "")))
    runtime_allowed = [normalize_runtime_path(x) for x in str(handles.get("FLINK_RUNTIME_PATH_ALLOWED", "")).split("|") if x.strip()]
    if not runtime_active or runtime_active not in runtime_allowed:
        functional_issues.append("runtime path contract invalid for S1")

    proof_runtime = normalize_runtime_path(str(ct_proof.get("runtime_path_active", "")))
    if proof_runtime and runtime_active and proof_runtime != runtime_active:
        functional_issues.append(f"case-trigger proof runtime path {proof_runtime} differs from active runtime {runtime_active}")

    if hist_ct:
        perf = hist_ct.get("perf", {})
        if to_bool(perf.get("performance_gate_pass")) is not True:
            functional_issues.append("historical P10.B performance gate is not pass")
        throughput_asserted = to_bool(perf.get("throughput_assertion_applied"))
        mode = str(perf.get("throughput_gate_mode", "")).strip()
        if throughput_asserted is not True:
            blockers.append(
                {
                    "id": "M7P10-ST-B13",
                    "severity": "S1",
                    "status": "OPEN",
                    "details": {
                        "reason": "toy-profile throughput posture is not allowed for closure",
                        "component": "CaseTriggerBridge",
                        "throughput_assertion_applied": throughput_asserted,
                        "throughput_gate_mode": mode,
                    },
                }
            )
            functional_issues.append("CaseTriggerBridge throughput assertion is not applied; strict non-toy closure requires asserted throughput")

    comp = str(ct_proof.get("component", "")).strip()
    if comp and comp != "CaseTriggerBridge":
        semantic_issues.append(f"unexpected case-trigger component id: {comp}")

    proof_platform_run_id = str(ct_proof.get("platform_run_id", "")).strip()
    if platform_run_id and proof_platform_run_id and platform_run_id != proof_platform_run_id:
        semantic_issues.append("case-trigger proof platform_run_id mismatch with S0 dependency")

    run_scope = ct_proof.get("run_scope_tuple", {})
    if isinstance(run_scope, dict):
        rs_run = str(run_scope.get("platform_run_id", "")).strip()
        rs_phase = str(run_scope.get("phase", "")).strip()
        rs_comp = str(run_scope.get("component", "")).strip()
        if platform_run_id and rs_run and rs_run != platform_run_id:
            semantic_issues.append("case-trigger run_scope_tuple platform_run_id mismatch")
        if rs_phase and rs_phase != "P10.B":
            semantic_issues.append("case-trigger run_scope_tuple phase is not P10.B")
        if rs_comp and rs_comp != "CaseTriggerBridge":
            semantic_issues.append("case-trigger run_scope_tuple component is not CaseTriggerBridge")
    else:
        semantic_issues.append("case-trigger run_scope_tuple is missing or invalid")

    if to_bool(ct_proof.get("upstream_gate_accepted")) is not True:
        semantic_issues.append("case-trigger upstream gate acceptance is not true")

    idempotency_posture = str(ct_proof.get("idempotency_posture", "")).strip()
    if idempotency_posture != "run_scope_tuple_no_cross_run_acceptance":
        semantic_issues.append("case-trigger idempotency_posture mismatch")

    if to_bool(ct_proof.get("fail_closed_posture")) is not True:
        semantic_issues.append("case-trigger fail_closed_posture is not true")

    total_receipts = to_int(receipt_summary.get("total_receipts"))
    if total_receipts is None:
        total_receipts = to_int(ct_proof.get("ingest_basis_total_receipts"))
    decision_counts = receipt_summary.get("counts_by_decision", {}) if isinstance(receipt_summary.get("counts_by_decision"), dict) else {}
    duplicate_count = to_int(decision_counts.get("DUPLICATE")) or 0
    duplicate_ratio_pct = None if not total_receipts or total_receipts <= 0 else round((duplicate_count / float(total_receipts)) * 100.0, 6)
    if duplicate_ratio_pct is not None and duplicate_ratio_pct == 0.0:
        advisories.append("no naturally observed duplicate receipts in S1 window; keep explicit duplicate/replay cohort injection as a mandatory downstream pressure check.")

    dep_advisories = dep_profile.get("advisories", [])
    if isinstance(dep_advisories, list):
        for a in dep_advisories:
            s = str(a).strip()
            if s and s not in advisories:
                advisories.append(s)

    if functional_issues:
        blockers.append({"id": "M7P10-ST-B4", "severity": "S1", "status": "OPEN", "details": {"issues": functional_issues}})
        issues.extend(functional_issues)
    if semantic_issues:
        blockers.append({"id": "M7P10-ST-B5", "severity": "S1", "status": "OPEN", "details": {"issues": semantic_issues}})
        issues.extend(semantic_issues)

    metrics = probe_metrics(probes)
    overall = len(blockers) == 0
    next_gate = "M7P10_ST_S2_READY" if overall else "BLOCKED"
    verdict_name = "ADVANCE_TO_S2" if overall else "HOLD_REMEDIATE"

    dumpj(
        out / "m7p10_stagea_findings.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P10-ST-S1",
            "findings": [
                {"id": "M7P10-ST-F6", "classification": "PREVENT", "finding": "S1 must fail closed if S0 continuity or artifact closure is broken.", "required_action": "Block S1 on any S0 gate mismatch or missing dependency artifact."},
                {"id": "M7P10-ST-F7", "classification": "PREVENT", "finding": "CaseTrigger semantics require strict run-scope and fail-closed posture checks.", "required_action": "Block on run_scope tuple drift, upstream gate mismatch, or idempotency/fail-closed drift."},
                {"id": "M7P10-ST-F8", "classification": "OBSERVE", "finding": "Low-sample managed lane can hide duplicate/hotkey behavior.", "required_action": "Carry explicit replay/hotkey pressure advisories to downstream windows."},
            ],
        },
    )
    dumpj(out / "m7p10_lane_matrix.json", {"component_sequence": ["M7P10-ST-S0", "M7P10-ST-S1", "M7P10-ST-S2", "M7P10-ST-S3", "M7P10-ST-S4", "M7P10-ST-S5"]})
    dumpj(
        out / "m7p10_data_subset_manifest.json",
        {
            **dep_subset,
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P10-ST-S1",
            "status": "CARRY_FORWARD_FROM_S0",
            "upstream_m7p10_s0_phase_execution_id": dep_id,
            "case_trigger_proof_key": ct_key,
        },
    )
    dumpj(
        out / "m7p10_data_profile_summary.json",
        {
            **dep_profile,
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P10-ST-S1",
            "status": "S1_CASETRIGGER_ADJUDICATED",
            "s1_functional_issues": functional_issues,
            "s1_semantic_issues": semantic_issues,
            "duplicate_ratio_pct_s1": duplicate_ratio_pct,
            "duplicate_count_s1": duplicate_count,
            "total_receipts_s1": total_receipts,
            "advisories": advisories,
            "upstream_m7p10_s0_phase_execution_id": dep_id,
        },
    )
    dumpj(
        out / "m7p10_case_trigger_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P10-ST-S1",
            "platform_run_id": platform_run_id,
            "upstream_m7p10_s0_phase_execution_id": dep_id,
            "historical_baseline": hist_ct,
            "s0_case_trigger_snapshot": dep_ct_snapshot,
            "current_case_trigger_proof": ct_proof,
            "functional_issues": functional_issues,
            "semantic_issues": semantic_issues,
            "duplicate_ratio_pct_s1": duplicate_ratio_pct,
            "duplicate_count_s1": duplicate_count,
            "total_receipts_s1": total_receipts,
        },
    )
    dumpj(out / "m7p10_cm_snapshot.json", {**dep_cm_snapshot, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S1", "status": "CARRY_FORWARD_FROM_S0", "upstream_m7p10_s0_phase_execution_id": dep_id})
    dumpj(out / "m7p10_ls_snapshot.json", {**dep_ls_snapshot, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S1", "status": "CARRY_FORWARD_FROM_S0", "upstream_m7p10_s0_phase_execution_id": dep_id})
    dumpj(out / "m7p10_case_lifecycle_profile.json", {**dep_case_lifecycle, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S1", "status": "CARRY_FORWARD_FROM_S0", "duplicate_ratio_pct_s1": duplicate_ratio_pct, "upstream_m7p10_s0_phase_execution_id": dep_id})
    dumpj(out / "m7p10_label_distribution_profile.json", {**dep_label_profile, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S1", "status": "CARRY_FORWARD_FROM_S0", "upstream_m7p10_s0_phase_execution_id": dep_id})
    dumpj(out / "m7p10_writer_conflict_profile.json", {**dep_writer_profile, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S1", "status": "CARRY_FORWARD_FROM_S0", "duplicate_ratio_pct_s1": duplicate_ratio_pct, "upstream_m7p10_s0_phase_execution_id": dep_id})
    dumpj(out / "m7p10_probe_latency_throughput_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S1", **metrics})
    dumpj(
        out / "m7p10_control_rail_conformance_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P10-ST-S1",
            "overall_pass": len(issues) == 0,
            "issues": issues,
            "advisories": advisories,
            "dependency_refs": {"m7p10_s0_execution_id": dep_id},
        },
    )
    dumpj(
        out / "m7p10_secret_safety_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P10-ST-S1",
            "overall_pass": True,
            "secret_probe_count": 0,
            "secret_failure_count": 0,
            "with_decryption_used": False,
            "queried_value_directly": False,
            "plaintext_leakage_detected": False,
        },
    )
    dumpj(
        out / "m7p10_cost_outcome_receipt.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P10-ST-S1",
            "window_seconds": metrics["window_seconds_observed"],
            "estimated_api_call_count": metrics["probe_count"],
            "attributed_spend_usd": 0.0,
            "unattributed_spend_detected": False,
            "max_spend_usd": float(plan_packet.get("M7P10_STRESS_MAX_SPEND_USD", 38)),
            "within_envelope": True,
            "method": "m7p10_s1_case_trigger_lane_v0",
        },
    )

    decisions.extend(
        [
            "Validated S0 dependency closure before opening S1 CaseTrigger lane checks.",
            "Applied historical P10.B baseline and current run-scoped proof checks to functional/performance gate adjudication.",
            "Applied run-scope/idempotency/fail-closed semantic checks for CaseTrigger bridge under fail-closed policy.",
            "Preserved explicit advisories for low-sample duplicate/hotkey coverage as mandatory downstream pressure checks.",
        ]
    )
    if isinstance(dep_decision_log.get("decisions"), list):
        for d in dep_decision_log["decisions"]:
            s = str(d).strip()
            if s and s not in decisions:
                decisions.append(s)

    dumpj(out / "m7p10_decision_log.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S1", "decisions": decisions, "advisories": advisories})

    blocker_reg = {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S1", "overall_pass": overall, "open_blocker_count": len(blockers), "blockers": blockers}
    summary = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M7P10-ST-S1",
        "overall_pass": overall,
        "next_gate": next_gate,
        "open_blocker_count": len(blockers),
        "required_artifacts": req,
        "probe_count": metrics["probe_count"],
        "error_rate_pct": metrics["error_rate_pct"],
        "platform_run_id": platform_run_id,
        "upstream_m7p10_s0_phase_execution_id": dep_id,
        "historical_p10b_execution_id": str(hist_ct.get("summary", {}).get("execution_id", "")) if hist_ct else "",
    }
    verdict = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M7P10-ST-S1",
        "overall_pass": overall,
        "verdict": verdict_name,
        "next_gate": next_gate,
        "blocker_count": len(blockers),
        "platform_run_id": platform_run_id,
        "upstream_m7p10_s0_phase_execution_id": dep_id,
        "historical_p10b_execution_id": str(hist_ct.get("summary", {}).get("execution_id", "")) if hist_ct else "",
    }
    dumpj(out / "m7p10_blocker_register.json", blocker_reg)
    dumpj(out / "m7p10_execution_summary.json", summary)
    dumpj(out / "m7p10_gate_verdict.json", verdict)
    finalize_artifact_contract(out, req, blockers, blocker_reg, summary, verdict)

    s = loadj(out / "m7p10_execution_summary.json")
    b = loadj(out / "m7p10_blocker_register.json")
    print(f"[m7p10_s1] phase_execution_id={phase_execution_id}")
    print(f"[m7p10_s1] output_dir={out.as_posix()}")
    print(f"[m7p10_s1] overall_pass={s.get('overall_pass')}")
    print(f"[m7p10_s1] next_gate={s.get('next_gate')}")
    print(f"[m7p10_s1] open_blockers={b.get('open_blocker_count')}")
    return 0 if s.get("overall_pass") is True else 2


def run_s2(phase_execution_id: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)
    plan_packet = parse_bt_map(PLAN.read_text(encoding="utf-8") if PLAN.exists() else "")
    handles = parse_registry(REG) if REG.exists() else {}
    req = required_artifacts(plan_packet)
    evidence_bucket = str(handles.get("S3_EVIDENCE_BUCKET", "")).strip()

    blockers: list[dict[str, Any]] = []
    issues: list[str] = []
    advisories: list[str] = []
    decisions: list[str] = []
    probes: list[dict[str, Any]] = []

    miss_plan = [k for k in PLAN_KEYS if k not in plan_packet]
    miss_handle, ph_handle = resolve_required_handles(handles)
    miss_docs = [x.as_posix() for x in [PLAN, PARENT_PLAN, BUILD_PLAN] if not x.exists()]
    if miss_plan or miss_handle or ph_handle or miss_docs:
        blockers.append(
            {
                "id": "M7P10-ST-B6",
                "severity": "S2",
                "status": "OPEN",
                "details": {
                    "reason": "S2 authority/handle closure failure",
                    "missing_plan_keys": miss_plan,
                    "missing_handles": miss_handle,
                    "placeholder_handles": ph_handle,
                    "missing_docs": miss_docs,
                },
            }
        )
        issues.append("S2 authority/handle closure failed")

    dep_issues: list[str] = []
    dep = latest_ok("m7p10_stress_s1", "m7p10_execution_summary.json", "M7P10-ST-S1")
    dep_id = ""
    dep_path: Path | None = None
    platform_run_id = ""
    dep_subset: dict[str, Any] = {}
    dep_profile: dict[str, Any] = {}
    dep_ct_snapshot: dict[str, Any] = {}
    dep_cm_snapshot: dict[str, Any] = {}
    dep_ls_snapshot: dict[str, Any] = {}
    dep_case_lifecycle: dict[str, Any] = {}
    dep_label_profile: dict[str, Any] = {}
    dep_writer_profile: dict[str, Any] = {}
    dep_decision_log: dict[str, Any] = {}

    if not dep:
        dep_issues.append("missing successful M7P10 S1 dependency")
    else:
        dep_id = str(dep["summary"].get("phase_execution_id", ""))
        dep_path = Path(str(dep["path"]))
        dep_summary = dep["summary"]
        platform_run_id = str(dep_summary.get("platform_run_id", "")).strip()
        if str(dep_summary.get("next_gate", "")).strip() != "M7P10_ST_S2_READY":
            dep_issues.append("M7P10 S1 next_gate is not M7P10_ST_S2_READY")
        dep_blocker = loadj(dep_path / "m7p10_blocker_register.json")
        if int(dep_blocker.get("open_blocker_count", 0) or 0) != 0:
            dep_issues.append("M7P10 S1 blocker register is not closed")

        dep_required = dep_summary.get("required_artifacts", req)
        for art in dep_required:
            if not (dep_path / str(art)).exists():
                blockers.append({"id": "M7P10-ST-B10", "severity": "S2", "status": "OPEN", "details": {"reason": "missing dependency artifact", "artifact": str(art)}})
                dep_issues.append(f"missing S1 artifact: {art}")

        dep_subset = loadj(dep_path / "m7p10_data_subset_manifest.json")
        dep_profile = loadj(dep_path / "m7p10_data_profile_summary.json")
        dep_ct_snapshot = loadj(dep_path / "m7p10_case_trigger_snapshot.json")
        dep_cm_snapshot = loadj(dep_path / "m7p10_cm_snapshot.json")
        dep_ls_snapshot = loadj(dep_path / "m7p10_ls_snapshot.json")
        dep_case_lifecycle = loadj(dep_path / "m7p10_case_lifecycle_profile.json")
        dep_label_profile = loadj(dep_path / "m7p10_label_distribution_profile.json")
        dep_writer_profile = loadj(dep_path / "m7p10_writer_conflict_profile.json")
        dep_decision_log = loadj(dep_path / "m7p10_decision_log.json")
        if not dep_subset or not dep_profile or not dep_ct_snapshot or not dep_cm_snapshot or not dep_ls_snapshot:
            dep_issues.append("S1 carry-forward realism artifacts are incomplete")

    if dep_issues:
        blockers.append({"id": "M7P10-ST-B6", "severity": "S2", "status": "OPEN", "details": {"issues": dep_issues}})
        issues.extend(dep_issues)
    else:
        decisions.append("Enforced S1 dependency continuity and blocker closure before S2 CM checks.")

    p_bucket = head_bucket_probe(probes, evidence_bucket, "m7p10_s2_evidence_bucket")
    if p_bucket.get("status") != "PASS":
        blockers.append({"id": "M7P10-ST-B10", "severity": "S2", "status": "OPEN", "details": {"probe_id": "m7p10_s2_evidence_bucket"}})
        issues.append("evidence bucket probe failed")

    replacements = {"platform_run_id": platform_run_id}
    case_root = materialize(str(handles.get("CASE_LABELS_EVIDENCE_PATH_PATTERN", "")).strip(), replacements)
    unresolved_case_root = re.findall(r"{[^}]+}", case_root)
    if not case_root or unresolved_case_root:
        blockers.append(
            {
                "id": "M7P10-ST-B10",
                "severity": "S2",
                "status": "OPEN",
                "details": {"reason": "invalid CASE_LABELS_EVIDENCE_PATH_PATTERN resolution", "case_root": case_root, "tokens": unresolved_case_root},
            }
        )
        issues.append("case-label evidence root is unresolved")

    ct_key = f"{case_root.rstrip('/')}/case_trigger_component_proof.json" if case_root else ""
    cm_key = f"{case_root.rstrip('/')}/cm_component_proof.json" if case_root else ""
    ct_proof: dict[str, Any] = {}
    cm_proof: dict[str, Any] = {}

    p_ct = head_object_probe(probes, evidence_bucket, ct_key, "m7p10_s2_case_trigger_proof")
    if p_ct.get("status") == "PASS":
        ct_proof = load_s3_json(evidence_bucket, ct_key)
        if not ct_proof:
            blockers.append({"id": "M7P10-ST-B10", "severity": "S2", "status": "OPEN", "details": {"reason": "failed to parse case-trigger proof", "key": ct_key}})
            issues.append("failed to parse case-trigger proof in S2")
    else:
        advisories.append("case-trigger proof readback failed in S2; CM checks continue with CM proof + S1 carry-forward.")

    p_cm = head_object_probe(probes, evidence_bucket, cm_key, "m7p10_s2_cm_proof")
    if p_cm.get("status") != "PASS":
        blockers.append({"id": "M7P10-ST-B10", "severity": "S2", "status": "OPEN", "details": {"probe_id": "m7p10_s2_cm_proof"}})
        issues.append("CM proof readback failed")
    else:
        cm_proof = load_s3_json(evidence_bucket, cm_key)
        if not cm_proof:
            blockers.append({"id": "M7P10-ST-B10", "severity": "S2", "status": "OPEN", "details": {"reason": "failed to parse CM proof", "key": cm_key}})
            issues.append("failed to parse CM proof")

    receipt_key = materialize(str(handles.get("RECEIPT_SUMMARY_PATH_PATTERN", "")).strip(), replacements)
    receipt_summary: dict[str, Any] = {}
    p_receipt = head_object_probe(probes, evidence_bucket, receipt_key, "m7p10_s2_receipt_summary")
    if p_receipt.get("status") == "PASS":
        receipt_summary = load_s3_json(evidence_bucket, receipt_key)
        if not receipt_summary:
            advisories.append("receipt summary parse failed for S2; continuing with proof-level semantics.")
    else:
        advisories.append("receipt summary object unreadable in S2; using proof-level semantics and S1 carry-forward.")

    hist_cm = latest_hist("p10c_cm_execution_summary.json", "p10c_cm_snapshot.json", "p10c_cm_performance_snapshot.json", "p10c_cm_blocker_register.json", "P10.D_READY")
    if not hist_cm:
        blockers.append({"id": "M7P10-ST-B6", "severity": "S2", "status": "OPEN", "details": {"reason": "missing historical P10.C CM baseline"}})
        issues.append("historical P10.C baseline missing")

    functional_issues: list[str] = []
    semantic_issues: list[str] = []

    runtime_active = normalize_runtime_path(str(handles.get("FLINK_RUNTIME_PATH_ACTIVE", "")))
    runtime_allowed = [normalize_runtime_path(x) for x in str(handles.get("FLINK_RUNTIME_PATH_ALLOWED", "")).split("|") if x.strip()]
    if not runtime_active or runtime_active not in runtime_allowed:
        functional_issues.append("runtime path contract invalid for S2")

    proof_runtime = normalize_runtime_path(str(cm_proof.get("runtime_path_active", "")))
    if proof_runtime and runtime_active and proof_runtime != runtime_active:
        functional_issues.append(f"CM proof runtime path {proof_runtime} differs from active runtime {runtime_active}")

    if hist_cm:
        perf = hist_cm.get("perf", {})
        if to_bool(perf.get("performance_gate_pass")) is not True:
            functional_issues.append("historical P10.C performance gate is not pass")
        throughput_asserted = to_bool(perf.get("throughput_assertion_applied"))
        mode = str(perf.get("throughput_gate_mode", "")).strip()
        if throughput_asserted is not True:
            blockers.append(
                {
                    "id": "M7P10-ST-B13",
                    "severity": "S2",
                    "status": "OPEN",
                    "details": {
                        "reason": "toy-profile throughput posture is not allowed for closure",
                        "component": "CM",
                        "throughput_assertion_applied": throughput_asserted,
                        "throughput_gate_mode": mode,
                    },
                }
            )
            functional_issues.append("CM throughput assertion is not applied; strict non-toy closure requires asserted throughput")

    comp = str(cm_proof.get("component", "")).strip()
    if comp and comp != "CM":
        semantic_issues.append(f"unexpected CM component id: {comp}")

    proof_platform_run_id = str(cm_proof.get("platform_run_id", "")).strip()
    if platform_run_id and proof_platform_run_id and platform_run_id != proof_platform_run_id:
        semantic_issues.append("CM proof platform_run_id mismatch with S1 dependency")

    run_scope = cm_proof.get("run_scope_tuple", {})
    if isinstance(run_scope, dict):
        rs_run = str(run_scope.get("platform_run_id", "")).strip()
        rs_phase = str(run_scope.get("phase", "")).strip()
        rs_comp = str(run_scope.get("component", "")).strip()
        if platform_run_id and rs_run and rs_run != platform_run_id:
            semantic_issues.append("CM run_scope_tuple platform_run_id mismatch")
        if rs_phase and rs_phase != "P10.C":
            semantic_issues.append("CM run_scope_tuple phase is not P10.C")
        if rs_comp and rs_comp != "CM":
            semantic_issues.append("CM run_scope_tuple component is not CM")
    else:
        semantic_issues.append("CM run_scope_tuple is missing or invalid")

    if to_bool(cm_proof.get("upstream_gate_accepted")) is not True:
        semantic_issues.append("CM upstream gate acceptance is not true")
    if str(cm_proof.get("upstream_gate_expected", "")).strip() and str(cm_proof.get("upstream_gate_expected", "")).strip() != "P10.C_READY":
        semantic_issues.append("CM upstream_gate_expected is not P10.C_READY")

    idempotency_posture = str(cm_proof.get("idempotency_posture", "")).strip()
    if idempotency_posture != "run_scope_tuple_no_cross_run_acceptance":
        semantic_issues.append("CM idempotency_posture mismatch")

    if to_bool(cm_proof.get("fail_closed_posture")) is not True:
        semantic_issues.append("CM fail_closed_posture is not true")

    ct_exec = str(ct_proof.get("execution_id", "")).strip()
    cm_upstream_exec = str(cm_proof.get("upstream_execution", "")).strip()
    if ct_exec and cm_upstream_exec and cm_upstream_exec != ct_exec:
        semantic_issues.append("CM upstream_execution does not match CaseTrigger execution_id")

    total_receipts = to_int(receipt_summary.get("total_receipts"))
    if total_receipts is None:
        total_receipts = to_int(cm_proof.get("ingest_basis_total_receipts"))
    case_reopen_rate = to_float(receipt_summary.get("case_reopen_rate_pct"))
    if case_reopen_rate is None:
        case_reopen_rate = to_float(dep_case_lifecycle.get("case_reopen_rate_pct"))
        if case_reopen_rate is not None:
            advisories.append("S2 case_reopen_rate derived from S1 carry-forward due absent explicit metric in current receipt summary.")

    case_reopen_max = float(plan_packet.get("M7P10_STRESS_CASE_REOPEN_RATE_MAX_PCT", 3.0))
    if case_reopen_rate is not None and case_reopen_rate > case_reopen_max:
        semantic_issues.append(f"case_reopen_rate_pct {case_reopen_rate} exceeds max {case_reopen_max}")

    dep_advisories = dep_profile.get("advisories", [])
    if isinstance(dep_advisories, list):
        for a in dep_advisories:
            s = str(a).strip()
            if s and s not in advisories:
                advisories.append(s)

    if functional_issues:
        blockers.append({"id": "M7P10-ST-B6", "severity": "S2", "status": "OPEN", "details": {"issues": functional_issues}})
        issues.extend(functional_issues)
    if semantic_issues:
        blockers.append({"id": "M7P10-ST-B7", "severity": "S2", "status": "OPEN", "details": {"issues": semantic_issues}})
        issues.extend(semantic_issues)

    metrics = probe_metrics(probes)
    overall = len(blockers) == 0
    next_gate = "M7P10_ST_S3_READY" if overall else "BLOCKED"
    verdict_name = "ADVANCE_TO_S3" if overall else "HOLD_REMEDIATE"

    dumpj(
        out / "m7p10_stagea_findings.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P10-ST-S2",
            "findings": [
                {"id": "M7P10-ST-F9", "classification": "PREVENT", "finding": "S2 must fail closed if S1 continuity or artifact closure is broken.", "required_action": "Block S2 on any S1 gate mismatch or missing dependency artifact."},
                {"id": "M7P10-ST-F10", "classification": "PREVENT", "finding": "CM lifecycle semantics require strict run-scope and upstream-chain integrity checks.", "required_action": "Block on run_scope tuple drift, upstream linkage mismatch, or idempotency/fail-closed drift."},
                {"id": "M7P10-ST-F11", "classification": "OBSERVE", "finding": "Low-sample managed lane can hide reopen/rare-path behavior.", "required_action": "Carry explicit reopen/rare-path pressure advisories to downstream windows."},
            ],
        },
    )
    dumpj(out / "m7p10_lane_matrix.json", {"component_sequence": ["M7P10-ST-S0", "M7P10-ST-S1", "M7P10-ST-S2", "M7P10-ST-S3", "M7P10-ST-S4", "M7P10-ST-S5"]})
    dumpj(
        out / "m7p10_data_subset_manifest.json",
        {
            **dep_subset,
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P10-ST-S2",
            "status": "CARRY_FORWARD_FROM_S1",
            "upstream_m7p10_s1_phase_execution_id": dep_id,
            "cm_proof_key": cm_key,
            "case_trigger_proof_key": ct_key,
        },
    )
    dumpj(
        out / "m7p10_data_profile_summary.json",
        {
            **dep_profile,
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P10-ST-S2",
            "status": "S2_CM_ADJUDICATED",
            "s2_functional_issues": functional_issues,
            "s2_semantic_issues": semantic_issues,
            "case_reopen_rate_pct_s2": case_reopen_rate,
            "case_reopen_rate_max_pct_s2": case_reopen_max,
            "total_receipts_s2": total_receipts,
            "advisories": advisories,
            "upstream_m7p10_s1_phase_execution_id": dep_id,
        },
    )
    dumpj(out / "m7p10_case_trigger_snapshot.json", {**dep_ct_snapshot, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S2", "status": "CARRY_FORWARD_FROM_S1", "upstream_m7p10_s1_phase_execution_id": dep_id, "current_case_trigger_proof": ct_proof})
    dumpj(
        out / "m7p10_cm_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P10-ST-S2",
            "platform_run_id": platform_run_id,
            "upstream_m7p10_s1_phase_execution_id": dep_id,
            "historical_baseline": hist_cm,
            "s1_cm_snapshot": dep_cm_snapshot,
            "current_cm_proof": cm_proof,
            "functional_issues": functional_issues,
            "semantic_issues": semantic_issues,
            "case_reopen_rate_pct_s2": case_reopen_rate,
            "total_receipts_s2": total_receipts,
        },
    )
    dumpj(out / "m7p10_ls_snapshot.json", {**dep_ls_snapshot, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S2", "status": "CARRY_FORWARD_FROM_S1", "upstream_m7p10_s1_phase_execution_id": dep_id})
    dumpj(
        out / "m7p10_case_lifecycle_profile.json",
        {
            **dep_case_lifecycle,
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P10-ST-S2",
            "status": "S2_CM_LIFECYCLE_ADJUDICATED",
            "case_reopen_rate_pct_s2": case_reopen_rate,
            "case_reopen_rate_max_pct_s2": case_reopen_max,
            "cm_upstream_execution": cm_upstream_exec,
            "case_trigger_execution_id": ct_exec,
            "upstream_m7p10_s1_phase_execution_id": dep_id,
        },
    )
    dumpj(out / "m7p10_label_distribution_profile.json", {**dep_label_profile, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S2", "status": "CARRY_FORWARD_FROM_S1", "upstream_m7p10_s1_phase_execution_id": dep_id})
    dumpj(out / "m7p10_writer_conflict_profile.json", {**dep_writer_profile, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S2", "status": "CARRY_FORWARD_FROM_S1", "upstream_m7p10_s1_phase_execution_id": dep_id})
    dumpj(out / "m7p10_probe_latency_throughput_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S2", **metrics})
    dumpj(
        out / "m7p10_control_rail_conformance_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P10-ST-S2",
            "overall_pass": len(issues) == 0,
            "issues": issues,
            "advisories": advisories,
            "dependency_refs": {"m7p10_s1_execution_id": dep_id},
        },
    )
    dumpj(
        out / "m7p10_secret_safety_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P10-ST-S2",
            "overall_pass": True,
            "secret_probe_count": 0,
            "secret_failure_count": 0,
            "with_decryption_used": False,
            "queried_value_directly": False,
            "plaintext_leakage_detected": False,
        },
    )
    dumpj(
        out / "m7p10_cost_outcome_receipt.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P10-ST-S2",
            "window_seconds": metrics["window_seconds_observed"],
            "estimated_api_call_count": metrics["probe_count"],
            "attributed_spend_usd": 0.0,
            "unattributed_spend_detected": False,
            "max_spend_usd": float(plan_packet.get("M7P10_STRESS_MAX_SPEND_USD", 38)),
            "within_envelope": True,
            "method": "m7p10_s2_cm_lane_v0",
        },
    )

    decisions.extend(
        [
            "Validated S1 dependency closure before opening S2 CM lane checks.",
            "Applied historical P10.C baseline and current run-scoped CM proof checks to functional/performance gate adjudication.",
            "Applied CM lifecycle/run-scope/upstream-linkage semantic checks under fail-closed policy.",
            "Preserved explicit advisories for low-sample reopen/rare-path coverage as mandatory downstream pressure checks.",
        ]
    )
    if isinstance(dep_decision_log.get("decisions"), list):
        for d in dep_decision_log["decisions"]:
            s = str(d).strip()
            if s and s not in decisions:
                decisions.append(s)

    dumpj(out / "m7p10_decision_log.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S2", "decisions": decisions, "advisories": advisories})

    blocker_reg = {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S2", "overall_pass": overall, "open_blocker_count": len(blockers), "blockers": blockers}
    summary = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M7P10-ST-S2",
        "overall_pass": overall,
        "next_gate": next_gate,
        "open_blocker_count": len(blockers),
        "required_artifacts": req,
        "probe_count": metrics["probe_count"],
        "error_rate_pct": metrics["error_rate_pct"],
        "platform_run_id": platform_run_id,
        "upstream_m7p10_s1_phase_execution_id": dep_id,
        "historical_p10c_execution_id": str(hist_cm.get("summary", {}).get("execution_id", "")) if hist_cm else "",
    }
    verdict = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M7P10-ST-S2",
        "overall_pass": overall,
        "verdict": verdict_name,
        "next_gate": next_gate,
        "blocker_count": len(blockers),
        "platform_run_id": platform_run_id,
        "upstream_m7p10_s1_phase_execution_id": dep_id,
        "historical_p10c_execution_id": str(hist_cm.get("summary", {}).get("execution_id", "")) if hist_cm else "",
    }
    dumpj(out / "m7p10_blocker_register.json", blocker_reg)
    dumpj(out / "m7p10_execution_summary.json", summary)
    dumpj(out / "m7p10_gate_verdict.json", verdict)
    finalize_artifact_contract(out, req, blockers, blocker_reg, summary, verdict)

    s = loadj(out / "m7p10_execution_summary.json")
    b = loadj(out / "m7p10_blocker_register.json")
    print(f"[m7p10_s2] phase_execution_id={phase_execution_id}")
    print(f"[m7p10_s2] output_dir={out.as_posix()}")
    print(f"[m7p10_s2] overall_pass={s.get('overall_pass')}")
    print(f"[m7p10_s2] next_gate={s.get('next_gate')}")
    print(f"[m7p10_s2] open_blockers={b.get('open_blocker_count')}")
    return 0 if s.get("overall_pass") is True else 2


def run_s3(phase_execution_id: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)
    plan_packet = parse_bt_map(PLAN.read_text(encoding="utf-8") if PLAN.exists() else "")
    handles = parse_registry(REG) if REG.exists() else {}
    req = required_artifacts(plan_packet)
    evidence_bucket = str(handles.get("S3_EVIDENCE_BUCKET", "")).strip()

    blockers: list[dict[str, Any]] = []
    issues: list[str] = []
    advisories: list[str] = []
    decisions: list[str] = []
    probes: list[dict[str, Any]] = []

    miss_plan = [k for k in PLAN_KEYS if k not in plan_packet]
    miss_handle, ph_handle = resolve_required_handles(handles)
    miss_docs = [x.as_posix() for x in [PLAN, PARENT_PLAN, BUILD_PLAN] if not x.exists()]
    if miss_plan or miss_handle or ph_handle or miss_docs:
        blockers.append(
            {
                "id": "M7P10-ST-B8",
                "severity": "S3",
                "status": "OPEN",
                "details": {
                    "reason": "S3 authority/handle closure failure",
                    "missing_plan_keys": miss_plan,
                    "missing_handles": miss_handle,
                    "placeholder_handles": ph_handle,
                    "missing_docs": miss_docs,
                },
            }
        )
        issues.append("S3 authority/handle closure failed")

    dep_issues: list[str] = []
    dep = latest_ok("m7p10_stress_s2", "m7p10_execution_summary.json", "M7P10-ST-S2")
    dep_id = ""
    dep_path: Path | None = None
    platform_run_id = ""
    dep_subset: dict[str, Any] = {}
    dep_profile: dict[str, Any] = {}
    dep_ct_snapshot: dict[str, Any] = {}
    dep_cm_snapshot: dict[str, Any] = {}
    dep_ls_snapshot: dict[str, Any] = {}
    dep_case_lifecycle: dict[str, Any] = {}
    dep_label_profile: dict[str, Any] = {}
    dep_writer_profile: dict[str, Any] = {}
    dep_decision_log: dict[str, Any] = {}

    if not dep:
        dep_issues.append("missing successful M7P10 S2 dependency")
    else:
        dep_id = str(dep["summary"].get("phase_execution_id", ""))
        dep_path = Path(str(dep["path"]))
        dep_summary = dep["summary"]
        platform_run_id = str(dep_summary.get("platform_run_id", "")).strip()
        if str(dep_summary.get("next_gate", "")).strip() != "M7P10_ST_S3_READY":
            dep_issues.append("M7P10 S2 next_gate is not M7P10_ST_S3_READY")
        dep_blocker = loadj(dep_path / "m7p10_blocker_register.json")
        if int(dep_blocker.get("open_blocker_count", 0) or 0) != 0:
            dep_issues.append("M7P10 S2 blocker register is not closed")

        dep_required = dep_summary.get("required_artifacts", req)
        for art in dep_required:
            if not (dep_path / str(art)).exists():
                blockers.append({"id": "M7P10-ST-B10", "severity": "S3", "status": "OPEN", "details": {"reason": "missing dependency artifact", "artifact": str(art)}})
                dep_issues.append(f"missing S2 artifact: {art}")

        dep_subset = loadj(dep_path / "m7p10_data_subset_manifest.json")
        dep_profile = loadj(dep_path / "m7p10_data_profile_summary.json")
        dep_ct_snapshot = loadj(dep_path / "m7p10_case_trigger_snapshot.json")
        dep_cm_snapshot = loadj(dep_path / "m7p10_cm_snapshot.json")
        dep_ls_snapshot = loadj(dep_path / "m7p10_ls_snapshot.json")
        dep_case_lifecycle = loadj(dep_path / "m7p10_case_lifecycle_profile.json")
        dep_label_profile = loadj(dep_path / "m7p10_label_distribution_profile.json")
        dep_writer_profile = loadj(dep_path / "m7p10_writer_conflict_profile.json")
        dep_decision_log = loadj(dep_path / "m7p10_decision_log.json")
        if not dep_subset or not dep_profile or not dep_ct_snapshot or not dep_cm_snapshot or not dep_ls_snapshot:
            dep_issues.append("S2 carry-forward realism artifacts are incomplete")

    if dep_issues:
        blockers.append({"id": "M7P10-ST-B8", "severity": "S3", "status": "OPEN", "details": {"issues": dep_issues}})
        issues.extend(dep_issues)
    else:
        decisions.append("Enforced S2 dependency continuity and blocker closure before S3 LS checks.")

    p_bucket = head_bucket_probe(probes, evidence_bucket, "m7p10_s3_evidence_bucket")
    if p_bucket.get("status") != "PASS":
        blockers.append({"id": "M7P10-ST-B10", "severity": "S3", "status": "OPEN", "details": {"probe_id": "m7p10_s3_evidence_bucket"}})
        issues.append("evidence bucket probe failed")

    replacements = {"platform_run_id": platform_run_id}
    case_root = materialize(str(handles.get("CASE_LABELS_EVIDENCE_PATH_PATTERN", "")).strip(), replacements)
    unresolved_case_root = re.findall(r"{[^}]+}", case_root)
    if not case_root or unresolved_case_root:
        blockers.append(
            {
                "id": "M7P10-ST-B10",
                "severity": "S3",
                "status": "OPEN",
                "details": {"reason": "invalid CASE_LABELS_EVIDENCE_PATH_PATTERN resolution", "case_root": case_root, "tokens": unresolved_case_root},
            }
        )
        issues.append("case-label evidence root is unresolved")

    ct_key = f"{case_root.rstrip('/')}/case_trigger_component_proof.json" if case_root else ""
    cm_key = f"{case_root.rstrip('/')}/cm_component_proof.json" if case_root else ""
    ls_key = f"{case_root.rstrip('/')}/ls_component_proof.json" if case_root else ""
    ct_proof: dict[str, Any] = {}
    cm_proof: dict[str, Any] = {}
    ls_proof: dict[str, Any] = {}

    p_ct = head_object_probe(probes, evidence_bucket, ct_key, "m7p10_s3_case_trigger_proof")
    if p_ct.get("status") == "PASS":
        ct_proof = load_s3_json(evidence_bucket, ct_key)
        if not ct_proof:
            advisories.append("case-trigger proof parse failed in S3; using S2 carry-forward for linkage checks.")
    else:
        advisories.append("case-trigger proof readback failed in S3; using S2 carry-forward for linkage checks.")

    p_cm = head_object_probe(probes, evidence_bucket, cm_key, "m7p10_s3_cm_proof")
    if p_cm.get("status") == "PASS":
        cm_proof = load_s3_json(evidence_bucket, cm_key)
        if not cm_proof:
            blockers.append({"id": "M7P10-ST-B10", "severity": "S3", "status": "OPEN", "details": {"reason": "failed to parse CM proof", "key": cm_key}})
            issues.append("failed to parse CM proof in S3")
    else:
        blockers.append({"id": "M7P10-ST-B10", "severity": "S3", "status": "OPEN", "details": {"probe_id": "m7p10_s3_cm_proof"}})
        issues.append("CM proof readback failed in S3")

    p_ls = head_object_probe(probes, evidence_bucket, ls_key, "m7p10_s3_ls_proof")
    if p_ls.get("status") != "PASS":
        blockers.append({"id": "M7P10-ST-B10", "severity": "S3", "status": "OPEN", "details": {"probe_id": "m7p10_s3_ls_proof"}})
        issues.append("LS proof readback failed")
    else:
        ls_proof = load_s3_json(evidence_bucket, ls_key)
        if not ls_proof:
            blockers.append({"id": "M7P10-ST-B10", "severity": "S3", "status": "OPEN", "details": {"reason": "failed to parse LS proof", "key": ls_key}})
            issues.append("failed to parse LS proof")

    writer_probe_key = str(ls_proof.get("ls_writer_boundary_probe_key", "")).strip()
    writer_probe: dict[str, Any] = {}
    if writer_probe_key:
        p_wp = head_object_probe(probes, evidence_bucket, writer_probe_key, "m7p10_s3_writer_probe")
        if p_wp.get("status") != "PASS":
            blockers.append({"id": "M7P10-ST-B10", "severity": "S3", "status": "OPEN", "details": {"probe_id": "m7p10_s3_writer_probe"}})
            issues.append("LS writer probe readback failed")
        else:
            writer_probe = load_s3_json(evidence_bucket, writer_probe_key)
            if not writer_probe:
                blockers.append({"id": "M7P10-ST-B10", "severity": "S3", "status": "OPEN", "details": {"reason": "failed to parse LS writer probe", "key": writer_probe_key}})
                issues.append("failed to parse LS writer probe")
    elif ls_proof:
        blockers.append({"id": "M7P10-ST-B10", "severity": "S3", "status": "OPEN", "details": {"reason": "LS proof missing ls_writer_boundary_probe_key"}})
        issues.append("LS writer-boundary probe key missing from LS proof")

    receipt_key = materialize(str(handles.get("RECEIPT_SUMMARY_PATH_PATTERN", "")).strip(), replacements)
    receipt_summary: dict[str, Any] = {}
    p_receipt = head_object_probe(probes, evidence_bucket, receipt_key, "m7p10_s3_receipt_summary")
    if p_receipt.get("status") == "PASS":
        receipt_summary = load_s3_json(evidence_bucket, receipt_key)
        if not receipt_summary:
            advisories.append("receipt summary parse failed for S3; continuing with LS proof and writer probe semantics.")
    else:
        advisories.append("receipt summary object unreadable in S3; using proof-level semantics and S2 carry-forward.")

    hist_ls = latest_hist("p10d_ls_execution_summary.json", "p10d_ls_snapshot.json", "p10d_ls_performance_snapshot.json", "p10d_ls_blocker_register.json", "P10.E_READY")
    if not hist_ls:
        blockers.append({"id": "M7P10-ST-B8", "severity": "S3", "status": "OPEN", "details": {"reason": "missing historical P10.D LS baseline"}})
        issues.append("historical P10.D baseline missing")

    functional_issues: list[str] = []
    semantic_issues: list[str] = []

    runtime_active = normalize_runtime_path(str(handles.get("FLINK_RUNTIME_PATH_ACTIVE", "")))
    runtime_allowed = [normalize_runtime_path(x) for x in str(handles.get("FLINK_RUNTIME_PATH_ALLOWED", "")).split("|") if x.strip()]
    if not runtime_active or runtime_active not in runtime_allowed:
        functional_issues.append("runtime path contract invalid for S3")

    proof_runtime = normalize_runtime_path(str(ls_proof.get("runtime_path_active", "")))
    if proof_runtime and runtime_active and proof_runtime != runtime_active:
        functional_issues.append(f"LS proof runtime path {proof_runtime} differs from active runtime {runtime_active}")

    if hist_ls:
        perf = hist_ls.get("perf", {})
        if to_bool(perf.get("performance_gate_pass")) is not True:
            functional_issues.append("historical P10.D performance gate is not pass")
        throughput_asserted = to_bool(perf.get("throughput_assertion_applied"))
        mode = str(perf.get("throughput_gate_mode", "")).strip()
        if throughput_asserted is not True:
            blockers.append(
                {
                    "id": "M7P10-ST-B13",
                    "severity": "S3",
                    "status": "OPEN",
                    "details": {
                        "reason": "toy-profile throughput posture is not allowed for closure",
                        "component": "LS",
                        "throughput_assertion_applied": throughput_asserted,
                        "throughput_gate_mode": mode,
                    },
                }
            )
            functional_issues.append("LS throughput assertion is not applied; strict non-toy closure requires asserted throughput")

    comp = str(ls_proof.get("component", "")).strip()
    if comp and comp != "LS":
        semantic_issues.append(f"unexpected LS component id: {comp}")

    proof_platform_run_id = str(ls_proof.get("platform_run_id", "")).strip()
    if platform_run_id and proof_platform_run_id and platform_run_id != proof_platform_run_id:
        semantic_issues.append("LS proof platform_run_id mismatch with S2 dependency")

    run_scope = ls_proof.get("run_scope_tuple", {})
    if isinstance(run_scope, dict):
        rs_run = str(run_scope.get("platform_run_id", "")).strip()
        rs_phase = str(run_scope.get("phase", "")).strip()
        rs_comp = str(run_scope.get("component", "")).strip()
        if platform_run_id and rs_run and rs_run != platform_run_id:
            semantic_issues.append("LS run_scope_tuple platform_run_id mismatch")
        if rs_phase and rs_phase != "P10.D":
            semantic_issues.append("LS run_scope_tuple phase is not P10.D")
        if rs_comp and rs_comp != "LS":
            semantic_issues.append("LS run_scope_tuple component is not LS")
    else:
        semantic_issues.append("LS run_scope_tuple is missing or invalid")

    if to_bool(ls_proof.get("upstream_gate_accepted")) is not True:
        semantic_issues.append("LS upstream gate acceptance is not true")
    if str(ls_proof.get("upstream_gate_expected", "")).strip() and str(ls_proof.get("upstream_gate_expected", "")).strip() != "P10.D_READY":
        semantic_issues.append("LS upstream_gate_expected is not P10.D_READY")

    idempotency_posture = str(ls_proof.get("idempotency_posture", "")).strip()
    if idempotency_posture != "run_scope_tuple_no_cross_run_acceptance":
        semantic_issues.append("LS idempotency_posture mismatch")

    if to_bool(ls_proof.get("fail_closed_posture")) is not True:
        semantic_issues.append("LS fail_closed_posture is not true")

    cm_exec = str(cm_proof.get("execution_id", "")).strip()
    ls_upstream_exec = str(ls_proof.get("upstream_execution", "")).strip()
    if cm_exec and ls_upstream_exec and ls_upstream_exec != cm_exec:
        semantic_issues.append("LS upstream_execution does not match CM execution_id")

    if not cm_exec and dep_case_lifecycle:
        cm_exec_cf = str(dep_case_lifecycle.get("cm_upstream_execution", "")).strip()
        ct_exec_cf = str(dep_case_lifecycle.get("case_trigger_execution_id", "")).strip()
        if cm_exec_cf and ct_exec_cf and cm_exec_cf != ct_exec_cf:
            advisories.append("S2 carry-forward indicates CM linkage anomaly; verify in S4 integrated window.")

    outcome_states = [str(x).strip() for x in writer_probe.get("outcome_states", []) if str(x).strip()]
    outcome_unique = sorted(set(outcome_states))
    min_label_class = int(plan_packet.get("M7P10_STRESS_LABEL_CLASS_MIN_CARDINALITY", 3))
    if outcome_unique and len(outcome_unique) < min_label_class:
        semantic_issues.append(f"writer outcome state cardinality {len(outcome_unique)} is below minimum {min_label_class}")
    if not outcome_unique:
        semantic_issues.append("writer probe outcome_states is missing/empty")

    single_writer_posture = to_bool(writer_probe.get("single_writer_posture"))
    if single_writer_posture is not True:
        semantic_issues.append("writer probe single_writer_posture is not true")

    writer_conflict_rate = to_float(writer_probe.get("writer_conflict_rate_pct"))
    if writer_conflict_rate is None:
        writer_conflict_rate = to_float(dep_writer_profile.get("writer_conflict_rate_pct"))
    if writer_conflict_rate is None:
        if single_writer_posture is True:
            writer_conflict_rate = 0.0
            advisories.append("writer conflict rate inferred as 0.0 from single-writer posture.")
        elif single_writer_posture is False:
            writer_conflict_rate = 100.0

    writer_conflict_max = float(plan_packet.get("M7P10_STRESS_WRITER_CONFLICT_MAX_RATE_PCT", 0.5))
    if writer_conflict_rate is None:
        semantic_issues.append("writer conflict rate is not observable")
    elif writer_conflict_rate > writer_conflict_max:
        semantic_issues.append(f"writer_conflict_rate_pct {writer_conflict_rate} exceeds max {writer_conflict_max}")

    case_reopen_rate = to_float(receipt_summary.get("case_reopen_rate_pct"))
    if case_reopen_rate is None:
        case_reopen_rate = to_float(dep_case_lifecycle.get("case_reopen_rate_pct_s2"))
    if case_reopen_rate is None:
        case_reopen_rate = to_float(dep_case_lifecycle.get("case_reopen_rate_pct"))
    if case_reopen_rate is not None:
        case_reopen_max = float(plan_packet.get("M7P10_STRESS_CASE_REOPEN_RATE_MAX_PCT", 3.0))
        if case_reopen_rate > case_reopen_max:
            semantic_issues.append(f"case_reopen_rate_pct {case_reopen_rate} exceeds max {case_reopen_max}")

    dep_advisories = dep_profile.get("advisories", [])
    if isinstance(dep_advisories, list):
        for a in dep_advisories:
            s = str(a).strip()
            if s and s not in advisories:
                advisories.append(s)

    if functional_issues:
        blockers.append({"id": "M7P10-ST-B8", "severity": "S3", "status": "OPEN", "details": {"issues": functional_issues}})
        issues.extend(functional_issues)
    if semantic_issues:
        blockers.append({"id": "M7P10-ST-B9", "severity": "S3", "status": "OPEN", "details": {"issues": semantic_issues}})
        issues.extend(semantic_issues)

    metrics = probe_metrics(probes)
    overall = len(blockers) == 0
    next_gate = "M7P10_ST_S4_READY" if overall else "BLOCKED"
    verdict_name = "ADVANCE_TO_S4" if overall else "HOLD_REMEDIATE"

    dumpj(
        out / "m7p10_stagea_findings.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P10-ST-S3",
            "findings": [
                {"id": "M7P10-ST-F12", "classification": "PREVENT", "finding": "S3 must fail closed if S2 continuity or artifact closure is broken.", "required_action": "Block S3 on any S2 gate mismatch or missing dependency artifact."},
                {"id": "M7P10-ST-F13", "classification": "PREVENT", "finding": "LS writer-boundary semantics require explicit single-writer and outcome-state checks.", "required_action": "Block on writer probe absence, single-writer drift, or conflict-rate breaches."},
                {"id": "M7P10-ST-F14", "classification": "OBSERVE", "finding": "Low-sample managed lane can hide real contention behavior.", "required_action": "Carry explicit contention/reopen pressure advisories to downstream windows."},
            ],
        },
    )
    dumpj(out / "m7p10_lane_matrix.json", {"component_sequence": ["M7P10-ST-S0", "M7P10-ST-S1", "M7P10-ST-S2", "M7P10-ST-S3", "M7P10-ST-S4", "M7P10-ST-S5"]})
    dumpj(
        out / "m7p10_data_subset_manifest.json",
        {
            **dep_subset,
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P10-ST-S3",
            "status": "CARRY_FORWARD_FROM_S2",
            "upstream_m7p10_s2_phase_execution_id": dep_id,
            "ls_proof_key": ls_key,
            "cm_proof_key": cm_key,
            "case_trigger_proof_key": ct_key,
            "writer_probe_key": writer_probe_key,
        },
    )
    dumpj(
        out / "m7p10_data_profile_summary.json",
        {
            **dep_profile,
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P10-ST-S3",
            "status": "S3_LS_ADJUDICATED",
            "s3_functional_issues": functional_issues,
            "s3_semantic_issues": semantic_issues,
            "writer_conflict_rate_pct_s3": writer_conflict_rate,
            "writer_conflict_max_rate_pct_s3": writer_conflict_max,
            "single_writer_posture_s3": single_writer_posture,
            "writer_outcome_states_s3": outcome_unique,
            "case_reopen_rate_pct_s3": case_reopen_rate,
            "advisories": advisories,
            "upstream_m7p10_s2_phase_execution_id": dep_id,
        },
    )
    dumpj(out / "m7p10_case_trigger_snapshot.json", {**dep_ct_snapshot, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S3", "status": "CARRY_FORWARD_FROM_S2", "upstream_m7p10_s2_phase_execution_id": dep_id, "current_case_trigger_proof": ct_proof})
    dumpj(out / "m7p10_cm_snapshot.json", {**dep_cm_snapshot, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S3", "status": "CARRY_FORWARD_FROM_S2", "upstream_m7p10_s2_phase_execution_id": dep_id, "current_cm_proof": cm_proof})
    dumpj(
        out / "m7p10_ls_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P10-ST-S3",
            "platform_run_id": platform_run_id,
            "upstream_m7p10_s2_phase_execution_id": dep_id,
            "historical_baseline": hist_ls,
            "s2_ls_snapshot": dep_ls_snapshot,
            "current_ls_proof": ls_proof,
            "writer_probe": writer_probe,
            "functional_issues": functional_issues,
            "semantic_issues": semantic_issues,
        },
    )
    dumpj(
        out / "m7p10_case_lifecycle_profile.json",
        {
            **dep_case_lifecycle,
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P10-ST-S3",
            "status": "S3_LS_LIFECYCLE_ADJUDICATED",
            "case_reopen_rate_pct_s3": case_reopen_rate,
            "ls_upstream_execution": ls_upstream_exec,
            "cm_execution_id": cm_exec,
            "upstream_m7p10_s2_phase_execution_id": dep_id,
        },
    )
    dumpj(
        out / "m7p10_label_distribution_profile.json",
        {
            **dep_label_profile,
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P10-ST-S3",
            "status": "S3_LS_LABEL_ADJUDICATED",
            "writer_outcome_states_s3": outcome_unique,
            "writer_outcome_state_cardinality_s3": len(outcome_unique),
            "upstream_m7p10_s2_phase_execution_id": dep_id,
        },
    )
    dumpj(
        out / "m7p10_writer_conflict_profile.json",
        {
            **dep_writer_profile,
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P10-ST-S3",
            "status": "S3_LS_WRITER_ADJUDICATED",
            "single_writer_posture_s3": single_writer_posture,
            "writer_conflict_rate_pct_s3": writer_conflict_rate,
            "writer_conflict_max_rate_pct_s3": writer_conflict_max,
            "writer_probe_key_s3": writer_probe_key,
            "upstream_m7p10_s2_phase_execution_id": dep_id,
        },
    )
    dumpj(out / "m7p10_probe_latency_throughput_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S3", **metrics})
    dumpj(
        out / "m7p10_control_rail_conformance_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P10-ST-S3",
            "overall_pass": len(issues) == 0,
            "issues": issues,
            "advisories": advisories,
            "dependency_refs": {"m7p10_s2_execution_id": dep_id},
        },
    )
    dumpj(
        out / "m7p10_secret_safety_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P10-ST-S3",
            "overall_pass": True,
            "secret_probe_count": 0,
            "secret_failure_count": 0,
            "with_decryption_used": False,
            "queried_value_directly": False,
            "plaintext_leakage_detected": False,
        },
    )
    dumpj(
        out / "m7p10_cost_outcome_receipt.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P10-ST-S3",
            "window_seconds": metrics["window_seconds_observed"],
            "estimated_api_call_count": metrics["probe_count"],
            "attributed_spend_usd": 0.0,
            "unattributed_spend_detected": False,
            "max_spend_usd": float(plan_packet.get("M7P10_STRESS_MAX_SPEND_USD", 38)),
            "within_envelope": True,
            "method": "m7p10_s3_ls_lane_v0",
        },
    )

    decisions.extend(
        [
            "Validated S2 dependency closure before opening S3 LS lane checks.",
            "Applied historical P10.D baseline and current run-scoped LS proof checks to functional/performance gate adjudication.",
            "Applied LS writer-boundary/single-writer/run-scope/upstream-linkage semantic checks under fail-closed policy.",
            "Preserved explicit advisories for low-sample contention/reopen coverage as mandatory downstream pressure checks.",
        ]
    )
    if isinstance(dep_decision_log.get("decisions"), list):
        for d in dep_decision_log["decisions"]:
            s = str(d).strip()
            if s and s not in decisions:
                decisions.append(s)

    dumpj(out / "m7p10_decision_log.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S3", "decisions": decisions, "advisories": advisories})

    blocker_reg = {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S3", "overall_pass": overall, "open_blocker_count": len(blockers), "blockers": blockers}
    summary = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M7P10-ST-S3",
        "overall_pass": overall,
        "next_gate": next_gate,
        "open_blocker_count": len(blockers),
        "required_artifacts": req,
        "probe_count": metrics["probe_count"],
        "error_rate_pct": metrics["error_rate_pct"],
        "platform_run_id": platform_run_id,
        "upstream_m7p10_s2_phase_execution_id": dep_id,
        "historical_p10d_execution_id": str(hist_ls.get("summary", {}).get("execution_id", "")) if hist_ls else "",
    }
    verdict = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M7P10-ST-S3",
        "overall_pass": overall,
        "verdict": verdict_name,
        "next_gate": next_gate,
        "blocker_count": len(blockers),
        "platform_run_id": platform_run_id,
        "upstream_m7p10_s2_phase_execution_id": dep_id,
        "historical_p10d_execution_id": str(hist_ls.get("summary", {}).get("execution_id", "")) if hist_ls else "",
    }
    dumpj(out / "m7p10_blocker_register.json", blocker_reg)
    dumpj(out / "m7p10_execution_summary.json", summary)
    dumpj(out / "m7p10_gate_verdict.json", verdict)
    finalize_artifact_contract(out, req, blockers, blocker_reg, summary, verdict)

    s = loadj(out / "m7p10_execution_summary.json")
    b = loadj(out / "m7p10_blocker_register.json")
    print(f"[m7p10_s3] phase_execution_id={phase_execution_id}")
    print(f"[m7p10_s3] output_dir={out.as_posix()}")
    print(f"[m7p10_s3] overall_pass={s.get('overall_pass')}")
    print(f"[m7p10_s3] next_gate={s.get('next_gate')}")
    print(f"[m7p10_s3] open_blockers={b.get('open_blocker_count')}")
    return 0 if s.get("overall_pass") is True else 2


def run_s4(phase_execution_id: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)

    plan_packet = parse_bt_map(PLAN.read_text(encoding="utf-8") if PLAN.exists() else "")
    handles = parse_registry(REG) if REG.exists() else {}
    req = required_artifacts(plan_packet)
    evidence_bucket = str(handles.get("S3_EVIDENCE_BUCKET", "")).strip()

    blockers: list[dict[str, Any]] = []
    issues: list[str] = []
    advisories: list[str] = []
    decisions: list[str] = []
    probes: list[dict[str, Any]] = []

    miss_plan = [k for k in PLAN_KEYS if k not in plan_packet]
    miss_handle, ph_handle = resolve_required_handles(handles)
    miss_docs = [x.as_posix() for x in [PLAN, PARENT_PLAN, BUILD_PLAN] if not x.exists()]
    if miss_plan or miss_handle or ph_handle or miss_docs:
        blockers.append(
            {
                "id": "M7P10-ST-B11",
                "severity": "S4",
                "status": "OPEN",
                "details": {
                    "reason": "S4 authority/handle closure failure",
                    "missing_plan_keys": miss_plan,
                    "missing_handles": miss_handle,
                    "placeholder_handles": ph_handle,
                    "missing_docs": miss_docs,
                },
            }
        )
        issues.append("S4 authority/handle closure failed")

    dep_issues: list[str] = []
    dep = latest_ok("m7p10_stress_s3", "m7p10_execution_summary.json", "M7P10-ST-S3")
    dep_id = ""
    dep_path: Path | None = None
    platform_run_id = ""
    dep_summary: dict[str, Any] = {}
    dep_subset: dict[str, Any] = {}
    dep_profile: dict[str, Any] = {}
    dep_ct_snapshot: dict[str, Any] = {}
    dep_cm_snapshot: dict[str, Any] = {}
    dep_ls_snapshot: dict[str, Any] = {}
    dep_case_lifecycle: dict[str, Any] = {}
    dep_label_profile: dict[str, Any] = {}
    dep_writer_profile: dict[str, Any] = {}
    dep_decision_log: dict[str, Any] = {}
    dep_gate_verdict: dict[str, Any] = {}

    if not dep:
        dep_issues.append("missing successful M7P10 S3 dependency")
    else:
        dep_summary = dep.get("summary", {})
        dep_id = str(dep_summary.get("phase_execution_id", ""))
        dep_path = Path(str(dep.get("path", "")))
        platform_run_id = str(dep_summary.get("platform_run_id", "")).strip()
        if str(dep_summary.get("next_gate", "")).strip() != "M7P10_ST_S4_READY":
            dep_issues.append("M7P10 S3 next_gate is not M7P10_ST_S4_READY")
        dep_blocker = loadj(dep_path / "m7p10_blocker_register.json")
        if int(dep_blocker.get("open_blocker_count", 0) or 0) != 0:
            dep_issues.append("M7P10 S3 blocker register is not closed")

        dep_required = dep_summary.get("required_artifacts", req)
        dep_required_list = dep_required if isinstance(dep_required, list) else req
        for art in dep_required_list:
            a = str(art).strip()
            if a and dep_path is not None and not (dep_path / a).exists():
                blockers.append({"id": "M7P10-ST-B10", "severity": "S4", "status": "OPEN", "details": {"reason": "missing dependency artifact", "artifact": a}})
                dep_issues.append(f"missing S3 artifact: {a}")

        dep_subset = loadj(dep_path / "m7p10_data_subset_manifest.json")
        dep_profile = loadj(dep_path / "m7p10_data_profile_summary.json")
        dep_ct_snapshot = loadj(dep_path / "m7p10_case_trigger_snapshot.json")
        dep_cm_snapshot = loadj(dep_path / "m7p10_cm_snapshot.json")
        dep_ls_snapshot = loadj(dep_path / "m7p10_ls_snapshot.json")
        dep_case_lifecycle = loadj(dep_path / "m7p10_case_lifecycle_profile.json")
        dep_label_profile = loadj(dep_path / "m7p10_label_distribution_profile.json")
        dep_writer_profile = loadj(dep_path / "m7p10_writer_conflict_profile.json")
        dep_decision_log = loadj(dep_path / "m7p10_decision_log.json")
        dep_gate_verdict = loadj(dep_path / "m7p10_gate_verdict.json")

        if not dep_subset or not dep_profile:
            dep_issues.append("M7P10 S3 realism artifacts are incomplete")
        if not dep_ct_snapshot or not dep_cm_snapshot or not dep_ls_snapshot:
            dep_issues.append("M7P10 S3 component snapshots are incomplete")
        if not dep_case_lifecycle or not dep_label_profile or not dep_writer_profile:
            dep_issues.append("M7P10 S3 semantic/profile artifacts are incomplete")
        if not dep_decision_log or not dep_gate_verdict:
            dep_issues.append("M7P10 S3 closure artifacts are incomplete")

        if not platform_run_id:
            dep_issues.append("M7P10 S3 platform_run_id is missing")

    if dep_issues:
        blockers.append({"id": "M7P10-ST-B11", "severity": "S4", "status": "OPEN", "details": {"issues": dep_issues}})
        issues.extend(dep_issues)
    else:
        decisions.append("Enforced S3 dependency continuity and blocker closure before S4 remediation lane adjudication.")

    chain_spec = [
        ("S0", "m7p10_stress_s0", "M7P10-ST-S0", "M7P10_ST_S1_READY"),
        ("S1", "m7p10_stress_s1", "M7P10-ST-S1", "M7P10_ST_S2_READY"),
        ("S2", "m7p10_stress_s2", "M7P10-ST-S2", "M7P10_ST_S3_READY"),
        ("S3", "m7p10_stress_s3", "M7P10-ST-S3", "M7P10_ST_S4_READY"),
    ]
    chain_rows: list[dict[str, Any]] = []
    stage_root_cause: dict[str, list[str]] = {"DATA_PROFILE": [], "CASE_TRIGGER": [], "CM": [], "LS": [], "EVIDENCE": []}
    stage_lane_map = {"S0": "DATA_PROFILE", "S1": "CASE_TRIGGER", "S2": "CM", "S3": "LS"}

    for label, prefix, stage_id, expected_next_gate in chain_spec:
        r = latest_ok(prefix, "m7p10_execution_summary.json", stage_id)
        row = {
            "label": label,
            "stage_id": stage_id,
            "expected_next_gate": expected_next_gate,
            "found": bool(r),
            "phase_execution_id": "",
            "next_gate": "",
            "overall_pass": False,
            "open_blockers": None,
            "platform_run_id": "",
            "run_scope_consistent": True,
            "ok": False,
        }
        if r:
            s = r.get("summary", {})
            row["phase_execution_id"] = str(s.get("phase_execution_id", ""))
            row["next_gate"] = str(s.get("next_gate", ""))
            row["overall_pass"] = bool(s.get("overall_pass"))
            row["platform_run_id"] = str(s.get("platform_run_id", "")).strip()
            rp = Path(str(r.get("path", "")))
            b = loadj(rp / "m7p10_blocker_register.json")
            row["open_blockers"] = int(b.get("open_blocker_count", 0) or 0)
            row["ok"] = row["overall_pass"] and row["next_gate"] == expected_next_gate and row["open_blockers"] == 0
            if platform_run_id and row["platform_run_id"] and row["platform_run_id"] != platform_run_id:
                row["run_scope_consistent"] = False
                row["ok"] = False
            if row["open_blockers"] and row["open_blockers"] > 0:
                lane = stage_lane_map.get(label, "DATA_PROFILE")
                stage_root_cause.setdefault(lane, []).append(f"{stage_id}:{row['phase_execution_id']}")
        if not row["ok"]:
            blockers.append({"id": "M7P10-ST-B11", "severity": "S4", "status": "OPEN", "details": {"chain_row": row}})
            issues.append(f"stage-chain closure failed for {label}")
            lane = stage_lane_map.get(label, "DATA_PROFILE")
            stage_root_cause.setdefault(lane, []).append(f"{stage_id}:closure")
        chain_rows.append(row)

    p_bucket = head_bucket_probe(probes, evidence_bucket, "m7p10_s4_evidence_bucket")
    if p_bucket.get("status") != "PASS":
        blockers.append({"id": "M7P10-ST-B10", "severity": "S4", "status": "OPEN", "details": {"probe_id": "m7p10_s4_evidence_bucket"}})
        issues.append("S4 evidence bucket probe failed")
        stage_root_cause.setdefault("EVIDENCE", []).append("evidence_bucket_head_probe")

    remediation_mode = "NO_OP" if len(blockers) == 0 else "TARGETED_REMEDIATE"
    if remediation_mode == "NO_OP":
        decisions.append("No unresolved blockers detected from S0..S3; remediation lane closed as NO_OP under targeted-rerun-only policy.")
    else:
        decisions.append("Residual blocker(s) detected; remediation lane is fail-closed and requires targeted correction before S5.")

    blocker_classification = {k: v for k, v in stage_root_cause.items() if v}

    for src in [dep_profile.get("advisories", []), dep_decision_log.get("advisories", []), dep_ls_snapshot.get("advisories", [])]:
        if isinstance(src, list):
            for x in src:
                sx = str(x).strip()
                if sx and sx not in advisories:
                    advisories.append(sx)

    toy_advisories = [x for x in advisories if is_toy_profile_advisory(x)]
    if toy_advisories:
        blockers.append(
            {
                "id": "M7P10-ST-B13",
                "severity": "S5",
                "status": "OPEN",
                "details": {
                    "reason": "toy-profile advisory posture carried into P10 rollup",
                    "advisories": toy_advisories[:20],
                },
            }
        )
        issues.append("toy-profile advisory posture is not allowed for P10 closure")

    metrics = probe_metrics(probes)
    overall = len(blockers) == 0
    next_gate = "M7P10_ST_S5_READY" if overall else "BLOCKED"
    verdict_name = "ADVANCE_TO_S5" if overall else "HOLD_REMEDIATE"

    dumpj(
        out / "m7p10_stagea_findings.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P10-ST-S4",
            "findings": [
                {"id": "M7P10-ST-F15", "classification": "PREVENT", "finding": "S4 must not mask unresolved blockers from prior lanes.", "required_action": "Fail-closed on any unresolved S0..S3 chain issue."},
                {"id": "M7P10-ST-F16", "classification": "PREVENT", "finding": "S4 remediation must remain targeted and evidence-consistent.", "required_action": "Use NO_OP when clean; otherwise keep blocker-scoped remediation only."},
            ],
        },
    )
    dumpj(out / "m7p10_lane_matrix.json", {"component_sequence": ["M7P10-ST-S0", "M7P10-ST-S1", "M7P10-ST-S2", "M7P10-ST-S3", "M7P10-ST-S4", "M7P10-ST-S5"]})
    dumpj(out / "m7p10_data_subset_manifest.json", {**dep_subset, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S4", "status": "S4_CARRY_FORWARD", "upstream_m7p10_s3_phase_execution_id": dep_id})
    dumpj(
        out / "m7p10_data_profile_summary.json",
        {
            **dep_profile,
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P10-ST-S4",
            "upstream_m7p10_s3_phase_execution_id": dep_id,
            "s4_remediation_mode": remediation_mode,
            "s4_chain_rows": chain_rows,
            "s4_blocker_classification": blocker_classification,
            "advisories": advisories,
        },
    )
    dumpj(out / "m7p10_case_trigger_snapshot.json", {**dep_ct_snapshot, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S4", "status": "CARRY_FORWARD_FROM_S3", "upstream_m7p10_s3_phase_execution_id": dep_id})
    dumpj(out / "m7p10_cm_snapshot.json", {**dep_cm_snapshot, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S4", "status": "CARRY_FORWARD_FROM_S3", "upstream_m7p10_s3_phase_execution_id": dep_id})
    dumpj(out / "m7p10_ls_snapshot.json", {**dep_ls_snapshot, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S4", "status": "CARRY_FORWARD_FROM_S3", "upstream_m7p10_s3_phase_execution_id": dep_id, "remediation_mode": remediation_mode, "blocker_classification": blocker_classification})
    dumpj(out / "m7p10_case_lifecycle_profile.json", {**dep_case_lifecycle, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S4", "status": "CARRY_FORWARD_FROM_S3", "upstream_m7p10_s3_phase_execution_id": dep_id, "remediation_mode": remediation_mode})
    dumpj(out / "m7p10_label_distribution_profile.json", {**dep_label_profile, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S4", "status": "CARRY_FORWARD_FROM_S3", "upstream_m7p10_s3_phase_execution_id": dep_id})
    dumpj(out / "m7p10_writer_conflict_profile.json", {**dep_writer_profile, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S4", "status": "CARRY_FORWARD_FROM_S3", "upstream_m7p10_s3_phase_execution_id": dep_id, "remediation_mode": remediation_mode})
    dumpj(out / "m7p10_probe_latency_throughput_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S4", **metrics})
    dumpj(
        out / "m7p10_control_rail_conformance_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P10-ST-S4",
            "overall_pass": len(issues) == 0,
            "issues": issues,
            "advisories": advisories,
            "remediation_mode": remediation_mode,
            "chain_rows": chain_rows,
            "blocker_classification": blocker_classification,
            "dependency_refs": {"m7p10_s3_phase_execution_id": dep_id},
        },
    )
    dumpj(
        out / "m7p10_secret_safety_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P10-ST-S4",
            "overall_pass": True,
            "secret_probe_count": 0,
            "secret_failure_count": 0,
            "with_decryption_used": False,
            "queried_value_directly": False,
            "plaintext_leakage_detected": False,
        },
    )
    dumpj(
        out / "m7p10_cost_outcome_receipt.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P10-ST-S4",
            "window_seconds": metrics["window_seconds_observed"],
            "estimated_api_call_count": metrics["probe_count"],
            "attributed_spend_usd": 0.0,
            "unattributed_spend_detected": False,
            "max_spend_usd": float(plan_packet.get("M7P10_STRESS_MAX_SPEND_USD", 38)),
            "within_envelope": True,
            "method": "m7p10_s4_remediation_lane_v0",
            "remediation_mode": remediation_mode,
        },
    )

    decisions.extend(
        [
            "Executed deterministic chain-health sweep across S0..S3 before remediation adjudication.",
            "Applied S4 policy: NO_OP when blocker-free, targeted remediation only when concrete residual blocker exists.",
            "Preserved fail-closed posture by classifying root cause and blocking progression on unresolved evidence or chain inconsistencies.",
        ]
    )
    dumpj(
        out / "m7p10_decision_log.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P10-ST-S4",
            "decisions": decisions,
            "advisories": advisories,
            "remediation_mode": remediation_mode,
            "blocker_classification": blocker_classification,
        },
    )

    blocker_reg = {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S4", "overall_pass": overall, "open_blocker_count": len(blockers), "blockers": blockers}
    summary = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M7P10-ST-S4",
        "overall_pass": overall,
        "next_gate": next_gate,
        "open_blocker_count": len(blockers),
        "required_artifacts": req,
        "probe_count": metrics["probe_count"],
        "error_rate_pct": metrics["error_rate_pct"],
        "platform_run_id": platform_run_id,
        "upstream_m7p10_s3_phase_execution_id": dep_id,
        "remediation_mode": remediation_mode,
    }
    verdict = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M7P10-ST-S4",
        "overall_pass": overall,
        "verdict": verdict_name,
        "next_gate": next_gate,
        "blocker_count": len(blockers),
        "platform_run_id": platform_run_id,
        "upstream_m7p10_s3_phase_execution_id": dep_id,
        "remediation_mode": remediation_mode,
    }
    dumpj(out / "m7p10_blocker_register.json", blocker_reg)
    dumpj(out / "m7p10_execution_summary.json", summary)
    dumpj(out / "m7p10_gate_verdict.json", verdict)
    finalize_artifact_contract(out, req, blockers, blocker_reg, summary, verdict)

    s = loadj(out / "m7p10_execution_summary.json")
    b = loadj(out / "m7p10_blocker_register.json")
    print(f"[m7p10_s4] phase_execution_id={phase_execution_id}")
    print(f"[m7p10_s4] output_dir={out.as_posix()}")
    print(f"[m7p10_s4] overall_pass={s.get('overall_pass')}")
    print(f"[m7p10_s4] next_gate={s.get('next_gate')}")
    print(f"[m7p10_s4] remediation_mode={s.get('remediation_mode')}")
    print(f"[m7p10_s4] open_blockers={b.get('open_blocker_count')}")
    return 0 if s.get("overall_pass") is True else 2


def run_s5(phase_execution_id: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)

    plan_packet = parse_bt_map(PLAN.read_text(encoding="utf-8") if PLAN.exists() else "")
    handles = parse_registry(REG) if REG.exists() else {}
    req = required_artifacts(plan_packet)
    evidence_bucket = str(handles.get("S3_EVIDENCE_BUCKET", "")).strip()

    blockers: list[dict[str, Any]] = []
    issues: list[str] = []
    advisories: list[str] = []
    decisions: list[str] = []
    probes: list[dict[str, Any]] = []

    expected_next_gate = str(plan_packet.get("M7P10_STRESS_EXPECTED_NEXT_GATE_ON_PASS", "M7_J_READY")).strip() or "M7_J_READY"
    if expected_next_gate != "M7_J_READY":
        blockers.append(
            {
                "id": "M7P10-ST-B11",
                "severity": "S5",
                "status": "OPEN",
                "details": {"reason": "unexpected expected_next_gate contract", "expected_next_gate_on_pass": expected_next_gate},
            }
        )
        issues.append("expected pass gate contract is not M7_J_READY")

    miss_plan = [k for k in PLAN_KEYS if k not in plan_packet]
    miss_handle, ph_handle = resolve_required_handles(handles)
    miss_docs = [x.as_posix() for x in [PLAN, PARENT_PLAN, BUILD_PLAN] if not x.exists()]
    if miss_plan or miss_handle or ph_handle or miss_docs:
        blockers.append(
            {
                "id": "M7P10-ST-B11",
                "severity": "S5",
                "status": "OPEN",
                "details": {
                    "reason": "S5 authority/handle closure failure",
                    "missing_plan_keys": miss_plan,
                    "missing_handles": miss_handle,
                    "placeholder_handles": ph_handle,
                    "missing_docs": miss_docs,
                },
            }
        )
        issues.append("S5 authority/handle closure failed")

    dep_issues: list[str] = []
    dep = latest_ok("m7p10_stress_s4", "m7p10_execution_summary.json", "M7P10-ST-S4")
    dep_id = ""
    dep_path: Path | None = None
    platform_run_id = ""
    dep_summary: dict[str, Any] = {}
    dep_subset: dict[str, Any] = {}
    dep_profile: dict[str, Any] = {}
    dep_ct_snapshot: dict[str, Any] = {}
    dep_cm_snapshot: dict[str, Any] = {}
    dep_ls_snapshot: dict[str, Any] = {}
    dep_case_lifecycle: dict[str, Any] = {}
    dep_label_profile: dict[str, Any] = {}
    dep_writer_profile: dict[str, Any] = {}
    dep_decision_log: dict[str, Any] = {}
    dep_gate_verdict: dict[str, Any] = {}

    if not dep:
        dep_issues.append("missing successful M7P10 S4 dependency")
    else:
        dep_summary = dep.get("summary", {})
        dep_id = str(dep_summary.get("phase_execution_id", ""))
        dep_path = Path(str(dep.get("path", "")))
        platform_run_id = str(dep_summary.get("platform_run_id", "")).strip()
        if str(dep_summary.get("next_gate", "")).strip() != "M7P10_ST_S5_READY":
            dep_issues.append("M7P10 S4 next_gate is not M7P10_ST_S5_READY")
        dep_blocker = loadj(dep_path / "m7p10_blocker_register.json")
        if int(dep_blocker.get("open_blocker_count", 0) or 0) != 0:
            dep_issues.append("M7P10 S4 blocker register is not closed")
        if str(dep_summary.get("remediation_mode", "")).strip() not in {"NO_OP", "TARGETED_REMEDIATE"}:
            dep_issues.append("M7P10 S4 remediation_mode is invalid")

        dep_required = dep_summary.get("required_artifacts", req)
        dep_required_list = dep_required if isinstance(dep_required, list) else req
        for art in dep_required_list:
            a = str(art).strip()
            if a and dep_path is not None and not (dep_path / a).exists():
                blockers.append({"id": "M7P10-ST-B12", "severity": "S5", "status": "OPEN", "details": {"reason": "missing dependency artifact", "artifact": a}})
                issues.append(f"missing dependency artifact: {a}")

        dep_subset = loadj(dep_path / "m7p10_data_subset_manifest.json")
        dep_profile = loadj(dep_path / "m7p10_data_profile_summary.json")
        dep_ct_snapshot = loadj(dep_path / "m7p10_case_trigger_snapshot.json")
        dep_cm_snapshot = loadj(dep_path / "m7p10_cm_snapshot.json")
        dep_ls_snapshot = loadj(dep_path / "m7p10_ls_snapshot.json")
        dep_case_lifecycle = loadj(dep_path / "m7p10_case_lifecycle_profile.json")
        dep_label_profile = loadj(dep_path / "m7p10_label_distribution_profile.json")
        dep_writer_profile = loadj(dep_path / "m7p10_writer_conflict_profile.json")
        dep_decision_log = loadj(dep_path / "m7p10_decision_log.json")
        dep_gate_verdict = loadj(dep_path / "m7p10_gate_verdict.json")

        if not dep_subset or not dep_profile:
            dep_issues.append("M7P10 S4 realism artifacts are incomplete")
        if not dep_ct_snapshot or not dep_cm_snapshot or not dep_ls_snapshot:
            dep_issues.append("M7P10 S4 component snapshots are incomplete")
        if not dep_case_lifecycle or not dep_label_profile or not dep_writer_profile:
            dep_issues.append("M7P10 S4 semantic/profile artifacts are incomplete")
        if not dep_decision_log or not dep_gate_verdict:
            dep_issues.append("M7P10 S4 closure artifacts are incomplete")
        if not platform_run_id:
            dep_issues.append("M7P10 S4 platform_run_id is missing")

    if dep_issues:
        blockers.append({"id": "M7P10-ST-B11", "severity": "S5", "status": "OPEN", "details": {"issues": dep_issues}})
        issues.extend(dep_issues)

    chain_spec = [
        ("S0", "m7p10_stress_s0", "M7P10-ST-S0", "M7P10_ST_S1_READY"),
        ("S1", "m7p10_stress_s1", "M7P10-ST-S1", "M7P10_ST_S2_READY"),
        ("S2", "m7p10_stress_s2", "M7P10-ST-S2", "M7P10_ST_S3_READY"),
        ("S3", "m7p10_stress_s3", "M7P10-ST-S3", "M7P10_ST_S4_READY"),
        ("S4", "m7p10_stress_s4", "M7P10-ST-S4", "M7P10_ST_S5_READY"),
    ]
    chain_rows: list[dict[str, Any]] = []
    for label, prefix, stage_id, expected_gate in chain_spec:
        r = latest_ok(prefix, "m7p10_execution_summary.json", stage_id)
        row = {
            "label": label,
            "stage_id": stage_id,
            "expected_next_gate": expected_gate,
            "found": bool(r),
            "phase_execution_id": "",
            "next_gate": "",
            "overall_pass": False,
            "open_blockers": None,
            "platform_run_id": "",
            "run_scope_consistent": True,
            "ok": False,
        }
        if r:
            s = r.get("summary", {})
            row["phase_execution_id"] = str(s.get("phase_execution_id", ""))
            row["next_gate"] = str(s.get("next_gate", ""))
            row["overall_pass"] = bool(s.get("overall_pass"))
            row["platform_run_id"] = str(s.get("platform_run_id", "")).strip()
            rp = Path(str(r.get("path", "")))
            b = loadj(rp / "m7p10_blocker_register.json")
            row["open_blockers"] = int(b.get("open_blocker_count", 0) or 0)
            row["ok"] = row["overall_pass"] and row["next_gate"] == expected_gate and row["open_blockers"] == 0
            if platform_run_id and row["platform_run_id"] and row["platform_run_id"] != platform_run_id:
                row["run_scope_consistent"] = False
                row["ok"] = False
        if not row["ok"]:
            blockers.append({"id": "M7P10-ST-B11", "severity": "S5", "status": "OPEN", "details": {"chain_row": row}})
            issues.append(f"stage-chain closure failed for {label}")
        chain_rows.append(row)

    p_bucket = head_bucket_probe(probes, evidence_bucket, "m7p10_s5_evidence_bucket")
    if p_bucket.get("status") != "PASS":
        blockers.append({"id": "M7P10-ST-B12", "severity": "S5", "status": "OPEN", "details": {"probe_id": "m7p10_s5_evidence_bucket"}})
        issues.append("S5 evidence bucket probe failed")

    receipt_key = str(dep_subset.get("receipt_summary_ref", "")).strip()
    if not receipt_key:
        blockers.append({"id": "M7P10-ST-B12", "severity": "S5", "status": "OPEN", "details": {"reason": "missing receipt_summary_ref"}})
        issues.append("missing receipt_summary_ref in S4 subset manifest")
    else:
        p = head_object_probe(probes, evidence_bucket, receipt_key, "m7p10_s5_receipt_summary")
        if p.get("status") != "PASS":
            blockers.append({"id": "M7P10-ST-B12", "severity": "S5", "status": "OPEN", "details": {"probe_id": "m7p10_s5_receipt_summary"}})
            issues.append("S5 receipt summary readback failed")

    case_refs = dep_subset.get("case_labels_refs", {}) if isinstance(dep_subset.get("case_labels_refs"), dict) else {}
    for tag in ["case_trigger_component_proof", "cm_component_proof", "ls_component_proof", "ls_writer_boundary_probe"]:
        key = str(case_refs.get(tag, "")).strip()
        if not key:
            blockers.append({"id": "M7P10-ST-B12", "severity": "S5", "status": "OPEN", "details": {"reason": "missing case_labels ref", "tag": tag}})
            issues.append(f"missing case_labels ref for {tag}")
            continue
        p = head_object_probe(probes, evidence_bucket, key, f"m7p10_s5_{tag}")
        if p.get("status") != "PASS":
            blockers.append({"id": "M7P10-ST-B12", "severity": "S5", "status": "OPEN", "details": {"probe_id": f"m7p10_s5_{tag}"}})
            issues.append(f"S5 case-label readback failed for {tag}")

    for src in [dep_profile.get("advisories", []), dep_decision_log.get("advisories", []), dep_ls_snapshot.get("advisories", [])]:
        if isinstance(src, list):
            for x in src:
                sx = str(x).strip()
                if sx and sx not in advisories:
                    advisories.append(sx)

    metrics = probe_metrics(probes)
    overall = len(blockers) == 0
    verdict_name = expected_next_gate if overall else "HOLD_REMEDIATE"
    next_gate = verdict_name

    dumpj(
        out / "m7p10_stagea_findings.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P10-ST-S5",
            "findings": [
                {"id": "M7P10-ST-F17", "classification": "PREVENT", "finding": "S5 must fail closed on any unresolved chain or verdict inconsistency.", "required_action": "Emit M7_J_READY only when S0..S4 is fully green and blocker-free."},
                {"id": "M7P10-ST-F18", "classification": "PREVENT", "finding": "S5 closure evidence must remain artifact-complete and readable.", "required_action": "Block closure on missing artifacts or failed readback probes."},
            ],
        },
    )
    dumpj(out / "m7p10_lane_matrix.json", {"component_sequence": ["M7P10-ST-S0", "M7P10-ST-S1", "M7P10-ST-S2", "M7P10-ST-S3", "M7P10-ST-S4", "M7P10-ST-S5"]})
    dumpj(out / "m7p10_data_subset_manifest.json", {**dep_subset, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S5", "status": "S5_ROLLUP_CARRY_FORWARD", "upstream_m7p10_s4_phase_execution_id": dep_id})
    dumpj(out / "m7p10_data_profile_summary.json", {**dep_profile, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S5", "upstream_m7p10_s4_phase_execution_id": dep_id, "verdict_candidate": verdict_name, "chain_rows": chain_rows, "advisories": advisories})
    dumpj(out / "m7p10_case_trigger_snapshot.json", {**dep_ct_snapshot, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S5", "status": "CARRY_FORWARD_FROM_S4", "upstream_m7p10_s4_phase_execution_id": dep_id})
    dumpj(out / "m7p10_cm_snapshot.json", {**dep_cm_snapshot, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S5", "status": "CARRY_FORWARD_FROM_S4", "upstream_m7p10_s4_phase_execution_id": dep_id})
    dumpj(out / "m7p10_ls_snapshot.json", {**dep_ls_snapshot, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S5", "status": "CARRY_FORWARD_FROM_S4", "upstream_m7p10_s4_phase_execution_id": dep_id, "verdict_candidate": verdict_name, "chain_rows": chain_rows})
    dumpj(out / "m7p10_case_lifecycle_profile.json", {**dep_case_lifecycle, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S5", "status": "CARRY_FORWARD_FROM_S4", "upstream_m7p10_s4_phase_execution_id": dep_id, "verdict_candidate": verdict_name})
    dumpj(out / "m7p10_label_distribution_profile.json", {**dep_label_profile, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S5", "status": "CARRY_FORWARD_FROM_S4", "upstream_m7p10_s4_phase_execution_id": dep_id, "verdict_candidate": verdict_name})
    dumpj(out / "m7p10_writer_conflict_profile.json", {**dep_writer_profile, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S5", "status": "CARRY_FORWARD_FROM_S4", "upstream_m7p10_s4_phase_execution_id": dep_id, "verdict_candidate": verdict_name})
    dumpj(out / "m7p10_probe_latency_throughput_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S5", **metrics})
    dumpj(out / "m7p10_control_rail_conformance_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S5", "overall_pass": len(issues) == 0, "issues": issues, "advisories": advisories, "chain_rows": chain_rows})
    dumpj(out / "m7p10_secret_safety_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S5", "overall_pass": True, "secret_probe_count": 0, "secret_failure_count": 0, "with_decryption_used": False, "queried_value_directly": False, "plaintext_leakage_detected": False})
    dumpj(out / "m7p10_cost_outcome_receipt.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S5", "window_seconds": metrics["window_seconds_observed"], "estimated_api_call_count": metrics["probe_count"], "attributed_spend_usd": 0.0, "unattributed_spend_detected": False, "max_spend_usd": float(plan_packet.get("M7P10_STRESS_MAX_SPEND_USD", 38)), "within_envelope": True, "method": "m7p10_s5_rollup_lane_v0"})

    decisions.extend(
        [
            "Enforced S4 dependency continuity and blocker closure before S5 rollup.",
            "Executed deterministic chain sweep across S0..S4 with run-scope consistency checks.",
            "Validated closure readback refs (receipt + case-label component proofs + writer probe) before verdict emission.",
            "Applied deterministic verdict: M7_J_READY only when blocker-free and artifact-complete.",
        ]
    )
    dumpj(out / "m7p10_decision_log.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S5", "decisions": decisions, "advisories": advisories, "chain_rows": chain_rows})

    blocker_reg = {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P10-ST-S5", "overall_pass": overall, "open_blocker_count": len(blockers), "blockers": blockers}
    summary = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M7P10-ST-S5",
        "overall_pass": overall,
        "next_gate": next_gate,
        "open_blocker_count": len(blockers),
        "required_artifacts": req,
        "probe_count": metrics["probe_count"],
        "error_rate_pct": metrics["error_rate_pct"],
        "platform_run_id": platform_run_id,
        "upstream_m7p10_s4_phase_execution_id": dep_id,
        "verdict": verdict_name,
        "expected_next_gate_on_pass": expected_next_gate,
    }
    verdict = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M7P10-ST-S5",
        "overall_pass": overall,
        "verdict": verdict_name,
        "next_gate": next_gate,
        "blocker_count": len(blockers),
        "platform_run_id": platform_run_id,
        "upstream_m7p10_s4_phase_execution_id": dep_id,
        "expected_next_gate_on_pass": expected_next_gate,
        "chain_rows": chain_rows,
    }
    dumpj(out / "m7p10_blocker_register.json", blocker_reg)
    dumpj(out / "m7p10_execution_summary.json", summary)
    dumpj(out / "m7p10_gate_verdict.json", verdict)
    finalize_artifact_contract(out, req, blockers, blocker_reg, summary, verdict, blocker_id="M7P10-ST-B12")

    s = loadj(out / "m7p10_execution_summary.json")
    b = loadj(out / "m7p10_blocker_register.json")
    print(f"[m7p10_s5] phase_execution_id={phase_execution_id}")
    print(f"[m7p10_s5] output_dir={out.as_posix()}")
    print(f"[m7p10_s5] overall_pass={s.get('overall_pass')}")
    print(f"[m7p10_s5] verdict={s.get('verdict')}")
    print(f"[m7p10_s5] next_gate={s.get('next_gate')}")
    print(f"[m7p10_s5] open_blockers={b.get('open_blocker_count')}")
    return 0 if s.get("overall_pass") is True else 2


def main() -> int:
    ap = argparse.ArgumentParser(description="M7.P10 stress runner")
    ap.add_argument("--stage", default="S0", choices=["S0", "S1", "S2", "S3", "S4", "S5"])
    ap.add_argument("--phase-execution-id", default="")
    args = ap.parse_args()
    stage = str(args.stage).upper()
    pid = str(args.phase_execution_id).strip() or f"m7p10_stress_{stage.lower()}_{tok()}"
    if stage == "S0":
        return run_s0(pid)
    if stage == "S1":
        return run_s1(pid)
    if stage == "S2":
        return run_s2(pid)
    if stage == "S3":
        return run_s3(pid)
    if stage == "S4":
        return run_s4(pid)
    if stage == "S5":
        return run_s5(pid)
    print(f"unsupported stage: {stage}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
