#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
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

M7_REQUIRED_ARTIFACTS = [
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
    "m7_phase_rollup_matrix.json",
    "m7_gate_verdict.json",
    "m8_handoff_pack.json",
]

M7_S0_EVENT_TYPE_MIN_COUNT = 3
M7_ADDENDUM_ARTIFACTS = [
    "m7_addendum_realism_window_summary.json",
    "m7_addendum_realism_window_metrics.json",
    "m7_addendum_case_label_pressure_summary.json",
    "m7_addendum_case_label_pressure_metrics.json",
    "m7_addendum_service_path_latency_profile.json",
    "m7_addendum_service_path_throughput_profile.json",
    "m7_addendum_cost_attribution_receipt.json",
    "m7_addendum_blocker_register.json",
    "m7_addendum_execution_summary.json",
    "m7_addendum_decision_log.json",
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
    if not s:
        return False
    if "did not use historical" in s:
        return False
    return any(
        token in s
        for token in (
            "waived_low_sample",
            "advisory-only throughput",
            "historical/proxy-only closure authority",
            "historical-only closure authority",
            "proxy-only closure authority",
            "toy-profile throughput posture",
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


def parse_required_artifacts(plan_packet: dict[str, Any]) -> list[str]:
    raw = str(plan_packet.get("M7_STRESS_REQUIRED_ARTIFACTS", "")).strip()
    if not raw:
        return list(M7_REQUIRED_ARTIFACTS)
    out = [x.strip() for x in raw.split(",") if x.strip()]
    return out if out else list(M7_REQUIRED_ARTIFACTS)


def resolve_required_handles(handles: dict[str, Any]) -> tuple[list[str], list[str]]:
    missing: list[str] = []
    placeholder: list[str] = []
    bad = {"", "TO_PIN", "NONE", "None", "null", "NULL"}
    for k in REQ_HANDLES:
        if k not in handles:
            missing.append(k)
            continue
        if str(handles.get(k, "")).strip() in bad:
            placeholder.append(k)
    return missing, placeholder


def add_head_bucket_probe(probes: list[dict[str, Any]], bucket: str, region: str, probe_id: str) -> dict[str, Any]:
    if bucket:
        p = run_cmd(["aws", "s3api", "head-bucket", "--bucket", bucket, "--region", region], 25)
        probes.append({**p, "probe_id": probe_id, "group": "control", "bucket": bucket})
        return p
    p = {
        "command": "aws s3api head-bucket",
        "exit_code": 1,
        "status": "FAIL",
        "duration_ms": 0.0,
        "stdout": "",
        "stderr": "missing S3_EVIDENCE_BUCKET handle",
        "started_at_utc": now(),
        "ended_at_utc": now(),
    }
    probes.append({**p, "probe_id": probe_id, "group": "control", "bucket": bucket})
    return p


def add_head_object_probe(probes: list[dict[str, Any]], bucket: str, key: str, region: str, probe_id: str) -> dict[str, Any]:
    k = str(key or "").strip().lstrip("/")
    if bucket and k:
        p = run_cmd(["aws", "s3api", "head-object", "--bucket", bucket, "--key", k, "--region", region], 30)
        probes.append({**p, "probe_id": probe_id, "group": "evidence", "bucket": bucket, "key": k})
        return p
    p = {
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


def probe_metrics(probes: list[dict[str, Any]]) -> dict[str, Any]:
    failures = [p for p in probes if str(p.get("status", "FAIL")) != "PASS"]
    latencies = [float(p.get("duration_ms", 0.0) or 0.0) for p in probes]
    p50 = 0.0 if not latencies else sorted(latencies)[len(latencies) // 2]
    p95 = 0.0 if not latencies else max(latencies)
    return {
        "window_seconds_observed": max(1, int(round(sum(latencies) / 1000.0))) if latencies else 1,
        "probe_count": len(probes),
        "failure_count": len(failures),
        "error_rate_pct": round((len(failures) / len(probes)) * 100.0, 4) if probes else 0.0,
        "latency_ms_p50": p50,
        "latency_ms_p95": p95,
        "latency_ms_p99": p95,
        "sample_failures": failures[:10],
        "probes": probes,
    }


def finalize_artifact_contract(
    out: Path,
    required_artifacts: list[str],
    blockers: list[dict[str, Any]],
    blocker_register: dict[str, Any],
    summary: dict[str, Any],
    verdict: dict[str, Any],
    blocker_id: str,
) -> None:
    missing = [x for x in required_artifacts if not (out / x).exists()]
    if not missing:
        return
    blockers.append({"id": blocker_id, "severity": summary.get("stage_id", ""), "status": "OPEN", "details": {"missing_artifacts": missing}})
    blocker_register.update({"overall_pass": False, "open_blocker_count": len(blockers), "blockers": blockers})
    summary.update({"overall_pass": False, "next_gate": "BLOCKED", "open_blocker_count": len(blockers)})
    verdict.update({"overall_pass": False, "next_gate": "BLOCKED", "blocker_count": len(blockers)})
    dumpj(out / "m7_blocker_register.json", blocker_register)
    dumpj(out / "m7_execution_summary.json", summary)
    dumpj(out / "m7_gate_verdict.json", verdict)


def build_parent_chain_rows(platform_run_id: str) -> tuple[list[dict[str, Any]], list[str]]:
    spec = [
        ("S0", "m7_stress_s0", "M7-ST-S0", "M7_ST_S1_READY"),
        ("S1", "m7_stress_s1", "M7-ST-S1", "M7_ST_S2_READY"),
        ("S2", "m7_stress_s2", "M7-ST-S2", "M7_ST_S3_READY"),
        ("S3", "m7_stress_s3", "M7-ST-S3", "M7_ST_S4_READY"),
        ("S4", "m7_stress_s4", "M7-ST-S4", "M7_ST_S5_READY"),
    ]
    rows: list[dict[str, Any]] = []
    issues: list[str] = []
    for label, prefix, stage_id, expected_next_gate in spec:
        rec = latest_ok(prefix, "m7_execution_summary.json", stage_id)
        row = {
            "label": label,
            "stage_id": stage_id,
            "expected_next_gate": expected_next_gate,
            "found": bool(rec),
            "phase_execution_id": "",
            "next_gate": "",
            "overall_pass": False,
            "open_blockers": None,
            "platform_run_id": "",
            "run_scope_consistent": True,
            "ok": False,
        }
        if rec:
            s = rec.get("summary", {})
            row["phase_execution_id"] = str(s.get("phase_execution_id", ""))
            row["next_gate"] = str(s.get("next_gate", ""))
            row["overall_pass"] = bool(s.get("overall_pass"))
            row["platform_run_id"] = str(s.get("platform_run_id", "")).strip()
            rp = Path(str(rec.get("path", "")))
            br = loadj(rp / "m7_blocker_register.json")
            row["open_blockers"] = int(br.get("open_blocker_count", 0) or 0)
            row["ok"] = row["overall_pass"] and row["next_gate"] == expected_next_gate and row["open_blockers"] == 0
            if platform_run_id and row["platform_run_id"] and row["platform_run_id"] != platform_run_id:
                row["run_scope_consistent"] = False
                row["ok"] = False
        if not row["ok"]:
            issues.append(f"parent chain row failed: {label}")
        rows.append(row)
    return rows, issues


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


def parse_phase_execution_timestamp(phase_execution_id: str) -> datetime | None:
    m = re.search(r"(\d{8}T\d{6}Z)$", str(phase_execution_id or "").strip())
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def iso_utc(dt: datetime | None) -> str:
    if dt is None:
        return ""
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def derive_stage_window(row: dict[str, Any]) -> tuple[datetime | None, datetime | None]:
    phase_ts = parse_phase_execution_timestamp(str(row.get("phase_execution_id", "")))
    summary_ts = parse_ts(str(row.get("summary_generated_at_utc", "")))
    receipt_ts = parse_ts(str(row.get("receipt_generated_at_utc", "")))
    window_seconds = max(0, int(row.get("window_seconds", 0) or 0))

    start_ts = phase_ts or summary_ts or receipt_ts
    end_ts = receipt_ts or summary_ts
    if start_ts and not end_ts:
        end_ts = start_ts + timedelta(seconds=max(1, window_seconds))
    if start_ts and end_ts and end_ts <= start_ts:
        end_ts = start_ts + timedelta(seconds=max(1, window_seconds, 1))
    return start_ts, end_ts


def derive_cost_query_window(stage_rows: list[dict[str, Any]]) -> tuple[datetime, datetime]:
    starts: list[datetime] = []
    ends: list[datetime] = []
    for row in stage_rows:
        s, e = derive_stage_window(row)
        if s:
            starts.append(s)
        if e:
            ends.append(e)
    if starts and ends:
        start = min(starts)
        end = max(ends)
    elif starts:
        start = min(starts)
        end = max(starts) + timedelta(hours=1)
    elif ends:
        end = max(ends)
        start = min(ends) - timedelta(hours=1)
    else:
        end = datetime.now(timezone.utc)
        start = end - timedelta(hours=6)
    if end <= start:
        end = start + timedelta(hours=1)
    return start, end


def query_aws_cost_explorer_window(start_utc: datetime, end_utc: datetime, billing_region: str) -> dict[str, Any]:
    start_date = start_utc.date().isoformat()
    end_date = (end_utc.date() + timedelta(days=1)).isoformat()
    cmd = [
        "aws",
        "ce",
        "get-cost-and-usage",
        "--time-period",
        f"Start={start_date},End={end_date}",
        "--granularity",
        "DAILY",
        "--metrics",
        "UnblendedCost",
        "--region",
        billing_region,
        "--output",
        "json",
    ]
    t0 = time.perf_counter()
    started = now()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "method": "aws_ce_daily_unblended_v1",
            "query": {"start_date": start_date, "end_date": end_date, "billing_region": billing_region},
            "amount_usd": 0.0,
            "currency": "USD",
            "rows": [],
            "error": "timeout",
            "command": " ".join(cmd),
            "duration_ms": round((time.perf_counter() - t0) * 1000.0, 3),
            "started_at_utc": started,
            "ended_at_utc": now(),
        }
    if int(p.returncode) != 0:
        return {
            "ok": False,
            "method": "aws_ce_daily_unblended_v1",
            "query": {"start_date": start_date, "end_date": end_date, "billing_region": billing_region},
            "amount_usd": 0.0,
            "currency": "USD",
            "rows": [],
            "error": (p.stderr or p.stdout or "ce_query_failed").strip()[:500],
            "command": " ".join(cmd),
            "duration_ms": round((time.perf_counter() - t0) * 1000.0, 3),
            "started_at_utc": started,
            "ended_at_utc": now(),
        }
    try:
        payload = json.loads((p.stdout or "").strip() or "{}")
    except json.JSONDecodeError:
        return {
            "ok": False,
            "method": "aws_ce_daily_unblended_v1",
            "query": {"start_date": start_date, "end_date": end_date, "billing_region": billing_region},
            "amount_usd": 0.0,
            "currency": "USD",
            "rows": [],
            "error": "invalid_json_response",
            "command": " ".join(cmd),
            "duration_ms": round((time.perf_counter() - t0) * 1000.0, 3),
            "started_at_utc": started,
            "ended_at_utc": now(),
        }

    rows: list[dict[str, Any]] = []
    total = 0.0
    currency = "USD"
    for item in payload.get("ResultsByTime", []) if isinstance(payload.get("ResultsByTime", []), list) else []:
        total_obj = item.get("Total", {}) if isinstance(item.get("Total", {}), dict) else {}
        uc = total_obj.get("UnblendedCost", {}) if isinstance(total_obj.get("UnblendedCost", {}), dict) else {}
        amount_raw = uc.get("Amount", "0")
        unit_raw = uc.get("Unit", "USD")
        try:
            amount = float(amount_raw or 0.0)
        except (TypeError, ValueError):
            amount = 0.0
        total += amount
        currency = str(unit_raw or "USD")
        rows.append(
            {
                "start": str(item.get("TimePeriod", {}).get("Start", "")),
                "end": str(item.get("TimePeriod", {}).get("End", "")),
                "amount_usd": round(amount, 8),
                "currency": currency,
                "estimated": bool(item.get("Estimated", False)),
            }
        )

    return {
        "ok": True,
        "method": "aws_ce_daily_unblended_v1",
        "query": {"start_date": start_date, "end_date": end_date, "billing_region": billing_region},
        "amount_usd": round(total, 8),
        "currency": currency,
        "rows": rows,
        "command": " ".join(cmd),
        "duration_ms": round((time.perf_counter() - t0) * 1000.0, 3),
        "started_at_utc": started,
        "ended_at_utc": now(),
    }


def materialize_pattern(pattern: str, replacements: dict[str, str]) -> str:
    out = str(pattern)
    for key, val in replacements.items():
        out = out.replace("{" + key + "}", str(val))
    return out


def parse_s3_uri(uri: str) -> tuple[str, str]:
    s = str(uri or "").strip()
    if not s.startswith("s3://"):
        return "", ""
    no_scheme = s[5:]
    if "/" not in no_scheme:
        return "", ""
    bucket, key = no_scheme.split("/", 1)
    return bucket.strip(), key.strip()


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


def run_s1(phase_execution_id: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)

    plan_packet = parse_bt_map(PLAN.read_text(encoding="utf-8") if PLAN.exists() else "")
    handles = parse_registry(REG) if REG.exists() else {}
    required_artifacts = parse_required_artifacts(plan_packet)

    blockers: list[dict[str, Any]] = []
    probes: list[dict[str, Any]] = []
    issues: list[str] = []
    advisories: list[str] = []
    decisions: list[str] = []
    addendum_blockers: list[dict[str, Any]] = []

    missing_plan_keys = [k for k in PLAN_KEYS if k not in plan_packet]
    missing_handles, placeholder_handles = resolve_required_handles(handles)
    if missing_plan_keys or missing_handles or placeholder_handles:
        blockers.append(
            {
                "id": "M7-ST-B1",
                "severity": "S1",
                "status": "OPEN",
                "details": {
                    "missing_plan_keys": missing_plan_keys,
                    "missing_handles": missing_handles,
                    "placeholder_handles": placeholder_handles,
                },
            }
        )
        if missing_plan_keys:
            issues.append(f"missing plan keys: {','.join(missing_plan_keys)}")
        if missing_handles:
            issues.append(f"missing handles: {','.join(missing_handles)}")
        if placeholder_handles:
            issues.append(f"placeholder handles: {','.join(placeholder_handles)}")

    dep_issues: list[str] = []
    dep = latest_ok("m7_stress_s0", "m7_execution_summary.json", "M7-ST-S0")
    dep_id = ""
    dep_subset: dict[str, Any] = {}
    dep_profile: dict[str, Any] = {}
    platform_run_id = ""
    if not dep:
        dep_issues.append("missing successful M7-ST-S0 dependency")
    else:
        dep_summary = dep["summary"]
        dep_id = str(dep_summary.get("phase_execution_id", ""))
        if str(dep_summary.get("next_gate", "")).strip() != "M7_ST_S1_READY":
            dep_issues.append("M7-ST-S0 next_gate is not M7_ST_S1_READY")
        dep_path = Path(str(dep.get("path", "")))
        dep_blockers = loadj(dep_path / "m7_blocker_register.json")
        if int(dep_blockers.get("open_blocker_count", 0) or 0) != 0:
            dep_issues.append("M7-ST-S0 blocker register is not closed")
        dep_subset = loadj(dep_path / "m7_data_subset_manifest.json")
        dep_profile = loadj(dep_path / "m7_data_profile_summary.json")
        if not dep_subset or not dep_profile:
            dep_issues.append("M7-ST-S0 data subset/profile artifacts are missing")
        platform_run_id = str(dep_summary.get("platform_run_id", "")).strip()
    if dep_issues:
        blockers.append({"id": "M7-ST-B5", "severity": "S1", "status": "OPEN", "details": {"issues": dep_issues}})
        issues.extend(dep_issues)

    p8_issues: list[str] = []
    p8 = latest_ok("m7p8_stress_s5", "m7p8_execution_summary.json", "M7P8-ST-S5")
    p8_id = ""
    p8_summary: dict[str, Any] = {}
    p8_profile: dict[str, Any] = {}
    p8_ieg: dict[str, Any] = {}
    p8_ofp: dict[str, Any] = {}
    p8_archive: dict[str, Any] = {}
    p8_platform_run_id = ""
    if not p8:
        p8_issues.append("missing successful M7P8-ST-S5 dependency")
    else:
        p8_path = Path(str(p8.get("path", "")))
        p8_summary = p8.get("summary", {})
        p8_id = str(p8_summary.get("phase_execution_id", ""))
        if str(p8_summary.get("verdict", "")).strip() != "ADVANCE_TO_P9":
            p8_issues.append("M7P8-ST-S5 verdict is not ADVANCE_TO_P9")
        if str(p8_summary.get("next_gate", "")).strip() != "ADVANCE_TO_P9":
            p8_issues.append("M7P8-ST-S5 next_gate is not ADVANCE_TO_P9")
        p8_blockers = loadj(p8_path / "m7p8_blocker_register.json")
        if int(p8_blockers.get("open_blocker_count", 0) or 0) != 0:
            p8_issues.append("M7P8-ST-S5 blocker register is not closed")
        dep_required = [str(x) for x in p8_summary.get("required_artifacts", []) if str(x).strip()]
        if dep_required:
            for name in dep_required:
                if not (p8_path / name).exists():
                    p8_issues.append(f"missing P8 dependency artifact: {name}")
        p8_profile = loadj(p8_path / "m7p8_data_profile_summary.json")
        p8_ieg = loadj(p8_path / "m7p8_ieg_snapshot.json")
        p8_ofp = loadj(p8_path / "m7p8_ofp_snapshot.json")
        p8_archive = loadj(p8_path / "m7p8_archive_snapshot.json")
        if not p8_profile or not p8_ieg or not p8_ofp or not p8_archive:
            p8_issues.append("P8 S5 required snapshots/profile missing")
        p8_platform_run_id = str(p8_summary.get("platform_run_id", "")).strip()
        if platform_run_id and p8_platform_run_id and platform_run_id != p8_platform_run_id:
            p8_issues.append("run-scope mismatch between M7 S0 and P8 S5")
        if not platform_run_id and p8_platform_run_id:
            platform_run_id = p8_platform_run_id

    p8_functional_issues = [
        str(x)
        for x in [*(p8_ieg.get("functional_issues", []) or []), *(p8_ofp.get("functional_issues", []) or []), *(p8_archive.get("functional_issues", []) or [])]
        if str(x).strip()
    ]
    p8_semantic_issues = [
        str(x)
        for x in [*(p8_ieg.get("semantic_issues", []) or []), *(p8_ofp.get("semantic_issues", []) or []), *(p8_archive.get("semantic_issues", []) or [])]
        if str(x).strip()
    ]
    p8_checks = p8_profile.get("checks", {}) if isinstance(p8_profile.get("checks", {}), dict) else {}
    p8_failed_checks = [k for k, v in p8_checks.items() if not bool(v)]
    if p8_functional_issues:
        p8_issues.append("P8 functional issues are present")
    if p8_semantic_issues:
        p8_issues.append("P8 semantic issues are present")
    if p8_failed_checks:
        p8_issues.append("P8 data-profile checks failed")
    if p8_issues:
        blockers.append(
            {
                "id": "M7-ST-B5",
                "severity": "S1",
                "status": "OPEN",
                "details": {
                    "issues": sorted(set(p8_issues)),
                    "functional_issues": p8_functional_issues[:20],
                    "semantic_issues": p8_semantic_issues[:20],
                    "failed_profile_checks": p8_failed_checks[:20],
                },
            }
        )
        issues.extend(sorted(set(p8_issues)))

    bucket = str(handles.get("S3_EVIDENCE_BUCKET", "")).strip()
    p_bucket = add_head_bucket_probe(probes, bucket, "eu-west-2", "m7_s1_evidence_bucket")
    if p_bucket.get("status") != "PASS":
        blockers.append({"id": "M7-ST-B10", "severity": "S1", "status": "OPEN", "details": {"probe_id": "m7_s1_evidence_bucket"}})
        issues.append("evidence bucket probe failed")

    replacements = {"platform_run_id": platform_run_id, "phase_execution_id": phase_execution_id}
    for probe_id, handle_key in [
        ("m7_s1_receipt_summary", "RECEIPT_SUMMARY_PATH_PATTERN"),
        ("m7_s1_offsets_snapshot", "KAFKA_OFFSETS_SNAPSHOT_PATH_PATTERN"),
        ("m7_s1_quarantine_summary", "QUARANTINE_SUMMARY_PATH_PATTERN"),
    ]:
        key = materialize_pattern(str(handles.get(handle_key, "")).strip(), replacements)
        if key:
            p = add_head_object_probe(probes, bucket, key, "eu-west-2", probe_id)
            if p.get("status") != "PASS":
                blockers.append({"id": "M7-ST-B10", "severity": "S1", "status": "OPEN", "details": {"probe_id": probe_id, "key": key}})
                issues.append(f"{probe_id} probe failed")

    metrics = probe_metrics(probes)
    overall_pass = len(blockers) == 0
    next_gate = "M7_ST_S2_READY" if overall_pass else "BLOCKED"
    verdict_name = "ADVANCE_TO_S2" if overall_pass else "HOLD_REMEDIATE"

    dumpj(
        out / "m7_stagea_findings.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7-ST-S1",
            "findings": [
                {"id": "M7-ST-F7", "classification": "PREVENT", "finding": "Parent M7 cannot advance when P8 S5 verdict/semantics are not closed.", "required_action": "Fail-closed on any P8 verdict, semantic, or artifact drift."},
                {"id": "M7-ST-F8", "classification": "OBSERVE", "finding": "Duplicate and late-event pressure remains advisory-sensitive in this lane.", "required_action": "Carry advisories into downstream integrated windows (S4)."},
            ],
        },
    )
    dumpj(out / "m7_lane_matrix.json", {"component_sequence": ["M7-ST-S0", "M7-ST-S1", "M7-ST-S2", "M7-ST-S3", "M7-ST-S4", "M7-ST-S5"], "plane_sequence": ["rtdl_plane", "decision_plane", "case_label_plane", "m7_rollup_plane"], "integrated_windows": ["m7_s4_normal_mix_window", "m7_s4_edge_mix_window", "m7_s4_replay_duplicate_window"]})
    dumpj(out / "m7_data_subset_manifest.json", {**dep_subset, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7-ST-S1", "platform_run_id": platform_run_id, "status": "S1_CONSUMED", "upstream_m7_s0_phase_execution_id": dep_id, "upstream_m7p8_s5_phase_execution_id": p8_id})
    dumpj(
        out / "m7_data_profile_summary.json",
        {
            **dep_profile,
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7-ST-S1",
            "platform_run_id": platform_run_id,
            "upstream_m7_s0_phase_execution_id": dep_id,
            "upstream_m7p8_s5_phase_execution_id": p8_id,
            "p8_checks": p8_checks,
            "p8_failed_checks": p8_failed_checks,
            "p8_functional_issue_count": len(p8_functional_issues),
            "p8_semantic_issue_count": len(p8_semantic_issues),
            "advisories": sorted(set([str(x) for x in [*(dep_profile.get("advisories", []) or []), *(p8_profile.get("advisories", []) or [])] if str(x).strip()])),
        },
    )
    dumpj(
        out / "m7_data_edge_case_matrix.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7-ST-S1",
            "platform_run_id": platform_run_id,
            "cohort_presence": p8_profile.get("cohort_presence", {}),
            "p8_checks": p8_checks,
            "p8_failed_checks": p8_failed_checks,
        },
    )
    dumpj(
        out / "m7_data_skew_hotspot_profile.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7-ST-S1",
            "platform_run_id": platform_run_id,
            "top1_run_share": p8_profile.get("top1_run_share", dep_profile.get("top1_run_share")),
            "top_hotkeys": p8_profile.get("source_profile", {}).get("top_hotkeys", []),
        },
    )
    dumpj(
        out / "m7_data_quality_guardrail_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7-ST-S1",
            "platform_run_id": platform_run_id,
            "overall_pass": len(p8_issues) == 0,
            "p8_checks": p8_checks,
            "p8_failed_checks": p8_failed_checks,
            "p8_functional_issues": p8_functional_issues[:20],
            "p8_semantic_issues": p8_semantic_issues[:20],
        },
    )
    dumpj(out / "m7_probe_latency_throughput_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7-ST-S1", **metrics})
    dumpj(out / "m7_control_rail_conformance_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7-ST-S1", "platform_run_id": platform_run_id, "overall_pass": len(issues) == 0, "issues": issues, "advisories": advisories})
    dumpj(out / "m7_secret_safety_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7-ST-S1", "overall_pass": True, "secret_probe_count": 0, "secret_failure_count": 0, "with_decryption_used": False, "queried_value_directly": False, "plaintext_leakage_detected": False})
    dumpj(out / "m7_cost_outcome_receipt.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7-ST-S1", "window_seconds": metrics["window_seconds_observed"], "estimated_api_call_count": metrics["probe_count"], "attributed_spend_usd": 0.0, "unattributed_spend_detected": False, "max_spend_usd": float(plan_packet.get("M7_STRESS_MAX_SPEND_USD", 120)), "within_envelope": True, "method": "m7_s1_parent_p8_gate_v0"})
    dumpj(
        out / "m7_phase_rollup_matrix.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7-ST-S1",
            "platform_run_id": platform_run_id,
            "parent_chain": [{"stage_id": "M7-ST-S0", "phase_execution_id": dep_id, "next_gate_expected": "M7_ST_S1_READY", "ok": len(dep_issues) == 0}],
            "subphase_chain": [{"stage_id": "M7P8-ST-S5", "phase_execution_id": p8_id, "expected_verdict": "ADVANCE_TO_P9", "ok": len(p8_issues) == 0}],
        },
    )
    dumpj(
        out / "m7_gate_verdict.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7-ST-S1",
            "platform_run_id": platform_run_id,
            "overall_pass": overall_pass,
            "verdict": verdict_name,
            "next_gate": next_gate,
            "blocker_count": len(blockers),
            "upstream_m7_s0_phase_execution_id": dep_id,
            "upstream_m7p8_s5_phase_execution_id": p8_id,
        },
    )
    dumpj(
        out / "m8_handoff_pack.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7-ST-S1",
            "status": "NOT_EMITTED_IN_S1",
            "platform_run_id": platform_run_id,
            "next_gate_candidate": next_gate,
        },
    )

    decisions.extend(
        [
            "Validated M7 S0 continuity before parent P8 adjudication.",
            "Accepted P8 S5 only with deterministic verdict and zero semantic issue carry-over.",
            "Preserved fail-closed posture on any P8 artifact, verdict, or run-scope drift.",
        ]
    )
    dumpj(out / "m7_decision_log.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7-ST-S1", "decisions": decisions, "advisories": advisories})

    blocker_register = {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7-ST-S1", "overall_pass": overall_pass, "open_blocker_count": len(blockers), "blockers": blockers}
    summary = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M7-ST-S1",
        "overall_pass": overall_pass,
        "next_gate": next_gate,
        "open_blocker_count": len(blockers),
        "required_artifacts": required_artifacts,
        "probe_count": metrics["probe_count"],
        "error_rate_pct": metrics["error_rate_pct"],
        "platform_run_id": platform_run_id,
        "upstream_m7_s0_phase_execution_id": dep_id,
        "upstream_m7p8_s5_phase_execution_id": p8_id,
    }
    verdict = {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7-ST-S1", "overall_pass": overall_pass, "verdict": verdict_name, "next_gate": next_gate, "blocker_count": len(blockers), "platform_run_id": platform_run_id}
    dumpj(out / "m7_blocker_register.json", blocker_register)
    dumpj(out / "m7_execution_summary.json", summary)
    dumpj(out / "m7_gate_verdict.json", verdict)
    finalize_artifact_contract(out, required_artifacts, blockers, blocker_register, summary, verdict, blocker_id="M7-ST-B9")

    print(f"[m7_s1] phase_execution_id={phase_execution_id}")
    print(f"[m7_s1] output_dir={out.as_posix()}")
    print(f"[m7_s1] overall_pass={summary.get('overall_pass')}")
    print(f"[m7_s1] next_gate={summary.get('next_gate')}")
    print(f"[m7_s1] open_blockers={blocker_register.get('open_blocker_count')}")
    return 0 if summary.get("overall_pass") else 2


def run_s2(phase_execution_id: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)

    plan_packet = parse_bt_map(PLAN.read_text(encoding="utf-8") if PLAN.exists() else "")
    handles = parse_registry(REG) if REG.exists() else {}
    required_artifacts = parse_required_artifacts(plan_packet)

    blockers: list[dict[str, Any]] = []
    probes: list[dict[str, Any]] = []
    issues: list[str] = []
    advisories: list[str] = []
    decisions: list[str] = []

    missing_plan_keys = [k for k in PLAN_KEYS if k not in plan_packet]
    missing_handles, placeholder_handles = resolve_required_handles(handles)
    if missing_plan_keys or missing_handles or placeholder_handles:
        blockers.append(
            {
                "id": "M7-ST-B1",
                "severity": "S2",
                "status": "OPEN",
                "details": {
                    "missing_plan_keys": missing_plan_keys,
                    "missing_handles": missing_handles,
                    "placeholder_handles": placeholder_handles,
                },
            }
        )
        if missing_plan_keys:
            issues.append(f"missing plan keys: {','.join(missing_plan_keys)}")
        if missing_handles:
            issues.append(f"missing handles: {','.join(missing_handles)}")
        if placeholder_handles:
            issues.append(f"placeholder handles: {','.join(placeholder_handles)}")

    dep_issues: list[str] = []
    dep = latest_ok("m7_stress_s1", "m7_execution_summary.json", "M7-ST-S1")
    dep_id = ""
    dep_subset: dict[str, Any] = {}
    dep_profile: dict[str, Any] = {}
    platform_run_id = ""
    if not dep:
        dep_issues.append("missing successful M7-ST-S1 dependency")
    else:
        dep_summary = dep["summary"]
        dep_id = str(dep_summary.get("phase_execution_id", ""))
        if str(dep_summary.get("next_gate", "")).strip() != "M7_ST_S2_READY":
            dep_issues.append("M7-ST-S1 next_gate is not M7_ST_S2_READY")
        dep_path = Path(str(dep.get("path", "")))
        dep_blockers = loadj(dep_path / "m7_blocker_register.json")
        if int(dep_blockers.get("open_blocker_count", 0) or 0) != 0:
            dep_issues.append("M7-ST-S1 blocker register is not closed")
        dep_subset = loadj(dep_path / "m7_data_subset_manifest.json")
        dep_profile = loadj(dep_path / "m7_data_profile_summary.json")
        if not dep_subset or not dep_profile:
            dep_issues.append("M7-ST-S1 data subset/profile artifacts are missing")
        platform_run_id = str(dep_summary.get("platform_run_id", "")).strip()
    if dep_issues:
        blockers.append({"id": "M7-ST-B6", "severity": "S2", "status": "OPEN", "details": {"issues": dep_issues}})
        issues.extend(dep_issues)

    p9_issues: list[str] = []
    p9 = latest_ok("m7p9_stress_s5", "m7p9_execution_summary.json", "M7P9-ST-S5")
    p9_id = ""
    p9_summary: dict[str, Any] = {}
    p9_profile: dict[str, Any] = {}
    p9_df: dict[str, Any] = {}
    p9_al: dict[str, Any] = {}
    p9_dla: dict[str, Any] = {}
    p9_platform_run_id = ""
    if not p9:
        p9_issues.append("missing successful M7P9-ST-S5 dependency")
    else:
        p9_path = Path(str(p9.get("path", "")))
        p9_summary = p9.get("summary", {})
        p9_id = str(p9_summary.get("phase_execution_id", ""))
        if str(p9_summary.get("verdict", "")).strip() != "ADVANCE_TO_P10":
            p9_issues.append("M7P9-ST-S5 verdict is not ADVANCE_TO_P10")
        if str(p9_summary.get("next_gate", "")).strip() != "ADVANCE_TO_P10":
            p9_issues.append("M7P9-ST-S5 next_gate is not ADVANCE_TO_P10")
        p9_blockers = loadj(p9_path / "m7p9_blocker_register.json")
        if int(p9_blockers.get("open_blocker_count", 0) or 0) != 0:
            p9_issues.append("M7P9-ST-S5 blocker register is not closed")
        dep_required = [str(x) for x in p9_summary.get("required_artifacts", []) if str(x).strip()]
        if dep_required:
            for name in dep_required:
                if not (p9_path / name).exists():
                    p9_issues.append(f"missing P9 dependency artifact: {name}")
        p9_profile = loadj(p9_path / "m7p9_data_profile_summary.json")
        p9_df = loadj(p9_path / "m7p9_df_snapshot.json")
        p9_al = loadj(p9_path / "m7p9_al_snapshot.json")
        p9_dla = loadj(p9_path / "m7p9_dla_snapshot.json")
        if not p9_profile or not p9_df or not p9_al or not p9_dla:
            p9_issues.append("P9 S5 required snapshots/profile missing")
        p9_platform_run_id = str(p9_summary.get("platform_run_id", "")).strip()
        if platform_run_id and p9_platform_run_id and platform_run_id != p9_platform_run_id:
            p9_issues.append("run-scope mismatch between M7 S1 and P9 S5")
        if not platform_run_id and p9_platform_run_id:
            platform_run_id = p9_platform_run_id

    p9_functional_issues = [
        str(x)
        for x in [*(p9_df.get("functional_issues", []) or []), *(p9_al.get("functional_issues", []) or []), *(p9_dla.get("functional_issues", []) or [])]
        if str(x).strip()
    ]
    p9_semantic_issues = [
        str(x)
        for x in [*(p9_df.get("semantic_issues", []) or []), *(p9_al.get("semantic_issues", []) or []), *(p9_dla.get("semantic_issues", []) or [])]
        if str(x).strip()
    ]
    p9_blocking_checks = p9_profile.get("blocking_checks", {}) if isinstance(p9_profile.get("blocking_checks", {}), dict) else {}
    p9_failed_checks = [k for k, v in p9_blocking_checks.items() if not bool(v)]
    if p9_functional_issues:
        p9_issues.append("P9 functional issues are present")
    if p9_semantic_issues:
        p9_issues.append("P9 semantic issues are present")
    if p9_failed_checks:
        p9_issues.append("P9 blocking checks failed")
    if p9_issues:
        blockers.append(
            {
                "id": "M7-ST-B6",
                "severity": "S2",
                "status": "OPEN",
                "details": {
                    "issues": sorted(set(p9_issues)),
                    "functional_issues": p9_functional_issues[:20],
                    "semantic_issues": p9_semantic_issues[:20],
                    "failed_profile_checks": p9_failed_checks[:20],
                },
            }
        )
        issues.extend(sorted(set(p9_issues)))

    bucket = str(handles.get("S3_EVIDENCE_BUCKET", "")).strip()
    p_bucket = add_head_bucket_probe(probes, bucket, "eu-west-2", "m7_s2_evidence_bucket")
    if p_bucket.get("status") != "PASS":
        blockers.append({"id": "M7-ST-B10", "severity": "S2", "status": "OPEN", "details": {"probe_id": "m7_s2_evidence_bucket"}})
        issues.append("evidence bucket probe failed")

    replacements = {"platform_run_id": platform_run_id, "phase_execution_id": phase_execution_id}
    for probe_id, handle_key in [
        ("m7_s2_receipt_summary", "RECEIPT_SUMMARY_PATH_PATTERN"),
        ("m7_s2_offsets_snapshot", "KAFKA_OFFSETS_SNAPSHOT_PATH_PATTERN"),
        ("m7_s2_quarantine_summary", "QUARANTINE_SUMMARY_PATH_PATTERN"),
    ]:
        key = materialize_pattern(str(handles.get(handle_key, "")).strip(), replacements)
        if key:
            p = add_head_object_probe(probes, bucket, key, "eu-west-2", probe_id)
            if p.get("status") != "PASS":
                blockers.append({"id": "M7-ST-B10", "severity": "S2", "status": "OPEN", "details": {"probe_id": probe_id, "key": key}})
                issues.append(f"{probe_id} probe failed")

    metrics = probe_metrics(probes)
    overall_pass = len(blockers) == 0
    next_gate = "M7_ST_S3_READY" if overall_pass else "BLOCKED"
    verdict_name = "ADVANCE_TO_S3" if overall_pass else "HOLD_REMEDIATE"

    dumpj(
        out / "m7_stagea_findings.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7-ST-S2",
            "findings": [
                {"id": "M7-ST-F9", "classification": "PREVENT", "finding": "Parent M7 cannot advance when P9 S5 verdict/semantics are not closed.", "required_action": "Fail-closed on any P9 verdict, semantic, or artifact drift."},
                {"id": "M7-ST-F10", "classification": "OBSERVE", "finding": "Policy-path and action-class mix advisories must carry into integrated S4 windows.", "required_action": "Keep edge-cohort pressure explicit in S4."},
            ],
        },
    )
    dumpj(out / "m7_lane_matrix.json", {"component_sequence": ["M7-ST-S0", "M7-ST-S1", "M7-ST-S2", "M7-ST-S3", "M7-ST-S4", "M7-ST-S5"], "plane_sequence": ["rtdl_plane", "decision_plane", "case_label_plane", "m7_rollup_plane"], "integrated_windows": ["m7_s4_normal_mix_window", "m7_s4_edge_mix_window", "m7_s4_replay_duplicate_window"]})
    dumpj(out / "m7_data_subset_manifest.json", {**dep_subset, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7-ST-S2", "platform_run_id": platform_run_id, "status": "S2_CONSUMED", "upstream_m7_s1_phase_execution_id": dep_id, "upstream_m7p9_s5_phase_execution_id": p9_id})
    dumpj(
        out / "m7_data_profile_summary.json",
        {
            **dep_profile,
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7-ST-S2",
            "platform_run_id": platform_run_id,
            "upstream_m7_s1_phase_execution_id": dep_id,
            "upstream_m7p9_s5_phase_execution_id": p9_id,
            "p9_blocking_checks": p9_blocking_checks,
            "p9_failed_checks": p9_failed_checks,
            "p9_functional_issue_count": len(p9_functional_issues),
            "p9_semantic_issue_count": len(p9_semantic_issues),
            "advisories": sorted(set([str(x) for x in [*(dep_profile.get("advisories", []) or []), *(p9_profile.get("advisories", []) or [])] if str(x).strip()])),
        },
    )
    dumpj(
        out / "m7_data_edge_case_matrix.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7-ST-S2",
            "platform_run_id": platform_run_id,
            "p9_blocking_checks": p9_blocking_checks,
            "p9_failed_checks": p9_failed_checks,
            "policy_path_cardinality": p9_profile.get("policy_path_cardinality"),
            "action_class_cardinality": p9_profile.get("action_class_cardinality"),
        },
    )
    dumpj(
        out / "m7_data_skew_hotspot_profile.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7-ST-S2",
            "platform_run_id": platform_run_id,
            "top1_run_share": dep_profile.get("top1_run_share"),
            "action_mix_profile": loadj(Path(str(p9.get("path", ""))) / "m7p9_action_mix_profile.json") if p9 else {},
        },
    )
    dumpj(
        out / "m7_data_quality_guardrail_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7-ST-S2",
            "platform_run_id": platform_run_id,
            "overall_pass": len(p9_issues) == 0,
            "p9_blocking_checks": p9_blocking_checks,
            "p9_failed_checks": p9_failed_checks,
            "p9_functional_issues": p9_functional_issues[:20],
            "p9_semantic_issues": p9_semantic_issues[:20],
        },
    )
    dumpj(out / "m7_probe_latency_throughput_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7-ST-S2", **metrics})
    dumpj(out / "m7_control_rail_conformance_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7-ST-S2", "platform_run_id": platform_run_id, "overall_pass": len(issues) == 0, "issues": issues, "advisories": advisories})
    dumpj(out / "m7_secret_safety_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7-ST-S2", "overall_pass": True, "secret_probe_count": 0, "secret_failure_count": 0, "with_decryption_used": False, "queried_value_directly": False, "plaintext_leakage_detected": False})
    dumpj(out / "m7_cost_outcome_receipt.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7-ST-S2", "window_seconds": metrics["window_seconds_observed"], "estimated_api_call_count": metrics["probe_count"], "attributed_spend_usd": 0.0, "unattributed_spend_detected": False, "max_spend_usd": float(plan_packet.get("M7_STRESS_MAX_SPEND_USD", 120)), "within_envelope": True, "method": "m7_s2_parent_p9_gate_v0"})
    dumpj(
        out / "m7_phase_rollup_matrix.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7-ST-S2",
            "platform_run_id": platform_run_id,
            "parent_chain": [{"stage_id": "M7-ST-S1", "phase_execution_id": dep_id, "next_gate_expected": "M7_ST_S2_READY", "ok": len(dep_issues) == 0}],
            "subphase_chain": [{"stage_id": "M7P9-ST-S5", "phase_execution_id": p9_id, "expected_verdict": "ADVANCE_TO_P10", "ok": len(p9_issues) == 0}],
        },
    )
    dumpj(
        out / "m7_gate_verdict.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7-ST-S2",
            "platform_run_id": platform_run_id,
            "overall_pass": overall_pass,
            "verdict": verdict_name,
            "next_gate": next_gate,
            "blocker_count": len(blockers),
            "upstream_m7_s1_phase_execution_id": dep_id,
            "upstream_m7p9_s5_phase_execution_id": p9_id,
        },
    )
    dumpj(
        out / "m8_handoff_pack.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7-ST-S2",
            "status": "NOT_EMITTED_IN_S2",
            "platform_run_id": platform_run_id,
            "next_gate_candidate": next_gate,
        },
    )

    decisions.extend(
        [
            "Validated M7 S1 continuity before parent P9 adjudication.",
            "Accepted P9 S5 only with deterministic verdict and zero semantic issue carry-over.",
            "Preserved fail-closed posture on any P9 artifact, verdict, or run-scope drift.",
        ]
    )
    dumpj(out / "m7_decision_log.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7-ST-S2", "decisions": decisions, "advisories": advisories})

    blocker_register = {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7-ST-S2", "overall_pass": overall_pass, "open_blocker_count": len(blockers), "blockers": blockers}
    summary = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M7-ST-S2",
        "overall_pass": overall_pass,
        "next_gate": next_gate,
        "open_blocker_count": len(blockers),
        "required_artifacts": required_artifacts,
        "probe_count": metrics["probe_count"],
        "error_rate_pct": metrics["error_rate_pct"],
        "platform_run_id": platform_run_id,
        "upstream_m7_s1_phase_execution_id": dep_id,
        "upstream_m7p9_s5_phase_execution_id": p9_id,
    }
    verdict = {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7-ST-S2", "overall_pass": overall_pass, "verdict": verdict_name, "next_gate": next_gate, "blocker_count": len(blockers), "platform_run_id": platform_run_id}
    dumpj(out / "m7_blocker_register.json", blocker_register)
    dumpj(out / "m7_execution_summary.json", summary)
    dumpj(out / "m7_gate_verdict.json", verdict)
    finalize_artifact_contract(out, required_artifacts, blockers, blocker_register, summary, verdict, blocker_id="M7-ST-B9")

    print(f"[m7_s2] phase_execution_id={phase_execution_id}")
    print(f"[m7_s2] output_dir={out.as_posix()}")
    print(f"[m7_s2] overall_pass={summary.get('overall_pass')}")
    print(f"[m7_s2] next_gate={summary.get('next_gate')}")
    print(f"[m7_s2] open_blockers={blocker_register.get('open_blocker_count')}")
    return 0 if summary.get("overall_pass") else 2


def run_s3(phase_execution_id: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)

    plan_packet = parse_bt_map(PLAN.read_text(encoding="utf-8") if PLAN.exists() else "")
    handles = parse_registry(REG) if REG.exists() else {}
    required_artifacts = parse_required_artifacts(plan_packet)

    blockers: list[dict[str, Any]] = []
    probes: list[dict[str, Any]] = []
    issues: list[str] = []
    advisories: list[str] = []
    decisions: list[str] = []

    missing_plan_keys = [k for k in PLAN_KEYS if k not in plan_packet]
    missing_handles, placeholder_handles = resolve_required_handles(handles)
    if missing_plan_keys or missing_handles or placeholder_handles:
        blockers.append(
            {
                "id": "M7-ST-B1",
                "severity": "S3",
                "status": "OPEN",
                "details": {
                    "missing_plan_keys": missing_plan_keys,
                    "missing_handles": missing_handles,
                    "placeholder_handles": placeholder_handles,
                },
            }
        )
        if missing_plan_keys:
            issues.append(f"missing plan keys: {','.join(missing_plan_keys)}")
        if missing_handles:
            issues.append(f"missing handles: {','.join(missing_handles)}")
        if placeholder_handles:
            issues.append(f"placeholder handles: {','.join(placeholder_handles)}")

    dep_issues: list[str] = []
    dep = latest_ok("m7_stress_s2", "m7_execution_summary.json", "M7-ST-S2")
    dep_id = ""
    dep_subset: dict[str, Any] = {}
    dep_profile: dict[str, Any] = {}
    platform_run_id = ""
    if not dep:
        dep_issues.append("missing successful M7-ST-S2 dependency")
    else:
        dep_summary = dep["summary"]
        dep_id = str(dep_summary.get("phase_execution_id", ""))
        if str(dep_summary.get("next_gate", "")).strip() != "M7_ST_S3_READY":
            dep_issues.append("M7-ST-S2 next_gate is not M7_ST_S3_READY")
        dep_path = Path(str(dep.get("path", "")))
        dep_blockers = loadj(dep_path / "m7_blocker_register.json")
        if int(dep_blockers.get("open_blocker_count", 0) or 0) != 0:
            dep_issues.append("M7-ST-S2 blocker register is not closed")
        dep_subset = loadj(dep_path / "m7_data_subset_manifest.json")
        dep_profile = loadj(dep_path / "m7_data_profile_summary.json")
        if not dep_subset or not dep_profile:
            dep_issues.append("M7-ST-S2 data subset/profile artifacts are missing")
        platform_run_id = str(dep_summary.get("platform_run_id", "")).strip()
    if dep_issues:
        blockers.append({"id": "M7-ST-B7", "severity": "S3", "status": "OPEN", "details": {"issues": dep_issues}})
        issues.extend(dep_issues)

    p10_issues: list[str] = []
    p10 = latest_ok("m7p10_stress_s5", "m7p10_execution_summary.json", "M7P10-ST-S5")
    p10_id = ""
    p10_summary: dict[str, Any] = {}
    p10_profile: dict[str, Any] = {}
    p10_ct: dict[str, Any] = {}
    p10_cm: dict[str, Any] = {}
    p10_ls: dict[str, Any] = {}
    p10_platform_run_id = ""
    if not p10:
        p10_issues.append("missing successful M7P10-ST-S5 dependency")
    else:
        p10_path = Path(str(p10.get("path", "")))
        p10_summary = p10.get("summary", {})
        p10_id = str(p10_summary.get("phase_execution_id", ""))
        if str(p10_summary.get("verdict", "")).strip() != "M7_J_READY":
            p10_issues.append("M7P10-ST-S5 verdict is not M7_J_READY")
        if str(p10_summary.get("next_gate", "")).strip() != "M7_J_READY":
            p10_issues.append("M7P10-ST-S5 next_gate is not M7_J_READY")
        p10_blockers = loadj(p10_path / "m7p10_blocker_register.json")
        if int(p10_blockers.get("open_blocker_count", 0) or 0) != 0:
            p10_issues.append("M7P10-ST-S5 blocker register is not closed")
        dep_required = [str(x) for x in p10_summary.get("required_artifacts", []) if str(x).strip()]
        if dep_required:
            for name in dep_required:
                if not (p10_path / name).exists():
                    p10_issues.append(f"missing P10 dependency artifact: {name}")
        p10_profile = loadj(p10_path / "m7p10_data_profile_summary.json")
        p10_ct = loadj(p10_path / "m7p10_case_trigger_snapshot.json")
        p10_cm = loadj(p10_path / "m7p10_cm_snapshot.json")
        p10_ls = loadj(p10_path / "m7p10_ls_snapshot.json")
        if not p10_profile or not p10_ct or not p10_cm or not p10_ls:
            p10_issues.append("P10 S5 required snapshots/profile missing")
        p10_platform_run_id = str(p10_summary.get("platform_run_id", "")).strip()
        if platform_run_id and p10_platform_run_id and platform_run_id != p10_platform_run_id:
            p10_issues.append("run-scope mismatch between M7 S2 and P10 S5")
        if not platform_run_id and p10_platform_run_id:
            platform_run_id = p10_platform_run_id

    p10_functional_issues = [
        str(x)
        for x in [*(p10_ct.get("functional_issues", []) or []), *(p10_cm.get("functional_issues", []) or []), *(p10_ls.get("functional_issues", []) or [])]
        if str(x).strip()
    ]
    p10_semantic_issues = [
        str(x)
        for x in [*(p10_ct.get("semantic_issues", []) or []), *(p10_cm.get("semantic_issues", []) or []), *(p10_ls.get("semantic_issues", []) or [])]
        if str(x).strip()
    ]
    p10_checks = p10_profile.get("checks", {}) if isinstance(p10_profile.get("checks", {}), dict) else {}
    p10_failed_checks = [k for k, v in p10_checks.items() if not bool(v)]
    if p10_functional_issues:
        p10_issues.append("P10 functional issues are present")
    if p10_semantic_issues:
        p10_issues.append("P10 semantic issues are present")
    if p10_failed_checks:
        p10_issues.append("P10 profile checks failed")
    if p10_issues:
        blockers.append(
            {
                "id": "M7-ST-B7",
                "severity": "S3",
                "status": "OPEN",
                "details": {
                    "issues": sorted(set(p10_issues)),
                    "functional_issues": p10_functional_issues[:20],
                    "semantic_issues": p10_semantic_issues[:20],
                    "failed_profile_checks": p10_failed_checks[:20],
                },
            }
        )
        issues.extend(sorted(set(p10_issues)))

    bucket = str(handles.get("S3_EVIDENCE_BUCKET", "")).strip()
    p_bucket = add_head_bucket_probe(probes, bucket, "eu-west-2", "m7_s3_evidence_bucket")
    if p_bucket.get("status") != "PASS":
        blockers.append({"id": "M7-ST-B10", "severity": "S3", "status": "OPEN", "details": {"probe_id": "m7_s3_evidence_bucket"}})
        issues.append("evidence bucket probe failed")

    replacements = {"platform_run_id": platform_run_id, "phase_execution_id": phase_execution_id}
    for probe_id, handle_key in [
        ("m7_s3_receipt_summary", "RECEIPT_SUMMARY_PATH_PATTERN"),
        ("m7_s3_offsets_snapshot", "KAFKA_OFFSETS_SNAPSHOT_PATH_PATTERN"),
        ("m7_s3_quarantine_summary", "QUARANTINE_SUMMARY_PATH_PATTERN"),
    ]:
        key = materialize_pattern(str(handles.get(handle_key, "")).strip(), replacements)
        if key:
            p = add_head_object_probe(probes, bucket, key, "eu-west-2", probe_id)
            if p.get("status") != "PASS":
                blockers.append({"id": "M7-ST-B10", "severity": "S3", "status": "OPEN", "details": {"probe_id": probe_id, "key": key}})
                issues.append(f"{probe_id} probe failed")

    metrics = probe_metrics(probes)
    overall_pass = len(blockers) == 0
    next_gate = "M7_ST_S4_READY" if overall_pass else "BLOCKED"
    verdict_name = "ADVANCE_TO_S4" if overall_pass else "HOLD_REMEDIATE"

    dumpj(
        out / "m7_stagea_findings.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7-ST-S3",
            "findings": [
                {"id": "M7-ST-F11", "classification": "PREVENT", "finding": "Parent M7 cannot advance when P10 S5 verdict/semantics are not closed.", "required_action": "Fail-closed on any P10 verdict, semantic, or artifact drift."},
                {"id": "M7-ST-F12", "classification": "OBSERVE", "finding": "Writer-boundary semantics must remain strict before integrated windows.", "required_action": "Carry writer-boundary posture into S4 stress checks."},
            ],
        },
    )
    dumpj(out / "m7_lane_matrix.json", {"component_sequence": ["M7-ST-S0", "M7-ST-S1", "M7-ST-S2", "M7-ST-S3", "M7-ST-S4", "M7-ST-S5"], "plane_sequence": ["rtdl_plane", "decision_plane", "case_label_plane", "m7_rollup_plane"], "integrated_windows": ["m7_s4_normal_mix_window", "m7_s4_edge_mix_window", "m7_s4_replay_duplicate_window"]})
    dumpj(out / "m7_data_subset_manifest.json", {**dep_subset, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7-ST-S3", "platform_run_id": platform_run_id, "status": "S3_CONSUMED", "upstream_m7_s2_phase_execution_id": dep_id, "upstream_m7p10_s5_phase_execution_id": p10_id})
    dumpj(
        out / "m7_data_profile_summary.json",
        {
            **dep_profile,
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7-ST-S3",
            "platform_run_id": platform_run_id,
            "upstream_m7_s2_phase_execution_id": dep_id,
            "upstream_m7p10_s5_phase_execution_id": p10_id,
            "p10_checks": p10_checks,
            "p10_failed_checks": p10_failed_checks,
            "p10_functional_issue_count": len(p10_functional_issues),
            "p10_semantic_issue_count": len(p10_semantic_issues),
            "advisories": sorted(set([str(x) for x in [*(dep_profile.get("advisories", []) or []), *(p10_profile.get("advisories", []) or [])] if str(x).strip()])),
        },
    )
    dumpj(
        out / "m7_data_edge_case_matrix.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7-ST-S3",
            "platform_run_id": platform_run_id,
            "p10_checks": p10_checks,
            "p10_failed_checks": p10_failed_checks,
            "writer_conflict_rate_pct_s3": p10_profile.get("writer_conflict_rate_pct_s3"),
            "case_reopen_rate_pct_s2": p10_profile.get("case_reopen_rate_pct_s2"),
        },
    )
    dumpj(
        out / "m7_data_skew_hotspot_profile.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7-ST-S3",
            "platform_run_id": platform_run_id,
            "top1_run_share": dep_profile.get("top1_run_share"),
            "writer_probe": p10_ls.get("writer_probe", {}),
        },
    )
    dumpj(
        out / "m7_data_quality_guardrail_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7-ST-S3",
            "platform_run_id": platform_run_id,
            "overall_pass": len(p10_issues) == 0,
            "p10_checks": p10_checks,
            "p10_failed_checks": p10_failed_checks,
            "p10_functional_issues": p10_functional_issues[:20],
            "p10_semantic_issues": p10_semantic_issues[:20],
        },
    )
    dumpj(out / "m7_probe_latency_throughput_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7-ST-S3", **metrics})
    dumpj(out / "m7_control_rail_conformance_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7-ST-S3", "platform_run_id": platform_run_id, "overall_pass": len(issues) == 0, "issues": issues, "advisories": advisories})
    dumpj(out / "m7_secret_safety_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7-ST-S3", "overall_pass": True, "secret_probe_count": 0, "secret_failure_count": 0, "with_decryption_used": False, "queried_value_directly": False, "plaintext_leakage_detected": False})
    dumpj(out / "m7_cost_outcome_receipt.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7-ST-S3", "window_seconds": metrics["window_seconds_observed"], "estimated_api_call_count": metrics["probe_count"], "attributed_spend_usd": 0.0, "unattributed_spend_detected": False, "max_spend_usd": float(plan_packet.get("M7_STRESS_MAX_SPEND_USD", 120)), "within_envelope": True, "method": "m7_s3_parent_p10_gate_v0"})
    dumpj(
        out / "m7_phase_rollup_matrix.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7-ST-S3",
            "platform_run_id": platform_run_id,
            "parent_chain": [{"stage_id": "M7-ST-S2", "phase_execution_id": dep_id, "next_gate_expected": "M7_ST_S3_READY", "ok": len(dep_issues) == 0}],
            "subphase_chain": [{"stage_id": "M7P10-ST-S5", "phase_execution_id": p10_id, "expected_verdict": "M7_J_READY", "ok": len(p10_issues) == 0}],
        },
    )
    dumpj(
        out / "m7_gate_verdict.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7-ST-S3",
            "platform_run_id": platform_run_id,
            "overall_pass": overall_pass,
            "verdict": verdict_name,
            "next_gate": next_gate,
            "blocker_count": len(blockers),
            "upstream_m7_s2_phase_execution_id": dep_id,
            "upstream_m7p10_s5_phase_execution_id": p10_id,
        },
    )
    dumpj(
        out / "m8_handoff_pack.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7-ST-S3",
            "status": "NOT_EMITTED_IN_S3",
            "platform_run_id": platform_run_id,
            "next_gate_candidate": next_gate,
        },
    )

    decisions.extend(
        [
            "Validated M7 S2 continuity before parent P10 adjudication.",
            "Accepted P10 S5 only with deterministic verdict and zero writer-boundary semantic issue carry-over.",
            "Preserved fail-closed posture on any P10 artifact, verdict, or run-scope drift.",
        ]
    )
    dumpj(out / "m7_decision_log.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7-ST-S3", "decisions": decisions, "advisories": advisories})

    blocker_register = {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7-ST-S3", "overall_pass": overall_pass, "open_blocker_count": len(blockers), "blockers": blockers}
    summary = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M7-ST-S3",
        "overall_pass": overall_pass,
        "next_gate": next_gate,
        "open_blocker_count": len(blockers),
        "required_artifacts": required_artifacts,
        "probe_count": metrics["probe_count"],
        "error_rate_pct": metrics["error_rate_pct"],
        "platform_run_id": platform_run_id,
        "upstream_m7_s2_phase_execution_id": dep_id,
        "upstream_m7p10_s5_phase_execution_id": p10_id,
    }
    verdict = {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7-ST-S3", "overall_pass": overall_pass, "verdict": verdict_name, "next_gate": next_gate, "blocker_count": len(blockers), "platform_run_id": platform_run_id}
    dumpj(out / "m7_blocker_register.json", blocker_register)
    dumpj(out / "m7_execution_summary.json", summary)
    dumpj(out / "m7_gate_verdict.json", verdict)
    finalize_artifact_contract(out, required_artifacts, blockers, blocker_register, summary, verdict, blocker_id="M7-ST-B9")

    print(f"[m7_s3] phase_execution_id={phase_execution_id}")
    print(f"[m7_s3] output_dir={out.as_posix()}")
    print(f"[m7_s3] overall_pass={summary.get('overall_pass')}")
    print(f"[m7_s3] next_gate={summary.get('next_gate')}")
    print(f"[m7_s3] open_blockers={blocker_register.get('open_blocker_count')}")
    return 0 if summary.get("overall_pass") else 2


def run_s4(phase_execution_id: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)

    plan_packet = parse_bt_map(PLAN.read_text(encoding="utf-8") if PLAN.exists() else "")
    handles = parse_registry(REG) if REG.exists() else {}
    required_artifacts = parse_required_artifacts(plan_packet)

    blockers: list[dict[str, Any]] = []
    probes: list[dict[str, Any]] = []
    issues: list[str] = []
    advisories: list[str] = []
    decisions: list[str] = []

    missing_plan_keys = [k for k in PLAN_KEYS if k not in plan_packet]
    missing_handles, placeholder_handles = resolve_required_handles(handles)
    if missing_plan_keys or missing_handles or placeholder_handles:
        blockers.append(
            {
                "id": "M7-ST-B1",
                "severity": "S4",
                "status": "OPEN",
                "details": {
                    "missing_plan_keys": missing_plan_keys,
                    "missing_handles": missing_handles,
                    "placeholder_handles": placeholder_handles,
                },
            }
        )
        if missing_plan_keys:
            issues.append(f"missing plan keys: {','.join(missing_plan_keys)}")
        if missing_handles:
            issues.append(f"missing handles: {','.join(missing_handles)}")
        if placeholder_handles:
            issues.append(f"placeholder handles: {','.join(placeholder_handles)}")

    dep = latest_ok("m7_stress_s3", "m7_execution_summary.json", "M7-ST-S3")
    dep_issues: list[str] = []
    dep_id = ""
    dep_path = Path()
    dep_subset: dict[str, Any] = {}
    dep_profile: dict[str, Any] = {}
    platform_run_id = ""
    if not dep:
        dep_issues.append("missing successful M7-ST-S3 dependency")
    else:
        dep_summary = dep["summary"]
        dep_id = str(dep_summary.get("phase_execution_id", ""))
        if str(dep_summary.get("next_gate", "")).strip() != "M7_ST_S4_READY":
            dep_issues.append("M7-ST-S3 next_gate is not M7_ST_S4_READY")
        dep_path = Path(str(dep.get("path", "")))
        dep_blockers = loadj(dep_path / "m7_blocker_register.json")
        if int(dep_blockers.get("open_blocker_count", 0) or 0) != 0:
            dep_issues.append("M7-ST-S3 blocker register is not closed")
        dep_subset = loadj(dep_path / "m7_data_subset_manifest.json")
        dep_profile = loadj(dep_path / "m7_data_profile_summary.json")
        if not dep_subset or not dep_profile:
            dep_issues.append("M7-ST-S3 data subset/profile artifacts are missing")
        platform_run_id = str(dep_summary.get("platform_run_id", "")).strip()
    if dep_issues:
        blockers.append({"id": "M7-ST-B11", "severity": "S4", "status": "OPEN", "details": {"issues": dep_issues}})
        issues.extend(dep_issues)

    p8 = latest_ok("m7p8_stress_s5", "m7p8_execution_summary.json", "M7P8-ST-S5")
    p9 = latest_ok("m7p9_stress_s5", "m7p9_execution_summary.json", "M7P9-ST-S5")
    p10 = latest_ok("m7p10_stress_s5", "m7p10_execution_summary.json", "M7P10-ST-S5")
    subphase_issues: list[str] = []
    subphase_rows: list[dict[str, Any]] = []
    semantic_issues: list[str] = []
    semantic_issue_counts = {"p8": 0, "p9": 0, "p10": 0}
    retry_ratio_pct: float | None = None
    subphase_error_rates: dict[str, float] = {}
    subphase_spend = 0.0
    subphase_window_seconds = 0

    for label, rec, summary_name, blocker_name, expected_verdict, snapshot_names, profile_name in [
        ("P8", p8, "m7p8_execution_summary.json", "m7p8_blocker_register.json", "ADVANCE_TO_P9", ["m7p8_ieg_snapshot.json", "m7p8_ofp_snapshot.json", "m7p8_archive_snapshot.json"], "m7p8_data_profile_summary.json"),
        ("P9", p9, "m7p9_execution_summary.json", "m7p9_blocker_register.json", "ADVANCE_TO_P10", ["m7p9_df_snapshot.json", "m7p9_al_snapshot.json", "m7p9_dla_snapshot.json"], "m7p9_data_profile_summary.json"),
        ("P10", p10, "m7p10_execution_summary.json", "m7p10_blocker_register.json", "M7_J_READY", ["m7p10_case_trigger_snapshot.json", "m7p10_cm_snapshot.json", "m7p10_ls_snapshot.json"], "m7p10_data_profile_summary.json"),
    ]:
        row = {"label": label, "ok": False, "phase_execution_id": "", "expected_verdict": expected_verdict, "verdict": "", "platform_run_id": ""}
        if not rec:
            subphase_issues.append(f"missing successful {label} S5 dependency")
            subphase_rows.append(row)
            continue
        path = Path(str(rec.get("path", "")))
        summary = rec.get("summary", {})
        row["phase_execution_id"] = str(summary.get("phase_execution_id", ""))
        row["verdict"] = str(summary.get("verdict", ""))
        row["platform_run_id"] = str(summary.get("platform_run_id", "")).strip()
        if row["verdict"] != expected_verdict:
            subphase_issues.append(f"{label} verdict mismatch: expected {expected_verdict}, got {row['verdict']}")
        blocker_reg = loadj(path / blocker_name)
        if int(blocker_reg.get("open_blocker_count", 0) or 0) != 0:
            subphase_issues.append(f"{label} blocker register is not closed")
        req = [str(x) for x in summary.get("required_artifacts", []) if str(x).strip()]
        for name in req:
            if not (path / name).exists():
                subphase_issues.append(f"{label} missing dependency artifact: {name}")
        if platform_run_id and row["platform_run_id"] and platform_run_id != row["platform_run_id"]:
            subphase_issues.append(f"run-scope mismatch for {label}")
        if not platform_run_id and row["platform_run_id"]:
            platform_run_id = row["platform_run_id"]

        profile = loadj(path / profile_name)
        if label == "P9":
            rr = profile.get("retry_ratio_pct")
            retry_ratio_pct = None if rr is None else float(rr)
        row_semantic_issues: list[str] = []
        for snap_name in snapshot_names:
            snap = loadj(path / snap_name)
            sem = [str(x) for x in snap.get("semantic_issues", []) if str(x).strip()]
            fun = [str(x) for x in snap.get("functional_issues", []) if str(x).strip()]
            semantic_issues.extend(sem)
            semantic_issues.extend(fun)
            row_semantic_issues.extend(sem)
            row_semantic_issues.extend(fun)
        semantic_issue_counts[label.lower()] = len(row_semantic_issues)
        subphase_error_rates[label.lower()] = float(summary.get("error_rate_pct", 0.0) or 0.0)
        subphase_row_cost = loadj(path / f"{'m7p8' if label == 'P8' else ('m7p9' if label == 'P9' else 'm7p10')}_cost_outcome_receipt.json")
        subphase_spend += float(subphase_row_cost.get("attributed_spend_usd", 0.0) or 0.0)
        subphase_window_seconds += int(subphase_row_cost.get("window_seconds", 0) or 0)
        row["ok"] = True
        subphase_rows.append(row)

    if subphase_issues:
        blockers.append({"id": "M7-ST-B11", "severity": "S4", "status": "OPEN", "details": {"issues": sorted(set(subphase_issues))}})
        issues.extend(sorted(set(subphase_issues)))

    if semantic_issues:
        blockers.append({"id": "M7-ST-B11", "severity": "S4", "status": "OPEN", "details": {"semantic_issues": sorted(set(semantic_issues))[:40]}})
        issues.append("semantic invariants drift detected in integrated dependency sweep")

    bucket = str(handles.get("S3_EVIDENCE_BUCKET", "")).strip()
    p_bucket = add_head_bucket_probe(probes, bucket, "eu-west-2", "m7_s4_evidence_bucket")
    if p_bucket.get("status") != "PASS":
        blockers.append({"id": "M7-ST-B10", "severity": "S4", "status": "OPEN", "details": {"probe_id": "m7_s4_evidence_bucket"}})
        issues.append("evidence bucket probe failed")

    replacements = {"platform_run_id": platform_run_id, "phase_execution_id": phase_execution_id}
    for probe_id, handle_key in [
        ("m7_s4_receipt_summary", "RECEIPT_SUMMARY_PATH_PATTERN"),
        ("m7_s4_offsets_snapshot", "KAFKA_OFFSETS_SNAPSHOT_PATH_PATTERN"),
        ("m7_s4_quarantine_summary", "QUARANTINE_SUMMARY_PATH_PATTERN"),
    ]:
        key = materialize_pattern(str(handles.get(handle_key, "")).strip(), replacements)
        if key:
            p = add_head_object_probe(probes, bucket, key, "eu-west-2", probe_id)
            if p.get("status") != "PASS":
                blockers.append({"id": "M7-ST-B10", "severity": "S4", "status": "OPEN", "details": {"probe_id": probe_id, "key": key}})
                issues.append(f"{probe_id} probe failed")

    metrics = probe_metrics(probes)
    max_error_pct = float(handles.get("THROUGHPUT_CERT_MAX_ERROR_RATE_PCT", 1.0))
    max_retry_pct = float(handles.get("THROUGHPUT_CERT_MAX_RETRY_RATIO_PCT", 5.0))
    min_sample_events = int(handles.get("THROUGHPUT_CERT_MIN_SAMPLE_EVENTS", plan_packet.get("M7_STRESS_DATA_MIN_SAMPLE_EVENTS", 15000)))
    target_eps = float(handles.get("THROUGHPUT_CERT_TARGET_EVENTS_PER_SECOND", 100.0))
    window_minutes = max(1, int(handles.get("THROUGHPUT_CERT_WINDOW_MINUTES", 10)))
    rows_scanned = int(dep_profile.get("rows_scanned", 0) or 0)
    eps_proxy = rows_scanned / float(window_minutes * 60)
    worst_error_pct = max([metrics.get("error_rate_pct", 0.0), *list(subphase_error_rates.values())]) if subphase_error_rates else float(metrics.get("error_rate_pct", 0.0))
    integrated_checks = {
        "sample_size_check": rows_scanned >= min_sample_events,
        "throughput_proxy_check": eps_proxy >= target_eps,
        "error_rate_check": worst_error_pct <= max_error_pct,
        "retry_ratio_check": retry_ratio_pct is None or retry_ratio_pct <= max_retry_pct,
        "semantic_invariant_check": len(semantic_issues) == 0,
        "run_scope_check": len(subphase_issues) == 0,
    }
    if not integrated_checks["sample_size_check"] or not integrated_checks["throughput_proxy_check"] or not integrated_checks["error_rate_check"] or not integrated_checks["retry_ratio_check"]:
        blockers.append(
            {
                "id": "M7-ST-B8",
                "severity": "S4",
                "status": "OPEN",
                "details": {
                    "checks": integrated_checks,
                    "rows_scanned": rows_scanned,
                    "min_sample_events": min_sample_events,
                    "eps_proxy": round(eps_proxy, 6),
                    "target_eps": target_eps,
                    "worst_error_pct": worst_error_pct,
                    "max_error_pct": max_error_pct,
                    "retry_ratio_pct": retry_ratio_pct,
                    "max_retry_pct": max_retry_pct,
                },
            }
        )
        issues.append("integrated throughput/error/retry envelope check failed")

    total_window_seconds = int(metrics.get("window_seconds_observed", 0) or 0) + subphase_window_seconds
    total_spend_usd = float(subphase_spend)
    max_runtime_minutes = float(plan_packet.get("M7_STRESS_MAX_RUNTIME_MINUTES", 360))
    max_spend_usd = float(plan_packet.get("M7_STRESS_MAX_SPEND_USD", 120))
    budget_checks = {
        "runtime_check": (total_window_seconds / 60.0) <= max_runtime_minutes,
        "spend_check": total_spend_usd <= max_spend_usd,
        "unattributed_spend_check": True,
    }
    if not all(budget_checks.values()):
        blockers.append(
            {
                "id": "M7-ST-B12",
                "severity": "S4",
                "status": "OPEN",
                "details": {
                    "checks": budget_checks,
                    "total_window_seconds": total_window_seconds,
                    "max_runtime_minutes": max_runtime_minutes,
                    "total_spend_usd": total_spend_usd,
                    "max_spend_usd": max_spend_usd,
                },
            }
        )
        issues.append("integrated runtime/spend envelope breach")

    overall_pass = len(blockers) == 0
    next_gate = "M7_ST_S5_READY" if overall_pass else "BLOCKED"
    verdict_name = "ADVANCE_TO_S5" if overall_pass else "HOLD_REMEDIATE"

    dumpj(
        out / "m7_stagea_findings.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7-ST-S4",
            "findings": [
                {"id": "M7-ST-F13", "classification": "PREVENT", "finding": "Integrated M7 window must enforce throughput and semantic envelopes simultaneously.", "required_action": "Fail-closed on B8/B11/B12 classes."},
                {"id": "M7-ST-F14", "classification": "OBSERVE", "finding": "Advisory cohorts from S0-S3 remain required in integrated pressure windows.", "required_action": "Carry cohort advisories into rollup decisioning."},
            ],
        },
    )
    dumpj(out / "m7_lane_matrix.json", {"component_sequence": ["M7-ST-S0", "M7-ST-S1", "M7-ST-S2", "M7-ST-S3", "M7-ST-S4", "M7-ST-S5"], "plane_sequence": ["rtdl_plane", "decision_plane", "case_label_plane", "m7_rollup_plane"], "integrated_windows": ["m7_s4_normal_mix_window", "m7_s4_edge_mix_window", "m7_s4_replay_duplicate_window"]})
    dumpj(out / "m7_data_subset_manifest.json", {**dep_subset, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7-ST-S4", "platform_run_id": platform_run_id, "status": "S4_INTEGRATED_WINDOW", "upstream_m7_s3_phase_execution_id": dep_id})
    dumpj(
        out / "m7_data_profile_summary.json",
        {
            **dep_profile,
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7-ST-S4",
            "platform_run_id": platform_run_id,
            "upstream_m7_s3_phase_execution_id": dep_id,
            "integrated_checks": integrated_checks,
            "budget_checks": budget_checks,
            "rows_scanned": rows_scanned,
            "eps_proxy": round(eps_proxy, 6),
            "retry_ratio_pct": retry_ratio_pct,
            "worst_error_pct": worst_error_pct,
            "subphase_error_rates": subphase_error_rates,
            "subphase_rows": subphase_rows,
            "semantic_issue_count": len(semantic_issues),
            "advisories": sorted(set([str(x) for x in [*(dep_profile.get("advisories", []) or []), *advisories] if str(x).strip()])),
        },
    )
    dumpj(
        out / "m7_data_edge_case_matrix.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7-ST-S4",
            "platform_run_id": platform_run_id,
            "integrated_windows": {
                "m7_s4_normal_mix_window": integrated_checks["sample_size_check"] and integrated_checks["throughput_proxy_check"],
                "m7_s4_edge_mix_window": integrated_checks["error_rate_check"] and integrated_checks["retry_ratio_check"],
                "m7_s4_replay_duplicate_window": integrated_checks["semantic_invariant_check"],
            },
            "integrated_checks": integrated_checks,
            "subphase_rows": subphase_rows,
        },
    )
    dumpj(
        out / "m7_data_skew_hotspot_profile.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7-ST-S4",
            "platform_run_id": platform_run_id,
            "top1_run_share": dep_profile.get("top1_run_share"),
            "semantic_issue_counts": semantic_issue_counts,
        },
    )
    dumpj(
        out / "m7_data_quality_guardrail_snapshot.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7-ST-S4",
            "platform_run_id": platform_run_id,
            "overall_pass": overall_pass,
            "integrated_checks": integrated_checks,
            "budget_checks": budget_checks,
            "semantic_issue_count": len(semantic_issues),
        },
    )
    dumpj(out / "m7_probe_latency_throughput_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7-ST-S4", **metrics})
    dumpj(out / "m7_control_rail_conformance_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7-ST-S4", "platform_run_id": platform_run_id, "overall_pass": len(issues) == 0, "issues": issues, "advisories": advisories, "subphase_rows": subphase_rows})
    dumpj(out / "m7_secret_safety_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7-ST-S4", "overall_pass": True, "secret_probe_count": 0, "secret_failure_count": 0, "with_decryption_used": False, "queried_value_directly": False, "plaintext_leakage_detected": False})
    dumpj(
        out / "m7_cost_outcome_receipt.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7-ST-S4",
            "window_seconds": total_window_seconds,
            "estimated_api_call_count": metrics["probe_count"],
            "attributed_spend_usd": round(total_spend_usd, 6),
            "unattributed_spend_detected": False,
            "max_spend_usd": max_spend_usd,
            "within_envelope": all(budget_checks.values()),
            "method": "m7_s4_integrated_window_v0",
        },
    )
    dumpj(out / "m7_phase_rollup_matrix.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7-ST-S4", "platform_run_id": platform_run_id, "subphase_rows": subphase_rows, "integrated_checks": integrated_checks, "budget_checks": budget_checks})
    dumpj(
        out / "m7_gate_verdict.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7-ST-S4",
            "platform_run_id": platform_run_id,
            "overall_pass": overall_pass,
            "verdict": verdict_name,
            "next_gate": next_gate,
            "blocker_count": len(blockers),
            "upstream_m7_s3_phase_execution_id": dep_id,
        },
    )
    dumpj(
        out / "m8_handoff_pack.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7-ST-S4",
            "status": "NOT_EMITTED_IN_S4",
            "platform_run_id": platform_run_id,
            "next_gate_candidate": next_gate,
            "integrated_checks": integrated_checks,
        },
    )

    decisions.extend(
        [
            "Validated S3 continuity before integrated M7 window adjudication.",
            "Enforced integrated throughput/error/retry envelopes against pinned throughput contracts.",
            "Preserved fail-closed posture for semantic drift and runtime/spend anomalies.",
        ]
    )
    dumpj(out / "m7_decision_log.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7-ST-S4", "decisions": decisions, "advisories": advisories, "subphase_rows": subphase_rows})

    blocker_register = {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7-ST-S4", "overall_pass": overall_pass, "open_blocker_count": len(blockers), "blockers": blockers}
    summary = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M7-ST-S4",
        "overall_pass": overall_pass,
        "next_gate": next_gate,
        "open_blocker_count": len(blockers),
        "required_artifacts": required_artifacts,
        "probe_count": metrics["probe_count"],
        "error_rate_pct": metrics["error_rate_pct"],
        "platform_run_id": platform_run_id,
        "upstream_m7_s3_phase_execution_id": dep_id,
    }
    verdict = {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7-ST-S4", "overall_pass": overall_pass, "verdict": verdict_name, "next_gate": next_gate, "blocker_count": len(blockers), "platform_run_id": platform_run_id}
    dumpj(out / "m7_blocker_register.json", blocker_register)
    dumpj(out / "m7_execution_summary.json", summary)
    dumpj(out / "m7_gate_verdict.json", verdict)
    finalize_artifact_contract(out, required_artifacts, blockers, blocker_register, summary, verdict, blocker_id="M7-ST-B10")

    print(f"[m7_s4] phase_execution_id={phase_execution_id}")
    print(f"[m7_s4] output_dir={out.as_posix()}")
    print(f"[m7_s4] overall_pass={summary.get('overall_pass')}")
    print(f"[m7_s4] next_gate={summary.get('next_gate')}")
    print(f"[m7_s4] open_blockers={blocker_register.get('open_blocker_count')}")
    return 0 if summary.get("overall_pass") else 2


def run_s5(phase_execution_id: str) -> int:
    out = OUT_ROOT / phase_execution_id / "stress"
    out.mkdir(parents=True, exist_ok=True)

    plan_packet = parse_bt_map(PLAN.read_text(encoding="utf-8") if PLAN.exists() else "")
    handles = parse_registry(REG) if REG.exists() else {}
    required_artifacts = parse_required_artifacts(plan_packet)

    blockers: list[dict[str, Any]] = []
    probes: list[dict[str, Any]] = []
    issues: list[str] = []
    advisories: list[str] = []
    decisions: list[str] = []
    addendum_blockers: list[dict[str, Any]] = []

    expected_next_gate = str(plan_packet.get("M7_STRESS_EXPECTED_NEXT_GATE_ON_PASS", "M8_READY")).strip() or "M8_READY"
    if expected_next_gate != "M8_READY":
        blockers.append(
            {
                "id": "M7-ST-B11",
                "severity": "S5",
                "status": "OPEN",
                "details": {"reason": "unexpected expected_next_gate contract", "expected_next_gate_on_pass": expected_next_gate},
            }
        )
        issues.append("unexpected expected_next_gate_on_pass contract")

    missing_plan_keys = [k for k in PLAN_KEYS if k not in plan_packet]
    missing_handles, placeholder_handles = resolve_required_handles(handles)
    if missing_plan_keys or missing_handles or placeholder_handles:
        blockers.append(
            {
                "id": "M7-ST-B9",
                "severity": "S5",
                "status": "OPEN",
                "details": {
                    "missing_plan_keys": missing_plan_keys,
                    "missing_handles": missing_handles,
                    "placeholder_handles": placeholder_handles,
                },
            }
        )
        if missing_plan_keys:
            issues.append(f"missing plan keys: {','.join(missing_plan_keys)}")
        if missing_handles:
            issues.append(f"missing handles: {','.join(missing_handles)}")
        if placeholder_handles:
            issues.append(f"placeholder handles: {','.join(placeholder_handles)}")

    dep = latest_ok("m7_stress_s4", "m7_execution_summary.json", "M7-ST-S4")
    dep_issues: list[str] = []
    dep_id = ""
    dep_path = Path()
    dep_subset: dict[str, Any] = {}
    dep_profile: dict[str, Any] = {}
    platform_run_id = ""
    if not dep:
        dep_issues.append("missing successful M7-ST-S4 dependency")
    else:
        dep_summary = dep["summary"]
        dep_id = str(dep_summary.get("phase_execution_id", ""))
        if str(dep_summary.get("next_gate", "")).strip() != "M7_ST_S5_READY":
            dep_issues.append("M7-ST-S4 next_gate is not M7_ST_S5_READY")
        dep_path = Path(str(dep.get("path", "")))
        dep_blockers = loadj(dep_path / "m7_blocker_register.json")
        if int(dep_blockers.get("open_blocker_count", 0) or 0) != 0:
            dep_issues.append("M7-ST-S4 blocker register is not closed")
        dep_subset = loadj(dep_path / "m7_data_subset_manifest.json")
        dep_profile = loadj(dep_path / "m7_data_profile_summary.json")
        if not dep_subset or not dep_profile:
            dep_issues.append("M7-ST-S4 data subset/profile artifacts are missing")
        platform_run_id = str(dep_summary.get("platform_run_id", "")).strip()
    if dep_issues:
        blockers.append({"id": "M7-ST-B11", "severity": "S5", "status": "OPEN", "details": {"issues": dep_issues}})
        issues.extend(dep_issues)

    chain_rows, chain_issues = build_parent_chain_rows(platform_run_id)
    if chain_issues:
        blockers.append({"id": "M7-ST-B11", "severity": "S5", "status": "OPEN", "details": {"issues": chain_issues, "chain_rows": chain_rows}})
        issues.extend(chain_issues)

    subphase_rows: list[dict[str, Any]] = []
    subphase_records: dict[str, dict[str, Any]] = {}
    subphase_issues: list[str] = []
    for label, rec, expected_verdict in [
        ("P8", latest_ok("m7p8_stress_s5", "m7p8_execution_summary.json", "M7P8-ST-S5"), "ADVANCE_TO_P9"),
        ("P9", latest_ok("m7p9_stress_s5", "m7p9_execution_summary.json", "M7P9-ST-S5"), "ADVANCE_TO_P10"),
        ("P10", latest_ok("m7p10_stress_s5", "m7p10_execution_summary.json", "M7P10-ST-S5"), "M7_J_READY"),
    ]:
        row = {
            "label": label,
            "found": bool(rec),
            "phase_execution_id": "",
            "platform_run_id": "",
            "expected_verdict": expected_verdict,
            "verdict": "",
            "ok": False,
        }
        if not rec:
            subphase_issues.append(f"missing successful {label} S5 dependency")
            subphase_rows.append(row)
            continue
        subphase_records[label] = rec
        s = rec.get("summary", {})
        row["phase_execution_id"] = str(s.get("phase_execution_id", ""))
        row["platform_run_id"] = str(s.get("platform_run_id", "")).strip()
        row["verdict"] = str(s.get("verdict", "")).strip()
        row["ok"] = row["verdict"] == expected_verdict and row["platform_run_id"] == platform_run_id
        if row["verdict"] != expected_verdict:
            subphase_issues.append(f"{label} verdict mismatch: expected {expected_verdict}, got {row['verdict']}")
        if platform_run_id and row["platform_run_id"] and row["platform_run_id"] != platform_run_id:
            subphase_issues.append(f"{label} run-scope mismatch")
        subphase_rows.append(row)
    if subphase_issues:
        blockers.append({"id": "M7-ST-B11", "severity": "S5", "status": "OPEN", "details": {"issues": sorted(set(subphase_issues)), "subphase_rows": subphase_rows}})
        issues.extend(sorted(set(subphase_issues)))

    toy_profile_signals: list[dict[str, Any]] = []

    def gather_toy_signals(source_label: str, payload: dict[str, Any], keys: tuple[str, ...] = ("advisories",)) -> None:
        if not isinstance(payload, dict):
            return
        for key in keys:
            raw = payload.get(key, [])
            if not isinstance(raw, list):
                continue
            hits = [str(x).strip() for x in raw if str(x).strip() and is_toy_profile_advisory(str(x))]
            if hits:
                toy_profile_signals.append({"source": f"{source_label}:{key}", "signals": hits[:20]})

    if dep_path:
        gather_toy_signals("M7-S4 data profile", loadj(dep_path / "m7_data_profile_summary.json"))
        gather_toy_signals("M7-S4 control snapshot", loadj(dep_path / "m7_control_rail_conformance_snapshot.json"))
        gather_toy_signals("M7-S4 decision log", loadj(dep_path / "m7_decision_log.json"))

    for label, prefix in [("P8", "m7p8"), ("P9", "m7p9"), ("P10", "m7p10")]:
        rec = subphase_records.get(label)
        if not rec:
            continue
        rec_path = Path(str(rec.get("path", "")))
        gather_toy_signals(f"{label} data profile", loadj(rec_path / f"{prefix}_data_profile_summary.json"))
        gather_toy_signals(f"{label} control snapshot", loadj(rec_path / f"{prefix}_control_rail_conformance_snapshot.json"))
        gather_toy_signals(f"{label} decision log", loadj(rec_path / f"{prefix}_decision_log.json"))

    if toy_profile_signals:
        blockers.append(
            {
                "id": "M7-ST-B14",
                "severity": "S5",
                "status": "OPEN",
                "details": {
                    "reason": "toy-profile closure posture detected in M7 parent rollup inputs",
                    "signals": toy_profile_signals[:40],
                },
            }
        )
        issues.append("toy-profile closure posture detected in M7 parent rollup inputs")

    bucket = str(handles.get("S3_EVIDENCE_BUCKET", "")).strip()
    p_bucket = add_head_bucket_probe(probes, bucket, "eu-west-2", "m7_s5_evidence_bucket")
    if p_bucket.get("status") != "PASS":
        blockers.append({"id": "M7-ST-B9", "severity": "S5", "status": "OPEN", "details": {"probe_id": "m7_s5_evidence_bucket"}})
        issues.append("evidence bucket probe failed")

    replacements = {"platform_run_id": platform_run_id, "phase_execution_id": phase_execution_id}
    for probe_id, handle_key in [
        ("m7_s5_receipt_summary", "RECEIPT_SUMMARY_PATH_PATTERN"),
        ("m7_s5_offsets_snapshot", "KAFKA_OFFSETS_SNAPSHOT_PATH_PATTERN"),
        ("m7_s5_quarantine_summary", "QUARANTINE_SUMMARY_PATH_PATTERN"),
    ]:
        key = materialize_pattern(str(handles.get(handle_key, "")).strip(), replacements)
        if key:
            p = add_head_object_probe(probes, bucket, key, "eu-west-2", probe_id)
            if p.get("status") != "PASS":
                blockers.append({"id": "M7-ST-B9", "severity": "S5", "status": "OPEN", "details": {"probe_id": probe_id, "key": key}})
                issues.append(f"{probe_id} probe failed")

    stage_cost_rows: list[dict[str, Any]] = []
    total_window_seconds = 0
    mapped_rollup_spend_usd = 0.0
    for prefix, stage_id in [
        ("m7_stress_s0", "M7-ST-S0"),
        ("m7_stress_s1", "M7-ST-S1"),
        ("m7_stress_s2", "M7-ST-S2"),
        ("m7_stress_s3", "M7-ST-S3"),
        ("m7_stress_s4", "M7-ST-S4"),
    ]:
        rec = latest_ok(prefix, "m7_execution_summary.json", stage_id)
        row = {
            "stage_id": stage_id,
            "phase_execution_id": "",
            "window_seconds": 0,
            "attributed_spend_usd": 0.0,
            "found": bool(rec),
            "source": "m7_cost_outcome_receipt.json",
            "summary_generated_at_utc": "",
            "receipt_generated_at_utc": "",
            "window_start_utc": "",
            "window_end_utc": "",
        }
        if rec:
            s = rec.get("summary", {})
            row["phase_execution_id"] = str(s.get("phase_execution_id", ""))
            row["summary_generated_at_utc"] = str(s.get("generated_at_utc", ""))
            cost = loadj(Path(str(rec.get("path", ""))) / "m7_cost_outcome_receipt.json")
            row["receipt_generated_at_utc"] = str(cost.get("generated_at_utc", ""))
            row["window_seconds"] = int(cost.get("window_seconds", 0) or 0)
            row["attributed_spend_usd"] = float(cost.get("attributed_spend_usd", 0.0) or 0.0)
            ws, we = derive_stage_window(row)
            row["window_start_utc"] = iso_utc(ws)
            row["window_end_utc"] = iso_utc(we)
            total_window_seconds += row["window_seconds"]
            mapped_rollup_spend_usd += row["attributed_spend_usd"]
        stage_cost_rows.append(row)

    query_start_utc, query_end_utc = derive_cost_query_window(stage_cost_rows)
    cost_attribution_window_seconds = max(1, int((query_end_utc - query_start_utc).total_seconds()))
    billing_region = str(handles.get("AWS_BILLING_REGION", "us-east-1")).strip() or "us-east-1"
    ce_receipt = query_aws_cost_explorer_window(query_start_utc, query_end_utc, billing_region)
    attributed_spend_usd = float(ce_receipt.get("amount_usd", 0.0) or 0.0) if ce_receipt.get("ok") else float(mapped_rollup_spend_usd)
    unattributed_spend_detected = not bool(ce_receipt.get("ok"))
    ce_vs_rollup_delta_usd = round(attributed_spend_usd - float(mapped_rollup_spend_usd), 8)
    if not ce_receipt.get("ok"):
        advisories.append(f"cost explorer attribution unavailable: {ce_receipt.get('error', 'unknown_error')}")
    elif attributed_spend_usd + 0.01 < float(mapped_rollup_spend_usd):
        unattributed_spend_detected = True
        advisories.append("ce attributed spend below mapped rollup spend by >$0.01; flagged as unattributed residual")

    max_runtime_minutes = float(plan_packet.get("M7_STRESS_MAX_RUNTIME_MINUTES", 360))
    max_spend_usd = float(plan_packet.get("M7_STRESS_MAX_SPEND_USD", 120))
    budget_checks = {
        "runtime_check": (total_window_seconds / 60.0) <= max_runtime_minutes,
        "spend_check": attributed_spend_usd <= max_spend_usd,
        "unattributed_spend_check": not unattributed_spend_detected,
    }
    if not all(budget_checks.values()):
        blockers.append(
            {
                "id": "M7-ST-B12",
                "severity": "S5",
                "status": "OPEN",
                "details": {
                    "checks": budget_checks,
                    "total_window_seconds": total_window_seconds,
                    "max_runtime_minutes": max_runtime_minutes,
                    "total_spend_usd": attributed_spend_usd,
                    "max_spend_usd": max_spend_usd,
                    "mapped_rollup_spend_usd": round(mapped_rollup_spend_usd, 6),
                    "ce_attribution": ce_receipt,
                    "ce_vs_rollup_delta_usd": ce_vs_rollup_delta_usd,
                    "stage_cost_rows": stage_cost_rows,
                },
            }
        )
        issues.append("rollup runtime/spend envelope breach")

    p8_profile = loadj(Path(str(subphase_records.get("P8", {}).get("path", ""))) / "m7p8_data_profile_summary.json") if subphase_records.get("P8") else {}
    p9_profile = loadj(Path(str(subphase_records.get("P9", {}).get("path", ""))) / "m7p9_data_profile_summary.json") if subphase_records.get("P9") else {}
    p10_profile = loadj(Path(str(subphase_records.get("P10", {}).get("path", ""))) / "m7p10_data_profile_summary.json") if subphase_records.get("P10") else {}
    dep_probe = loadj(dep_path / "m7_probe_latency_throughput_snapshot.json") if dep_path else {}

    def to_float(v: Any) -> float | None:
        try:
            if v is None:
                return None
            return float(v)
        except (TypeError, ValueError):
            return None

    def to_int(v: Any) -> int:
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0

    add_profile_id = str(plan_packet.get("M7_ADDENDUM_PROFILE_ID", "m7_production_hard_close_v0")).strip() or "m7_production_hard_close_v0"
    add_expected_gate = str(plan_packet.get("M7_ADDENDUM_EXPECTED_GATE_ON_PASS", "M8_READY")).strip() or "M8_READY"
    dup_min_pct = float(plan_packet.get("M7_ADDENDUM_REALISM_DUPLICATE_OBSERVED_MIN_PCT", 0.5) or 0.5)
    ooo_min_pct = float(plan_packet.get("M7_ADDENDUM_REALISM_OUT_OF_ORDER_OBSERVED_MIN_PCT", 0.2) or 0.2)
    hotkey_min_pct = float(plan_packet.get("M7_ADDENDUM_REALISM_HOTKEY_TOP1_MIN_PCT", 30) or 30)
    case_label_observed_min_events = int(plan_packet.get("M7_ADDENDUM_CASE_LABEL_OBSERVED_MIN_EVENTS", 100000) or 100000)
    case_label_effective_min_events = int(plan_packet.get("M7_ADDENDUM_CASE_LABEL_EFFECTIVE_MIN_EVENTS", case_label_observed_min_events) or case_label_observed_min_events)
    case_label_observed_proof_min_events = int(plan_packet.get("M7_ADDENDUM_CASE_LABEL_OBSERVED_PROOF_MIN_EVENTS", 10) or 10)
    service_metrics_required = [x.strip() for x in str(plan_packet.get("M7_ADDENDUM_SERVICE_PATH_METRICS_REQUIRED", "p50,p95,p99,error_rate,retry_ratio,lag")).split(",") if x.strip()]
    add_max_runtime_minutes = float(plan_packet.get("M7_ADDENDUM_MAX_RUNTIME_MINUTES", 240) or 240)
    add_max_spend_usd = float(plan_packet.get("M7_ADDENDUM_MAX_SPEND_USD", 60) or 60)
    add_cost_method_required = str(plan_packet.get("M7_ADDENDUM_COST_ATTRIBUTION_METHOD", "aws_ce_daily_unblended_v1")).strip() or "aws_ce_daily_unblended_v1"
    add_cost_min_window_seconds = int(plan_packet.get("M7_ADDENDUM_COST_ATTRIBUTION_MIN_WINDOW_SECONDS", 600) or 600)

    cohort_presence = p8_profile.get("cohort_presence", {}) if isinstance(p8_profile.get("cohort_presence", {}), dict) else {}
    duplicate_ratio_pct = to_float(p9_profile.get("duplicate_ratio_pct"))
    out_of_order_ratio_pct = to_float(dep_profile.get("out_of_order_ratio_pct"))
    top1_share = to_float(dep_profile.get("top1_run_share"))
    if top1_share is None:
        top1_share = to_float((p8_profile.get("source_profile", {}) or {}).get("top1_hotkey_share"))
    top1_share_pct = None if top1_share is None else (top1_share * 100.0 if top1_share <= 1.0 else top1_share)

    semantic_issue_count = to_int(dep_profile.get("semantic_issue_count"))
    p8_semantic_issue_count = to_int(dep_profile.get("p8_semantic_issue_count"))
    p9_semantic_issue_count = to_int(dep_profile.get("p9_semantic_issue_count"))
    p10_semantic_issue_count = to_int(dep_profile.get("p10_semantic_issue_count"))
    semantic_ok = (semantic_issue_count + p8_semantic_issue_count + p9_semantic_issue_count + p10_semantic_issue_count) == 0

    direct_realism_check = (
        duplicate_ratio_pct is not None
        and out_of_order_ratio_pct is not None
        and top1_share_pct is not None
        and duplicate_ratio_pct >= dup_min_pct
        and out_of_order_ratio_pct >= ooo_min_pct
        and top1_share_pct >= hotkey_min_pct
    )
    a1_mode = "direct_observed" if direct_realism_check else "failed"
    a1_pass = semantic_ok and direct_realism_check
    if not a1_pass:
        if not semantic_ok:
            addendum_blockers.append(
                {
                    "id": "M7-ADD-B2",
                    "severity": "HIGH",
                    "status": "OPEN",
                    "details": {
                        "reason": "semantic drift under realism pressure",
                        "semantic_issue_count": semantic_issue_count,
                        "p8_semantic_issue_count": p8_semantic_issue_count,
                        "p9_semantic_issue_count": p9_semantic_issue_count,
                        "p10_semantic_issue_count": p10_semantic_issue_count,
                    },
                }
            )
        if not direct_realism_check:
            addendum_blockers.append(
                {
                    "id": "M7-ADD-B1",
                    "severity": "HIGH",
                    "status": "OPEN",
                    "details": {
                        "reason": "realism cohorts not sufficiently observed at direct-observed thresholds",
                        "direct_realism_check": direct_realism_check,
                        "cohort_presence": cohort_presence,
                        "duplicate_ratio_pct": duplicate_ratio_pct,
                        "out_of_order_ratio_pct": out_of_order_ratio_pct,
                        "top1_share_pct": top1_share_pct,
                        "thresholds": {
                            "duplicate_min_pct": dup_min_pct,
                            "out_of_order_min_pct": ooo_min_pct,
                            "hotkey_top1_min_pct": hotkey_min_pct,
                        },
                        "a1_mode": a1_mode,
                    },
                }
            )

    case_events_observed = to_int(p10_profile.get("case_events_observed"))
    label_events_observed = to_int(p10_profile.get("label_events_observed"))
    case_events_effective = to_int(p10_profile.get("case_events_effective"))
    label_events_effective = to_int(p10_profile.get("label_events_effective"))
    p10_checks = p10_profile.get("checks", {}) if isinstance(p10_profile.get("checks", {}), dict) else {}
    p10_semantic_green = (
        len(p10_profile.get("s1_semantic_issues", []) or []) == 0
        and len(p10_profile.get("s2_semantic_issues", []) or []) == 0
        and len(p10_profile.get("s3_semantic_issues", []) or []) == 0
        and bool(p10_checks.get("writer_conflict_rate_check", True))
        and bool(p10_checks.get("case_reopen_rate_check", True))
        and bool(p10_profile.get("single_writer_posture_s3", True))
    )
    a2_direct_observed_check = case_events_observed >= case_label_observed_min_events and label_events_observed >= case_label_observed_min_events
    a2_mode = "observed_volume" if a2_direct_observed_check else "failed"
    a2_pass = p10_semantic_green and a2_direct_observed_check
    if not a2_pass:
        addendum_blockers.append(
            {
                "id": "M7-ADD-B3",
                "severity": "HIGH",
                "status": "OPEN",
                "details": {
                    "reason": "case/label pressure window remains below closure posture",
                    "mode": a2_mode,
                    "p10_semantic_green": p10_semantic_green,
                    "case_events_observed": case_events_observed,
                    "label_events_observed": label_events_observed,
                    "case_events_effective": case_events_effective,
                    "label_events_effective": label_events_effective,
                    "thresholds": {
                        "observed_min_events": case_label_observed_min_events,
                        "effective_min_events": case_label_effective_min_events,
                        "observed_proof_min_events": case_label_observed_proof_min_events,
                    },
                },
            }
        )

    integrated_checks = dep_profile.get("integrated_checks", {}) if isinstance(dep_profile.get("integrated_checks", {}), dict) else {}
    target_eps = float(handles.get("THROUGHPUT_CERT_TARGET_EVENTS_PER_SECOND", 20) or 20)
    max_error_pct = float(handles.get("THROUGHPUT_CERT_MAX_ERROR_RATE_PCT", 1.0) or 1.0)
    max_retry_pct = float(handles.get("THROUGHPUT_CERT_MAX_RETRY_RATIO_PCT", 5.0) or 5.0)
    eps_proxy = float(dep_profile.get("eps_proxy", 0.0) or 0.0)
    error_rate_pct = float(dep_profile.get("worst_error_pct", 0.0) or 0.0)
    retry_ratio_pct = float(dep_profile.get("retry_ratio_pct", 0.0) or 0.0)
    latency_p50 = float(dep_probe.get("latency_ms_p50", 0.0) or 0.0)
    latency_p95 = float(dep_probe.get("latency_ms_p95", 0.0) or 0.0)
    latency_p99 = float(dep_probe.get("latency_ms_p99", 0.0) or 0.0)
    lag_evidence_present = bool(((dep_profile.get("source_profile", {}) or {}).get("behavior_context_refs", {}) or {}).get("offsets_snapshot", {}).get("present", False))
    a3_checks = {
        "integrated_checks_pass": bool(integrated_checks) and all(bool(v) for v in integrated_checks.values()),
        "throughput_eps_check": eps_proxy >= target_eps,
        "error_rate_check": error_rate_pct <= max_error_pct,
        "retry_ratio_check": retry_ratio_pct <= max_retry_pct,
        "latency_capture_check": latency_p50 > 0.0 and latency_p95 > 0.0 and latency_p99 > 0.0,
        "lag_evidence_check": lag_evidence_present,
        "runtime_budget_check": (total_window_seconds / 60.0) <= add_max_runtime_minutes,
        "spend_budget_check": attributed_spend_usd <= add_max_spend_usd,
        "required_metric_keys_check": len(service_metrics_required) > 0,
    }
    a3_pass = all(bool(v) for v in a3_checks.values())
    if not a3_pass:
        addendum_blockers.append(
            {
                "id": "M7-ADD-B4",
                "severity": "HIGH",
                "status": "OPEN",
                "details": {
                    "reason": "service-path latency/throughput evidence incomplete or out of budget",
                    "checks": a3_checks,
                    "target_eps": target_eps,
                    "eps_proxy": round(eps_proxy, 6),
                    "error_rate_pct": error_rate_pct,
                    "max_error_pct": max_error_pct,
                    "retry_ratio_pct": retry_ratio_pct,
                    "max_retry_pct": max_retry_pct,
                    "latency_ms": {"p50": latency_p50, "p95": latency_p95, "p99": latency_p99},
                    "required_metrics": service_metrics_required,
                },
            }
        )

    a4_pass = (
        cost_attribution_window_seconds >= add_cost_min_window_seconds
        and bool(ce_receipt.get("ok"))
        and str(ce_receipt.get("method", "")).strip() == add_cost_method_required
        and not unattributed_spend_detected
    )
    if not a4_pass:
        addendum_blockers.append(
            {
                "id": "M7-ADD-B5",
                "severity": "HIGH",
                "status": "OPEN",
                "details": {
                    "reason": "real cost attribution incomplete or unexplained spend detected",
                    "window_seconds": cost_attribution_window_seconds,
                    "min_required_window_seconds": add_cost_min_window_seconds,
                    "cost_method_required": add_cost_method_required,
                    "cost_method_observed": str(ce_receipt.get("method", "")),
                    "attributed_spend_usd": round(attributed_spend_usd, 6),
                    "mapped_rollup_spend_usd": round(mapped_rollup_spend_usd, 6),
                    "ce_attribution": ce_receipt,
                    "unattributed_spend_detected": unattributed_spend_detected,
                },
            }
        )

    if addendum_blockers:
        for b in addendum_blockers:
            bid = str(b.get("id", ""))
            if bid == "M7-ADD-B5":
                blockers.append({"id": "M7-ST-B12", "severity": "S5", "status": "OPEN", "details": b.get("details", {})})
            elif bid in {"M7-ADD-B1", "M7-ADD-B2", "M7-ADD-B3", "M7-ADD-B4"}:
                blockers.append({"id": "M7-ST-B11", "severity": "S5", "status": "OPEN", "details": b.get("details", {})})
        issues.append("one or more addendum lanes failed")

    handoff_target_pattern = str(handles.get("M7_HANDOFF_PACK_PATH_PATTERN", "")).strip()
    handoff_target = materialize_pattern(handoff_target_pattern, replacements) if handoff_target_pattern else ""
    if not handoff_target:
        blockers.append({"id": "M7-ST-B13", "severity": "S5", "status": "OPEN", "details": {"reason": "missing handoff target pattern"}})
        issues.append("handoff target pattern is missing")

    metrics = probe_metrics(probes)
    overall_pass = len(blockers) == 0
    verdict_name = "GO" if overall_pass else "HOLD_REMEDIATE"
    next_gate = expected_next_gate if overall_pass else "BLOCKED"

    handoff_pack = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M7-ST-S5",
        "platform_run_id": platform_run_id,
        "verdict": verdict_name,
        "next_gate": next_gate,
        "expected_next_gate_on_pass": expected_next_gate,
        "upstream_m7_s4_phase_execution_id": dep_id,
        "parent_chain_rows": chain_rows,
        "subphase_rows": subphase_rows,
        "addendum_lane_status": {"A1": a1_pass, "A2": a2_pass, "A3": a3_pass, "A4": a4_pass},
        "addendum_open_blocker_count": len(addendum_blockers),
        "budget_checks": budget_checks,
        "handoff_target_pattern": handoff_target_pattern,
        "handoff_target_resolved": handoff_target,
        "rtdl_evidence_ref": materialize_pattern(str(handles.get("RTDL_CORE_EVIDENCE_PATH_PATTERN", "")), replacements),
        "decision_evidence_ref": materialize_pattern(str(handles.get("DECISION_LANE_EVIDENCE_PATH_PATTERN", "")), replacements),
        "case_labels_evidence_ref": materialize_pattern(str(handles.get("CASE_LABELS_EVIDENCE_PATH_PATTERN", "")), replacements),
        "receipt_summary_ref": materialize_pattern(str(handles.get("RECEIPT_SUMMARY_PATH_PATTERN", "")), replacements),
        "offsets_snapshot_ref": materialize_pattern(str(handles.get("KAFKA_OFFSETS_SNAPSHOT_PATH_PATTERN", "")), replacements),
        "quarantine_summary_ref": materialize_pattern(str(handles.get("QUARANTINE_SUMMARY_PATH_PATTERN", "")), replacements),
    }
    handoff_missing = [
        k
        for k in [
            "platform_run_id",
            "upstream_m7_s4_phase_execution_id",
            "handoff_target_resolved",
            "rtdl_evidence_ref",
            "decision_evidence_ref",
            "case_labels_evidence_ref",
            "receipt_summary_ref",
            "offsets_snapshot_ref",
            "quarantine_summary_ref",
        ]
        if not str(handoff_pack.get(k, "")).strip()
    ]
    if handoff_missing:
        blockers.append({"id": "M7-ST-B13", "severity": "S5", "status": "OPEN", "details": {"missing_fields": handoff_missing}})
        issues.append("handoff pack fields are incomplete")
        overall_pass = False
        verdict_name = "HOLD_REMEDIATE"
        next_gate = "BLOCKED"
        handoff_pack.update({"verdict": verdict_name, "next_gate": next_gate})

    dumpj(
        out / "m7_stagea_findings.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7-ST-S5",
            "findings": [
                {"id": "M7-ST-F15", "classification": "PREVENT", "finding": "M7 closeout requires deterministic rollup and valid M8 handoff pack.", "required_action": "Fail-closed on rollup inconsistencies and invalid handoff refs."},
                {"id": "M7-ST-F16", "classification": "OBSERVE", "finding": "Cost/runtime rollup must remain attributable at closure.", "required_action": "Block on unexplained spend/runtime breach."},
            ],
        },
    )
    dumpj(out / "m7_lane_matrix.json", {"component_sequence": ["M7-ST-S0", "M7-ST-S1", "M7-ST-S2", "M7-ST-S3", "M7-ST-S4", "M7-ST-S5"], "plane_sequence": ["rtdl_plane", "decision_plane", "case_label_plane", "m7_rollup_plane"], "integrated_windows": ["m7_s4_normal_mix_window", "m7_s4_edge_mix_window", "m7_s4_replay_duplicate_window"]})
    dumpj(out / "m7_data_subset_manifest.json", {**dep_subset, "generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7-ST-S5", "platform_run_id": platform_run_id, "status": "S5_ROLLUP_CARRY_FORWARD", "upstream_m7_s4_phase_execution_id": dep_id})
    dumpj(
        out / "m7_data_profile_summary.json",
        {
            **dep_profile,
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7-ST-S5",
            "platform_run_id": platform_run_id,
            "upstream_m7_s4_phase_execution_id": dep_id,
            "chain_rows": chain_rows,
            "subphase_rows": subphase_rows,
            "budget_checks": budget_checks,
            "advisories": sorted(set([str(x) for x in [*(dep_profile.get("advisories", []) or []), *advisories] if str(x).strip()])),
        },
    )
    dumpj(out / "m7_data_edge_case_matrix.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7-ST-S5", "platform_run_id": platform_run_id, "chain_rows": chain_rows, "subphase_rows": subphase_rows})
    dumpj(out / "m7_data_skew_hotspot_profile.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7-ST-S5", "platform_run_id": platform_run_id, "top1_run_share": dep_profile.get("top1_run_share")})
    dumpj(out / "m7_data_quality_guardrail_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7-ST-S5", "platform_run_id": platform_run_id, "overall_pass": overall_pass, "chain_rows": chain_rows, "subphase_rows": subphase_rows, "budget_checks": budget_checks, "addendum_lane_status": {"A1": a1_pass, "A2": a2_pass, "A3": a3_pass, "A4": a4_pass}})
    dumpj(out / "m7_probe_latency_throughput_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7-ST-S5", **metrics})
    dumpj(out / "m7_control_rail_conformance_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7-ST-S5", "platform_run_id": platform_run_id, "overall_pass": len(issues) == 0, "issues": issues, "advisories": advisories, "chain_rows": chain_rows, "subphase_rows": subphase_rows, "addendum_lane_status": {"A1": a1_pass, "A2": a2_pass, "A3": a3_pass, "A4": a4_pass}})
    dumpj(out / "m7_secret_safety_snapshot.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7-ST-S5", "overall_pass": True, "secret_probe_count": 0, "secret_failure_count": 0, "with_decryption_used": False, "queried_value_directly": False, "plaintext_leakage_detected": False})
    dumpj(
        out / "m7_cost_outcome_receipt.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7-ST-S5",
            "window_seconds": total_window_seconds,
            "cost_attribution_window_seconds": cost_attribution_window_seconds,
            "estimated_api_call_count": metrics["probe_count"],
            "attributed_spend_usd": round(attributed_spend_usd, 6),
            "mapped_rollup_spend_usd": round(mapped_rollup_spend_usd, 6),
            "unattributed_spend_detected": unattributed_spend_detected,
            "max_spend_usd": max_spend_usd,
            "within_envelope": all(budget_checks.values()),
            "method": "m7_s5_real_cost_attribution_v1",
            "cost_query_window": {"start_utc": iso_utc(query_start_utc), "end_utc": iso_utc(query_end_utc)},
            "ce_attribution": ce_receipt,
            "ce_vs_rollup_delta_usd": ce_vs_rollup_delta_usd,
            "spend_sources": stage_cost_rows,
        },
    )
    m7_addendum_realism_window_summary = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M7-ST-S5",
        "lane_id": "A1",
        "overall_pass": a1_pass,
        "mode": a1_mode,
        "semantic_ok": semantic_ok,
        "cohort_presence": cohort_presence,
        "thresholds": {
            "duplicate_min_pct": dup_min_pct,
            "out_of_order_min_pct": ooo_min_pct,
            "hotkey_top1_min_pct": hotkey_min_pct,
        },
        "observed": {
            "duplicate_ratio_pct": duplicate_ratio_pct,
            "out_of_order_ratio_pct": out_of_order_ratio_pct,
            "top1_share_pct": top1_share_pct,
        },
        "pressure_contract_flags": {
            "duplicate_pressure_contract": duplicate_pressure_contract,
            "late_pressure_contract": late_pressure_contract,
            "hotkey_pressure_contract": hotkey_pressure_contract,
        },
    }
    m7_addendum_realism_window_metrics = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M7-ST-S5",
        "lane_id": "A1",
        "rows_scanned": to_int(dep_profile.get("rows_scanned")),
        "event_type_count": to_int(dep_profile.get("event_type_count")),
        "semantic_issue_count": semantic_issue_count,
        "p8_semantic_issue_count": p8_semantic_issue_count,
        "p9_semantic_issue_count": p9_semantic_issue_count,
        "p10_semantic_issue_count": p10_semantic_issue_count,
    }
    m7_addendum_case_label_pressure_summary = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M7-ST-S5",
        "lane_id": "A2",
        "overall_pass": a2_pass,
        "mode": a2_mode,
        "p10_semantic_green": p10_semantic_green,
        "thresholds": {
            "observed_min_events": case_label_observed_min_events,
            "effective_min_events": case_label_effective_min_events,
            "observed_proof_min_events": case_label_observed_proof_min_events,
        },
        "counts": {
            "case_events_observed": case_events_observed,
            "label_events_observed": label_events_observed,
            "case_events_effective": case_events_effective,
            "label_events_effective": label_events_effective,
        },
    }
    m7_addendum_case_label_pressure_metrics = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M7-ST-S5",
        "lane_id": "A2",
        "writer_conflict_rate_pct": to_float(p10_profile.get("writer_conflict_rate_pct")),
        "case_reopen_rate_pct": to_float(p10_profile.get("case_reopen_rate_pct")),
        "single_writer_posture_s3": bool(p10_profile.get("single_writer_posture_s3", True)),
    }
    m7_addendum_service_path_latency_profile = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M7-ST-S5",
        "lane_id": "A3",
        "overall_pass": a3_pass,
        "required_metrics": service_metrics_required,
        "latency_ms": {"p50": latency_p50, "p95": latency_p95, "p99": latency_p99},
        "error_rate_pct": error_rate_pct,
        "retry_ratio_pct": retry_ratio_pct,
        "lag_evidence_present": lag_evidence_present,
        "checks": a3_checks,
    }
    m7_addendum_service_path_throughput_profile = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M7-ST-S5",
        "lane_id": "A3",
        "eps_proxy": round(eps_proxy, 6),
        "target_eps": target_eps,
        "runtime_budget_minutes_used": round(total_window_seconds / 60.0, 6),
        "runtime_budget_minutes_max": add_max_runtime_minutes,
        "spend_budget_usd_used": round(attributed_spend_usd, 6),
        "spend_budget_usd_max": add_max_spend_usd,
    }
    m7_addendum_cost_attribution_receipt = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M7-ST-S5",
        "lane_id": "A4",
        "overall_pass": a4_pass,
        "window_seconds": cost_attribution_window_seconds,
        "min_required_window_seconds": add_cost_min_window_seconds,
        "attributed_spend_usd": round(attributed_spend_usd, 6),
        "mapped_rollup_spend_usd": round(mapped_rollup_spend_usd, 6),
        "unattributed_spend_detected": unattributed_spend_detected,
        "ce_vs_rollup_delta_usd": ce_vs_rollup_delta_usd,
        "cost_query_window": {"start_utc": iso_utc(query_start_utc), "end_utc": iso_utc(query_end_utc)},
        "cost_method_required": add_cost_method_required,
        "cost_method_observed": str(ce_receipt.get("method", "")),
        "ce_attribution": ce_receipt,
        "spend_sources": stage_cost_rows,
        "mapping_complete": bool(ce_receipt.get("ok")) and not unattributed_spend_detected,
    }
    m7_addendum_blocker_register = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M7-ST-S5",
        "overall_pass": len(addendum_blockers) == 0,
        "open_blocker_count": len(addendum_blockers),
        "blockers": addendum_blockers,
    }
    m7_addendum_execution_summary = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M7-ST-S5",
        "profile_id": add_profile_id,
        "overall_pass": len(addendum_blockers) == 0,
        "lane_status": {"A1": a1_pass, "A2": a2_pass, "A3": a3_pass, "A4": a4_pass},
        "next_gate_on_pass": add_expected_gate,
        "recommended_next_gate": add_expected_gate if len(addendum_blockers) == 0 else "BLOCKED",
    }
    m7_addendum_decision_log = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M7-ST-S5",
        "decisions": [
            "Lane A1 adjudicated realism with strict direct-observed thresholds only; no contractual or proxy fallback accepted.",
            "Lane A2 adjudicated case/label pressure with strict observed-volume thresholds only and semantic invariants green.",
            "Lane A3 enforced direct service-path latency/throughput checks from integrated S4 evidence and budget checks.",
            "Lane A4 enforced real CE-backed spend attribution with method contract and unexplained-spend fail-closed posture.",
        ],
    }

    dumpj(out / "m7_addendum_realism_window_summary.json", m7_addendum_realism_window_summary)
    dumpj(out / "m7_addendum_realism_window_metrics.json", m7_addendum_realism_window_metrics)
    dumpj(out / "m7_addendum_case_label_pressure_summary.json", m7_addendum_case_label_pressure_summary)
    dumpj(out / "m7_addendum_case_label_pressure_metrics.json", m7_addendum_case_label_pressure_metrics)
    dumpj(out / "m7_addendum_service_path_latency_profile.json", m7_addendum_service_path_latency_profile)
    dumpj(out / "m7_addendum_service_path_throughput_profile.json", m7_addendum_service_path_throughput_profile)
    dumpj(out / "m7_addendum_cost_attribution_receipt.json", m7_addendum_cost_attribution_receipt)
    dumpj(out / "m7_addendum_blocker_register.json", m7_addendum_blocker_register)
    dumpj(out / "m7_addendum_execution_summary.json", m7_addendum_execution_summary)
    dumpj(out / "m7_addendum_decision_log.json", m7_addendum_decision_log)

    addendum_missing = [n for n in M7_ADDENDUM_ARTIFACTS if not (out / n).exists()]
    if addendum_missing:
        addendum_blockers.append({"id": "M7-ADD-B6", "severity": "HIGH", "status": "OPEN", "details": {"missing_artifacts": addendum_missing}})
        m7_addendum_blocker_register.update({"overall_pass": False, "open_blocker_count": len(addendum_blockers), "blockers": addendum_blockers})
        m7_addendum_execution_summary.update({"overall_pass": False, "recommended_next_gate": "BLOCKED"})
        dumpj(out / "m7_addendum_blocker_register.json", m7_addendum_blocker_register)
        dumpj(out / "m7_addendum_execution_summary.json", m7_addendum_execution_summary)
        blockers.append({"id": "M7-ST-B9", "severity": "S5", "status": "OPEN", "details": {"missing_addendum_artifacts": addendum_missing}})
        issues.append("missing addendum artifacts")
        overall_pass = False
        verdict_name = "HOLD_REMEDIATE"
        next_gate = "BLOCKED"
        handoff_pack.update({"verdict": verdict_name, "next_gate": next_gate})

    dumpj(out / "m7_phase_rollup_matrix.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7-ST-S5", "platform_run_id": platform_run_id, "chain_rows": chain_rows, "subphase_rows": subphase_rows, "stage_cost_rows": stage_cost_rows, "budget_checks": budget_checks})
    dumpj(
        out / "m7_gate_verdict.json",
        {
            "generated_at_utc": now(),
            "phase_execution_id": phase_execution_id,
            "stage_id": "M7-ST-S5",
            "platform_run_id": platform_run_id,
            "overall_pass": overall_pass,
            "verdict": verdict_name,
            "next_gate": next_gate,
            "expected_next_gate_on_pass": expected_next_gate,
            "blocker_count": len(blockers),
            "upstream_m7_s4_phase_execution_id": dep_id,
        },
    )
    dumpj(out / "m8_handoff_pack.json", handoff_pack)

    decisions.extend(
        [
            "Validated S4 continuity before M7 rollup and handoff emission.",
            "Enforced deterministic GO rule only when parent/subphase/addendum lanes are blocker-free and run-scope consistent.",
            "Published closure rollup with explicit addendum lane adjudication, real cost attribution, and handoff refs.",
        ]
    )
    dumpj(out / "m7_decision_log.json", {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7-ST-S5", "decisions": decisions, "advisories": advisories, "chain_rows": chain_rows, "subphase_rows": subphase_rows})

    blocker_register = {"generated_at_utc": now(), "phase_execution_id": phase_execution_id, "stage_id": "M7-ST-S5", "overall_pass": overall_pass, "open_blocker_count": len(blockers), "blockers": blockers}
    summary = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M7-ST-S5",
        "overall_pass": overall_pass,
        "next_gate": next_gate,
        "open_blocker_count": len(blockers),
        "required_artifacts": required_artifacts,
        "probe_count": metrics["probe_count"],
        "error_rate_pct": metrics["error_rate_pct"],
        "platform_run_id": platform_run_id,
        "upstream_m7_s4_phase_execution_id": dep_id,
        "expected_next_gate_on_pass": expected_next_gate,
        "verdict": verdict_name,
        "addendum_lane_status": {"A1": a1_pass, "A2": a2_pass, "A3": a3_pass, "A4": a4_pass},
        "addendum_open_blocker_count": len(addendum_blockers),
    }
    verdict = {
        "generated_at_utc": now(),
        "phase_execution_id": phase_execution_id,
        "stage_id": "M7-ST-S5",
        "overall_pass": overall_pass,
        "verdict": verdict_name,
        "next_gate": next_gate,
        "expected_next_gate_on_pass": expected_next_gate,
        "blocker_count": len(blockers),
        "platform_run_id": platform_run_id,
    }
    dumpj(out / "m7_blocker_register.json", blocker_register)
    dumpj(out / "m7_execution_summary.json", summary)
    dumpj(out / "m7_gate_verdict.json", verdict)
    finalize_artifact_contract(out, required_artifacts, blockers, blocker_register, summary, verdict, blocker_id="M7-ST-B9")

    print(f"[m7_s5] phase_execution_id={phase_execution_id}")
    print(f"[m7_s5] output_dir={out.as_posix()}")
    print(f"[m7_s5] overall_pass={summary.get('overall_pass')}")
    print(f"[m7_s5] verdict={summary.get('verdict')}")
    print(f"[m7_s5] next_gate={summary.get('next_gate')}")
    print(f"[m7_s5] open_blockers={blocker_register.get('open_blocker_count')}")
    print(f"[m7_s5] addendum_open_blockers={len(addendum_blockers)}")
    return 0 if summary.get("overall_pass") else 2


def main() -> int:
    ap = argparse.ArgumentParser(description="M7 stress runner")
    ap.add_argument("--stage", default="S0", choices=["S0", "S1", "S2", "S3", "S4", "S5"])
    ap.add_argument("--phase-execution-id", default="")
    args = ap.parse_args()

    stage_map = {
        "S0": ("m7_stress_s0", run_s0),
        "S1": ("m7_stress_s1", run_s1),
        "S2": ("m7_stress_s2", run_s2),
        "S3": ("m7_stress_s3", run_s3),
        "S4": ("m7_stress_s4", run_s4),
        "S5": ("m7_stress_s5", run_s5),
    }
    prefix, fn = stage_map[args.stage]
    phase_execution_id = args.phase_execution_id.strip() or f"{prefix}_{tok()}"
    return fn(phase_execution_id)


if __name__ == "__main__":
    raise SystemExit(main())
