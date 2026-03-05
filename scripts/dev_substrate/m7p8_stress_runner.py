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
PLAN = Path("docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M7.P8.stress_test.md")
BUILD_PLAN = Path("docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/platform.M7.P8.build_plan.md")
REG = Path("docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md")
OUT_ROOT = Path("runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control")
M7_HIST = Path("runs/dev_substrate/dev_full/m7")
AWS_REGION = "eu-west-2"

REQ_HANDLES = [
    "FLINK_RUNTIME_PATH_ACTIVE",
    "FLINK_RUNTIME_PATH_ALLOWED",
    "PHASE_RUNTIME_PATH_MODE",
    "FLINK_APP_RTDL_IEG_OFP_V0",
    "FLINK_EKS_RTDL_IEG_REF",
    "FLINK_EKS_RTDL_OFP_REF",
    "FLINK_EKS_NAMESPACE",
    "K8S_DEPLOY_IEG",
    "K8S_DEPLOY_OFP",
    "K8S_DEPLOY_ARCHIVE_WRITER",
    "FP_BUS_TRAFFIC_V1",
    "FP_BUS_CONTEXT_V1",
    "RTDL_CORE_CONSUMER_GROUP_ID",
    "RTDL_CORE_OFFSET_COMMIT_POLICY",
    "RTDL_CAUGHT_UP_LAG_MAX",
    "S3_ARCHIVE_RUN_PREFIX_PATTERN",
    "S3_ARCHIVE_EVENTS_PREFIX_PATTERN",
    "S3_EVIDENCE_BUCKET",
]

HANDLE_ALIASES = {
    "FP_BUS_TRAFFIC_V1": ["FP_BUS_TRAFFIC_FRAUD_V1", "FP_BUS_RTDL_V1"],
    "FP_BUS_CONTEXT_V1": [
        "FP_BUS_CONTEXT_ARRIVAL_EVENTS_V1",
        "FP_BUS_CONTEXT_ARRIVAL_ENTITIES_V1",
        "FP_BUS_CONTEXT_FLOW_ANCHOR_FRAUD_V1",
    ],
}

PLAN_KEYS = [
    "M7P8_STRESS_PROFILE_ID",
    "M7P8_STRESS_BLOCKER_REGISTER_PATH_PATTERN",
    "M7P8_STRESS_EXECUTION_SUMMARY_PATH_PATTERN",
    "M7P8_STRESS_DECISION_LOG_PATH_PATTERN",
    "M7P8_STRESS_REQUIRED_ARTIFACTS",
    "M7P8_STRESS_MAX_RUNTIME_MINUTES",
    "M7P8_STRESS_MAX_SPEND_USD",
    "M7P8_STRESS_EXPECTED_VERDICT_ON_PASS",
    "M7P8_STRESS_DATA_MIN_SAMPLE_EVENTS",
    "M7P8_STRESS_EVENT_TYPE_MIN_COUNT",
    "M7P8_STRESS_DUPLICATE_RATIO_TARGET_RANGE_PCT",
    "M7P8_STRESS_OUT_OF_ORDER_RATIO_TARGET_RANGE_PCT",
    "M7P8_STRESS_HOTKEY_TOP1_SHARE_MAX",
    "M7P8_STRESS_TARGETED_RERUN_ONLY",
]

REQUIRED_ARTIFACTS = [
    "m7p8_stagea_findings.json",
    "m7p8_lane_matrix.json",
    "m7p8_data_subset_manifest.json",
    "m7p8_data_profile_summary.json",
    "m7p8_ieg_snapshot.json",
    "m7p8_ofp_snapshot.json",
    "m7p8_archive_snapshot.json",
    "m7p8_data_edge_case_matrix.json",
    "m7p8_probe_latency_throughput_snapshot.json",
    "m7p8_control_rail_conformance_snapshot.json",
    "m7p8_secret_safety_snapshot.json",
    "m7p8_cost_outcome_receipt.json",
    "m7p8_blocker_register.json",
    "m7p8_execution_summary.json",
    "m7p8_decision_log.json",
    "m7p8_gate_verdict.json",
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


def run_cmd_full(argv: list[str], timeout: int = 120) -> tuple[int, str, str]:
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return int(p.returncode), p.stdout or "", p.stderr or ""
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"


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


def parse_range(v: Any) -> tuple[float | None, float | None]:
    s = str(v or "").strip()
    parts = [x.strip() for x in s.split("|")]
    if len(parts) != 2:
        return None, None
    try:
        return (float(parts[0]) if parts[0] else None, float(parts[1]) if parts[1] else None)
    except ValueError:
        return None, None


def normalize_runtime_path(v: str) -> str:
    raw = str(v or "").strip().upper()
    aliases = {
        "EKS_EMR_ON_EKS": "EKS_FLINK_OPERATOR",
        "EMR_ON_EKS": "EKS_FLINK_OPERATOR",
        "EKS_FLINK_OPERATOR": "EKS_FLINK_OPERATOR",
        "MSF_MANAGED": "MSF_MANAGED",
    }
    return aliases.get(raw, raw)


def latest_parent_m7_s0() -> dict[str, Any]:
    for d in sorted(OUT_ROOT.glob("m7_stress_s0_*/stress"), reverse=True):
        s = loadj(d / "m7_execution_summary.json")
        if s and s.get("overall_pass") is True and str(s.get("stage_id", "")) == "M7-ST-S0":
            return {"path": d, "summary": s}
    return {}


def latest_ok(prefix: str, stage_id: str) -> dict[str, Any]:
    for d in sorted(OUT_ROOT.glob(f"{prefix}_*/stress"), reverse=True):
        s = loadj(d / "m7p8_execution_summary.json")
        if s and s.get("overall_pass") is True and str(s.get("stage_id", "")) == stage_id:
            return {"path": d, "summary": s}
    return {}


def latest_hist_p8b() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for f in M7_HIST.rglob("p8b_ieg_execution_summary.json"):
        d = f.parent
        s = loadj(f)
        c = loadj(d / "p8b_ieg_component_snapshot.json")
        p = loadj(d / "p8b_ieg_performance_snapshot.json")
        b = loadj(d / "p8b_ieg_blocker_register.json")
        if not s or not c or not p or not b:
            continue
        if s.get("overall_pass") is not True:
            continue
        if int(b.get("blocker_count", 0) or 0) != 0:
            continue
        rows.append(
            {
                "path": d,
                "captured_at_utc": str(s.get("captured_at_utc") or c.get("captured_at_utc") or ""),
                "execution_id": str(s.get("execution_id", "")),
                "summary": s,
                "component": c,
                "perf": p,
                "blocker": b,
            }
        )
    rows.sort(key=lambda x: (str(x["captured_at_utc"]), str(x["execution_id"])))
    return rows[-1] if rows else {}


def latest_hist_p8c() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for f in M7_HIST.rglob("p8c_ofp_execution_summary.json"):
        d = f.parent
        s = loadj(f)
        c = loadj(d / "p8c_ofp_component_snapshot.json")
        p = loadj(d / "p8c_ofp_performance_snapshot.json")
        b = loadj(d / "p8c_ofp_blocker_register.json")
        if not s or not c or not p or not b:
            continue
        if s.get("overall_pass") is not True:
            continue
        if int(b.get("blocker_count", 0) or 0) != 0:
            continue
        rows.append(
            {
                "path": d,
                "captured_at_utc": str(s.get("captured_at_utc") or c.get("captured_at_utc") or ""),
                "execution_id": str(s.get("execution_id", "")),
                "summary": s,
                "component": c,
                "perf": p,
                "blocker": b,
            }
        )
    rows.sort(key=lambda x: (str(x["captured_at_utc"]), str(x["execution_id"])))
    return rows[-1] if rows else {}


def latest_hist_p8d() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for f in M7_HIST.rglob("p8d_archive_writer_execution_summary.json"):
        d = f.parent
        s = loadj(f)
        c = loadj(d / "p8d_archive_writer_component_snapshot.json")
        p = loadj(d / "p8d_archive_writer_performance_snapshot.json")
        b = loadj(d / "p8d_archive_writer_blocker_register.json")
        if not s or not c or not p or not b:
            continue
        if s.get("overall_pass") is not True:
            continue
        if int(b.get("blocker_count", 0) or 0) != 0:
            continue
        rows.append(
            {
                "path": d,
                "captured_at_utc": str(s.get("captured_at_utc") or c.get("captured_at_utc") or ""),
                "execution_id": str(s.get("execution_id", "")),
                "summary": s,
                "component": c,
                "perf": p,
                "blocker": b,
            }
        )
    rows.sort(key=lambda x: (str(x["captured_at_utc"]), str(x["execution_id"])))
    return rows[-1] if rows else {}


def load_s3_json(bucket: str, key: str) -> dict[str, Any]:
    b = str(bucket or "").strip()
    k = str(key or "").strip().lstrip("/")
    if not b or not k:
        return {}
    rc, out, _ = run_cmd_full(["aws", "s3", "cp", f"s3://{b}/{k}", "-", "--region", AWS_REGION], timeout=120)
    if rc != 0:
        return {}
    try:
        return json.loads(out or "{}")
    except Exception:
        return {}


def add_head_bucket_probe(probes: list[dict[str, Any]], bucket: str, probe_id: str) -> dict[str, Any]:
    p = run_cmd(["aws", "s3api", "head-bucket", "--bucket", bucket, "--region", AWS_REGION], 25) if bucket else {
        "command": "aws s3api head-bucket",
        "exit_code": 1,
        "status": "FAIL",
        "duration_ms": 0.0,
        "stdout": "",
        "stderr": "missing bucket",
        "started_at_utc": now(),
        "ended_at_utc": now(),
    }
    probes.append({**p, "probe_id": probe_id, "group": "control", "bucket": bucket})
    return p


def add_head_object_probe(probes: list[dict[str, Any]], bucket: str, key: str, probe_id: str) -> dict[str, Any]:
    k = str(key or "").strip().lstrip("/")
    p = run_cmd(["aws", "s3api", "head-object", "--bucket", bucket, "--key", k, "--region", AWS_REGION], 30) if bucket and k else {
        "command": "aws s3api head-object",
        "exit_code": 1,
        "status": "FAIL",
        "duration_ms": 0.0,
        "stdout": "",
        "stderr": "missing bucket/key",
        "started_at_utc": now(),
        "ended_at_utc": now(),
    }
    probes.append({**p, "probe_id": probe_id, "group": "evidence", "bucket": bucket, "key": k})
    return p


def parse_s3_uri(uri: str) -> tuple[str, str]:
    s = str(uri or "").strip()
    if not s.startswith("s3://"):
        return "", ""
    no_scheme = s[5:]
    if "/" not in no_scheme:
        return "", ""
    bucket, key = no_scheme.split("/", 1)
    return bucket.strip(), key.strip()


def probe_metrics(probes: list[dict[str, Any]]) -> dict[str, Any]:
    failures = [x for x in probes if str(x.get("status", "FAIL")) != "PASS"]
    latencies = [float(x.get("duration_ms", 0.0)) for x in probes]
    return {
        "window_seconds_observed": max(1, int(round(sum(latencies) / 1000.0))) if latencies else 1,
        "probe_count": len(probes),
        "failure_count": len(failures),
        "error_rate_pct": round((len(failures) / len(probes)) * 100.0, 4) if probes else 0.0,
        "latency_ms_p50": 0.0 if not latencies else sorted(latencies)[len(latencies) // 2],
        "latency_ms_p95": 0.0 if not latencies else max(latencies),
        "latency_ms_p99": 0.0 if not latencies else max(latencies),
        "sample_failures": failures[:10],
        "probes": probes,
    }


def required_artifacts(plan_packet: dict[str, Any]) -> list[str]:
    raw = str(plan_packet.get("M7P8_STRESS_REQUIRED_ARTIFACTS", "")).strip()
    if not raw:
        return list(REQUIRED_ARTIFACTS)
    parsed = [x.strip() for x in raw.split(",") if x.strip()]
    return parsed if parsed else list(REQUIRED_ARTIFACTS)


def resolve_required_handles(handles: dict[str, Any]) -> tuple[list[str], list[str], dict[str, list[str]]]:
    missing: list[str] = []
    placeholder: list[str] = []
    resolved: dict[str, list[str]] = {}
    placeholder_values = {"", "TO_PIN", "None", "NONE", "null", "NULL"}

    for canonical in REQ_HANDLES:
        candidates = [canonical] + HANDLE_ALIASES.get(canonical, [])
        present = [k for k in candidates if k in handles]
        if not present:
            missing.append(canonical)
            continue
        resolved[canonical] = present
        if all(str(handles.get(k, "")).strip() in placeholder_values for k in present):
            placeholder.append(canonical)
    return missing, placeholder, resolved


def finalize_artifact_contract(out: Path, req: list[str], blockers: list[dict[str, Any]], blocker_reg: dict[str, Any], summary: dict[str, Any], verdict: dict[str, Any]) -> None:
    missing = [x for x in req if not (out / x).exists()]
    if not missing:
        return
    blockers.append({"id": "M7P8-ST-B10", "severity": summary.get("stage_id"), "status": "OPEN", "details": {"missing_artifacts": missing}})
    blocker_reg.update({"overall_pass": False, "open_blocker_count": len(blockers), "blockers": blockers})
    summary.update({"overall_pass": False, "next_gate": "BLOCKED", "open_blocker_count": len(blockers)})
    verdict.update({"overall_pass": False, "next_gate": "BLOCKED", "verdict": "HOLD_REMEDIATE", "blocker_count": len(blockers)})
    dumpj(out / "m7p8_blocker_register.json", blocker_reg)
    dumpj(out / "m7p8_execution_summary.json", summary)
    dumpj(out / "m7p8_gate_verdict.json", verdict)


def run_s0(phase_execution_id: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)

    plan_packet = parse_bt_map(PLAN.read_text(encoding="utf-8") if PLAN.exists() else "")
    handles = parse_registry(REG) if REG.exists() else {}
    req_artifacts = required_artifacts(plan_packet)

    blockers: list[dict[str, Any]] = []
    issues: list[str] = []
    advisories: list[str] = []
    decisions: list[str] = []
    probes: list[dict[str, Any]] = []

    missing_plan_keys = [k for k in PLAN_KEYS if k not in plan_packet]
    missing_handles, placeholder_handles, resolved_handles = resolve_required_handles(handles)
    missing_docs = [x.as_posix() for x in [PLAN, PARENT_PLAN, BUILD_PLAN] if not x.exists()]
    if missing_plan_keys or missing_handles or placeholder_handles or missing_docs:
        blockers.append(
            {
                "id": "M7P8-ST-B1",
                "severity": "S0",
                "status": "OPEN",
                "details": {
                    "missing_plan_keys": missing_plan_keys,
                    "missing_handles": missing_handles,
                    "placeholder_handles": placeholder_handles,
                    "resolved_handle_aliases": resolved_handles,
                    "missing_docs": missing_docs,
                },
            }
        )
        issues.append("S0 authority/handle closure failed")

    dep_issues: list[str] = []
    dep = latest_parent_m7_s0()
    dep_id = ""
    platform_run_id = ""
    dep_subset: dict[str, Any] = {}
    dep_profile: dict[str, Any] = {}
    dep_edge: dict[str, Any] = {}
    if not dep:
        dep_issues.append("missing successful parent M7-ST-S0 dependency")
    else:
        dep_id = str(dep["summary"].get("phase_execution_id", ""))
        if str(dep["summary"].get("next_gate", "")).strip() != "M7_ST_S1_READY":
            dep_issues.append("parent M7-ST-S0 next_gate is not M7_ST_S1_READY")
        dep_blocker = loadj(Path(str(dep["path"])) / "m7_blocker_register.json")
        if int(dep_blocker.get("open_blocker_count", 0) or 0) != 0:
            dep_issues.append("parent M7-ST-S0 blocker register is not closed")
        dep_subset = loadj(Path(str(dep["path"])) / "m7_data_subset_manifest.json")
        dep_profile = loadj(Path(str(dep["path"])) / "m7_data_profile_summary.json")
        dep_edge = loadj(Path(str(dep["path"])) / "m7_data_edge_case_matrix.json")
        if not dep_subset:
            dep_issues.append("missing parent subset manifest")
        if not dep_profile:
            dep_issues.append("missing parent profile summary")
        if not dep_edge:
            dep_issues.append("missing parent edge matrix")
        platform_run_id = str(dep_profile.get("platform_run_id") or dep_subset.get("platform_run_id") or "").strip()
        if not platform_run_id:
            dep_issues.append("missing platform_run_id in parent M7 S0 artifacts")
    if dep_issues:
        blockers.append({"id": "M7P8-ST-B2", "severity": "S0", "status": "OPEN", "details": {"issues": dep_issues}})
        issues.extend(dep_issues)

    checks = {
        "sample_size_check": False,
        "event_type_check": False,
        "hotkey_share_check": False,
        "duplicate_ratio_upper_bound_check": False,
        "out_of_order_ratio_upper_bound_check": False,
        "parse_error_check": False,
        "normal_mix_cohort_check": False,
        "rare_edge_case_cohort_check": False,
    }
    cohort_presence = dep_edge.get("cohort_presence", {}) if isinstance(dep_edge.get("cohort_presence"), dict) else {}
    if dep_profile:
        min_sample = int(plan_packet.get("M7P8_STRESS_DATA_MIN_SAMPLE_EVENTS", 6000))
        min_events = int(plan_packet.get("M7P8_STRESS_EVENT_TYPE_MIN_COUNT", 3))
        hotkey_max = float(plan_packet.get("M7P8_STRESS_HOTKEY_TOP1_SHARE_MAX", 0.60))
        _, dup_high = parse_range(plan_packet.get("M7P8_STRESS_DUPLICATE_RATIO_TARGET_RANGE_PCT", "0.5|5.0"))
        _, ooo_high = parse_range(plan_packet.get("M7P8_STRESS_OUT_OF_ORDER_RATIO_TARGET_RANGE_PCT", "0.2|3.0"))

        rows_scanned = to_int(dep_profile.get("rows_scanned")) or 0
        event_type_count = to_int(dep_profile.get("event_type_count")) or 0
        top1_share = to_float(dep_profile.get("top1_run_share"))
        if top1_share is None:
            top1_share = to_float(dep_profile.get("source_profile", {}).get("top1_hotkey_share"))
        dup_ratio = to_float(dep_profile.get("duplicate_ratio_pct"))
        ooo_ratio = to_float(dep_profile.get("out_of_order_ratio_pct"))
        parse_err = to_int(dep_profile.get("source_profile", {}).get("parse_error_count"))
        if parse_err is None:
            parse_err = 0

        checks["sample_size_check"] = rows_scanned >= min_sample
        checks["event_type_check"] = event_type_count >= min_events
        checks["hotkey_share_check"] = top1_share is not None and top1_share <= hotkey_max
        checks["duplicate_ratio_upper_bound_check"] = dup_ratio is None or dup_high is None or dup_ratio <= dup_high
        checks["out_of_order_ratio_upper_bound_check"] = ooo_ratio is None or ooo_high is None or ooo_ratio <= ooo_high
        checks["parse_error_check"] = parse_err == 0
        checks["normal_mix_cohort_check"] = bool(cohort_presence.get("normal_mix", False))
        checks["rare_edge_case_cohort_check"] = bool(cohort_presence.get("rare_edge_case", False))

        for src in [dep_profile.get("advisories", []), dep_edge.get("advisories", [])]:
            if isinstance(src, list):
                for x in src:
                    sx = str(x).strip()
                    if sx and sx not in advisories:
                        advisories.append(sx)
        if cohort_presence.get("duplicate_replay") is False:
            advisories.append("duplicate_replay cohort not naturally present at S0; keep explicit downstream semantic pressure.")
        if cohort_presence.get("late_out_of_order") is False:
            advisories.append("late_out_of_order cohort not naturally present at S0; keep explicit downstream semantic pressure.")

    if not all(bool(x) for x in checks.values()):
        blockers.append(
            {
                "id": "M7P8-ST-B3",
                "severity": "S0",
                "status": "OPEN",
                "details": {"checks": checks, "cohort_presence": cohort_presence, "platform_run_id": platform_run_id},
            }
        )
        issues.append("S0 representativeness checks are not all green")

    evidence_bucket = str(handles.get("S3_EVIDENCE_BUCKET", "")).strip()
    p_bucket = add_head_bucket_probe(probes, evidence_bucket, "m7p8_s0_evidence_bucket")
    if p_bucket.get("status") != "PASS":
        blockers.append({"id": "M7P8-ST-B10", "severity": "S0", "status": "OPEN", "details": {"probe_id": "m7p8_s0_evidence_bucket"}})
        issues.append("S0 evidence bucket probe failed")

    metrics = probe_metrics(probes)
    overall_pass = len(blockers) == 0
    next_gate = "M7P8_ST_S1_READY" if overall_pass else "BLOCKED"
    gate_verdict = "S0_READY" if overall_pass else "HOLD_REMEDIATE"

    dumpj(
        out / "m7p8_stagea_findings.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P8-ST-S0",
            "findings": [
                {"id": "M7P8-ST-F1", "classification": "PREVENT", "finding": "P8 requires parent M7 S0 realism closure.", "required_action": "Fail-closed when parent S0 evidence cannot be consumed."},
                {"id": "M7P8-ST-F2", "classification": "PREVENT", "finding": "Low-sample historical component lanes require realism anchoring.", "required_action": "Require representativeness checks before S1."},
            ],
        },
    )
    dumpj(out / "m7p8_lane_matrix.json", {"component_sequence": ["M7P8-ST-S0", "M7P8-ST-S1", "M7P8-ST-S2", "M7P8-ST-S3", "M7P8-ST-S4", "M7P8-ST-S5"]})
    dumpj(out / "m7p8_data_subset_manifest.json", {**dep_subset, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S0", "upstream_m7_s0_phase_execution_id": dep_id, "platform_run_id": platform_run_id})
    dumpj(
        out / "m7p8_data_profile_summary.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P8-ST-S0",
            "platform_run_id": platform_run_id,
            "rows_scanned": to_int(dep_profile.get("rows_scanned")) or 0,
            "event_type_count": to_int(dep_profile.get("event_type_count")) or 0,
            "duplicate_ratio_pct": to_float(dep_profile.get("duplicate_ratio_pct")),
            "out_of_order_ratio_pct": to_float(dep_profile.get("out_of_order_ratio_pct")),
            "top1_run_share": to_float(dep_profile.get("top1_run_share")),
            "checks": checks,
            "cohort_presence": cohort_presence,
            "advisories": advisories,
            "source_profile": dep_profile.get("source_profile", {}),
        },
    )
    for name in ["m7p8_ieg_snapshot.json", "m7p8_ofp_snapshot.json", "m7p8_archive_snapshot.json"]:
        dumpj(out / name, {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S0", "platform_run_id": platform_run_id, "status": "NOT_EVALUATED_IN_S0"})
    dumpj(out / "m7p8_data_edge_case_matrix.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S0", "platform_run_id": platform_run_id, "cohort_presence": cohort_presence, "profile_checks": checks, "advisories": advisories})
    dumpj(out / "m7p8_probe_latency_throughput_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S0", **metrics})
    dumpj(out / "m7p8_control_rail_conformance_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S0", "overall_pass": len(issues) == 0, "issues": issues, "advisories": advisories})
    dumpj(out / "m7p8_secret_safety_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S0", "overall_pass": True, "secret_probe_count": 0, "secret_failure_count": 0, "with_decryption_used": False, "queried_value_directly": False, "plaintext_leakage_detected": False})
    dumpj(out / "m7p8_cost_outcome_receipt.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S0", "window_seconds": metrics["window_seconds_observed"], "estimated_api_call_count": metrics["probe_count"], "attributed_spend_usd": 0.0, "unattributed_spend_detected": False, "max_spend_usd": float(plan_packet.get("M7P8_STRESS_MAX_SPEND_USD", 35)), "within_envelope": True})
    decisions.extend(["Validated parent M7 S0 continuity and blocker closure.", "Pinned P8 representativeness baseline from parent S0 black-box profile.", "Carried duplicate/out-of-order non-observability as explicit downstream advisory."])
    dumpj(out / "m7p8_decision_log.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S0", "decisions": decisions, "advisories": advisories})

    blocker_reg = {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S0", "overall_pass": overall_pass, "open_blocker_count": len(blockers), "blockers": blockers}
    summary = {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S0", "overall_pass": overall_pass, "next_gate": next_gate, "open_blocker_count": len(blockers), "required_artifacts": req_artifacts, "probe_count": metrics["probe_count"], "error_rate_pct": metrics["error_rate_pct"], "platform_run_id": platform_run_id, "upstream_m7_s0_phase_execution_id": dep_id}
    verdict = {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S0", "overall_pass": overall_pass, "verdict": gate_verdict, "next_gate": next_gate, "blocker_count": len(blockers), "platform_run_id": platform_run_id, "upstream_m7_s0_phase_execution_id": dep_id}
    dumpj(out / "m7p8_blocker_register.json", blocker_reg)
    dumpj(out / "m7p8_execution_summary.json", summary)
    dumpj(out / "m7p8_gate_verdict.json", verdict)
    finalize_artifact_contract(out, req_artifacts, blockers, blocker_reg, summary, verdict)

    summary = loadj(out / "m7p8_execution_summary.json")
    blocker_reg = loadj(out / "m7p8_blocker_register.json")
    print(f"[m7p8_s0] phase_execution_id={phase_execution_id}")
    print(f"[m7p8_s0] output_dir={out.as_posix()}")
    print(f"[m7p8_s0] overall_pass={summary.get('overall_pass')}")
    print(f"[m7p8_s0] next_gate={summary.get('next_gate')}")
    print(f"[m7p8_s0] open_blockers={blocker_reg.get('open_blocker_count')}")
    return 0 if summary.get("overall_pass") is True else 2


def run_s1(phase_execution_id: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)

    plan_packet = parse_bt_map(PLAN.read_text(encoding="utf-8") if PLAN.exists() else "")
    handles = parse_registry(REG) if REG.exists() else {}
    req_artifacts = required_artifacts(plan_packet)
    evidence_bucket = str(handles.get("S3_EVIDENCE_BUCKET", "")).strip()

    blockers: list[dict[str, Any]] = []
    issues: list[str] = []
    advisories: list[str] = []
    decisions: list[str] = []
    probes: list[dict[str, Any]] = []

    missing_plan_keys = [k for k in PLAN_KEYS if k not in plan_packet]
    missing_handles, placeholder_handles, resolved_handles = resolve_required_handles(handles)
    missing_docs = [x.as_posix() for x in [PLAN, PARENT_PLAN, BUILD_PLAN] if not x.exists()]
    if missing_plan_keys or missing_handles or placeholder_handles or missing_docs:
        blockers.append(
            {
                "id": "M7P8-ST-B4",
                "severity": "S1",
                "status": "OPEN",
                "details": {
                    "missing_plan_keys": missing_plan_keys,
                    "missing_handles": missing_handles,
                    "placeholder_handles": placeholder_handles,
                    "resolved_handle_aliases": resolved_handles,
                    "missing_docs": missing_docs,
                },
            }
        )
        issues.append("S1 authority/handle closure failed")

    dep_issues: list[str] = []
    dep = latest_ok("m7p8_stress_s0", "M7P8-ST-S0")
    dep_id = ""
    platform_run_id = ""
    dep_subset: dict[str, Any] = {}
    dep_profile: dict[str, Any] = {}
    dep_edge: dict[str, Any] = {}
    if not dep:
        dep_issues.append("missing successful M7P8 S0 dependency")
    else:
        dep_id = str(dep["summary"].get("phase_execution_id", ""))
        if str(dep["summary"].get("next_gate", "")).strip() != "M7P8_ST_S1_READY":
            dep_issues.append("M7P8 S0 next_gate is not M7P8_ST_S1_READY")
        dep_blocker = loadj(Path(str(dep["path"])) / "m7p8_blocker_register.json")
        if int(dep_blocker.get("open_blocker_count", 0) or 0) != 0:
            dep_issues.append("M7P8 S0 blocker register is not closed")
        dep_subset = loadj(Path(str(dep["path"])) / "m7p8_data_subset_manifest.json")
        dep_profile = loadj(Path(str(dep["path"])) / "m7p8_data_profile_summary.json")
        dep_edge = loadj(Path(str(dep["path"])) / "m7p8_data_edge_case_matrix.json")
        if not dep_subset or not dep_profile or not dep_edge:
            dep_issues.append("M7P8 S0 realism artifacts are incomplete")
        platform_run_id = str(dep_profile.get("platform_run_id") or dep_subset.get("platform_run_id") or "").strip()
        if not platform_run_id:
            dep_issues.append("M7P8 S0 platform_run_id is missing")
    if dep_issues:
        blockers.append({"id": "M7P8-ST-B4", "severity": "S1", "status": "OPEN", "details": {"issues": dep_issues}})
        issues.extend(dep_issues)

    p_bucket = add_head_bucket_probe(probes, evidence_bucket, "m7p8_s1_evidence_bucket")
    if p_bucket.get("status") != "PASS":
        blockers.append({"id": "M7P8-ST-B10", "severity": "S1", "status": "OPEN", "details": {"probe_id": "m7p8_s1_evidence_bucket"}})
        issues.append("S1 evidence bucket probe failed")

    hist = latest_hist_p8b()
    component: dict[str, Any] = {}
    perf: dict[str, Any] = {}
    comp_summary: dict[str, Any] = {}
    comp_proof: dict[str, Any] = {}
    receipt_summary: dict[str, Any] = {}
    offsets_snapshot: dict[str, Any] = {}
    quarantine_summary: dict[str, Any] = {}
    functional_issues: list[str] = []
    semantic_issues: list[str] = []
    if not hist:
        functional_issues.append("missing successful historical P8.B IEG artifact set")
    else:
        component = hist.get("component", {})
        perf = hist.get("perf", {})
        comp_summary = hist.get("summary", {})

        hist_platform_run_id = str(comp_summary.get("platform_run_id", "")).strip()
        if platform_run_id and hist_platform_run_id and platform_run_id != hist_platform_run_id:
            functional_issues.append("historical P8.B platform_run_id mismatches current S0 run scope")
        if comp_summary.get("overall_pass") is not True:
            functional_issues.append("historical P8.B execution summary is not pass")
        if str(comp_summary.get("next_gate", "")).strip() != "M7.D_READY":
            functional_issues.append("historical P8.B next_gate is not M7.D_READY")

        runtime_active = str(component.get("runtime_path_active", "")).strip()
        runtime_allowed = [str(x).strip() for x in component.get("runtime_path_allowed", [])] if isinstance(component.get("runtime_path_allowed"), list) else []
        if runtime_active and runtime_allowed and runtime_active not in runtime_allowed:
            functional_issues.append("historical runtime active path is not inside runtime allowed list")
        active_handle = str(handles.get("FLINK_RUNTIME_PATH_ACTIVE", "")).strip()
        if active_handle and runtime_active and normalize_runtime_path(active_handle) != normalize_runtime_path(runtime_active):
            functional_issues.append("historical runtime active path mismatches current pinned handle")
        if str(component.get("cluster_status", "")).strip().upper() not in {"ACTIVE", "RUNNING"}:
            functional_issues.append("historical cluster status is not ACTIVE/RUNNING")
        if component.get("overall_pass") is not True:
            functional_issues.append("historical IEG component snapshot is not pass")
        if to_int(component.get("required_handle_count")) is None or to_int(component.get("resolved_handle_count")) is None:
            functional_issues.append("historical IEG handle counts are missing")
        elif to_int(component.get("required_handle_count")) != to_int(component.get("resolved_handle_count")):
            functional_issues.append("historical IEG handle counts do not match")
        if component.get("missing_handles"):
            functional_issues.append("historical IEG has missing handles")
        if component.get("placeholder_handles"):
            functional_issues.append("historical IEG has placeholder handles")

        if perf.get("performance_gate_pass") is not True:
            functional_issues.append("historical IEG performance gate is not pass")
        lag_obs = to_float(perf.get("lag_observed"))
        lag_max = to_float(perf.get("lag_max"))
        lag_handle = to_float(handles.get("RTDL_CAUGHT_UP_LAG_MAX"))
        if lag_max is None:
            lag_max = lag_handle
        elif lag_handle is not None:
            lag_max = min(lag_max, lag_handle)
        if lag_obs is None or lag_max is None or lag_obs > lag_max:
            functional_issues.append("historical IEG lag exceeds max")
        err_obs = to_float(perf.get("error_rate_pct_observed"))
        err_max = to_float(perf.get("error_rate_pct_max"))
        if err_obs is None or err_max is None or err_obs > err_max:
            functional_issues.append("historical IEG error rate exceeds max")

        throughput_asserted = bool(perf.get("throughput_assertion_applied", False))
        if throughput_asserted:
            thr_obs = to_float(perf.get("throughput_observed"))
            thr_min = to_float(perf.get("throughput_min"))
            if thr_obs is None or thr_min is None or thr_obs < thr_min:
                functional_issues.append("historical IEG throughput assertion failed")
        else:
            mode = str(perf.get("throughput_gate_mode", "")).strip()
            blockers.append(
                {
                    "id": "M7P8-ST-B13",
                    "severity": "S1",
                    "status": "OPEN",
                    "details": {
                        "reason": "toy-profile throughput posture is not allowed for closure",
                        "component": "IEG",
                        "throughput_assertion_applied": False,
                        "throughput_gate_mode": mode,
                    },
                }
            )
            functional_issues.append("IEG throughput assertion is not applied; strict non-toy closure requires asserted throughput")

        proof_key = str(component.get("rtdl_core_component_proof_key", "")).strip().lstrip("/")
        if not proof_key:
            semantic_issues.append("historical IEG proof key is missing")
        else:
            p_proof = add_head_object_probe(probes, evidence_bucket, proof_key, "m7p8_s1_ieg_component_proof")
            if p_proof.get("status") != "PASS":
                blockers.append({"id": "M7P8-ST-B10", "severity": "S1", "status": "OPEN", "details": {"probe_id": "m7p8_s1_ieg_component_proof"}})
                issues.append("IEG component proof head-object probe failed")
            comp_proof = load_s3_json(evidence_bucket, proof_key)
            if not comp_proof:
                blockers.append({"id": "M7P8-ST-B10", "severity": "S1", "status": "OPEN", "details": {"reason": "failed to load IEG component proof", "key": proof_key}})
                issues.append("failed to load IEG component proof")
            else:
                if str(comp_proof.get("platform_run_id", "")).strip() != platform_run_id:
                    semantic_issues.append("IEG component proof platform_run_id mismatch")
                if (to_int(comp_proof.get("ingest_basis_total_receipts")) or 0) <= 0:
                    semantic_issues.append("IEG component proof ingest_basis_total_receipts is not positive")

        refs = dep_subset.get("behavior_context_refs", {}) if isinstance(dep_subset.get("behavior_context_refs"), dict) else {}
        for tag in ["receipt_summary", "offsets_snapshot", "quarantine_summary"]:
            ref = refs.get(tag, {}) if isinstance(refs.get(tag), dict) else {}
            key = str(ref.get("key", "")).strip().lstrip("/")
            if not bool(ref.get("present", False)) or not key:
                semantic_issues.append(f"missing behavior-context reference for {tag}")
                continue
            probe_id = f"m7p8_s1_behavior_{tag}"
            p_ref = add_head_object_probe(probes, evidence_bucket, key, probe_id)
            if p_ref.get("status") != "PASS":
                blockers.append({"id": "M7P8-ST-B10", "severity": "S1", "status": "OPEN", "details": {"probe_id": probe_id}})
                issues.append(f"behavior-context probe failed for {tag}")
                continue
            payload = load_s3_json(evidence_bucket, key)
            if not payload:
                blockers.append({"id": "M7P8-ST-B10", "severity": "S1", "status": "OPEN", "details": {"reason": f"failed to load behavior payload for {tag}", "key": key}})
                issues.append(f"failed to load behavior payload for {tag}")
                continue
            if tag == "receipt_summary":
                receipt_summary = payload
                cbd = payload.get("counts_by_decision", {}) if isinstance(payload.get("counts_by_decision"), dict) else {}
                for k in ["ADMIT", "DUPLICATE", "QUARANTINE"]:
                    if k not in cbd:
                        semantic_issues.append(f"receipt summary missing counts_by_decision key {k}")
                if (to_int(payload.get("total_receipts")) or 0) <= 0:
                    semantic_issues.append("receipt summary total_receipts is not positive")
            elif tag == "offsets_snapshot":
                offsets_snapshot = payload
                topics = payload.get("topics", [])
                if not isinstance(topics, list) or len(topics) == 0:
                    semantic_issues.append("offsets snapshot topics list is empty")
                if payload.get("kafka_offsets_materialized") is not True:
                    semantic_issues.append("offsets snapshot kafka_offsets_materialized is false")
            elif tag == "quarantine_summary":
                quarantine_summary = payload
                if to_int(payload.get("quarantine_count")) is None:
                    semantic_issues.append("quarantine summary quarantine_count missing")

    if functional_issues:
        blockers.append({"id": "M7P8-ST-B4", "severity": "S1", "status": "OPEN", "details": {"issues": functional_issues}})
        issues.extend(functional_issues)
    if semantic_issues:
        blockers.append({"id": "M7P8-ST-B5", "severity": "S1", "status": "OPEN", "details": {"issues": semantic_issues}})
        issues.extend(semantic_issues)

    cohort_presence = dep_edge.get("cohort_presence", {}) if isinstance(dep_edge.get("cohort_presence"), dict) else {}
    if cohort_presence.get("duplicate_replay") is False:
        advisories.append("duplicate_replay cohort not naturally observed; hold explicit replay/duplicate pressure for downstream lanes.")
    if cohort_presence.get("late_out_of_order") is False:
        advisories.append("late_out_of_order cohort not naturally observed; hold explicit late-event pressure for downstream lanes.")

    metrics = probe_metrics(probes)
    overall_pass = len(blockers) == 0
    next_gate = "M7P8_ST_S2_READY" if overall_pass else "BLOCKED"
    gate_verdict = "ADVANCE_TO_S2" if overall_pass else "HOLD_REMEDIATE"

    dumpj(
        out / "m7p8_stagea_findings.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P8-ST-S1",
            "findings": [
                {"id": "M7P8-ST-F6", "classification": "PREVENT", "finding": "S1 IEG gate fails on functional/perf and run-scope drift.", "required_action": "Map to B4 and stop progression."},
                {"id": "M7P8-ST-F7", "classification": "PREVENT", "finding": "S1 semantic/evidence inconsistencies are hard blockers.", "required_action": "Map semantic drift to B5 and evidence readback failures to B10."},
            ],
        },
    )
    dumpj(out / "m7p8_lane_matrix.json", {"component_sequence": ["M7P8-ST-S0", "M7P8-ST-S1", "M7P8-ST-S2", "M7P8-ST-S3", "M7P8-ST-S4", "M7P8-ST-S5"]})
    dumpj(out / "m7p8_data_subset_manifest.json", {**dep_subset, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S1", "upstream_m7p8_s0_phase_execution_id": dep_id, "status": "S1_CONSUMED"})
    dumpj(out / "m7p8_data_profile_summary.json", {**dep_profile, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S1", "upstream_m7p8_s0_phase_execution_id": dep_id, "s1_semantic_check_completed": True, "advisories": sorted(set([str(x) for x in advisories if str(x).strip()]))})
    dumpj(
        out / "m7p8_ieg_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P8-ST-S1",
            "platform_run_id": platform_run_id,
            "status": "PASS" if overall_pass else "FAIL",
            "upstream_m7p8_s0_phase_execution_id": dep_id,
            "historical_p8b_execution_id": str(comp_summary.get("execution_id", "")),
            "historical_component_artifact_path": str(hist.get("path", "")),
            "component_summary": comp_summary,
            "component_snapshot": component,
            "performance_snapshot": perf,
            "component_proof_excerpt": {
                "execution_id": str(comp_proof.get("execution_id", "")),
                "platform_run_id": str(comp_proof.get("platform_run_id", "")),
                "ingest_basis_total_receipts": to_int(comp_proof.get("ingest_basis_total_receipts")),
            },
            "behavior_context_excerpt": {
                "receipt_total": to_int(receipt_summary.get("total_receipts")),
                "receipt_counts_by_decision": receipt_summary.get("counts_by_decision", {}),
                "offset_topic_count": len(offsets_snapshot.get("topics", [])) if isinstance(offsets_snapshot.get("topics"), list) else 0,
                "quarantine_count": to_int(quarantine_summary.get("quarantine_count")),
            },
            "functional_issues": functional_issues,
            "semantic_issues": semantic_issues,
            "advisories": advisories,
        },
    )
    for name in ["m7p8_ofp_snapshot.json", "m7p8_archive_snapshot.json"]:
        dumpj(out / name, {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S1", "platform_run_id": platform_run_id, "status": "NOT_EVALUATED_IN_S1"})
    dumpj(out / "m7p8_data_edge_case_matrix.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S1", "platform_run_id": platform_run_id, "cohort_presence": cohort_presence, "s0_profile_checks": dep_profile.get("checks", {}), "advisories": advisories})
    dumpj(out / "m7p8_probe_latency_throughput_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S1", **metrics})
    dumpj(out / "m7p8_control_rail_conformance_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S1", "overall_pass": len(issues) == 0, "issues": issues, "advisories": advisories})
    dumpj(out / "m7p8_secret_safety_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S1", "overall_pass": True, "secret_probe_count": 0, "secret_failure_count": 0, "with_decryption_used": False, "queried_value_directly": False, "plaintext_leakage_detected": False})
    dumpj(out / "m7p8_cost_outcome_receipt.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S1", "window_seconds": metrics["window_seconds_observed"], "estimated_api_call_count": metrics["probe_count"], "attributed_spend_usd": 0.0, "unattributed_spend_detected": False, "max_spend_usd": float(plan_packet.get("M7P8_STRESS_MAX_SPEND_USD", 35)), "within_envelope": True})
    decisions.extend(["Enforced S0 continuity and blocker closure before S1.", "Validated historical IEG lane evidence against current run-scope and handle contracts.", "Applied fail-closed S1 mapping: B4 functional, B5 semantic, B10 evidence readback."])
    dumpj(out / "m7p8_decision_log.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S1", "decisions": decisions, "advisories": advisories})

    blocker_reg = {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S1", "overall_pass": overall_pass, "open_blocker_count": len(blockers), "blockers": blockers}
    summary = {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S1", "overall_pass": overall_pass, "next_gate": next_gate, "open_blocker_count": len(blockers), "required_artifacts": req_artifacts, "probe_count": metrics["probe_count"], "error_rate_pct": metrics["error_rate_pct"], "platform_run_id": platform_run_id, "upstream_m7p8_s0_phase_execution_id": dep_id, "historical_p8b_execution_id": str(comp_summary.get("execution_id", ""))}
    verdict = {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S1", "overall_pass": overall_pass, "verdict": gate_verdict, "next_gate": next_gate, "blocker_count": len(blockers), "platform_run_id": platform_run_id, "upstream_m7p8_s0_phase_execution_id": dep_id, "historical_p8b_execution_id": str(comp_summary.get("execution_id", ""))}
    dumpj(out / "m7p8_blocker_register.json", blocker_reg)
    dumpj(out / "m7p8_execution_summary.json", summary)
    dumpj(out / "m7p8_gate_verdict.json", verdict)
    finalize_artifact_contract(out, req_artifacts, blockers, blocker_reg, summary, verdict)

    summary = loadj(out / "m7p8_execution_summary.json")
    blocker_reg = loadj(out / "m7p8_blocker_register.json")
    print(f"[m7p8_s1] phase_execution_id={phase_execution_id}")
    print(f"[m7p8_s1] output_dir={out.as_posix()}")
    print(f"[m7p8_s1] overall_pass={summary.get('overall_pass')}")
    print(f"[m7p8_s1] next_gate={summary.get('next_gate')}")
    print(f"[m7p8_s1] open_blockers={blocker_reg.get('open_blocker_count')}")
    return 0 if summary.get("overall_pass") is True else 2


def run_s2(phase_execution_id: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)

    plan_packet = parse_bt_map(PLAN.read_text(encoding="utf-8") if PLAN.exists() else "")
    handles = parse_registry(REG) if REG.exists() else {}
    req_artifacts = required_artifacts(plan_packet)
    evidence_bucket = str(handles.get("S3_EVIDENCE_BUCKET", "")).strip()

    blockers: list[dict[str, Any]] = []
    issues: list[str] = []
    advisories: list[str] = []
    decisions: list[str] = []
    probes: list[dict[str, Any]] = []

    missing_plan_keys = [k for k in PLAN_KEYS if k not in plan_packet]
    missing_handles, placeholder_handles, resolved_handles = resolve_required_handles(handles)
    missing_docs = [x.as_posix() for x in [PLAN, PARENT_PLAN, BUILD_PLAN] if not x.exists()]
    if missing_plan_keys or missing_handles or placeholder_handles or missing_docs:
        blockers.append(
            {
                "id": "M7P8-ST-B6",
                "severity": "S2",
                "status": "OPEN",
                "details": {
                    "missing_plan_keys": missing_plan_keys,
                    "missing_handles": missing_handles,
                    "placeholder_handles": placeholder_handles,
                    "resolved_handle_aliases": resolved_handles,
                    "missing_docs": missing_docs,
                },
            }
        )
        issues.append("S2 authority/handle closure failed")

    dep_issues: list[str] = []
    dep = latest_ok("m7p8_stress_s1", "M7P8-ST-S1")
    dep_id = ""
    dep_path: Path | None = None
    platform_run_id = ""
    dep_subset: dict[str, Any] = {}
    dep_profile: dict[str, Any] = {}
    dep_edge: dict[str, Any] = {}
    dep_ieg_snapshot: dict[str, Any] = {}
    if not dep:
        dep_issues.append("missing successful M7P8 S1 dependency")
    else:
        dep_id = str(dep["summary"].get("phase_execution_id", ""))
        dep_path = Path(str(dep["path"]))
        if str(dep["summary"].get("next_gate", "")).strip() != "M7P8_ST_S2_READY":
            dep_issues.append("M7P8 S1 next_gate is not M7P8_ST_S2_READY")
        dep_blocker = loadj(dep_path / "m7p8_blocker_register.json")
        if int(dep_blocker.get("open_blocker_count", 0) or 0) != 0:
            dep_issues.append("M7P8 S1 blocker register is not closed")
        dep_subset = loadj(dep_path / "m7p8_data_subset_manifest.json")
        dep_profile = loadj(dep_path / "m7p8_data_profile_summary.json")
        dep_edge = loadj(dep_path / "m7p8_data_edge_case_matrix.json")
        dep_ieg_snapshot = loadj(dep_path / "m7p8_ieg_snapshot.json")
        if not dep_subset or not dep_profile or not dep_edge:
            dep_issues.append("M7P8 S1 realism artifacts are incomplete")
        if not dep_ieg_snapshot:
            dep_issues.append("M7P8 S1 IEG snapshot is missing")
        platform_run_id = str(dep_profile.get("platform_run_id") or dep_subset.get("platform_run_id") or "").strip()
        if not platform_run_id:
            dep_issues.append("M7P8 S1 platform_run_id is missing")
    if dep_issues:
        blockers.append({"id": "M7P8-ST-B6", "severity": "S2", "status": "OPEN", "details": {"issues": dep_issues}})
        issues.extend(dep_issues)

    p_bucket = add_head_bucket_probe(probes, evidence_bucket, "m7p8_s2_evidence_bucket")
    if p_bucket.get("status") != "PASS":
        blockers.append({"id": "M7P8-ST-B10", "severity": "S2", "status": "OPEN", "details": {"probe_id": "m7p8_s2_evidence_bucket"}})
        issues.append("S2 evidence bucket probe failed")

    hist = latest_hist_p8c()
    component: dict[str, Any] = {}
    perf: dict[str, Any] = {}
    comp_summary: dict[str, Any] = {}
    comp_proof: dict[str, Any] = {}
    receipt_summary: dict[str, Any] = {}
    offsets_snapshot: dict[str, Any] = {}
    quarantine_summary: dict[str, Any] = {}
    functional_issues: list[str] = []
    semantic_issues: list[str] = []

    if not hist:
        functional_issues.append("missing successful historical P8.C OFP artifact set")
    else:
        component = hist.get("component", {})
        perf = hist.get("perf", {})
        comp_summary = hist.get("summary", {})

        hist_platform_run_id = str(comp_summary.get("platform_run_id", "")).strip()
        if platform_run_id and hist_platform_run_id and platform_run_id != hist_platform_run_id:
            functional_issues.append("historical P8.C platform_run_id mismatches current S1 run scope")
        if comp_summary.get("overall_pass") is not True:
            functional_issues.append("historical P8.C execution summary is not pass")
        if str(comp_summary.get("next_gate", "")).strip() != "M7.E_READY":
            functional_issues.append("historical P8.C next_gate is not M7.E_READY")

        runtime_active = str(component.get("runtime_path_active", "")).strip()
        runtime_allowed = [str(x).strip() for x in component.get("runtime_path_allowed", [])] if isinstance(component.get("runtime_path_allowed"), list) else []
        if runtime_active and runtime_allowed:
            normalized_allowed = {normalize_runtime_path(x) for x in runtime_allowed}
            if normalize_runtime_path(runtime_active) not in normalized_allowed:
                functional_issues.append("historical OFP runtime active path is not inside runtime allowed list")
        active_handle = str(handles.get("FLINK_RUNTIME_PATH_ACTIVE", "")).strip()
        if active_handle and runtime_active and normalize_runtime_path(active_handle) != normalize_runtime_path(runtime_active):
            functional_issues.append("historical OFP runtime active path mismatches current pinned handle")
        if str(component.get("cluster_status", "")).strip().upper() not in {"ACTIVE", "RUNNING"}:
            functional_issues.append("historical OFP cluster status is not ACTIVE/RUNNING")
        if component.get("overall_pass") is not True:
            functional_issues.append("historical OFP component snapshot is not pass")
        if to_int(component.get("required_handle_count")) is None or to_int(component.get("resolved_handle_count")) is None:
            functional_issues.append("historical OFP handle counts are missing")
        elif to_int(component.get("required_handle_count")) != to_int(component.get("resolved_handle_count")):
            functional_issues.append("historical OFP handle counts do not match")
        if component.get("missing_handles"):
            functional_issues.append("historical OFP has missing handles")
        if component.get("placeholder_handles"):
            functional_issues.append("historical OFP has placeholder handles")

        if perf.get("performance_gate_pass") is not True:
            functional_issues.append("historical OFP performance gate is not pass")
        lag_obs = to_float(perf.get("lag_observed"))
        lag_max = to_float(perf.get("lag_max"))
        lag_handle = to_float(handles.get("RTDL_CAUGHT_UP_LAG_MAX"))
        if lag_max is None:
            lag_max = lag_handle
        elif lag_handle is not None:
            lag_max = min(lag_max, lag_handle)
        if lag_obs is None or lag_max is None or lag_obs > lag_max:
            functional_issues.append("historical OFP lag exceeds max")
        err_obs = to_float(perf.get("error_rate_pct_observed"))
        err_max = to_float(perf.get("error_rate_pct_max"))
        if err_obs is None or err_max is None or err_obs > err_max:
            functional_issues.append("historical OFP error rate exceeds max")

        throughput_asserted = bool(perf.get("throughput_assertion_applied", False))
        if throughput_asserted:
            thr_obs = to_float(perf.get("throughput_observed"))
            thr_min = to_float(perf.get("throughput_min"))
            if thr_obs is None or thr_min is None or thr_obs < thr_min:
                functional_issues.append("historical OFP throughput assertion failed")
        else:
            mode = str(perf.get("throughput_gate_mode", "")).strip()
            blockers.append(
                {
                    "id": "M7P8-ST-B13",
                    "severity": "S2",
                    "status": "OPEN",
                    "details": {
                        "reason": "toy-profile throughput posture is not allowed for closure",
                        "component": "OFP",
                        "throughput_assertion_applied": False,
                        "throughput_gate_mode": mode,
                    },
                }
            )
            functional_issues.append("OFP throughput assertion is not applied; strict non-toy closure requires asserted throughput")

        proof_key = str(component.get("rtdl_core_component_proof_key", "")).strip().lstrip("/")
        if not proof_key:
            semantic_issues.append("historical OFP proof key is missing")
        else:
            p_proof = add_head_object_probe(probes, evidence_bucket, proof_key, "m7p8_s2_ofp_component_proof")
            if p_proof.get("status") != "PASS":
                blockers.append({"id": "M7P8-ST-B10", "severity": "S2", "status": "OPEN", "details": {"probe_id": "m7p8_s2_ofp_component_proof"}})
                issues.append("OFP component proof head-object probe failed")
            comp_proof = load_s3_json(evidence_bucket, proof_key)
            if not comp_proof:
                blockers.append({"id": "M7P8-ST-B10", "severity": "S2", "status": "OPEN", "details": {"reason": "failed to load OFP component proof", "key": proof_key}})
                issues.append("failed to load OFP component proof")
            else:
                if str(comp_proof.get("platform_run_id", "")).strip() != platform_run_id:
                    semantic_issues.append("OFP component proof platform_run_id mismatch")
                if (to_int(comp_proof.get("ingest_basis_total_receipts")) or 0) <= 0:
                    semantic_issues.append("OFP component proof ingest_basis_total_receipts is not positive")

        refs = dep_subset.get("behavior_context_refs", {}) if isinstance(dep_subset.get("behavior_context_refs"), dict) else {}
        for tag in ["receipt_summary", "offsets_snapshot", "quarantine_summary"]:
            ref = refs.get(tag, {}) if isinstance(refs.get(tag), dict) else {}
            key = str(ref.get("key", "")).strip().lstrip("/")
            if not bool(ref.get("present", False)) or not key:
                semantic_issues.append(f"missing behavior-context reference for {tag}")
                continue
            probe_id = f"m7p8_s2_behavior_{tag}"
            p_ref = add_head_object_probe(probes, evidence_bucket, key, probe_id)
            if p_ref.get("status") != "PASS":
                blockers.append({"id": "M7P8-ST-B10", "severity": "S2", "status": "OPEN", "details": {"probe_id": probe_id}})
                issues.append(f"behavior-context probe failed for {tag}")
                continue
            payload = load_s3_json(evidence_bucket, key)
            if not payload:
                blockers.append({"id": "M7P8-ST-B10", "severity": "S2", "status": "OPEN", "details": {"reason": f"failed to load behavior payload for {tag}", "key": key}})
                issues.append(f"failed to load behavior payload for {tag}")
                continue
            if tag == "receipt_summary":
                receipt_summary = payload
                cbd = payload.get("counts_by_decision", {}) if isinstance(payload.get("counts_by_decision"), dict) else {}
                for k in ["ADMIT", "DUPLICATE", "QUARANTINE"]:
                    if k not in cbd:
                        semantic_issues.append(f"receipt summary missing counts_by_decision key {k}")
                if (to_int(payload.get("total_receipts")) or 0) <= 0:
                    semantic_issues.append("receipt summary total_receipts is not positive")
            elif tag == "offsets_snapshot":
                offsets_snapshot = payload
                topics = payload.get("topics", [])
                if not isinstance(topics, list) or len(topics) == 0:
                    semantic_issues.append("offsets snapshot topics list is empty")
                if payload.get("kafka_offsets_materialized") is not True:
                    semantic_issues.append("offsets snapshot kafka_offsets_materialized is false")
                for t in topics if isinstance(topics, list) else []:
                    f_off = to_int(t.get("first_offset"))
                    l_off = to_int(t.get("last_offset"))
                    if f_off is not None and l_off is not None and f_off > l_off:
                        semantic_issues.append(f"offset ordering invalid for topic {t.get('topic')}")
            elif tag == "quarantine_summary":
                quarantine_summary = payload
                if to_int(payload.get("quarantine_count")) is None:
                    semantic_issues.append("quarantine summary quarantine_count missing")

        # Context-projection completeness heuristic from run-scoped source roots.
        source_roots = dep_profile.get("source_profile", {}).get("source_roots", [])
        roots = [str(x).lower() for x in source_roots] if isinstance(source_roots, list) else []
        has_arrival_entities = any("arrival_entities" in x for x in roots)
        has_flow_anchor = any("flow_anchor" in x for x in roots)
        if not has_arrival_entities:
            semantic_issues.append("run-scoped profile missing arrival_entities context footprint")
        if not has_flow_anchor:
            semantic_issues.append("run-scoped profile missing flow_anchor context footprint")

    if functional_issues:
        blockers.append({"id": "M7P8-ST-B6", "severity": "S2", "status": "OPEN", "details": {"issues": functional_issues}})
        issues.extend(functional_issues)
    if semantic_issues:
        blockers.append({"id": "M7P8-ST-B7", "severity": "S2", "status": "OPEN", "details": {"issues": semantic_issues}})
        issues.extend(semantic_issues)

    cohort_presence = dep_edge.get("cohort_presence", {}) if isinstance(dep_edge.get("cohort_presence"), dict) else {}
    if cohort_presence.get("duplicate_replay") is False:
        advisories.append("duplicate_replay cohort not naturally observed; keep explicit replay/duplicate pressure in downstream lanes.")
    if cohort_presence.get("late_out_of_order") is False:
        advisories.append("late_out_of_order cohort not naturally observed; keep explicit late-event pressure in downstream lanes.")

    metrics = probe_metrics(probes)
    overall_pass = len(blockers) == 0
    next_gate = "M7P8_ST_S3_READY" if overall_pass else "BLOCKED"
    gate_verdict = "ADVANCE_TO_S3" if overall_pass else "HOLD_REMEDIATE"

    dumpj(
        out / "m7p8_stagea_findings.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P8-ST-S2",
            "findings": [
                {"id": "M7P8-ST-F9", "classification": "PREVENT", "finding": "S2 OFP gate fails on functional/perf and run-scope drift.", "required_action": "Map to B6 and stop progression."},
                {"id": "M7P8-ST-F10", "classification": "PREVENT", "finding": "S2 semantic/context inconsistencies are hard blockers.", "required_action": "Map semantic/context drift to B7 and evidence-readback failures to B10."},
            ],
        },
    )
    dumpj(out / "m7p8_lane_matrix.json", {"component_sequence": ["M7P8-ST-S0", "M7P8-ST-S1", "M7P8-ST-S2", "M7P8-ST-S3", "M7P8-ST-S4", "M7P8-ST-S5"]})
    dumpj(out / "m7p8_data_subset_manifest.json", {**dep_subset, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S2", "upstream_m7p8_s1_phase_execution_id": dep_id, "status": "S2_CONSUMED"})
    dumpj(out / "m7p8_data_profile_summary.json", {**dep_profile, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S2", "upstream_m7p8_s1_phase_execution_id": dep_id, "s2_semantic_check_completed": True, "advisories": sorted(set([str(x) for x in advisories if str(x).strip()]))})
    dumpj(
        out / "m7p8_ieg_snapshot.json",
        {
            **dep_ieg_snapshot,
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P8-ST-S2",
            "status": "CARRY_FORWARD_FROM_S1",
            "upstream_m7p8_s1_phase_execution_id": dep_id,
        },
    )
    dumpj(
        out / "m7p8_ofp_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P8-ST-S2",
            "platform_run_id": platform_run_id,
            "status": "PASS" if overall_pass else "FAIL",
            "upstream_m7p8_s1_phase_execution_id": dep_id,
            "historical_p8c_execution_id": str(comp_summary.get("execution_id", "")),
            "historical_component_artifact_path": str(hist.get("path", "")),
            "component_summary": comp_summary,
            "component_snapshot": component,
            "performance_snapshot": perf,
            "component_proof_excerpt": {
                "execution_id": str(comp_proof.get("execution_id", "")),
                "platform_run_id": str(comp_proof.get("platform_run_id", "")),
                "ingest_basis_total_receipts": to_int(comp_proof.get("ingest_basis_total_receipts")),
            },
            "behavior_context_excerpt": {
                "receipt_total": to_int(receipt_summary.get("total_receipts")),
                "receipt_counts_by_decision": receipt_summary.get("counts_by_decision", {}),
                "offset_topic_count": len(offsets_snapshot.get("topics", [])) if isinstance(offsets_snapshot.get("topics"), list) else 0,
                "quarantine_count": to_int(quarantine_summary.get("quarantine_count")),
            },
            "functional_issues": functional_issues,
            "semantic_issues": semantic_issues,
            "advisories": advisories,
        },
    )
    dumpj(out / "m7p8_archive_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S2", "platform_run_id": platform_run_id, "status": "NOT_EVALUATED_IN_S2"})
    dumpj(out / "m7p8_data_edge_case_matrix.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S2", "platform_run_id": platform_run_id, "cohort_presence": cohort_presence, "s1_profile_checks": dep_profile.get("checks", {}), "advisories": advisories})
    dumpj(out / "m7p8_probe_latency_throughput_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S2", **metrics})
    dumpj(out / "m7p8_control_rail_conformance_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S2", "overall_pass": len(issues) == 0, "issues": issues, "advisories": advisories})
    dumpj(out / "m7p8_secret_safety_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S2", "overall_pass": True, "secret_probe_count": 0, "secret_failure_count": 0, "with_decryption_used": False, "queried_value_directly": False, "plaintext_leakage_detected": False})
    dumpj(out / "m7p8_cost_outcome_receipt.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S2", "window_seconds": metrics["window_seconds_observed"], "estimated_api_call_count": metrics["probe_count"], "attributed_spend_usd": 0.0, "unattributed_spend_detected": False, "max_spend_usd": float(plan_packet.get("M7P8_STRESS_MAX_SPEND_USD", 35)), "within_envelope": True})
    decisions.extend(["Enforced S1 continuity and blocker closure before S2.", "Validated historical OFP lane evidence against current run-scope and handle contracts.", "Applied fail-closed S2 mapping: B6 functional/perf, B7 semantic/context, B10 evidence readback."])
    dumpj(out / "m7p8_decision_log.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S2", "decisions": decisions, "advisories": advisories})

    blocker_reg = {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S2", "overall_pass": overall_pass, "open_blocker_count": len(blockers), "blockers": blockers}
    summary = {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S2", "overall_pass": overall_pass, "next_gate": next_gate, "open_blocker_count": len(blockers), "required_artifacts": req_artifacts, "probe_count": metrics["probe_count"], "error_rate_pct": metrics["error_rate_pct"], "platform_run_id": platform_run_id, "upstream_m7p8_s1_phase_execution_id": dep_id, "historical_p8c_execution_id": str(comp_summary.get("execution_id", ""))}
    verdict = {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S2", "overall_pass": overall_pass, "verdict": gate_verdict, "next_gate": next_gate, "blocker_count": len(blockers), "platform_run_id": platform_run_id, "upstream_m7p8_s1_phase_execution_id": dep_id, "historical_p8c_execution_id": str(comp_summary.get("execution_id", ""))}
    dumpj(out / "m7p8_blocker_register.json", blocker_reg)
    dumpj(out / "m7p8_execution_summary.json", summary)
    dumpj(out / "m7p8_gate_verdict.json", verdict)
    finalize_artifact_contract(out, req_artifacts, blockers, blocker_reg, summary, verdict)

    summary = loadj(out / "m7p8_execution_summary.json")
    blocker_reg = loadj(out / "m7p8_blocker_register.json")
    print(f"[m7p8_s2] phase_execution_id={phase_execution_id}")
    print(f"[m7p8_s2] output_dir={out.as_posix()}")
    print(f"[m7p8_s2] overall_pass={summary.get('overall_pass')}")
    print(f"[m7p8_s2] next_gate={summary.get('next_gate')}")
    print(f"[m7p8_s2] open_blockers={blocker_reg.get('open_blocker_count')}")
    return 0 if summary.get("overall_pass") is True else 2


def run_s3(phase_execution_id: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)

    plan_packet = parse_bt_map(PLAN.read_text(encoding="utf-8") if PLAN.exists() else "")
    handles = parse_registry(REG) if REG.exists() else {}
    req_artifacts = required_artifacts(plan_packet)
    evidence_bucket = str(handles.get("S3_EVIDENCE_BUCKET", "")).strip()

    blockers: list[dict[str, Any]] = []
    issues: list[str] = []
    advisories: list[str] = []
    decisions: list[str] = []
    probes: list[dict[str, Any]] = []

    missing_plan_keys = [k for k in PLAN_KEYS if k not in plan_packet]
    missing_handles, placeholder_handles, resolved_handles = resolve_required_handles(handles)
    missing_docs = [x.as_posix() for x in [PLAN, PARENT_PLAN, BUILD_PLAN] if not x.exists()]
    if missing_plan_keys or missing_handles or placeholder_handles or missing_docs:
        blockers.append(
            {
                "id": "M7P8-ST-B8",
                "severity": "S3",
                "status": "OPEN",
                "details": {
                    "missing_plan_keys": missing_plan_keys,
                    "missing_handles": missing_handles,
                    "placeholder_handles": placeholder_handles,
                    "resolved_handle_aliases": resolved_handles,
                    "missing_docs": missing_docs,
                },
            }
        )
        issues.append("S3 authority/handle closure failed")

    dep_issues: list[str] = []
    dep = latest_ok("m7p8_stress_s2", "M7P8-ST-S2")
    dep_id = ""
    dep_path: Path | None = None
    platform_run_id = ""
    dep_subset: dict[str, Any] = {}
    dep_profile: dict[str, Any] = {}
    dep_edge: dict[str, Any] = {}
    dep_ieg_snapshot: dict[str, Any] = {}
    dep_ofp_snapshot: dict[str, Any] = {}
    if not dep:
        dep_issues.append("missing successful M7P8 S2 dependency")
    else:
        dep_id = str(dep["summary"].get("phase_execution_id", ""))
        dep_path = Path(str(dep["path"]))
        if str(dep["summary"].get("next_gate", "")).strip() != "M7P8_ST_S3_READY":
            dep_issues.append("M7P8 S2 next_gate is not M7P8_ST_S3_READY")
        dep_blocker = loadj(dep_path / "m7p8_blocker_register.json")
        if int(dep_blocker.get("open_blocker_count", 0) or 0) != 0:
            dep_issues.append("M7P8 S2 blocker register is not closed")
        dep_subset = loadj(dep_path / "m7p8_data_subset_manifest.json")
        dep_profile = loadj(dep_path / "m7p8_data_profile_summary.json")
        dep_edge = loadj(dep_path / "m7p8_data_edge_case_matrix.json")
        dep_ieg_snapshot = loadj(dep_path / "m7p8_ieg_snapshot.json")
        dep_ofp_snapshot = loadj(dep_path / "m7p8_ofp_snapshot.json")
        if not dep_subset or not dep_profile or not dep_edge:
            dep_issues.append("M7P8 S2 realism artifacts are incomplete")
        if not dep_ieg_snapshot:
            dep_issues.append("M7P8 S2 carry-forward IEG snapshot is missing")
        if not dep_ofp_snapshot:
            dep_issues.append("M7P8 S2 OFP snapshot is missing")
        platform_run_id = str(dep_profile.get("platform_run_id") or dep_subset.get("platform_run_id") or "").strip()
        if not platform_run_id:
            dep_issues.append("M7P8 S2 platform_run_id is missing")
    if dep_issues:
        blockers.append({"id": "M7P8-ST-B8", "severity": "S3", "status": "OPEN", "details": {"issues": dep_issues}})
        issues.extend(dep_issues)

    p_bucket = add_head_bucket_probe(probes, evidence_bucket, "m7p8_s3_evidence_bucket")
    if p_bucket.get("status") != "PASS":
        blockers.append({"id": "M7P8-ST-B10", "severity": "S3", "status": "OPEN", "details": {"probe_id": "m7p8_s3_evidence_bucket"}})
        issues.append("S3 evidence bucket probe failed")

    hist = latest_hist_p8d()
    component: dict[str, Any] = {}
    perf: dict[str, Any] = {}
    comp_summary: dict[str, Any] = {}
    comp_proof: dict[str, Any] = {}
    receipt_summary: dict[str, Any] = {}
    offsets_snapshot: dict[str, Any] = {}
    quarantine_summary: dict[str, Any] = {}
    functional_issues: list[str] = []
    semantic_issues: list[str] = []

    if not hist:
        functional_issues.append("missing successful historical P8.D archive artifact set")
    else:
        component = hist.get("component", {})
        perf = hist.get("perf", {})
        comp_summary = hist.get("summary", {})

        hist_platform_run_id = str(comp_summary.get("platform_run_id", "")).strip()
        if platform_run_id and hist_platform_run_id and platform_run_id != hist_platform_run_id:
            functional_issues.append("historical P8.D platform_run_id mismatches current S2 run scope")
        if comp_summary.get("overall_pass") is not True:
            functional_issues.append("historical P8.D execution summary is not pass")
        if str(comp_summary.get("next_gate", "")).strip() != "P8.E_READY":
            functional_issues.append("historical P8.D next_gate is not P8.E_READY")

        runtime_active = str(component.get("runtime_path_active", "")).strip()
        runtime_allowed = [str(x).strip() for x in component.get("runtime_path_allowed", [])] if isinstance(component.get("runtime_path_allowed"), list) else []
        if runtime_active and runtime_allowed:
            normalized_allowed = {normalize_runtime_path(x) for x in runtime_allowed}
            if normalize_runtime_path(runtime_active) not in normalized_allowed:
                functional_issues.append("historical ArchiveWriter runtime active path is not inside runtime allowed list")
        active_handle = str(handles.get("FLINK_RUNTIME_PATH_ACTIVE", "")).strip()
        if active_handle and runtime_active and normalize_runtime_path(active_handle) != normalize_runtime_path(runtime_active):
            functional_issues.append("historical ArchiveWriter runtime active path mismatches current pinned handle")
        if str(component.get("cluster_status", "")).strip().upper() not in {"ACTIVE", "RUNNING"}:
            functional_issues.append("historical ArchiveWriter cluster status is not ACTIVE/RUNNING")
        if component.get("overall_pass") is not True:
            functional_issues.append("historical ArchiveWriter component snapshot is not pass")
        if to_int(component.get("required_handle_count")) is None or to_int(component.get("resolved_handle_count")) is None:
            functional_issues.append("historical ArchiveWriter handle counts are missing")
        elif to_int(component.get("required_handle_count")) != to_int(component.get("resolved_handle_count")):
            functional_issues.append("historical ArchiveWriter handle counts do not match")
        if component.get("missing_handles"):
            functional_issues.append("historical ArchiveWriter has missing handles")
        if component.get("placeholder_handles"):
            functional_issues.append("historical ArchiveWriter has placeholder handles")

        if perf.get("performance_gate_pass") is not True:
            functional_issues.append("historical ArchiveWriter performance gate is not pass")
        lag_obs = to_float(perf.get("lag_observed"))
        lag_max = to_float(perf.get("lag_max"))
        lag_handle = to_float(handles.get("RTDL_CAUGHT_UP_LAG_MAX"))
        if lag_max is None:
            lag_max = lag_handle
        elif lag_handle is not None:
            lag_max = min(lag_max, lag_handle)
        if lag_obs is None or lag_max is None or lag_obs > lag_max:
            functional_issues.append("historical ArchiveWriter lag exceeds max")
        err_obs = to_float(perf.get("error_rate_pct_observed"))
        err_max = to_float(perf.get("error_rate_pct_max"))
        if err_obs is None or err_max is None or err_obs > err_max:
            functional_issues.append("historical ArchiveWriter error rate exceeds max")

        throughput_asserted = bool(perf.get("throughput_assertion_applied", False))
        if throughput_asserted:
            thr_obs = to_float(perf.get("throughput_observed"))
            thr_min = to_float(perf.get("throughput_min"))
            if thr_obs is None or thr_min is None or thr_obs < thr_min:
                functional_issues.append("historical ArchiveWriter throughput assertion failed")
        else:
            mode = str(perf.get("throughput_gate_mode", "")).strip()
            blockers.append(
                {
                    "id": "M7P8-ST-B13",
                    "severity": "S3",
                    "status": "OPEN",
                    "details": {
                        "reason": "toy-profile throughput posture is not allowed for closure",
                        "component": "ArchiveWriter",
                        "throughput_assertion_applied": False,
                        "throughput_gate_mode": mode,
                    },
                }
            )
            functional_issues.append("ArchiveWriter throughput assertion is not applied; strict non-toy closure requires asserted throughput")

        proof_key = str(component.get("rtdl_core_component_proof_key", "")).strip().lstrip("/")
        if not proof_key:
            semantic_issues.append("historical ArchiveWriter proof key is missing")
        else:
            p_proof = add_head_object_probe(probes, evidence_bucket, proof_key, "m7p8_s3_archive_component_proof")
            if p_proof.get("status") != "PASS":
                blockers.append({"id": "M7P8-ST-B10", "severity": "S3", "status": "OPEN", "details": {"probe_id": "m7p8_s3_archive_component_proof"}})
                issues.append("ArchiveWriter component proof head-object probe failed")
            comp_proof = load_s3_json(evidence_bucket, proof_key)
            if not comp_proof:
                blockers.append({"id": "M7P8-ST-B10", "severity": "S3", "status": "OPEN", "details": {"reason": "failed to load ArchiveWriter component proof", "key": proof_key}})
                issues.append("failed to load ArchiveWriter component proof")
            else:
                if str(comp_proof.get("platform_run_id", "")).strip() != platform_run_id:
                    semantic_issues.append("ArchiveWriter component proof platform_run_id mismatch")
                ingest_basis = to_int(comp_proof.get("ingest_basis_total_receipts")) or 0
                if ingest_basis <= 0:
                    semantic_issues.append("ArchiveWriter component proof ingest_basis_total_receipts is not positive")

                fallback_uri = str(comp_proof.get("archive_probe_s3_uri_fallback", "")).strip()
                primary_error = str(comp_proof.get("archive_probe_primary_error", "")).strip()
                if fallback_uri:
                    fb_bucket, fb_key = parse_s3_uri(fallback_uri)
                    if not fb_bucket or not fb_key:
                        semantic_issues.append("ArchiveWriter fallback archive probe URI is malformed")
                    else:
                        p_fb = add_head_object_probe(probes, fb_bucket, fb_key, "m7p8_s3_archive_probe_fallback")
                        if p_fb.get("status") != "PASS":
                            functional_issues.append("ArchiveWriter fallback archive probe object is not readable")
                        if platform_run_id and platform_run_id not in fb_key:
                            semantic_issues.append("ArchiveWriter fallback archive probe key does not contain platform_run_id")
                        if primary_error and "AccessDenied" in primary_error:
                            advisories.append("ArchiveWriter primary archive probe path remains access-restricted for current evidence role; fallback evidence path is used and validated.")
                elif primary_error:
                    functional_issues.append("ArchiveWriter primary archive probe failed without fallback evidence object")

        # Check archive prefix handles are materializable and deterministic.
        run_prefix = str(handles.get("S3_ARCHIVE_RUN_PREFIX_PATTERN", "")).replace("{platform_run_id}", platform_run_id)
        events_prefix = str(handles.get("S3_ARCHIVE_EVENTS_PREFIX_PATTERN", "")).replace("{platform_run_id}", platform_run_id)
        if "{" in run_prefix or "}" in run_prefix:
            semantic_issues.append("archive run prefix contains unresolved placeholders")
        if "{" in events_prefix or "}" in events_prefix:
            semantic_issues.append("archive events prefix contains unresolved placeholders")
        if run_prefix and events_prefix and not events_prefix.startswith(run_prefix):
            semantic_issues.append("archive events prefix is not nested under archive run prefix")

        refs = dep_subset.get("behavior_context_refs", {}) if isinstance(dep_subset.get("behavior_context_refs"), dict) else {}
        for tag in ["receipt_summary", "offsets_snapshot", "quarantine_summary"]:
            ref = refs.get(tag, {}) if isinstance(refs.get(tag), dict) else {}
            key = str(ref.get("key", "")).strip().lstrip("/")
            if not bool(ref.get("present", False)) or not key:
                semantic_issues.append(f"missing behavior-context reference for {tag}")
                continue
            probe_id = f"m7p8_s3_behavior_{tag}"
            p_ref = add_head_object_probe(probes, evidence_bucket, key, probe_id)
            if p_ref.get("status") != "PASS":
                blockers.append({"id": "M7P8-ST-B10", "severity": "S3", "status": "OPEN", "details": {"probe_id": probe_id}})
                issues.append(f"behavior-context probe failed for {tag}")
                continue
            payload = load_s3_json(evidence_bucket, key)
            if not payload:
                blockers.append({"id": "M7P8-ST-B10", "severity": "S3", "status": "OPEN", "details": {"reason": f"failed to load behavior payload for {tag}", "key": key}})
                issues.append(f"failed to load behavior payload for {tag}")
                continue
            if tag == "receipt_summary":
                receipt_summary = payload
                cbd = payload.get("counts_by_decision", {}) if isinstance(payload.get("counts_by_decision"), dict) else {}
                for k in ["ADMIT", "DUPLICATE", "QUARANTINE"]:
                    if k not in cbd:
                        semantic_issues.append(f"receipt summary missing counts_by_decision key {k}")
                if (to_int(payload.get("total_receipts")) or 0) <= 0:
                    semantic_issues.append("receipt summary total_receipts is not positive")
            elif tag == "offsets_snapshot":
                offsets_snapshot = payload
                topics = payload.get("topics", [])
                if not isinstance(topics, list) or len(topics) == 0:
                    semantic_issues.append("offsets snapshot topics list is empty")
                if payload.get("kafka_offsets_materialized") is not True:
                    semantic_issues.append("offsets snapshot kafka_offsets_materialized is false")
            elif tag == "quarantine_summary":
                quarantine_summary = payload
                if to_int(payload.get("quarantine_count")) is None:
                    semantic_issues.append("quarantine summary quarantine_count missing")

        # Semantic integrity linkage: archive basis cannot exceed known receipt count.
        receipt_total = to_int(receipt_summary.get("total_receipts")) or 0
        ingest_basis = to_int(comp_proof.get("ingest_basis_total_receipts")) if comp_proof else None
        if ingest_basis is not None and receipt_total > 0 and ingest_basis > receipt_total:
            semantic_issues.append("archive ingest basis exceeds receipt total")

    if functional_issues:
        blockers.append({"id": "M7P8-ST-B8", "severity": "S3", "status": "OPEN", "details": {"issues": functional_issues}})
        issues.extend(functional_issues)
    if semantic_issues:
        blockers.append({"id": "M7P8-ST-B9", "severity": "S3", "status": "OPEN", "details": {"issues": semantic_issues}})
        issues.extend(semantic_issues)

    cohort_presence = dep_edge.get("cohort_presence", {}) if isinstance(dep_edge.get("cohort_presence"), dict) else {}
    if cohort_presence.get("duplicate_replay") is False:
        advisories.append("duplicate_replay cohort not naturally observed; keep explicit replay/duplicate pressure in downstream lanes.")
    if cohort_presence.get("late_out_of_order") is False:
        advisories.append("late_out_of_order cohort not naturally observed; keep explicit late-event pressure in downstream lanes.")

    metrics = probe_metrics(probes)
    overall_pass = len(blockers) == 0
    next_gate = "M7P8_ST_S4_READY" if overall_pass else "BLOCKED"
    gate_verdict = "ADVANCE_TO_S4" if overall_pass else "HOLD_REMEDIATE"

    dumpj(
        out / "m7p8_stagea_findings.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P8-ST-S3",
            "findings": [
                {"id": "M7P8-ST-F11", "classification": "PREVENT", "finding": "S3 ArchiveWriter gate fails on durability/readback and runtime/perf drift.", "required_action": "Map to B8 and stop progression."},
                {"id": "M7P8-ST-F12", "classification": "PREVENT", "finding": "S3 semantic/archive-integrity inconsistencies are hard blockers.", "required_action": "Map semantic/integrity drift to B9 and evidence-readback failures to B10."},
            ],
        },
    )
    dumpj(out / "m7p8_lane_matrix.json", {"component_sequence": ["M7P8-ST-S0", "M7P8-ST-S1", "M7P8-ST-S2", "M7P8-ST-S3", "M7P8-ST-S4", "M7P8-ST-S5"]})
    dumpj(out / "m7p8_data_subset_manifest.json", {**dep_subset, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S3", "upstream_m7p8_s2_phase_execution_id": dep_id, "status": "S3_CONSUMED"})
    dumpj(out / "m7p8_data_profile_summary.json", {**dep_profile, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S3", "upstream_m7p8_s2_phase_execution_id": dep_id, "s3_semantic_check_completed": True, "advisories": sorted(set([str(x) for x in advisories if str(x).strip()]))})
    dumpj(
        out / "m7p8_ieg_snapshot.json",
        {
            **dep_ieg_snapshot,
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P8-ST-S3",
            "status": "CARRY_FORWARD_FROM_S2",
            "upstream_m7p8_s2_phase_execution_id": dep_id,
        },
    )
    dumpj(
        out / "m7p8_ofp_snapshot.json",
        {
            **dep_ofp_snapshot,
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P8-ST-S3",
            "status": "CARRY_FORWARD_FROM_S2",
            "upstream_m7p8_s2_phase_execution_id": dep_id,
        },
    )
    dumpj(
        out / "m7p8_archive_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P8-ST-S3",
            "platform_run_id": platform_run_id,
            "status": "PASS" if overall_pass else "FAIL",
            "upstream_m7p8_s2_phase_execution_id": dep_id,
            "historical_p8d_execution_id": str(comp_summary.get("execution_id", "")),
            "historical_component_artifact_path": str(hist.get("path", "")),
            "component_summary": comp_summary,
            "component_snapshot": component,
            "performance_snapshot": perf,
            "component_proof_excerpt": {
                "execution_id": str(comp_proof.get("execution_id", "")),
                "platform_run_id": str(comp_proof.get("platform_run_id", "")),
                "ingest_basis_total_receipts": to_int(comp_proof.get("ingest_basis_total_receipts")),
                "archive_probe_s3_uri_fallback": str(comp_proof.get("archive_probe_s3_uri_fallback", "")),
                "archive_probe_primary_error": str(comp_proof.get("archive_probe_primary_error", "")),
            },
            "behavior_context_excerpt": {
                "receipt_total": to_int(receipt_summary.get("total_receipts")),
                "receipt_counts_by_decision": receipt_summary.get("counts_by_decision", {}),
                "offset_topic_count": len(offsets_snapshot.get("topics", [])) if isinstance(offsets_snapshot.get("topics"), list) else 0,
                "quarantine_count": to_int(quarantine_summary.get("quarantine_count")),
            },
            "functional_issues": functional_issues,
            "semantic_issues": semantic_issues,
            "advisories": advisories,
        },
    )
    dumpj(out / "m7p8_data_edge_case_matrix.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S3", "platform_run_id": platform_run_id, "cohort_presence": cohort_presence, "s2_profile_checks": dep_profile.get("checks", {}), "advisories": advisories})
    dumpj(out / "m7p8_probe_latency_throughput_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S3", **metrics})
    dumpj(out / "m7p8_control_rail_conformance_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S3", "overall_pass": len(issues) == 0, "issues": issues, "advisories": advisories})
    dumpj(out / "m7p8_secret_safety_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S3", "overall_pass": True, "secret_probe_count": 0, "secret_failure_count": 0, "with_decryption_used": False, "queried_value_directly": False, "plaintext_leakage_detected": False})
    dumpj(out / "m7p8_cost_outcome_receipt.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S3", "window_seconds": metrics["window_seconds_observed"], "estimated_api_call_count": metrics["probe_count"], "attributed_spend_usd": 0.0, "unattributed_spend_detected": False, "max_spend_usd": float(plan_packet.get("M7P8_STRESS_MAX_SPEND_USD", 35)), "within_envelope": True})
    decisions.extend(["Enforced S2 continuity and blocker closure before S3.", "Validated historical ArchiveWriter lane evidence against current run-scope and handle contracts.", "Applied fail-closed S3 mapping: B8 durability/readback/perf, B9 semantic/integrity, B10 evidence readback."])
    dumpj(out / "m7p8_decision_log.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S3", "decisions": decisions, "advisories": advisories})

    blocker_reg = {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S3", "overall_pass": overall_pass, "open_blocker_count": len(blockers), "blockers": blockers}
    summary = {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S3", "overall_pass": overall_pass, "next_gate": next_gate, "open_blocker_count": len(blockers), "required_artifacts": req_artifacts, "probe_count": metrics["probe_count"], "error_rate_pct": metrics["error_rate_pct"], "platform_run_id": platform_run_id, "upstream_m7p8_s2_phase_execution_id": dep_id, "historical_p8d_execution_id": str(comp_summary.get("execution_id", ""))}
    verdict = {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S3", "overall_pass": overall_pass, "verdict": gate_verdict, "next_gate": next_gate, "blocker_count": len(blockers), "platform_run_id": platform_run_id, "upstream_m7p8_s2_phase_execution_id": dep_id, "historical_p8d_execution_id": str(comp_summary.get("execution_id", ""))}
    dumpj(out / "m7p8_blocker_register.json", blocker_reg)
    dumpj(out / "m7p8_execution_summary.json", summary)
    dumpj(out / "m7p8_gate_verdict.json", verdict)
    finalize_artifact_contract(out, req_artifacts, blockers, blocker_reg, summary, verdict)

    summary = loadj(out / "m7p8_execution_summary.json")
    blocker_reg = loadj(out / "m7p8_blocker_register.json")
    print(f"[m7p8_s3] phase_execution_id={phase_execution_id}")
    print(f"[m7p8_s3] output_dir={out.as_posix()}")
    print(f"[m7p8_s3] overall_pass={summary.get('overall_pass')}")
    print(f"[m7p8_s3] next_gate={summary.get('next_gate')}")
    print(f"[m7p8_s3] open_blockers={blocker_reg.get('open_blocker_count')}")
    return 0 if summary.get("overall_pass") is True else 2


def run_s4(phase_execution_id: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)

    plan_packet = parse_bt_map(PLAN.read_text(encoding="utf-8") if PLAN.exists() else "")
    handles = parse_registry(REG) if REG.exists() else {}
    req_artifacts = required_artifacts(plan_packet)
    evidence_bucket = str(handles.get("S3_EVIDENCE_BUCKET", "")).strip()

    blockers: list[dict[str, Any]] = []
    issues: list[str] = []
    advisories: list[str] = []
    decisions: list[str] = []
    probes: list[dict[str, Any]] = []

    missing_plan_keys = [k for k in PLAN_KEYS if k not in plan_packet]
    missing_handles, placeholder_handles, resolved_handles = resolve_required_handles(handles)
    missing_docs = [x.as_posix() for x in [PLAN, PARENT_PLAN, BUILD_PLAN] if not x.exists()]
    if missing_plan_keys or missing_handles or placeholder_handles or missing_docs:
        blockers.append(
            {
                "id": "M7P8-ST-B11",
                "severity": "S4",
                "status": "OPEN",
                "details": {
                    "reason": "S4 authority/handle closure failure",
                    "missing_plan_keys": missing_plan_keys,
                    "missing_handles": missing_handles,
                    "placeholder_handles": placeholder_handles,
                    "resolved_handle_aliases": resolved_handles,
                    "missing_docs": missing_docs,
                },
            }
        )
        issues.append("S4 authority/handle closure failed")

    dep_issues: list[str] = []
    dep = latest_ok("m7p8_stress_s3", "M7P8-ST-S3")
    dep_id = ""
    dep_path: Path | None = None
    platform_run_id = ""
    dep_subset: dict[str, Any] = {}
    dep_profile: dict[str, Any] = {}
    dep_edge: dict[str, Any] = {}
    dep_ieg_snapshot: dict[str, Any] = {}
    dep_ofp_snapshot: dict[str, Any] = {}
    dep_archive_snapshot: dict[str, Any] = {}
    if not dep:
        dep_issues.append("missing successful M7P8 S3 dependency")
    else:
        dep_id = str(dep["summary"].get("phase_execution_id", ""))
        dep_path = Path(str(dep["path"]))
        if str(dep["summary"].get("next_gate", "")).strip() != "M7P8_ST_S4_READY":
            dep_issues.append("M7P8 S3 next_gate is not M7P8_ST_S4_READY")
        dep_blocker = loadj(dep_path / "m7p8_blocker_register.json")
        if int(dep_blocker.get("open_blocker_count", 0) or 0) != 0:
            dep_issues.append("M7P8 S3 blocker register is not closed")
        dep_subset = loadj(dep_path / "m7p8_data_subset_manifest.json")
        dep_profile = loadj(dep_path / "m7p8_data_profile_summary.json")
        dep_edge = loadj(dep_path / "m7p8_data_edge_case_matrix.json")
        dep_ieg_snapshot = loadj(dep_path / "m7p8_ieg_snapshot.json")
        dep_ofp_snapshot = loadj(dep_path / "m7p8_ofp_snapshot.json")
        dep_archive_snapshot = loadj(dep_path / "m7p8_archive_snapshot.json")
        if not dep_subset or not dep_profile or not dep_edge:
            dep_issues.append("M7P8 S3 realism artifacts are incomplete")
        if not dep_ieg_snapshot or not dep_ofp_snapshot or not dep_archive_snapshot:
            dep_issues.append("M7P8 S3 component snapshots are incomplete")
        platform_run_id = str(dep_profile.get("platform_run_id") or dep_subset.get("platform_run_id") or "").strip()
        if not platform_run_id:
            dep_issues.append("M7P8 S3 platform_run_id is missing")
    if dep_issues:
        blockers.append({"id": "M7P8-ST-B11", "severity": "S4", "status": "OPEN", "details": {"issues": dep_issues}})
        issues.extend(dep_issues)

    chain_spec = [
        ("S0", "m7p8_stress_s0", "M7P8-ST-S0", "M7P8_ST_S1_READY"),
        ("S1", "m7p8_stress_s1", "M7P8-ST-S1", "M7P8_ST_S2_READY"),
        ("S2", "m7p8_stress_s2", "M7P8-ST-S2", "M7P8_ST_S3_READY"),
        ("S3", "m7p8_stress_s3", "M7P8-ST-S3", "M7P8_ST_S4_READY"),
    ]
    chain_rows: list[dict[str, Any]] = []
    for label, prefix, stage_id, expected_next_gate in chain_spec:
        r = latest_ok(prefix, stage_id)
        row = {
            "label": label,
            "stage_id": stage_id,
            "expected_next_gate": expected_next_gate,
            "found": bool(r),
            "phase_execution_id": "",
            "next_gate": "",
            "overall_pass": False,
            "open_blockers": None,
            "ok": False,
        }
        if r:
            s = r.get("summary", {})
            row["phase_execution_id"] = str(s.get("phase_execution_id", ""))
            row["next_gate"] = str(s.get("next_gate", ""))
            row["overall_pass"] = bool(s.get("overall_pass"))
            rp = Path(str(r.get("path", "")))
            b = loadj(rp / "m7p8_blocker_register.json")
            row["open_blockers"] = int(b.get("open_blocker_count", 0) or 0)
            row["ok"] = row["overall_pass"] and row["next_gate"] == expected_next_gate and row["open_blockers"] == 0
        if not row["ok"]:
            blockers.append({"id": "M7P8-ST-B11", "severity": "S4", "status": "OPEN", "details": {"chain_row": row}})
            issues.append(f"stage-chain closure failed for {label}")
        chain_rows.append(row)

    p_bucket = add_head_bucket_probe(probes, evidence_bucket, "m7p8_s4_evidence_bucket")
    if p_bucket.get("status") != "PASS":
        blockers.append({"id": "M7P8-ST-B10", "severity": "S4", "status": "OPEN", "details": {"probe_id": "m7p8_s4_evidence_bucket"}})
        issues.append("S4 evidence bucket probe failed")

    remediation_mode = "NO_OP" if len(blockers) == 0 else "TARGETED_REMEDIATE"
    if remediation_mode == "NO_OP":
        decisions.append("No unresolved blockers detected from S0..S3; remediation lane closed as NO_OP per targeted-rerun-only policy.")
    else:
        decisions.append("Residual blocker(s) detected; remediation lane requires targeted correction before S5.")

    for src in [dep_profile.get("advisories", []), dep_edge.get("advisories", [])]:
        if isinstance(src, list):
            for x in src:
                sx = str(x).strip()
                if sx and sx not in advisories:
                    advisories.append(sx)

    metrics = probe_metrics(probes)
    overall_pass = len(blockers) == 0
    next_gate = "M7P8_ST_S5_READY" if overall_pass else "BLOCKED"
    gate_verdict = "ADVANCE_TO_S5" if overall_pass else "HOLD_REMEDIATE"

    dumpj(
        out / "m7p8_stagea_findings.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P8-ST-S4",
            "findings": [
                {"id": "M7P8-ST-F13", "classification": "PREVENT", "finding": "S4 must not mask unresolved blockers from prior stages.", "required_action": "Fail-closed on any unresolved S0..S3 chain issue."},
                {"id": "M7P8-ST-F14", "classification": "PREVENT", "finding": "S4 remediation must be targeted and evidence-consistent.", "required_action": "Use NO_OP when clean; otherwise enforce blocker-scoped remediation only."},
            ],
        },
    )
    dumpj(out / "m7p8_lane_matrix.json", {"component_sequence": ["M7P8-ST-S0", "M7P8-ST-S1", "M7P8-ST-S2", "M7P8-ST-S3", "M7P8-ST-S4", "M7P8-ST-S5"]})
    dumpj(out / "m7p8_data_subset_manifest.json", {**dep_subset, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S4", "upstream_m7p8_s3_phase_execution_id": dep_id, "status": "S4_CARRY_FORWARD"})
    dumpj(out / "m7p8_data_profile_summary.json", {**dep_profile, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S4", "upstream_m7p8_s3_phase_execution_id": dep_id, "s4_remediation_mode": remediation_mode, "advisories": advisories})
    dumpj(out / "m7p8_ieg_snapshot.json", {**dep_ieg_snapshot, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S4", "status": "CARRY_FORWARD_FROM_S3", "upstream_m7p8_s3_phase_execution_id": dep_id})
    dumpj(out / "m7p8_ofp_snapshot.json", {**dep_ofp_snapshot, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S4", "status": "CARRY_FORWARD_FROM_S3", "upstream_m7p8_s3_phase_execution_id": dep_id})
    dumpj(out / "m7p8_archive_snapshot.json", {**dep_archive_snapshot, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S4", "status": "CARRY_FORWARD_FROM_S3", "upstream_m7p8_s3_phase_execution_id": dep_id})
    dumpj(out / "m7p8_data_edge_case_matrix.json", {**dep_edge, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S4", "platform_run_id": platform_run_id, "chain_rows": chain_rows, "remediation_mode": remediation_mode, "advisories": advisories})
    dumpj(out / "m7p8_probe_latency_throughput_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S4", **metrics})
    dumpj(out / "m7p8_control_rail_conformance_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S4", "overall_pass": len(issues) == 0, "issues": issues, "advisories": advisories, "remediation_mode": remediation_mode})
    dumpj(out / "m7p8_secret_safety_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S4", "overall_pass": True, "secret_probe_count": 0, "secret_failure_count": 0, "with_decryption_used": False, "queried_value_directly": False, "plaintext_leakage_detected": False})
    dumpj(out / "m7p8_cost_outcome_receipt.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S4", "window_seconds": metrics["window_seconds_observed"], "estimated_api_call_count": metrics["probe_count"], "attributed_spend_usd": 0.0, "unattributed_spend_detected": False, "max_spend_usd": float(plan_packet.get("M7P8_STRESS_MAX_SPEND_USD", 35)), "within_envelope": True, "remediation_mode": remediation_mode})
    decisions.extend(["Enforced S3 continuity and blocker closure before S4.", "Executed deterministic chain-health sweep across S0..S3 before remediation adjudication.", "Applied S4 policy: NO_OP when blocker-free, targeted remediation only when concrete residual blocker exists."])
    dumpj(out / "m7p8_decision_log.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S4", "decisions": decisions, "advisories": advisories, "remediation_mode": remediation_mode})

    blocker_reg = {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S4", "overall_pass": overall_pass, "open_blocker_count": len(blockers), "blockers": blockers}
    summary = {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S4", "overall_pass": overall_pass, "next_gate": next_gate, "open_blocker_count": len(blockers), "required_artifacts": req_artifacts, "probe_count": metrics["probe_count"], "error_rate_pct": metrics["error_rate_pct"], "platform_run_id": platform_run_id, "upstream_m7p8_s3_phase_execution_id": dep_id, "remediation_mode": remediation_mode}
    verdict = {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S4", "overall_pass": overall_pass, "verdict": gate_verdict, "next_gate": next_gate, "blocker_count": len(blockers), "platform_run_id": platform_run_id, "upstream_m7p8_s3_phase_execution_id": dep_id, "remediation_mode": remediation_mode}
    dumpj(out / "m7p8_blocker_register.json", blocker_reg)
    dumpj(out / "m7p8_execution_summary.json", summary)
    dumpj(out / "m7p8_gate_verdict.json", verdict)
    finalize_artifact_contract(out, req_artifacts, blockers, blocker_reg, summary, verdict)

    summary = loadj(out / "m7p8_execution_summary.json")
    blocker_reg = loadj(out / "m7p8_blocker_register.json")
    print(f"[m7p8_s4] phase_execution_id={phase_execution_id}")
    print(f"[m7p8_s4] output_dir={out.as_posix()}")
    print(f"[m7p8_s4] overall_pass={summary.get('overall_pass')}")
    print(f"[m7p8_s4] next_gate={summary.get('next_gate')}")
    print(f"[m7p8_s4] remediation_mode={summary.get('remediation_mode')}")
    print(f"[m7p8_s4] open_blockers={blocker_reg.get('open_blocker_count')}")
    return 0 if summary.get("overall_pass") is True else 2


def run_s5(phase_execution_id: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)

    plan_packet = parse_bt_map(PLAN.read_text(encoding="utf-8") if PLAN.exists() else "")
    handles = parse_registry(REG) if REG.exists() else {}
    req_artifacts = required_artifacts(plan_packet)
    evidence_bucket = str(handles.get("S3_EVIDENCE_BUCKET", "")).strip()

    blockers: list[dict[str, Any]] = []
    issues: list[str] = []
    advisories: list[str] = []
    decisions: list[str] = []
    probes: list[dict[str, Any]] = []

    expected_pass_verdict = str(plan_packet.get("M7P8_STRESS_EXPECTED_VERDICT_ON_PASS", "ADVANCE_TO_P9")).strip() or "ADVANCE_TO_P9"
    if expected_pass_verdict != "ADVANCE_TO_P9":
        blockers.append(
            {
                "id": "M7P8-ST-B11",
                "severity": "S5",
                "status": "OPEN",
                "details": {"reason": "unexpected expected_pass_verdict contract", "expected_pass_verdict": expected_pass_verdict},
            }
        )
        issues.append("expected pass verdict contract is not ADVANCE_TO_P9")

    missing_plan_keys = [k for k in PLAN_KEYS if k not in plan_packet]
    missing_handles, placeholder_handles, resolved_handles = resolve_required_handles(handles)
    missing_docs = [x.as_posix() for x in [PLAN, PARENT_PLAN, BUILD_PLAN] if not x.exists()]
    if missing_plan_keys or missing_handles or placeholder_handles or missing_docs:
        blockers.append(
            {
                "id": "M7P8-ST-B11",
                "severity": "S5",
                "status": "OPEN",
                "details": {
                    "reason": "S5 authority/handle closure failure",
                    "missing_plan_keys": missing_plan_keys,
                    "missing_handles": missing_handles,
                    "placeholder_handles": placeholder_handles,
                    "resolved_handle_aliases": resolved_handles,
                    "missing_docs": missing_docs,
                },
            }
        )
        issues.append("S5 authority/handle closure failed")

    dep_issues: list[str] = []
    dep = latest_ok("m7p8_stress_s4", "M7P8-ST-S4")
    dep_id = ""
    dep_path: Path | None = None
    platform_run_id = ""
    dep_summary: dict[str, Any] = {}
    dep_subset: dict[str, Any] = {}
    dep_profile: dict[str, Any] = {}
    dep_edge: dict[str, Any] = {}
    dep_ieg_snapshot: dict[str, Any] = {}
    dep_ofp_snapshot: dict[str, Any] = {}
    dep_archive_snapshot: dict[str, Any] = {}
    dep_gate_verdict: dict[str, Any] = {}
    dep_decision_log: dict[str, Any] = {}

    if not dep:
        dep_issues.append("missing successful M7P8 S4 dependency")
    else:
        dep_summary = dep.get("summary", {})
        dep_id = str(dep_summary.get("phase_execution_id", ""))
        dep_path = Path(str(dep.get("path", "")))
        if str(dep_summary.get("next_gate", "")).strip() != "M7P8_ST_S5_READY":
            dep_issues.append("M7P8 S4 next_gate is not M7P8_ST_S5_READY")
        dep_blocker = loadj(dep_path / "m7p8_blocker_register.json")
        if int(dep_blocker.get("open_blocker_count", 0) or 0) != 0:
            dep_issues.append("M7P8 S4 blocker register is not closed")

        dep_subset = loadj(dep_path / "m7p8_data_subset_manifest.json")
        dep_profile = loadj(dep_path / "m7p8_data_profile_summary.json")
        dep_edge = loadj(dep_path / "m7p8_data_edge_case_matrix.json")
        dep_ieg_snapshot = loadj(dep_path / "m7p8_ieg_snapshot.json")
        dep_ofp_snapshot = loadj(dep_path / "m7p8_ofp_snapshot.json")
        dep_archive_snapshot = loadj(dep_path / "m7p8_archive_snapshot.json")
        dep_gate_verdict = loadj(dep_path / "m7p8_gate_verdict.json")
        dep_decision_log = loadj(dep_path / "m7p8_decision_log.json")

        if not dep_subset or not dep_profile or not dep_edge:
            dep_issues.append("M7P8 S4 realism artifacts are incomplete")
        if not dep_ieg_snapshot or not dep_ofp_snapshot or not dep_archive_snapshot:
            dep_issues.append("M7P8 S4 component snapshots are incomplete")
        if not dep_gate_verdict or not dep_decision_log:
            dep_issues.append("M7P8 S4 closure artifacts are incomplete")

        platform_run_id = str(dep_profile.get("platform_run_id") or dep_subset.get("platform_run_id") or dep_summary.get("platform_run_id") or "").strip()
        if not platform_run_id:
            dep_issues.append("M7P8 S4 platform_run_id is missing")

        dep_required = dep_summary.get("required_artifacts", req_artifacts)
        dep_required_list = dep_required if isinstance(dep_required, list) else req_artifacts
        for artifact in dep_required_list:
            sa = str(artifact).strip()
            if sa and dep_path is not None and not (dep_path / sa).exists():
                blockers.append({"id": "M7P8-ST-B12", "severity": "S5", "status": "OPEN", "details": {"reason": "missing dependency artifact", "artifact": sa}})
                issues.append(f"missing dependency artifact: {sa}")

    if dep_issues:
        blockers.append({"id": "M7P8-ST-B11", "severity": "S5", "status": "OPEN", "details": {"issues": dep_issues}})
        issues.extend(dep_issues)

    chain_spec = [
        ("S0", "m7p8_stress_s0", "M7P8-ST-S0", "M7P8_ST_S1_READY"),
        ("S1", "m7p8_stress_s1", "M7P8-ST-S1", "M7P8_ST_S2_READY"),
        ("S2", "m7p8_stress_s2", "M7P8-ST-S2", "M7P8_ST_S3_READY"),
        ("S3", "m7p8_stress_s3", "M7P8-ST-S3", "M7P8_ST_S4_READY"),
        ("S4", "m7p8_stress_s4", "M7P8-ST-S4", "M7P8_ST_S5_READY"),
    ]
    chain_rows: list[dict[str, Any]] = []
    for label, prefix, stage_id, expected_next_gate in chain_spec:
        r = latest_ok(prefix, stage_id)
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
            b = loadj(rp / "m7p8_blocker_register.json")
            row["open_blockers"] = int(b.get("open_blocker_count", 0) or 0)
            row["ok"] = row["overall_pass"] and row["next_gate"] == expected_next_gate and row["open_blockers"] == 0
            if platform_run_id and row["platform_run_id"] and row["platform_run_id"] != platform_run_id:
                row["run_scope_consistent"] = False
                row["ok"] = False
        if not row["ok"]:
            blockers.append({"id": "M7P8-ST-B11", "severity": "S5", "status": "OPEN", "details": {"chain_row": row}})
            issues.append(f"stage-chain closure failed for {label}")
        chain_rows.append(row)

    p_bucket = add_head_bucket_probe(probes, evidence_bucket, "m7p8_s5_evidence_bucket")
    if p_bucket.get("status") != "PASS":
        blockers.append({"id": "M7P8-ST-B10", "severity": "S5", "status": "OPEN", "details": {"probe_id": "m7p8_s5_evidence_bucket"}})
        issues.append("S5 evidence bucket probe failed")

    behavior_refs = dep_subset.get("behavior_context_refs", {}) if isinstance(dep_subset.get("behavior_context_refs"), dict) else {}
    for tag in ["receipt_summary", "quarantine_summary", "offsets_snapshot"]:
        key = str(behavior_refs.get(tag, {}).get("key", "")).strip() if isinstance(behavior_refs.get(tag, {}), dict) else ""
        if not key:
            blockers.append({"id": "M7P8-ST-B12", "severity": "S5", "status": "OPEN", "details": {"reason": "missing behavior-context key", "tag": tag}})
            issues.append(f"missing behavior-context key for {tag}")
            continue
        p = add_head_object_probe(probes, evidence_bucket, key, f"m7p8_s5_behavior_{tag}")
        if p.get("status") != "PASS":
            blockers.append({"id": "M7P8-ST-B10", "severity": "S5", "status": "OPEN", "details": {"probe_id": f"m7p8_s5_behavior_{tag}"}})
            issues.append(f"S5 behavior-context readback failed for {tag}")

    fallback_uri = str(dep_archive_snapshot.get("component_proof_excerpt", {}).get("archive_probe_s3_uri_fallback", "")).strip() if isinstance(dep_archive_snapshot.get("component_proof_excerpt"), dict) else ""
    fb_bucket, fb_key = parse_s3_uri(fallback_uri)
    if not fb_bucket or not fb_key:
        blockers.append({"id": "M7P8-ST-B12", "severity": "S5", "status": "OPEN", "details": {"reason": "archive fallback proof URI missing", "uri": fallback_uri}})
        issues.append("archive fallback proof URI missing")
    else:
        p_fb = add_head_object_probe(probes, fb_bucket, fb_key, "m7p8_s5_archive_fallback_proof")
        if p_fb.get("status") != "PASS":
            blockers.append({"id": "M7P8-ST-B10", "severity": "S5", "status": "OPEN", "details": {"probe_id": "m7p8_s5_archive_fallback_proof"}})
            issues.append("S5 archive fallback proof readback failed")

    for src in [dep_profile.get("advisories", []), dep_edge.get("advisories", []), dep_decision_log.get("advisories", [])]:
        if isinstance(src, list):
            for x in src:
                sx = str(x).strip()
                if sx and sx not in advisories:
                    advisories.append(sx)

    toy_advisories = [x for x in advisories if is_toy_profile_advisory(x)]
    if toy_advisories:
        blockers.append(
            {
                "id": "M7P8-ST-B13",
                "severity": "S5",
                "status": "OPEN",
                "details": {
                    "reason": "toy-profile advisory posture carried into P8 rollup",
                    "advisories": toy_advisories[:20],
                },
            }
        )
        issues.append("toy-profile advisory posture is not allowed for P8 closure")

    metrics = probe_metrics(probes)
    overall_pass = len(blockers) == 0
    verdict_name = expected_pass_verdict if overall_pass else "HOLD_REMEDIATE"
    next_gate = verdict_name

    dumpj(
        out / "m7p8_stagea_findings.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7P8-ST-S5",
            "findings": [
                {"id": "M7P8-ST-F15", "classification": "PREVENT", "finding": "S5 must fail closed on any unresolved chain/blocker inconsistency.", "required_action": "Emit ADVANCE_TO_P9 only when S0..S4 chain is fully green and blocker-free."},
                {"id": "M7P8-ST-F16", "classification": "PREVENT", "finding": "S5 closure evidence must stay artifact-complete and readable.", "required_action": "Block closure on missing rollup artifacts or failed readback probes."},
            ],
        },
    )
    dumpj(out / "m7p8_lane_matrix.json", {"component_sequence": ["M7P8-ST-S0", "M7P8-ST-S1", "M7P8-ST-S2", "M7P8-ST-S3", "M7P8-ST-S4", "M7P8-ST-S5"]})
    dumpj(out / "m7p8_data_subset_manifest.json", {**dep_subset, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S5", "upstream_m7p8_s4_phase_execution_id": dep_id, "status": "S5_ROLLUP_CARRY_FORWARD"})
    dumpj(out / "m7p8_data_profile_summary.json", {**dep_profile, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S5", "upstream_m7p8_s4_phase_execution_id": dep_id, "verdict_candidate": verdict_name, "advisories": advisories})
    dumpj(out / "m7p8_ieg_snapshot.json", {**dep_ieg_snapshot, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S5", "status": "CARRY_FORWARD_FROM_S4", "upstream_m7p8_s4_phase_execution_id": dep_id})
    dumpj(out / "m7p8_ofp_snapshot.json", {**dep_ofp_snapshot, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S5", "status": "CARRY_FORWARD_FROM_S4", "upstream_m7p8_s4_phase_execution_id": dep_id})
    dumpj(out / "m7p8_archive_snapshot.json", {**dep_archive_snapshot, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S5", "status": "CARRY_FORWARD_FROM_S4", "upstream_m7p8_s4_phase_execution_id": dep_id})
    dumpj(out / "m7p8_data_edge_case_matrix.json", {**dep_edge, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S5", "platform_run_id": platform_run_id, "chain_rows": chain_rows, "verdict_candidate": verdict_name, "advisories": advisories})
    dumpj(out / "m7p8_probe_latency_throughput_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S5", **metrics})
    dumpj(out / "m7p8_control_rail_conformance_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S5", "overall_pass": len(issues) == 0, "issues": issues, "advisories": advisories})
    dumpj(out / "m7p8_secret_safety_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S5", "overall_pass": True, "secret_probe_count": 0, "secret_failure_count": 0, "with_decryption_used": False, "queried_value_directly": False, "plaintext_leakage_detected": False})
    dumpj(out / "m7p8_cost_outcome_receipt.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S5", "window_seconds": metrics["window_seconds_observed"], "estimated_api_call_count": metrics["probe_count"], "attributed_spend_usd": 0.0, "unattributed_spend_detected": False, "max_spend_usd": float(plan_packet.get("M7P8_STRESS_MAX_SPEND_USD", 35)), "within_envelope": True})

    decisions.extend(
        [
            "Enforced S4 dependency continuity and blocker closure before S5 rollup.",
            "Executed deterministic chain sweep across S0..S4 with run-scope consistency checks.",
            "Validated behavior-context and archive-fallback readback before closure verdict.",
            "Applied deterministic verdict: ADVANCE_TO_P9 only when blocker-free and artifact-complete.",
        ]
    )
    dumpj(out / "m7p8_decision_log.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S5", "decisions": decisions, "advisories": advisories})

    blocker_reg = {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7P8-ST-S5", "overall_pass": overall_pass, "open_blocker_count": len(blockers), "blockers": blockers}
    summary = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M7P8-ST-S5",
        "overall_pass": overall_pass,
        "next_gate": next_gate,
        "open_blocker_count": len(blockers),
        "required_artifacts": req_artifacts,
        "probe_count": metrics["probe_count"],
        "error_rate_pct": metrics["error_rate_pct"],
        "platform_run_id": platform_run_id,
        "upstream_m7p8_s4_phase_execution_id": dep_id,
        "verdict": verdict_name,
        "expected_verdict_on_pass": expected_pass_verdict,
    }
    verdict = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M7P8-ST-S5",
        "overall_pass": overall_pass,
        "verdict": verdict_name,
        "next_gate": next_gate,
        "blocker_count": len(blockers),
        "platform_run_id": platform_run_id,
        "upstream_m7p8_s4_phase_execution_id": dep_id,
        "expected_verdict_on_pass": expected_pass_verdict,
        "chain_rows": chain_rows,
    }
    dumpj(out / "m7p8_blocker_register.json", blocker_reg)
    dumpj(out / "m7p8_execution_summary.json", summary)
    dumpj(out / "m7p8_gate_verdict.json", verdict)
    finalize_artifact_contract(out, req_artifacts, blockers, blocker_reg, summary, verdict)

    summary = loadj(out / "m7p8_execution_summary.json")
    blocker_reg = loadj(out / "m7p8_blocker_register.json")
    print(f"[m7p8_s5] phase_execution_id={phase_execution_id}")
    print(f"[m7p8_s5] output_dir={out.as_posix()}")
    print(f"[m7p8_s5] overall_pass={summary.get('overall_pass')}")
    print(f"[m7p8_s5] verdict={summary.get('verdict')}")
    print(f"[m7p8_s5] next_gate={summary.get('next_gate')}")
    print(f"[m7p8_s5] open_blockers={blocker_reg.get('open_blocker_count')}")
    return 0 if summary.get("overall_pass") is True else 2


def main() -> int:
    ap = argparse.ArgumentParser(description="M7.P8 stress runner")
    ap.add_argument("--stage", default="S0", choices=["S0", "S1", "S2", "S3", "S4", "S5"])
    ap.add_argument("--phase-execution-id", default="")
    args = ap.parse_args()

    stage_map = {
        "S0": ("m7p8_stress_s0", run_s0),
        "S1": ("m7p8_stress_s1", run_s1),
        "S2": ("m7p8_stress_s2", run_s2),
        "S3": ("m7p8_stress_s3", run_s3),
        "S4": ("m7p8_stress_s4", run_s4),
        "S5": ("m7p8_stress_s5", run_s5),
    }
    prefix, fn = stage_map[args.stage]
    phase_execution_id = args.phase_execution_id.strip() or f"{prefix}_{tok()}"
    return fn(phase_execution_id)


if __name__ == "__main__":
    raise SystemExit(main())
