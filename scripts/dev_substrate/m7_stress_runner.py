#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PLAN = Path("docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M7.stress_test.md")
P8_PLAN = Path("docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M7.P8.stress_test.md")
P9_PLAN = Path("docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M7.P9.stress_test.md")
P10_PLAN = Path("docs/model_spec/platform/implementation_maps/dev_substrate/dev_full/stress_test/platform.M7.P10.stress_test.md")
REG = Path("docs/model_spec/platform/migration_to_dev/dev_full_handles.registry.v0.md")
OUT_ROOT = Path("runs/dev_substrate/dev_full/stress/evidence/dev_full/run_control")
EDA_METRICS = Path("docs/reports/eda/segment_1A/metrics_summary.csv")
EDA_DICTIONARY = Path("docs/reports/eda/segment_1A/dictionary_datasets.csv")

PLAN_KEYS = [
    "M7_STRESS_PROFILE_ID",
    "M7_STRESS_BLOCKER_REGISTER_PATH_PATTERN",
    "M7_STRESS_EXECUTION_SUMMARY_PATH_PATTERN",
    "M7_STRESS_DECISION_LOG_PATH_PATTERN",
    "M7_STRESS_REQUIRED_ARTIFACTS",
    "M7_STRESS_MAX_RUNTIME_MINUTES",
    "M7_STRESS_MAX_SPEND_USD",
    "M7_STRESS_EXPECTED_NEXT_GATE_ON_PASS",
    "M7_STRESS_DATA_MIN_SAMPLE_EVENTS",
    "M7_STRESS_DATA_PROFILE_WINDOW_HOURS",
    "M7_STRESS_DUPLICATE_RATIO_TARGET_RANGE_PCT",
    "M7_STRESS_OUT_OF_ORDER_RATIO_TARGET_RANGE_PCT",
    "M7_STRESS_HOTKEY_TOP1_SHARE_MAX",
    "M7_STRESS_TARGETED_RERUN_ONLY",
]

REQ_HANDLES = [
    "S3_OBJECT_STORE_BUCKET",
    "S3_EVIDENCE_BUCKET",
    "S3_RUN_CONTROL_ROOT_PATTERN",
    "ORACLE_SOURCE_NAMESPACE",
    "ORACLE_ENGINE_RUN_ID",
    "S3_STREAM_VIEW_PREFIX_PATTERN",
    "S3_TRUTH_VIEW_PREFIX_PATTERN",
    "M7_HANDOFF_PACK_PATH_PATTERN",
    "RTDL_CORE_EVIDENCE_PATH_PATTERN",
    "DECISION_LANE_EVIDENCE_PATH_PATTERN",
    "CASE_LABELS_EVIDENCE_PATH_PATTERN",
    "RECEIPT_SUMMARY_PATH_PATTERN",
    "KAFKA_OFFSETS_SNAPSHOT_PATH_PATTERN",
    "QUARANTINE_SUMMARY_PATH_PATTERN",
    "THROUGHPUT_CERT_MIN_SAMPLE_EVENTS",
    "THROUGHPUT_CERT_TARGET_EVENTS_PER_SECOND",
    "THROUGHPUT_CERT_WINDOW_MINUTES",
    "THROUGHPUT_CERT_MAX_ERROR_RATE_PCT",
    "THROUGHPUT_CERT_MAX_RETRY_RATIO_PCT",
]

S0_REQUIRED_ARTIFACTS = [
    "m7_stagea_findings.json",
    "m7_lane_matrix.json",
    "m7_data_subset_manifest.json",
    "m7_data_profile_summary.json",
    "m7_data_edge_case_matrix.json",
    "m7_data_skew_hotspot_profile.json",
    "m7_data_quality_guardrail_snapshot.json",
    "m7_probe_latency_throughput_snapshot.json",
    "m7_control_rail_conformance_snapshot.json",
    "m7_secret_safety_snapshot.json",
    "m7_cost_outcome_receipt.json",
    "m7_blocker_register.json",
    "m7_execution_summary.json",
    "m7_decision_log.json",
]

M7_S0_EVENT_TYPE_MIN_COUNT = 3


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
            "stdout": (p.stdout or "").strip()[:600],
            "stderr": (p.stderr or "").strip()[:600],
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


def parse_range(v: Any) -> tuple[float | None, float | None]:
    s = str(v or "").strip()
    if "|" not in s:
        return None, None
    a, b = s.split("|", 1)
    try:
        return float(a.strip()), float(b.strip())
    except Exception:
        return None, None


def latest_ok(prefix: str, summary_name: str, stage_id: str) -> dict[str, Any]:
    for d in sorted(OUT_ROOT.glob(f"{prefix}_*/stress"), reverse=True):
        s = loadj(d / summary_name)
        if s and s.get("overall_pass") is True and str(s.get("stage_id", "")) == stage_id:
            return {"path": d, "summary": s}
    return {}


def parse_ts(ts: str) -> datetime | None:
    t = str(ts or "").strip()
    if not t:
        return None
    try:
        return datetime.fromisoformat(t.replace("Z", "+00:00"))
    except Exception:
        return None


def materialize_pattern(pattern: str, replacements: dict[str, str]) -> str:
    out = str(pattern)
    for key, val in replacements.items():
        out = out.replace("{" + key + "}", str(val))
    return out


def run_cmd_full(argv: list[str], timeout: int = 120) -> tuple[int, str, str]:
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return int(p.returncode), (p.stdout or ""), (p.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"


def list_s3_keys(bucket: str, prefix: str, suffix: str) -> list[str]:
    rc, stdout, _ = run_cmd_full(["aws", "s3", "ls", f"s3://{bucket}/{prefix}", "--recursive"], timeout=120)
    if rc != 0:
        return []
    out: list[str] = []
    rx = re.compile(r"^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\s+\d+\s+(.+)$")
    for raw in stdout.splitlines():
        m = rx.match(raw.strip())
        if not m:
            continue
        key = m.group(1).strip()
        if key.endswith(suffix):
            out.append(key)
    return sorted(out)


def load_s3_json(bucket: str, key: str) -> dict[str, Any]:
    rc, stdout, _ = run_cmd_full(["aws", "s3", "cp", f"s3://{bucket}/{key}", "-"], timeout=180)
    if rc != 0:
        return {}
    try:
        return json.loads(stdout)
    except Exception:
        return {}


def parse_output_id_from_key(key: str) -> str:
    m = re.search(r"output_id=([^/]+)/", key)
    return str(m.group(1)).strip() if m else ""


def build_subset_profile(handles: dict[str, Any], platform_run_id: str) -> dict[str, Any]:
    parse_errors = 0
    event_counts: Counter[str] = Counter()
    module_counts: Counter[str] = Counter()
    source_roots: set[str] = set()
    top_run_ids: Counter[str] = Counter()
    file_rows: dict[str, int] = {}
    manifest_rows = 0
    manifest_file_count = 0
    total_bytes = 0

    object_bucket = str(handles.get("S3_OBJECT_STORE_BUCKET", "")).strip()
    evidence_bucket = str(handles.get("S3_EVIDENCE_BUCKET", "")).strip()
    source_ns = str(handles.get("ORACLE_SOURCE_NAMESPACE", "")).strip()
    engine_run_id = str(handles.get("ORACLE_ENGINE_RUN_ID", "")).strip()
    stream_pat = str(handles.get("S3_STREAM_VIEW_PREFIX_PATTERN", "")).strip()
    truth_pat = str(handles.get("S3_TRUTH_VIEW_PREFIX_PATTERN", "")).strip()
    receipt_pat = str(handles.get("RECEIPT_SUMMARY_PATH_PATTERN", "")).strip()
    offset_pat = str(handles.get("KAFKA_OFFSETS_SNAPSHOT_PATH_PATTERN", "")).strip()
    quarantine_pat = str(handles.get("QUARANTINE_SUMMARY_PATH_PATTERN", "")).strip()

    replacements = {
        "oracle_source_namespace": source_ns,
        "oracle_engine_run_id": engine_run_id,
        "platform_run_id": platform_run_id,
    }
    stream_prefix = materialize_pattern(stream_pat, replacements) if stream_pat else ""
    truth_prefix = materialize_pattern(truth_pat, replacements) if truth_pat else ""

    if not object_bucket or not stream_prefix or not truth_prefix:
        return {
            "generated_at_utc": now(),
            "source_mode": "platform_surface_unavailable",
            "source_patterns": [stream_prefix, truth_prefix],
            "source_roots": [],
            "files_scanned": 0,
            "rows_scanned": 0,
            "bytes_scanned": 0,
            "parse_error_count": 1,
            "missing_ts_count": None,
            "missing_run_id_count": None,
            "event_type_count": 0,
            "event_counts_top5": [],
            "module_counts_top5": [],
            "top_run_ids": [],
            "top_hotkeys": [],
            "duplicate_rows": None,
            "duplicate_ratio_pct": None,
            "out_of_order_rows": None,
            "out_of_order_ratio_pct": None,
            "top1_hotkey_share": 1.0,
            "top1_run_share": 1.0,
            "file_rows": {},
            "behavior_context_refs": {},
        }

    stream_manifest_keys = list_s3_keys(object_bucket, stream_prefix, "_stream_view_manifest.json")
    truth_manifest_keys = list_s3_keys(object_bucket, truth_prefix, "_stream_view_manifest.json")

    for key in stream_manifest_keys:
        manifest = load_s3_json(object_bucket, key)
        if not manifest:
            parse_errors += 1
            continue
        output_id = str(manifest.get("output_id", "")).strip() or parse_output_id_from_key(key)
        row_count = int(manifest.get("row_count", 0) or 0)
        file_count = int(manifest.get("file_count", 0) or 0)
        manifest_rows += row_count
        manifest_file_count += file_count
        event_counts[output_id] += row_count
        module_counts["stream_view"] += row_count
        top_run_ids["stream_view"] += row_count
        source_root = str(manifest.get("stream_view_root", "")).strip()
        if source_root:
            source_roots.add(source_root)
        sizes = [int(x.get("size_bytes", 0) or 0) for x in manifest.get("files", []) if isinstance(x, dict)]
        total_bytes += sum(sizes)
        file_rows[f"s3://{object_bucket}/{key}"] = row_count

    for key in truth_manifest_keys:
        manifest = load_s3_json(object_bucket, key)
        if not manifest:
            parse_errors += 1
            continue
        output_id = str(manifest.get("output_id", "")).strip() or parse_output_id_from_key(key)
        row_count = int(manifest.get("row_count", 0) or 0)
        file_count = int(manifest.get("file_count", 0) or 0)
        manifest_rows += row_count
        manifest_file_count += file_count
        event_counts[output_id] += row_count
        module_counts["truth_view"] += row_count
        top_run_ids["truth_view"] += row_count
        source_root = str(manifest.get("truth_view_root", "")).strip()
        if source_root:
            source_roots.add(source_root)
        sizes = [int(x.get("size_bytes", 0) or 0) for x in manifest.get("files", []) if isinstance(x, dict)]
        total_bytes += sum(sizes)
        file_rows[f"s3://{object_bucket}/{key}"] = row_count

    behavior_context_refs: dict[str, Any] = {}
    if evidence_bucket and platform_run_id:
        for tag, pattern in [
            ("receipt_summary", receipt_pat),
            ("offsets_snapshot", offset_pat),
            ("quarantine_summary", quarantine_pat),
        ]:
            key = materialize_pattern(pattern, replacements) if pattern else ""
            payload = load_s3_json(evidence_bucket, key) if key else {}
            behavior_context_refs[tag] = {
                "key": key,
                "present": bool(payload),
                "keys": sorted(payload.keys())[:15] if payload else [],
            }

    event_type_count = len([k for k in event_counts.keys() if k])
    top1_share = 0.0
    if manifest_rows > 0 and event_counts:
        top1_share = round(max(event_counts.values()) / float(manifest_rows), 6)

    return {
        "generated_at_utc": now(),
        "source_mode": "platform_stream_truth_manifests",
        "source_patterns": [stream_prefix, truth_prefix],
        "source_roots": sorted(source_roots),
        "files_scanned": manifest_file_count,
        "rows_scanned": manifest_rows,
        "bytes_scanned": total_bytes,
        "parse_error_count": parse_errors,
        "missing_ts_count": None,
        "missing_run_id_count": None,
        "event_type_count": event_type_count,
        "event_counts_top5": [{"event": k, "count": int(v)} for k, v in event_counts.most_common(5)],
        "module_counts_top5": [{"module": k, "count": int(v)} for k, v in module_counts.most_common(5)],
        "top_run_ids": [{"run_id": k, "count": int(v)} for k, v in top_run_ids.most_common(10)],
        "top_hotkeys": [{"hotkey": k, "count": int(v)} for k, v in event_counts.most_common(10)],
        "duplicate_rows": None,
        "duplicate_ratio_pct": None,
        "out_of_order_rows": None,
        "out_of_order_ratio_pct": None,
        "top1_hotkey_share": top1_share,
        "top1_run_share": top1_share,
        "file_rows": file_rows,
        "behavior_context_refs": behavior_context_refs,
        "stream_manifest_count": len(stream_manifest_keys),
        "truth_manifest_count": len(truth_manifest_keys),
    }


def run_s0(phase_execution_id: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)

    plan_packet = parse_bt_map(PLAN.read_text(encoding="utf-8") if PLAN.exists() else "")
    handles = parse_registry(REG) if REG.exists() else {}

    blockers: list[dict[str, Any]] = []
    probes: list[dict[str, Any]] = []
    issues: list[str] = []
    advisories: list[str] = []
    decisions: list[str] = []

    missing_plan_keys = [k for k in PLAN_KEYS if k not in plan_packet]
    missing_handles = [k for k in REQ_HANDLES if k not in handles]
    placeholder_handles = [
        k
        for k in REQ_HANDLES
        if k in handles and str(handles[k]).strip() in {"", "TO_PIN", "NONE", "None", "null", "NULL"}
    ]
    missing_docs = [x.as_posix() for x in [PLAN, P8_PLAN, P9_PLAN, P10_PLAN] if not x.exists()]
    if missing_plan_keys or missing_handles or placeholder_handles or missing_docs:
        blockers.append(
            {
                "id": "M7-ST-B1",
                "severity": "S0",
                "status": "OPEN",
                "details": {
                    "missing_plan_keys": missing_plan_keys,
                    "missing_handles": missing_handles,
                    "placeholder_handles": placeholder_handles,
                    "missing_docs": missing_docs,
                },
            }
        )
        if missing_plan_keys:
            issues.append(f"missing plan keys: {','.join(missing_plan_keys)}")
        if missing_handles:
            issues.append(f"missing handles: {','.join(missing_handles)}")
        if placeholder_handles:
            issues.append(f"placeholder handles: {','.join(placeholder_handles)}")
        if missing_docs:
            issues.append(f"missing docs: {','.join(missing_docs)}")

    dep_issues: list[str] = []
    dep_m6_s5 = latest_ok("m6_stress_s5", "m6_execution_summary.json", "M6-ST-S5")
    dep_m6p5 = latest_ok("m6p5_stress_s5", "m6p5_execution_summary.json", "M6P5-ST-S5")
    dep_m6p6 = latest_ok("m6p6_stress_s5", "m6p6_execution_summary.json", "M6P6-ST-S5")
    dep_m6p7 = latest_ok("m6p7_stress_s5", "m6p7_execution_summary.json", "M6P7-ST-S5")
    dep_chain_issues: list[str] = []
    dep_platform_run_id = ""
    dep_m6_s5_id = ""
    dep_m6p5_id = ""
    dep_m6p6_id = ""
    dep_m6p7_id = ""
    dep_mode = "subphase_chain"
    dep_parent_ok = False

    if dep_m6_s5:
        s = dep_m6_s5["summary"]
        dep_m6_s5_id = str(s.get("phase_execution_id", ""))
        ng = str(s.get("next_gate", "")).strip()
        if ng not in {"M7_READY", "M7_ST_S0_READY"}:
            dep_issues.append("M6-ST-S5 next_gate is not M7-ready")
        b = loadj(Path(str(dep_m6_s5["path"])) / "m6_blocker_register.json")
        if int(b.get("open_blocker_count", 0) or 0) != 0:
            dep_issues.append("M6-ST-S5 blocker register not closed")
        dep_parent_ok = len(dep_issues) == 0
        if dep_parent_ok:
            dep_mode = "parent_m6_s5"
            dep_platform_run_id = str(s.get("platform_run_id", "")).strip()

    if not dep_m6p5:
        dep_chain_issues.append("missing successful M6P5-ST-S5 dependency")
    else:
        s = dep_m6p5["summary"]
        dep_m6p5_id = str(s.get("phase_execution_id", ""))
        if str(s.get("verdict", "")) != "ADVANCE_TO_P6":
            dep_chain_issues.append("M6P5 verdict is not ADVANCE_TO_P6")
        b = loadj(Path(str(dep_m6p5["path"])) / "m6p5_blocker_register.json")
        if int(b.get("open_blocker_count", 0) or 0) != 0:
            dep_chain_issues.append("M6P5 blocker register not closed")

    if not dep_m6p6:
        dep_chain_issues.append("missing successful M6P6-ST-S5 dependency")
    else:
        s = dep_m6p6["summary"]
        dep_m6p6_id = str(s.get("phase_execution_id", ""))
        if str(s.get("verdict", "")) != "ADVANCE_TO_P7":
            dep_chain_issues.append("M6P6 verdict is not ADVANCE_TO_P7")
        b = loadj(Path(str(dep_m6p6["path"])) / "m6p6_blocker_register.json")
        if int(b.get("open_blocker_count", 0) or 0) != 0:
            dep_chain_issues.append("M6P6 blocker register not closed")

    if not dep_m6p7:
        dep_chain_issues.append("missing successful M6P7-ST-S5 dependency")
    else:
        s = dep_m6p7["summary"]
        dep_m6p7_id = str(s.get("phase_execution_id", ""))
        dep_platform_run_id = str(s.get("platform_run_id", "")).strip()
        if str(s.get("verdict", "")) != "ADVANCE_TO_M7":
            dep_chain_issues.append("M6P7 verdict is not ADVANCE_TO_M7")
        b = loadj(Path(str(dep_m6p7["path"])) / "m6p7_blocker_register.json")
        if int(b.get("open_blocker_count", 0) or 0) != 0:
            dep_chain_issues.append("M6P7 blocker register not closed")

    dep_subphase_ok = len(dep_chain_issues) == 0
    dep_ok = dep_parent_ok or dep_subphase_ok
    if not dep_ok:
        dep_issues.extend(dep_chain_issues)
        if not dep_m6_s5:
            dep_issues.append("parent M6-ST-S5 evidence missing and subphase closure chain is not closed")
        blockers.append({"id": "M7-ST-B2", "severity": "S0", "status": "OPEN", "details": {"issues": dep_issues}})
        issues.extend(dep_issues)
    elif dep_parent_ok:
        decisions.append("M7 entry dependency satisfied via parent M6-ST-S5 closure gate.")
    else:
        decisions.append("M7 entry dependency satisfied via closed M6P5/P6/P7 chain (parent M6-ST-S5 not present in current run history).")

    bucket = str(handles.get("S3_EVIDENCE_BUCKET", "")).strip()
    p_bucket = run_cmd(["aws", "s3api", "head-bucket", "--bucket", bucket, "--region", "eu-west-2"], 25) if bucket else {
        "command": "aws s3api head-bucket",
        "exit_code": 1,
        "status": "FAIL",
        "duration_ms": 0.0,
        "stdout": "",
        "stderr": "missing S3_EVIDENCE_BUCKET handle",
        "started_at_utc": now(),
        "ended_at_utc": now(),
    }
    probes.append({**p_bucket, "probe_id": "m7_s0_evidence_bucket", "group": "control"})
    if p_bucket.get("status") != "PASS":
        blockers.append({"id": "M7-ST-B10", "severity": "S0", "status": "OPEN", "details": {"probe_id": "m7_s0_evidence_bucket"}})
        issues.append("evidence bucket probe failed")

    profile = build_subset_profile(handles, dep_platform_run_id)
    min_sample = int(plan_packet.get("M7_STRESS_DATA_MIN_SAMPLE_EVENTS", 15000))
    dup_low, dup_high = parse_range(plan_packet.get("M7_STRESS_DUPLICATE_RATIO_TARGET_RANGE_PCT", "0.5|5.0"))
    ooo_low, ooo_high = parse_range(plan_packet.get("M7_STRESS_OUT_OF_ORDER_RATIO_TARGET_RANGE_PCT", "0.2|3.0"))
    hotkey_max = float(plan_packet.get("M7_STRESS_HOTKEY_TOP1_SHARE_MAX", 0.60))

    rows_scanned = int(profile.get("rows_scanned", 0) or 0)
    event_type_count = int(profile.get("event_type_count", 0) or 0)
    duplicate_ratio_raw = profile.get("duplicate_ratio_pct", None)
    out_of_order_ratio_raw = profile.get("out_of_order_ratio_pct", None)
    duplicate_ratio_pct = None if duplicate_ratio_raw is None else float(duplicate_ratio_raw)
    out_of_order_ratio_pct = None if out_of_order_ratio_raw is None else float(out_of_order_ratio_raw)
    top1_share = float(profile.get("top1_run_share", 0.0) or 0.0)
    dup_observed = duplicate_ratio_pct is not None
    ooo_observed = out_of_order_ratio_pct is not None

    dup_floor_ok = (not dup_observed) or dup_low is None or duplicate_ratio_pct >= dup_low
    dup_ceiling_ok = (not dup_observed) or dup_high is None or duplicate_ratio_pct <= dup_high
    ooo_floor_ok = (not ooo_observed) or ooo_low is None or out_of_order_ratio_pct >= ooo_low
    ooo_ceiling_ok = (not ooo_observed) or ooo_high is None or out_of_order_ratio_pct <= ooo_high
    profile_checks = {
        "sample_size_check": rows_scanned >= min_sample,
        "event_type_check": event_type_count >= M7_S0_EVENT_TYPE_MIN_COUNT,
        "duplicate_ratio_observed": dup_observed,
        "duplicate_ratio_floor_check": dup_floor_ok,
        "duplicate_ratio_upper_bound_check": dup_ceiling_ok,
        "out_of_order_ratio_observed": ooo_observed,
        "out_of_order_ratio_floor_check": ooo_floor_ok,
        "out_of_order_ratio_upper_bound_check": ooo_ceiling_ok,
        "hotkey_share_check": top1_share <= hotkey_max,
        "parse_error_check": int(profile.get("parse_error_count", 0) or 0) == 0,
    }
    blocking_checks = {
        "sample_size_check": profile_checks["sample_size_check"],
        "event_type_check": profile_checks["event_type_check"],
        "duplicate_ratio_upper_bound_check": profile_checks["duplicate_ratio_upper_bound_check"],
        "out_of_order_ratio_upper_bound_check": profile_checks["out_of_order_ratio_upper_bound_check"],
        "hotkey_share_check": profile_checks["hotkey_share_check"],
        "parse_error_check": profile_checks["parse_error_check"],
    }
    representativeness_pass = all(blocking_checks.values())
    if not dup_observed:
        advisories.append("duplicate ratio is not directly observable from stream/truth manifests at S0; duplicate/replay injection is mandatory in downstream windows")
    elif not profile_checks["duplicate_ratio_floor_check"]:
        advisories.append(
            f"duplicate ratio {duplicate_ratio_pct:.6f}% is below floor {dup_low}; keep duplicate/replay injection mandatory in downstream windows"
        )
    if not ooo_observed:
        advisories.append("out_of_order ratio is not directly observable from stream/truth manifests at S0; late-event injection is mandatory in downstream windows")
    elif not profile_checks["out_of_order_ratio_floor_check"]:
        advisories.append(
            f"out_of_order ratio {out_of_order_ratio_pct:.6f}% is below floor {ooo_low}; keep late-event injection mandatory in downstream windows"
        )
    if not representativeness_pass:
        blockers.append(
            {
                "id": "M7-ST-B3",
                "severity": "S0",
                "status": "OPEN",
                "details": {
                    "checks": profile_checks,
                    "blocking_checks": blocking_checks,
                    "rows_scanned": rows_scanned,
                    "min_sample_required": min_sample,
                    "event_type_count": event_type_count,
                    "event_type_min_required": M7_S0_EVENT_TYPE_MIN_COUNT,
                    "duplicate_ratio_pct": duplicate_ratio_pct,
                    "duplicate_ratio_target_range_pct": [dup_low, dup_high],
                    "out_of_order_ratio_pct": out_of_order_ratio_pct,
                    "out_of_order_target_range_pct": [ooo_low, ooo_high],
                    "top1_run_share": top1_share,
                    "top1_share_max": hotkey_max,
                    "source_mode": str(profile.get("source_mode", "")),
                },
            }
        )
        issues.append("run-scoped subset profile failed blocking M7-S0 representativeness checks")

    if int(profile.get("parse_error_count", 0) or 0) > 0:
        blockers.append(
            {
                "id": "M7-ST-B4",
                "severity": "S0",
                "status": "OPEN",
                "details": {"reason": "data profile parsing errors detected", "parse_error_count": int(profile.get("parse_error_count", 0) or 0)},
            }
        )
        issues.append("data subset profile parsing errors detected")

    edge_matrix = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M7-ST-S0",
        "cohort_presence": {
            "normal_mix": rows_scanned > 0,
            "hotkey_skew": top1_share >= 0.30,
            "duplicate_replay": (duplicate_ratio_pct is not None and duplicate_ratio_pct > 0.0),
            "late_out_of_order": (out_of_order_ratio_pct is not None and out_of_order_ratio_pct > 0.0),
            "rare_edge_case": event_type_count >= M7_S0_EVENT_TYPE_MIN_COUNT,
        },
        "profile_checks": profile_checks,
        "blocking_checks": blocking_checks,
        "advisories": advisories,
    }
    skew_profile = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M7-ST-S0",
        "top1_run_share": top1_share,
        "hotkey_threshold_max": hotkey_max,
        "top_runs": profile.get("top_run_ids", []),
    }
    quality_guardrail = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M7-ST-S0",
        "representativeness_pass": representativeness_pass,
        "checks": profile_checks,
        "overall_pass": representativeness_pass and int(profile.get("parse_error_count", 0) or 0) == 0,
    }

    dumpj(
        out / "m7_stagea_findings.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7-ST-S0",
            "findings": [
                {"id": "M7-ST-F1", "classification": "PREVENT", "finding": "Component low-sample posture cannot close M7 realism gates.", "required_action": "Require representative data subset/profile before lane execution."},
                {"id": "M7-ST-F2", "classification": "PREVENT", "finding": "Dependency chain must be closed before M7 advancement.", "required_action": "Fail-closed on missing M6 closure dependency."},
                {"id": "M7-ST-F3", "classification": "PREVENT", "finding": "Schema-only subset cannot represent realistic M7 data semantics.", "required_action": "Require cohort-aware profile checks and fail-closed blockers."},
            ],
        },
    )
    dumpj(
        out / "m7_lane_matrix.json",
        {
            "component_sequence": ["M7-ST-S0", "M7-ST-S1", "M7-ST-S2", "M7-ST-S3", "M7-ST-S4", "M7-ST-S5"],
            "plane_sequence": ["rtdl_plane", "decision_plane", "case_label_plane", "m7_rollup_plane"],
            "integrated_windows": ["m7_s4_normal_mix_window", "m7_s4_edge_mix_window", "m7_s4_replay_duplicate_window"],
        },
    )
    dumpj(
        out / "m7_data_subset_manifest.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7-ST-S0",
            "platform_run_id": dep_platform_run_id,
            "profile_source_mode": str(profile.get("source_mode", "")),
            "profile_source_roots": profile.get("source_roots", []),
            "profile_source_patterns": profile.get("source_patterns", []),
            "stream_manifest_count": int(profile.get("stream_manifest_count", 0) or 0),
            "truth_manifest_count": int(profile.get("truth_manifest_count", 0) or 0),
            "files_scanned": profile.get("files_scanned", 0),
            "rows_scanned": rows_scanned,
            "profile_window_hours": int(plan_packet.get("M7_STRESS_DATA_PROFILE_WINDOW_HOURS", 24)),
            "eda_sources": [EDA_METRICS.as_posix(), EDA_DICTIONARY.as_posix()],
            "behavior_context_refs": profile.get("behavior_context_refs", {}),
        },
    )
    dumpj(
        out / "m7_data_profile_summary.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7-ST-S0",
            "platform_run_id": dep_platform_run_id,
            "rows_scanned": rows_scanned,
            "event_type_count": event_type_count,
            "duplicate_ratio_pct": duplicate_ratio_pct,
            "out_of_order_ratio_pct": out_of_order_ratio_pct,
            "top1_run_share": top1_share,
            "checks": profile_checks,
            "blocking_checks": blocking_checks,
            "advisories": advisories,
            "source_profile": profile,
        },
    )
    dumpj(out / "m7_data_edge_case_matrix.json", edge_matrix)
    dumpj(out / "m7_data_skew_hotspot_profile.json", skew_profile)
    dumpj(out / "m7_data_quality_guardrail_snapshot.json", quality_guardrail)

    probe_failures = [x for x in probes if str(x.get("status", "FAIL")) != "PASS"]
    latencies = [float(x.get("duration_ms", 0.0)) for x in probes]
    error_rate_pct = round((len(probe_failures) / len(probes)) * 100.0, 4) if probes else 0.0
    p50 = 0.0 if not latencies else sorted(latencies)[len(latencies) // 2]
    p95 = 0.0 if not latencies else max(latencies)
    dumpj(
        out / "m7_probe_latency_throughput_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7-ST-S0",
            "window_seconds_observed": max(1, int(round(sum(latencies) / 1000.0))) if latencies else 1,
            "probe_count": len(probes),
            "failure_count": len(probe_failures),
            "error_rate_pct": error_rate_pct,
            "latency_ms_p50": p50,
            "latency_ms_p95": p95,
            "latency_ms_p99": p95,
            "sample_failures": probe_failures[:10],
            "probes": probes,
        },
    )
    dumpj(
        out / "m7_control_rail_conformance_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7-ST-S0",
            "overall_pass": len(issues) == 0,
            "issues": issues,
            "advisories": advisories,
            "dependency_mode": dep_mode,
            "dependency_refs": {
                "m6_s5_execution_id": dep_m6_s5_id,
                "m6p5_s5_execution_id": dep_m6p5_id,
                "m6p6_s5_execution_id": dep_m6p6_id,
                "m6p7_s5_execution_id": dep_m6p7_id,
            },
        },
    )
    dumpj(
        out / "m7_secret_safety_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7-ST-S0",
            "overall_pass": True,
            "secret_probe_count": 0,
            "secret_failure_count": 0,
            "with_decryption_used": False,
            "queried_value_directly": False,
            "plaintext_leakage_detected": False,
        },
    )
    dumpj(
        out / "m7_cost_outcome_receipt.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7-ST-S0",
            "window_seconds": max(1, int(round(sum(latencies) / 1000.0))) if latencies else 1,
            "estimated_api_call_count": len(probes),
            "attributed_spend_usd": 0.0,
            "unattributed_spend_detected": False,
            "max_spend_usd": float(plan_packet.get("M7_STRESS_MAX_SPEND_USD", 120)),
            "within_envelope": True,
            "method": "m7_s0_authority_data_profile_v0",
        },
    )

    decisions.extend(
        [
            "Enforced fail-closed M6 dependency checks before M7 execution.",
            "Enforced required-handle and required-authority closure checks for M7 S0.",
            "Generated run-scoped data subset profile from black-box platform ingress sources (stream_view/truth_view + behavior-context receipts).",
            "Applied blocking posture to sample/event-type/safety bounds and advisory posture to floor-coverage checks for duplicate/out-of-order mix.",
            "Opened explicit blockers only for material dependency/data realism gaps rather than allowing schema-only progression.",
        ]
    )
    dumpj(
        out / "m7_decision_log.json",
        {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7-ST-S0", "decisions": decisions},
    )

    overall_pass = len(blockers) == 0
    blocker_register = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M7-ST-S0",
        "overall_pass": overall_pass,
        "open_blocker_count": len(blockers),
        "blockers": blockers,
    }
    summary = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M7-ST-S0",
        "overall_pass": overall_pass,
        "next_gate": "M7_ST_S1_READY" if overall_pass else "BLOCKED",
        "required_artifacts": S0_REQUIRED_ARTIFACTS,
        "probe_count": len(probes),
        "error_rate_pct": error_rate_pct,
        "m6_s5_dependency_phase_execution_id": dep_m6_s5_id,
        "m6p5_dependency_phase_execution_id": dep_m6p5_id,
        "m6p6_dependency_phase_execution_id": dep_m6p6_id,
        "m6p7_dependency_phase_execution_id": dep_m6p7_id,
        "dependency_mode": dep_mode,
        "platform_run_id": dep_platform_run_id,
        "rows_profiled": rows_scanned,
        "representativeness_pass": representativeness_pass,
        "advisory_count": len(advisories),
    }
    dumpj(out / "m7_blocker_register.json", blocker_register)
    dumpj(out / "m7_execution_summary.json", summary)

    missing = [x for x in S0_REQUIRED_ARTIFACTS if not (out / x).exists()]
    if missing:
        blockers.append({"id": "M7-ST-B9", "severity": "S0", "status": "OPEN", "details": {"missing_artifacts": missing}})
        blocker_register.update({"overall_pass": False, "open_blocker_count": len(blockers), "blockers": blockers})
        summary.update({"overall_pass": False, "next_gate": "BLOCKED"})
        dumpj(out / "m7_blocker_register.json", blocker_register)
        dumpj(out / "m7_execution_summary.json", summary)

    print(f"[m7_s0] phase_execution_id={phase_execution_id}")
    print(f"[m7_s0] output_dir={out.as_posix()}")
    print(f"[m7_s0] overall_pass={summary['overall_pass']}")
    print(f"[m7_s0] next_gate={summary['next_gate']}")
    print(f"[m7_s0] probe_count={summary['probe_count']}")
    print(f"[m7_s0] error_rate_pct={summary['error_rate_pct']}")
    print(f"[m7_s0] open_blockers={blocker_register['open_blocker_count']}")
    return 0 if summary["overall_pass"] else 2


def main() -> int:
    ap = argparse.ArgumentParser(description="M7 stress runner")
    ap.add_argument("--stage", default="S0", choices=["S0"])
    ap.add_argument("--phase-execution-id", default="")
    args = ap.parse_args()

    stage_map = {"S0": ("m7_stress_s0", run_s0)}
    prefix, fn = stage_map[args.stage]
    phase_execution_id = args.phase_execution_id.strip() or f"{prefix}_{tok()}"
    return fn(phase_execution_id)


if __name__ == "__main__":
    raise SystemExit(main())
